import argparse
import shelve
import sys
import os
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv

from autoresttest.config import get_config
from autoresttest.config.config import Config
from autoresttest.graph import RequestGenerator
from autoresttest.graph.generate_graph import OperationGraph
from autoresttest.llm import LanguageModel
from autoresttest.marl import QLearning
from autoresttest.observability import (
    RunRecorder,
    reset_active_run_recorder,
    set_active_run_recorder,
)
from autoresttest.run_artifacts import (
    PROJECT_ROOT,
    atomic_write_json,
    build_error_payload,
    build_operation_status_codes_payload,
    build_q_table_payload,
    build_report_payload,
    build_report_title,
    build_success_payloads,
    ensure_output_dir,
    write_standard_output_snapshot,
)
from autoresttest.specification import SpecificationParser
from autoresttest.tui import (
    ConfigWizard,
    InitializationProgressDisplay,
    LiveDisplay,
    TUIDisplay,
)
from autoresttest.tui.config_wizard import apply_config_overrides
from autoresttest.tui.themes import DEFAULT_THEME
from autoresttest.utils import (
    EmbeddingModel,
    close_all_sessions,
    construct_db_dir,
    get_api_url,
    get_graph_cache_path,
    get_q_table_cache_path,
)

load_dotenv()


def parse_args():
    parser = argparse.ArgumentParser(
        description="AutoRestTest - Automated REST API Testing with Multi-Agent RL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  autoresttest                    # Run with TUI and configuration wizard
  autoresttest --quick            # Quick setup (essential settings only)
  autoresttest --skip-wizard      # Skip wizard, use configurations.toml directly

For more information, visit: https://github.com/tylerstennett/AutoRestTest
        """,
    )
    parser.add_argument(
        "--skip-wizard",
        action="store_true",
        help="Skip configuration wizard and use configurations.toml directly",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run quick setup wizard (essential settings only)",
    )
    parser.add_argument(
        "-s",
        "--spec",
        type=str,
        default=None,
        help="Override specification path (relative to project root)",
    )
    parser.add_argument(
        "-t",
        "--time",
        type=int,
        default=None,
        help="Override test duration in seconds",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=100,
        help="TUI display width (default: 100)",
    )
    return parser.parse_args()


def output_q_table(q_learning: QLearning, spec_name: str, run_id: str):
    output_dir = ensure_output_dir(spec_name, run_id)
    atomic_write_json(output_dir / "q_tables.json", build_q_table_payload(q_learning))


def output_successes(q_learning: QLearning, spec_name: str, run_id: str):
    output_dir = ensure_output_dir(spec_name, run_id)
    for filename, payload in build_success_payloads(q_learning).items():
        atomic_write_json(output_dir / filename, payload)


def output_errors(q_learning: QLearning, spec_name: str, run_id: str):
    output_dir = ensure_output_dir(spec_name, run_id)
    atomic_write_json(
        output_dir / "server_errors.json", build_error_payload(q_learning)
    )


def output_operation_status_codes(q_learning: QLearning, spec_name: str, run_id: str):
    output_dir = ensure_output_dir(spec_name, run_id)
    atomic_write_json(
        output_dir / "operation_status_codes.json",
        build_operation_status_codes_payload(q_learning),
    )


def output_report(
    q_learning: QLearning,
    spec_name: str,
    spec_parser: SpecificationParser,
    run_id: str,
    *,
    run_status: str = "completed",
    snapshot_reason: str = "run_completed",
):
    output_dir = ensure_output_dir(spec_name, run_id)
    atomic_write_json(
        output_dir / "report.json",
        build_report_payload(
            q_learning,
            build_report_title(spec_name, spec_parser.get_api_title()),
            run_status=run_status,
            snapshot_reason=snapshot_reason,
        ),
    )


def persist_run_snapshot(
    q_learning: QLearning,
    spec_name: str,
    run_id: str,
    report_title: str,
    *,
    run_status: str,
    snapshot_reason: str,
):
    return write_standard_output_snapshot(
        spec_name,
        run_id,
        q_learning,
        report_title,
        run_status=run_status,
        snapshot_reason=snapshot_reason,
    )


def parse_specification_location(spec_loc: str):
    spec_path = Path(spec_loc).expanduser()
    return spec_path.parent, spec_path.stem, spec_path.suffix


class AutoRestTest:
    """Main AutoRestTest execution class with TUI integration."""

    def __init__(
        self,
        spec_dir: Union[Path, str],
        config: Config,
        tui: TUIDisplay,
    ):
        self.spec_dir = Path(spec_dir).expanduser()
        self.is_naive = False
        construct_db_dir()

        self.config = config
        self.tui = tui

        self.use_cached_graph = self.config.cache.use_cached_graph
        self.use_cached_table = self.config.cache.use_cached_table

    def init_graph(
        self,
        spec_name: str,
        spec_path: Union[Path, str],
        embedding_model: EmbeddingModel,
    ) -> OperationGraph:
        self.tui.print_step(
            f"Parsing OpenAPI specification: {spec_path}...", "progress"
        )
        spec_parser = SpecificationParser(spec_path=str(spec_path), spec_name=spec_name)
        self.tui.print_step("Specification parsed successfully!", "success")

        if self.config.api.override_url:
            api_url = self.config.custom_api_url
            self.tui.print_step(f"Using custom API URL: {api_url}", "info")
        else:
            api_url = get_api_url(spec_parser)
            self.tui.print_step(f"Using API URL from specification: {api_url}", "info")

        operation_graph = OperationGraph(
            spec_path=str(spec_path),
            spec_name=spec_name,
            spec_parser=spec_parser,
            embedding_model=embedding_model,
        )
        request_generator = RequestGenerator(
            operation_graph=operation_graph, api_url=api_url, is_naive=self.is_naive
        )

        operation_graph.assign_request_generator(request_generator)
        return operation_graph

    def generate_graph(
        self, spec_name: str, ext: str, embedding_model: EmbeddingModel
    ) -> OperationGraph:
        spec_path = self.spec_dir / f"{spec_name}{ext}"
        db_graph = get_graph_cache_path(spec_name)

        self.tui.print_phase_start(
            "Semantic Operation Dependency Graph",
            "Building operation relationships and dependencies",
        )

        # Always initialize the graph first
        operation_graph = self.init_graph(spec_name, spec_path, embedding_model)

        with shelve.open(str(db_graph)) as db:
            loaded_from_shelf = False

            if spec_name in db and self.use_cached_graph:
                self.tui.print_step(
                    f"Loading cached graph for {spec_name}...", "progress"
                )
                try:
                    graph_properties = db[spec_name]
                    operation_graph.operation_edges = graph_properties["edges"]
                    operation_graph.operation_nodes = graph_properties["nodes"]
                    self.tui.print_step("Loaded graph from cache", "success")
                    loaded_from_shelf = True
                except Exception as e:
                    self.tui.print_step(f"Cache load failed: {e}", "warning")

            if not loaded_from_shelf:
                self.tui.print_step(
                    f"Building new graph for {spec_name}...", "progress"
                )
                operation_graph.create_graph()

                graph_properties = {
                    "edges": operation_graph.operation_edges,
                    "nodes": operation_graph.operation_nodes,
                }

                try:
                    db[spec_name] = graph_properties
                    self.tui.print_step("Graph cached for future runs", "success")
                except Exception as e:
                    self.tui.print_step(f"Cache save failed: {e}", "warning")

        self.tui.print_phase_complete(
            "Graph Construction",
            f"{len(operation_graph.operation_nodes)} operations discovered",
        )

        return operation_graph

    def perform_q_learning(
        self,
        operation_graph: OperationGraph,
        spec_name: str,
        run_recorder: RunRecorder | None = None,
    ):
        self.tui.print_phase_start(
            "Q-Table Initialization",
            "Initializing reinforcement learning agents",
        )

        if not self.use_cached_table:
            api_key = os.getenv("API_KEY")
            if api_key is None or api_key.strip() == "":
                self.tui.print_step(
                    "❌ ERROR: API_KEY environment variable is required but not set or empty!",
                    "error",
                )
                self.tui.print_step(
                    "Please set API_KEY in your .env file or use use_cached_table = true",
                    "info",
                )
                raise ValueError(
                    "API_KEY is required for Value Agent initialization. "
                    "Set API_KEY in .env or enable use_cached_table in configurations.toml"
                )

        q_learning = QLearning(
            operation_graph,
            alpha=self.config.q_learning.learning_rate,
            gamma=self.config.q_learning.discount_factor,
            epsilon=self.config.q_learning.max_exploration,
            time_duration=self.config.request_generation.time_duration,
            mutation_rate=self.config.request_generation.mutation_rate,
            tui=self.tui,
            run_recorder=run_recorder,
        )
        if operation_graph.request_generator is not None:
            operation_graph.request_generator.run_recorder = run_recorder
        if run_recorder is None:
            raise ValueError("Run recorder is required for run-scoped output paths.")
        run_id = run_recorder.run_id
        db_q_table = get_q_table_cache_path(spec_name)

        # Initialize Q-tables for all agents with progress tracking
        agents = [
            ("Operation", q_learning.operation_agent),
            ("Parameter", q_learning.parameter_agent),
            ("Body Object", q_learning.body_object_agent),
            ("Dependency", q_learning.dependency_agent),
            ("Data Source", q_learning.data_source_agent),
        ]

        for agent_name, agent in agents:
            agent.initialize_q_table()
            self.tui.print_step(f"Initialized {agent_name} Agent Q-table", "success")

        output_q_table(q_learning, spec_name, run_id)

        with shelve.open(str(db_q_table)) as db:
            loaded_value_from_shelf = False
            loaded_header_from_shelf = False

            if spec_name in db and self.use_cached_table:
                self.tui.print_step(
                    f"Loading cached Q-tables for {spec_name}...", "progress"
                )

                compiled_q_table = db[spec_name]

                try:
                    q_learning.value_agent.q_table = compiled_q_table["value"]
                    self.tui.print_step(
                        "Loaded Value Agent Q-table from cache", "success"
                    )
                    loaded_value_from_shelf = True
                except Exception:
                    self.tui.print_step("Cache load failed for Value Agent", "warning")
                    loaded_value_from_shelf = False

                if self.config.enable_header_agent:
                    try:
                        q_learning.header_agent.q_table = compiled_q_table["header"]
                        self.tui.print_step(
                            "Loaded Header Agent Q-table from cache", "success"
                        )
                        loaded_header_from_shelf = (
                            True if q_learning.header_agent.q_table else False
                        )
                    except Exception:
                        self.tui.print_step(
                            "Cache load failed for Header Agent", "warning"
                        )
                        loaded_header_from_shelf = False

            if not loaded_value_from_shelf:
                api_key = os.getenv("API_KEY")
                if api_key:
                    self.tui.print_step(
                        f"🤖 Using LLM: {self.config.openai_llm_engine} (API_KEY found)",
                        "info",
                    )
                else:
                    self.tui.print_step(
                        "⚠️  No API_KEY found - Value Agent will use fallback (empty values)",
                        "warning",
                    )
                total_ops = len(operation_graph.operation_nodes)
                with InitializationProgressDisplay(
                    title="Value Agent Q-Table Generation",
                    total_operations=total_ops,
                    width=self.tui.width,
                ) as progress:

                    def value_progress_callback(op_id: str, completed: int):
                        progress.update(op_id, completed)

                    q_learning.value_agent.initialize_q_table(
                        progress_callback=value_progress_callback
                    )

                token_counter = LanguageModel.get_tokens()
                self.tui.print_step(
                    f"Value Agent Q-table generated - Tokens: {token_counter.input_tokens:,} in / {token_counter.output_tokens:,} out",
                    "success",
                )

            persist_run_snapshot(
                q_learning,
                spec_name,
                run_id,
                run_recorder.report_title,
                run_status="running",
                snapshot_reason="post_value_agent_initialization",
            )

            if self.config.enable_header_agent and not loaded_header_from_shelf:
                total_ops = len(operation_graph.operation_nodes)
                with InitializationProgressDisplay(
                    title="Header Agent Q-Table Generation",
                    total_operations=total_ops,
                    width=self.tui.width,
                ) as progress:

                    def header_progress_callback(op_id: str, completed: int):
                        progress.update(op_id, completed)

                    q_learning.header_agent.initialize_q_table(
                        progress_callback=header_progress_callback
                    )

                token_counter = LanguageModel.get_tokens()
                self.tui.print_step(
                    f"Header Agent Q-table generated - Tokens: {token_counter.input_tokens:,} in / {token_counter.output_tokens:,} out",
                    "success",
                )
            elif not self.config.enable_header_agent:
                q_learning.header_agent.q_table = {}

            try:
                db[spec_name] = {
                    "value": q_learning.value_agent.q_table,
                    "header": q_learning.header_agent.q_table,
                }
                self.tui.print_step("Q-tables cached for future runs", "success")
            except Exception:
                self.tui.print_step("Failed to cache Q-tables", "warning")

        output_q_table(q_learning, spec_name, run_id)
        persist_run_snapshot(
            q_learning,
            spec_name,
            run_id,
            run_recorder.report_title,
            run_status="running",
            snapshot_reason="post_q_table_initialization",
        )
        if run_recorder is not None:
            run_recorder.mark_aggregate_dirty()
            run_recorder.maybe_checkpoint(
                q_learning,
                force=True,
                reason="post_q_table_initialization",
            )

        self.tui.print_phase_complete("Q-Table Initialization")
        self.tui.print_phase_start(
            "Request Generation (MARL)",
            f"Testing API for {self.config.request_generation.time_duration} seconds using Multi-Agent Reinforcement Learning",
        )

        q_learning.run()

        self.tui.print_phase_complete("Request Generation")

        return q_learning

    def print_performance(
        self, q_learning: QLearning, spec_parser: SpecificationParser
    ):
        token_counter = q_learning.get_run_token_usage()

        # Calculate statistics for final report
        unique_processed_200s = set()
        for (
            operation_idx,
            status_codes,
        ) in q_learning.operation_response_counter.items():
            for status_code in status_codes:
                if status_code // 100 == 2:
                    unique_processed_200s.add(operation_idx)

        unique_errors = sum(len(errs) for errs in q_learning.unique_errors.values())
        total_requests = sum(q_learning.responses.values())

        title = spec_parser.get_api_title() if spec_parser.get_api_title() else "API"

        self.tui.print_final_report(
            title=title,
            duration=q_learning.time_duration,
            total_requests=total_requests,
            status_distribution=dict(q_learning.responses),
            total_operations=len(q_learning.operation_agent.q_table),
            successful_operations=len(unique_processed_200s),
            unique_errors=unique_errors,
        )

        self.tui.print_token_usage(
            input_tokens=token_counter.input_tokens,
            output_tokens=token_counter.output_tokens,
        )

    def run_all(self):
        for spec_file in self.spec_dir.iterdir():
            if not spec_file.is_file():
                continue
            spec_name = spec_file.stem
            self.tui.print_section_header(f"Testing: {spec_name}")
            self.run_single(spec_name, spec_file.suffix)

    def run_single(self, spec_name: str, ext: str):
        self.tui.print_section_header(f"Testing: {spec_name}")

        embedding_model = EmbeddingModel()
        operation_graph = self.generate_graph(spec_name, ext, embedding_model)
        run_recorder = RunRecorder.from_api_title(
            spec_name,
            operation_graph.spec_parser.get_api_title(),
        )
        recorder_token = set_active_run_recorder(run_recorder)
        q_learning: QLearning | None = None

        try:
            q_learning = self.perform_q_learning(
                operation_graph,
                spec_name,
                run_recorder=run_recorder,
            )
            self.print_performance(q_learning, operation_graph.spec_parser)

            run_recorder.set_status("completed")
            if run_recorder.enabled:
                run_recorder.mark_aggregate_dirty()
                saved = run_recorder.maybe_checkpoint(
                    q_learning,
                    force=True,
                    reason="run_completed",
                )
                if not saved:
                    persist_run_snapshot(
                        q_learning,
                        spec_name,
                        run_recorder.run_id,
                        run_recorder.report_title,
                        run_status="completed",
                        snapshot_reason="run_completed",
                    )
            else:
                persist_run_snapshot(
                    q_learning,
                    spec_name,
                    run_recorder.run_id,
                    run_recorder.report_title,
                    run_status="completed",
                    snapshot_reason="run_completed",
                )

            self.tui.print_success("AutoRestTest completed successfully!")
            self.tui.print_step(
                f"Results saved to: data/{spec_name}/{run_recorder.run_id}/",
                "info",
            )
        except KeyboardInterrupt:
            run_recorder.set_status("interrupted")
            if q_learning is not None:
                run_recorder.mark_aggregate_dirty()
                saved = run_recorder.maybe_checkpoint(
                    q_learning,
                    force=True,
                    reason="keyboard_interrupt",
                )
                if not saved:
                    persist_run_snapshot(
                        q_learning,
                        spec_name,
                        run_recorder.run_id,
                        run_recorder.report_title,
                        run_status="interrupted",
                        snapshot_reason="keyboard_interrupt",
                    )
            raise
        except Exception:
            run_recorder.set_status("failed")
            if q_learning is not None:
                run_recorder.mark_aggregate_dirty()
                saved = run_recorder.maybe_checkpoint(
                    q_learning,
                    force=True,
                    reason="run_failed",
                )
                if not saved:
                    persist_run_snapshot(
                        q_learning,
                        spec_name,
                        run_recorder.run_id,
                        run_recorder.report_title,
                        run_status="failed",
                        snapshot_reason="run_failed",
                    )
            raise
        finally:
            close_all_sessions()
            reset_active_run_recorder(recorder_token)
            run_recorder.close()


def main():
    args = parse_args()

    # Initialize TUI (always enabled)
    tui = TUIDisplay(width=args.width)
    tui.clear()
    tui.print_banner()

    # Get configuration
    if args.skip_wizard:
        config = get_config()
    else:
        wizard = ConfigWizard(width=args.width)
        overrides = wizard.run(quick_mode=args.quick)

        if overrides is None:
            # User cancelled
            sys.exit(0)
        elif overrides:
            config = apply_config_overrides(overrides)
        else:
            config = get_config()

    # Apply CLI overrides
    if args.spec or args.time:
        from autoresttest.config.config import _load_raw_config

        raw_config = _load_raw_config()
        if args.spec:
            raw_config["spec"]["location"] = args.spec
        if args.time:
            raw_config["request_generation"]["time_duration"] = args.time
        config = Config.model_validate(raw_config)

    # Display configuration summary
    config_summary = {
        "Specification": config.specification_location,
        "LLM Engine": config.openai_llm_engine,
        "API Base": config.llm_api_base,
        "Duration": f"{config.request_generation.time_duration}s",
        "Cache Graph": config.cache.use_cached_graph,
        "Cache Q-Tables": config.cache.use_cached_table,
    }
    tui.print_config_summary(config_summary)

    if not tui.confirm("Start testing with this configuration?"):
        tui.print_warning("Execution cancelled by user")
        sys.exit(0)

    # Parse specification location and run
    specification_directory, specification_name, ext = parse_specification_location(
        str(PROJECT_ROOT / config.specification_location)
    )

    auto_rest_test = AutoRestTest(
        spec_dir=specification_directory,
        config=config,
        tui=tui,
    )
    auto_rest_test.run_single(specification_name, ext)


if __name__ == "__main__":
    main()
