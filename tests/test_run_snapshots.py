from __future__ import annotations

import json
from collections import defaultdict
from types import SimpleNamespace

import autoresttest.autoresttest as autoresttest_module
import autoresttest.run_artifacts as run_artifacts
from autoresttest.autoresttest import AutoRestTest
from autoresttest.config import get_config
from autoresttest.llm import LanguageModel, TokenCounter
from autoresttest.marl.marl import QLearning
from autoresttest.observability import RunRecorder
from autoresttest.run_artifacts import build_report_payload


class _StubTUI:
    width = 80

    def print_phase_start(self, phase_name: str, description: str = "") -> None:
        return None

    def print_step(self, message: str, status: str = "info") -> None:
        return None

    def print_phase_complete(self, phase_name: str, details: str | None = None) -> None:
        return None

    def print_final_report(self, **_: object) -> None:
        return None

    def print_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        return None

    def print_section_header(self, title: str, icon: str = "") -> None:
        return None

    def print_success(self, message: str) -> None:
        return None


class _FakeAgent:
    def __init__(self, initialize_callback=None) -> None:
        self.q_table: dict[str, object] = {}
        self._initialize_callback = initialize_callback

    def initialize_q_table(self, progress_callback=None) -> None:
        if callable(self._initialize_callback):
            self._initialize_callback(progress_callback)


class _FakeQLearning:
    def __init__(
        self,
        operation_graph,
        alpha: float = 0.1,
        gamma: float = 0.9,
        epsilon: float = 0.3,
        time_duration: int = 600,
        mutation_rate: float = 0.3,
        tui=None,
        run_recorder=None,
    ) -> None:
        self.operation_graph = operation_graph
        self.time_duration = time_duration
        self.tui = tui
        self.run_recorder = run_recorder
        self.responses: dict[int, int] = defaultdict(int)
        self.errors: dict[str, int] = {}
        self.unique_errors: dict[str, list[dict[str, object]]] = {}
        self.successful_parameters: dict[str, dict[str, list[object]]] = {}
        self.successful_bodies: dict[str, dict[str, list[object]]] = {}
        self.successful_responses: dict[str, dict[str, list[object]]] = {}
        self.successful_primitives: dict[str, list[object]] = {}
        self.operation_response_counter: dict[str, dict[int, int]] = {}
        self._run_token_usage = TokenCounter()
        self.run_called = False

        self.operation_agent = _FakeAgent(self._initialize_operation_agent)
        self.parameter_agent = _FakeAgent()
        self.body_object_agent = _FakeAgent()
        self.data_source_agent = _FakeAgent()
        self.dependency_agent = _FakeAgent()
        self.value_agent = _FakeAgent(self._initialize_value_agent)
        self.header_agent = _FakeAgent()

    def _initialize_operation_agent(self, progress_callback=None) -> None:
        self.operation_agent.q_table = {"op1": 0.0}

    def _initialize_value_agent(self, progress_callback=None) -> None:
        self.value_agent.q_table = {"op1": {"params": {}, "body": {}}}
        self._run_token_usage = TokenCounter(input_tokens=13, output_tokens=5)
        if callable(progress_callback):
            progress_callback("op1", 0)
            progress_callback("op1", 1)

    def get_run_token_usage(self) -> TokenCounter:
        return self._run_token_usage

    def run(self) -> None:
        self.run_called = True
        self.responses[200] += 1
        self.operation_response_counter = {"op1": {200: 1}}


def test_build_report_payload_includes_run_token_fields() -> None:
    q_learning = SimpleNamespace(
        operation_response_counter={"op1": {200: 2}, "op2": {400: 1}},
        unique_errors={"op1": [{"message": "boom"}], "op2": []},
        responses={200: 2, 400: 1},
        time_duration=60,
        operation_agent=SimpleNamespace(q_table={"op1": 0.0, "op2": 0.0}),
        errors={"op1": 1},
        get_run_token_usage=lambda: TokenCounter(input_tokens=12, output_tokens=7),
    )

    report = build_report_payload(
        q_learning,
        "'Demo API' (demo)",
        run_status="running",
        snapshot_reason="post_value_agent_initialization",
    )

    assert report["Run Status"] == "running"
    assert report["Snapshot Reason"] == "post_value_agent_initialization"
    assert report["Input Tokens"] == 12
    assert report["Output Tokens"] == 7
    assert report["Total Tokens"] == 19
    assert report["Number of Successfully Processed Operations"] == 1
    assert report["Number of Unique Server Errors"] == 1


def test_q_learning_token_usage_is_scoped_per_run(monkeypatch) -> None:
    operation_graph = SimpleNamespace(
        request_generator=SimpleNamespace(api_url="http://example.test/"),
        operation_nodes={},
        operation_edges={},
    )

    monkeypatch.setattr(LanguageModel, "input_tokens", 100)
    monkeypatch.setattr(LanguageModel, "output_tokens", 50)

    first_run = QLearning(operation_graph, time_duration=1)

    monkeypatch.setattr(LanguageModel, "input_tokens", 110)
    monkeypatch.setattr(LanguageModel, "output_tokens", 55)
    first_usage = first_run.get_run_token_usage()
    assert first_usage.input_tokens == 10
    assert first_usage.output_tokens == 5

    second_run = QLearning(operation_graph, time_duration=1)

    monkeypatch.setattr(LanguageModel, "input_tokens", 121)
    monkeypatch.setattr(LanguageModel, "output_tokens", 63)
    second_usage = second_run.get_run_token_usage()
    assert second_usage.input_tokens == 11
    assert second_usage.output_tokens == 8


def test_perform_q_learning_persists_report_before_run(monkeypatch, tmp_path) -> None:
    data_root = tmp_path / "data"
    real_snapshot_writer = run_artifacts.write_standard_output_snapshot
    snapshot_events: list[dict[str, object]] = []

    monkeypatch.setenv("API_KEY", "test-key")
    monkeypatch.setattr(run_artifacts, "DATA_ROOT", data_root)
    monkeypatch.setattr(autoresttest_module, "QLearning", _FakeQLearning)

    def snapshot_spy(
        spec_name: str,
        run_id: str,
        q_learning,
        report_title: str,
        *,
        run_status: str = "completed",
        snapshot_reason: str = "run_completed",
    ):
        written_paths = real_snapshot_writer(
            spec_name,
            run_id,
            q_learning,
            report_title,
            run_status=run_status,
            snapshot_reason=snapshot_reason,
        )
        report_path = written_paths["report.json"]
        snapshot_events.append(
            {
                "snapshot_reason": snapshot_reason,
                "run_status": run_status,
                "run_called": getattr(q_learning, "run_called", False),
                "report_path": report_path,
                "report": json.loads(report_path.read_text(encoding="utf-8")),
            }
        )
        return written_paths

    monkeypatch.setattr(
        autoresttest_module,
        "write_standard_output_snapshot",
        snapshot_spy,
    )

    request_generator = SimpleNamespace(run_recorder=None)
    operation_graph = SimpleNamespace(
        request_generator=request_generator,
        operation_nodes={"op1": SimpleNamespace(operation_id="op1")},
    )

    recorder = RunRecorder.from_api_title("demo", "Demo API")
    auto_rest_test = AutoRestTest(tmp_path, get_config(), _StubTUI())

    try:
        q_learning = auto_rest_test.perform_q_learning(
            operation_graph,
            "demo",
            run_recorder=recorder,
        )
    finally:
        recorder.close()

    assert isinstance(q_learning, _FakeQLearning)
    assert q_learning.run_called is True
    assert request_generator.run_recorder is recorder

    early_snapshot = next(
        event
        for event in snapshot_events
        if event["snapshot_reason"] == "post_value_agent_initialization"
    )
    assert early_snapshot["run_called"] is False
    assert early_snapshot["report_path"].exists() is True
    assert early_snapshot["report"]["Run Status"] == "running"
    assert (
        early_snapshot["report"]["Snapshot Reason"]
        == "post_value_agent_initialization"
    )
    assert early_snapshot["report"]["Input Tokens"] == 13
    assert early_snapshot["report"]["Output Tokens"] == 5
    assert early_snapshot["report"]["Total Tokens"] == 18
