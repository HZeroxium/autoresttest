from __future__ import annotations

import argparse
import concurrent.futures
import copy
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import tomli as tomllib


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_ROOT = PROJECT_ROOT / "data"
DEFAULT_BATCH_OUTPUT_DIR = DATA_ROOT / "batch-runs"
SUPPORTED_FAILURE_POLICY = "continue_all"

_ACTIVE_PROCESSES: dict[int, subprocess.Popen[str]] = {}
_ACTIVE_PROCESS_LOCK = threading.Lock()


@dataclass(frozen=True)
class RunnerConfig:
    base_config: Path
    max_parallel_datasets: int
    output_dir: Path
    failure_policy: str = SUPPORTED_FAILURE_POLICY


@dataclass(frozen=True)
class DatasetPlan:
    name: str
    spec_relative: str
    spec_path: Path
    spec_stem: str
    runs: int
    overrides: dict[str, Any]
    source_index: int


@dataclass(frozen=True)
class BatchPlan:
    plan_path: Path
    repo_root: Path
    runner: RunnerConfig
    defaults_overrides: dict[str, Any]
    datasets: list[DatasetPlan]


@dataclass(frozen=True)
class JobSpec:
    ordinal: int
    dataset_name: str
    spec_relative: str
    spec_path: Path
    spec_stem: str
    run_number: int
    effective_overrides: dict[str, Any]


@dataclass(frozen=True)
class JobArtifacts:
    job_dir: Path
    manifest_path: Path
    effective_config_path: Path
    stdout_log_path: Path
    stderr_log_path: Path


@dataclass
class JobResult:
    ordinal: int
    dataset_name: str
    spec: str
    spec_stem: str
    run_number: int
    effective_overrides: dict[str, Any]
    command: list[str]
    status: str
    started_at: str | None = None
    completed_at: str | None = None
    duration_seconds: float | None = None
    exit_code: int | None = None
    stdout_log: str | None = None
    stderr_log: str | None = None
    effective_config: str | None = None
    manifest_path: str | None = None
    detected_run_dir: str | None = None
    detected_run_dirs: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ordinal": self.ordinal,
            "dataset_name": self.dataset_name,
            "spec": self.spec,
            "spec_stem": self.spec_stem,
            "run_number": self.run_number,
            "effective_overrides": self.effective_overrides,
            "command": self.command,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "exit_code": self.exit_code,
            "stdout_log": self.stdout_log,
            "stderr_log": self.stderr_log,
            "effective_config": self.effective_config,
            "manifest_path": self.manifest_path,
            "detected_run_dir": self.detected_run_dir,
            "detected_run_dirs": self.detected_run_dirs,
            "error": self.error,
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def slugify(value: str) -> str:
    cleaned = []
    for char in value:
        if char.isalnum() or char in {"-", "_", "."}:
            cleaned.append(char)
        else:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    return slug or "item"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run AutoRestTest datasets in batch without modifying AutoRestTest core code."
        )
    )
    parser.add_argument(
        "plan",
        nargs="?",
        help="Path to the batch plan TOML file.",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=None,
        help="Override runner.max_parallel_datasets from the plan.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve and print the schedule without executing any jobs.",
    )
    parser.add_argument(
        "--job-manifest",
        help=argparse.SUPPRESS,
    )
    return parser


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Expected TOML object at {path}")
    return data


def resolve_repo_path(raw_path: str, repo_root: Path) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve(strict=False)


def normalize_relative_path(raw_path: str, repo_root: Path) -> str:
    resolved = resolve_repo_path(raw_path, repo_root)
    try:
        relative = resolved.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError(
            f"Path must stay within the repository root: {raw_path}"
        ) from exc
    return relative.as_posix()


def normalize_override_map(raw_value: Any, field_name: str) -> dict[str, Any]:
    if raw_value is None:
        return {}
    if not isinstance(raw_value, dict):
        raise ValueError(f"{field_name} must be a TOML table")
    normalized: dict[str, Any] = {}
    for key, value in raw_value.items():
        key_text = str(key).strip()
        if not key_text:
            raise ValueError(f"{field_name} keys must not be empty")
        normalized[key_text] = value
    return normalized


def apply_dotted_overrides(
    base_config: dict[str, Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(base_config)
    for raw_path, value in overrides.items():
        parts = str(raw_path).split(".")
        if any(part.strip() == "" for part in parts):
            raise ValueError(f"Invalid dotted override key: {raw_path}")
        cursor: dict[str, Any] = result
        for part in parts[:-1]:
            existing = cursor.get(part)
            if existing is None:
                existing = {}
                cursor[part] = existing
            if not isinstance(existing, dict):
                raise ValueError(
                    f"Cannot assign override '{raw_path}': '{part}' is not a table"
                )
            cursor = existing
        cursor[parts[-1]] = value
    return result


def load_batch_plan(
    plan_path: Path,
    *,
    repo_root: Path = PROJECT_ROOT,
    max_parallel_override: int | None = None,
) -> BatchPlan:
    plan_payload = load_toml(plan_path)
    runner_payload = plan_payload.get("runner", {})
    if not isinstance(runner_payload, dict):
        raise ValueError("[runner] must be a TOML table")

    defaults_payload = plan_payload.get("defaults", {})
    if not isinstance(defaults_payload, dict):
        raise ValueError("[defaults] must be a TOML table")

    base_config_raw = str(runner_payload.get("base_config", "configurations.toml"))
    max_parallel = (
        int(max_parallel_override)
        if max_parallel_override is not None
        else int(runner_payload.get("max_parallel_datasets", 2))
    )
    if max_parallel < 1:
        raise ValueError("max_parallel_datasets must be at least 1")

    failure_policy = str(
        runner_payload.get("failure_policy", SUPPORTED_FAILURE_POLICY)
    ).strip()
    if failure_policy != SUPPORTED_FAILURE_POLICY:
        raise ValueError(
            f"Unsupported failure_policy '{failure_policy}'. "
            f"Only '{SUPPORTED_FAILURE_POLICY}' is supported."
        )

    output_dir_raw = str(runner_payload.get("output_dir", DEFAULT_BATCH_OUTPUT_DIR))
    runner = RunnerConfig(
        base_config=resolve_repo_path(base_config_raw, repo_root),
        max_parallel_datasets=max_parallel,
        output_dir=resolve_repo_path(output_dir_raw, repo_root),
        failure_policy=failure_policy,
    )
    if not runner.base_config.exists():
        raise FileNotFoundError(f"Base config not found: {runner.base_config}")

    defaults_overrides = normalize_override_map(
        defaults_payload.get("overrides"),
        "defaults.overrides",
    )

    raw_datasets = plan_payload.get("datasets")
    if not isinstance(raw_datasets, list) or not raw_datasets:
        raise ValueError("At least one [[datasets]] entry is required")

    datasets: list[DatasetPlan] = []
    names_by_stem: dict[str, str] = {}
    spec_paths_by_stem: dict[str, Path] = {}
    for index, raw_dataset in enumerate(raw_datasets):
        if not isinstance(raw_dataset, dict):
            raise ValueError("Each [[datasets]] entry must be a TOML table")

        name = str(raw_dataset.get("name", "")).strip()
        if not name:
            raise ValueError(f"datasets[{index}] is missing a non-empty 'name'")

        spec_raw = str(raw_dataset.get("spec", "")).strip()
        if not spec_raw:
            raise ValueError(f"datasets[{index}] is missing a non-empty 'spec'")
        spec_relative = normalize_relative_path(spec_raw, repo_root)
        spec_path = repo_root / spec_relative
        if not spec_path.exists():
            raise FileNotFoundError(f"Spec file not found: {spec_path}")

        runs = int(raw_dataset.get("runs", 1))
        if runs < 1:
            raise ValueError(f"datasets[{index}].runs must be at least 1")

        overrides = normalize_override_map(
            raw_dataset.get("overrides"),
            f"datasets[{index}].overrides",
        )

        spec_stem_key = spec_path.stem.casefold()
        previous_name = names_by_stem.get(spec_stem_key)
        previous_path = spec_paths_by_stem.get(spec_stem_key)
        if previous_name is not None and previous_name != name:
            raise ValueError(
                f"Spec stem '{spec_path.stem}' is mapped to multiple dataset names "
                f"('{previous_name}' and '{name}'). Use one name to avoid cache collisions."
            )
        if previous_path is not None and previous_path != spec_path:
            raise ValueError(
                f"Different spec files share the same stem '{spec_path.stem}': "
                f"{previous_path} and {spec_path}. Rename one file to avoid collisions."
            )
        names_by_stem[spec_stem_key] = name
        spec_paths_by_stem[spec_stem_key] = spec_path

        datasets.append(
            DatasetPlan(
                name=name,
                spec_relative=spec_relative,
                spec_path=spec_path,
                spec_stem=spec_path.stem,
                runs=runs,
                overrides=overrides,
                source_index=index,
            )
        )

    return BatchPlan(
        plan_path=plan_path.resolve(strict=False),
        repo_root=repo_root.resolve(strict=False),
        runner=runner,
        defaults_overrides=defaults_overrides,
        datasets=datasets,
    )


def load_base_config(path: Path) -> dict[str, Any]:
    return load_toml(path)


def build_jobs(plan: BatchPlan, base_config: dict[str, Any]) -> list[JobSpec]:
    jobs: list[JobSpec] = []
    ordinal = 0
    for dataset in plan.datasets:
        merged_overrides = dict(plan.defaults_overrides)
        merged_overrides.update(dataset.overrides)
        merged_overrides["spec.location"] = dataset.spec_relative

        for run_number in range(1, dataset.runs + 1):
            ordinal += 1
            effective_overrides = dict(merged_overrides)
            effective_config = apply_dotted_overrides(base_config, effective_overrides)
            if "spec" not in effective_config or not isinstance(
                effective_config["spec"], dict
            ):
                raise ValueError("Effective config is missing [spec]")
            jobs.append(
                JobSpec(
                    ordinal=ordinal,
                    dataset_name=dataset.name,
                    spec_relative=dataset.spec_relative,
                    spec_path=dataset.spec_path,
                    spec_stem=dataset.spec_stem,
                    run_number=run_number,
                    effective_overrides=effective_overrides,
                )
            )
    return jobs


def group_jobs_by_dataset_name(jobs: Iterable[JobSpec]) -> list[tuple[str, list[JobSpec]]]:
    grouped: dict[str, list[JobSpec]] = {}
    order: list[str] = []
    for job in jobs:
        if job.dataset_name not in grouped:
            grouped[job.dataset_name] = []
            order.append(job.dataset_name)
        grouped[job.dataset_name].append(job)
    return [(name, grouped[name]) for name in order]


def toml_quote_key(key: str) -> str:
    if key.replace("-", "").replace("_", "").isalnum():
        return key
    return json.dumps(key, ensure_ascii=False)


def toml_format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ", ".join(toml_format_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value type: {type(value)!r}")


def serialize_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []

    def emit_table(table: dict[str, Any], path: list[str] | None) -> None:
        scalar_items: list[tuple[str, Any]] = []
        nested_items: list[tuple[str, dict[str, Any]]] = []
        for key, value in table.items():
            if isinstance(value, dict):
                if value:
                    nested_items.append((key, value))
            else:
                scalar_items.append((key, value))

        if path is not None:
            lines.append("[" + ".".join(toml_quote_key(part) for part in path) + "]")
        for key, value in scalar_items:
            lines.append(f"{toml_quote_key(key)} = {toml_format_value(value)}")

        for index, (key, value) in enumerate(nested_items):
            if lines and lines[-1] != "":
                lines.append("")
            emit_table(value, [*path, key] if path else [key])
            if index != len(nested_items) - 1:
                lines.append("")

    emit_table(data, None)
    return "\n".join(lines).rstrip() + "\n"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(path)


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def list_run_directories(spec_stem: str) -> set[str]:
    dataset_dir = DATA_ROOT / spec_stem
    if not dataset_dir.exists():
        return set()
    return {child.name for child in dataset_dir.iterdir() if child.is_dir()}


def build_batch_output_dir(plan: BatchPlan) -> Path:
    timestamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    plan_slug = slugify(plan.plan_path.stem)
    batch_dir = plan.runner.output_dir / f"{plan_slug}-{timestamp}-{os.getpid()}"
    batch_dir.mkdir(parents=True, exist_ok=False)
    return batch_dir


def create_job_artifacts(
    batch_dir: Path,
    job: JobSpec,
    effective_config: dict[str, Any],
) -> JobArtifacts:
    job_slug = slugify(job.dataset_name)
    job_dir = batch_dir / "jobs" / f"{job.ordinal:03d}-{job_slug}-run{job.run_number}"
    job_dir.mkdir(parents=True, exist_ok=False)

    artifacts = JobArtifacts(
        job_dir=job_dir,
        manifest_path=job_dir / "job_manifest.json",
        effective_config_path=job_dir / "effective_config.toml",
        stdout_log_path=job_dir / "stdout.log",
        stderr_log_path=job_dir / "stderr.log",
    )
    atomic_write_text(artifacts.effective_config_path, serialize_toml(effective_config))
    return artifacts


def build_job_manifest(
    job: JobSpec,
    artifacts: JobArtifacts,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "repo_root": str(repo_root),
        "effective_config_path": str(artifacts.effective_config_path),
        "job": {
            "ordinal": job.ordinal,
            "dataset_name": job.dataset_name,
            "spec": job.spec_relative,
            "spec_stem": job.spec_stem,
            "run_number": job.run_number,
            "effective_overrides": job.effective_overrides,
        },
    }


def patch_core_runtime(config_path: Path, repo_root: Path) -> None:
    src_path = repo_root / "src"
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    if str(repo_root) not in sys.path:
        sys.path.insert(1, str(repo_root))

    import autoresttest.config.config as config_module

    config_module.CONFIG_PATH = config_path.resolve(strict=False)
    cache_clear = getattr(config_module.get_config, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()

    import autoresttest.tui.display as display_module

    display_module.TUIDisplay.confirm = lambda self, message, default=True: True


def run_child_job(job_manifest_path: Path) -> int:
    manifest = json.loads(job_manifest_path.read_text(encoding="utf-8"))
    repo_root = Path(manifest["repo_root"])
    effective_config_path = Path(manifest["effective_config_path"])

    patch_core_runtime(effective_config_path, repo_root)

    import autoresttest.autoresttest as runtime_module

    original_argv = sys.argv[:]
    try:
        sys.argv = ["autoresttest", "--skip-wizard"]
        result = runtime_module.main()
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    finally:
        sys.argv = original_argv

    if isinstance(result, int):
        return result
    return 0


def register_process(job_ordinal: int, process: subprocess.Popen[str]) -> None:
    with _ACTIVE_PROCESS_LOCK:
        _ACTIVE_PROCESSES[job_ordinal] = process


def unregister_process(job_ordinal: int) -> None:
    with _ACTIVE_PROCESS_LOCK:
        _ACTIVE_PROCESSES.pop(job_ordinal, None)


def terminate_active_processes() -> None:
    with _ACTIVE_PROCESS_LOCK:
        active_items = list(_ACTIVE_PROCESSES.items())

    for _, process in active_items:
        if process.poll() is None:
            process.terminate()

    deadline = time.time() + 5.0
    for _, process in active_items:
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()


def execute_job_subprocess(
    job: JobSpec,
    artifacts: JobArtifacts,
    repo_root: Path,
    *,
    cancel_event: threading.Event,
) -> JobResult:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--job-manifest",
        str(artifacts.manifest_path),
    ]
    result = JobResult(
        ordinal=job.ordinal,
        dataset_name=job.dataset_name,
        spec=job.spec_relative,
        spec_stem=job.spec_stem,
        run_number=job.run_number,
        effective_overrides=job.effective_overrides,
        command=command,
        status="pending",
        stdout_log=str(artifacts.stdout_log_path),
        stderr_log=str(artifacts.stderr_log_path),
        effective_config=str(artifacts.effective_config_path),
        manifest_path=str(artifacts.manifest_path),
    )

    if cancel_event.is_set():
        result.status = "cancelled"
        return result

    before_run_dirs = list_run_directories(job.spec_stem)
    result.started_at = utc_now_iso()
    monotonic_started = time.perf_counter()

    try:
        with artifacts.stdout_log_path.open(
            "w", encoding="utf-8"
        ) as stdout_handle, artifacts.stderr_log_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            process = subprocess.Popen(
                command,
                cwd=repo_root,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
            )
            register_process(job.ordinal, process)
            exit_code = process.wait()
            result.exit_code = exit_code
    except Exception as exc:  # noqa: BLE001
        artifacts.stderr_log_path.write_text(f"{exc}\n", encoding="utf-8")
        result.status = "failed"
        result.error = str(exc)
    finally:
        unregister_process(job.ordinal)
        result.completed_at = utc_now_iso()
        result.duration_seconds = round(
            time.perf_counter() - monotonic_started,
            3,
        )

    if result.status == "failed":
        return finalize_run_dir_detection(job, result, before_run_dirs)

    if cancel_event.is_set() and (result.exit_code or 0) != 0:
        result.status = "cancelled"
    elif result.exit_code == 0:
        result.status = "completed"
    else:
        result.status = "failed"

    return finalize_run_dir_detection(job, result, before_run_dirs)


def finalize_run_dir_detection(
    job: JobSpec,
    result: JobResult,
    before_run_dirs: set[str],
) -> JobResult:
    after_run_dirs = list_run_directories(job.spec_stem)
    new_dirs = sorted(after_run_dirs - before_run_dirs)
    result.detected_run_dirs = [
        str((DATA_ROOT / job.spec_stem / run_dir).resolve(strict=False))
        for run_dir in new_dirs
    ]
    if result.detected_run_dirs:
        result.detected_run_dir = result.detected_run_dirs[0]
    return result


def execute_dataset_queue(
    dataset_name: str,
    jobs: list[JobSpec],
    *,
    batch_dir: Path,
    repo_root: Path,
    base_config: dict[str, Any],
    cancel_event: threading.Event,
    record_result: Callable[[JobResult], None],
    job_executor: Callable[..., JobResult] = execute_job_subprocess,
) -> list[JobResult]:
    results: list[JobResult] = []
    for job in jobs:
        if cancel_event.is_set():
            pending_result = JobResult(
                ordinal=job.ordinal,
                dataset_name=job.dataset_name,
                spec=job.spec_relative,
                spec_stem=job.spec_stem,
                run_number=job.run_number,
                effective_overrides=job.effective_overrides,
                command=[],
                status="cancelled",
            )
            results.append(pending_result)
            record_result(pending_result)
            continue

        try:
            effective_config = apply_dotted_overrides(base_config, job.effective_overrides)
            artifacts = create_job_artifacts(batch_dir, job, effective_config)
            manifest = build_job_manifest(job, artifacts, repo_root)
            atomic_write_json(artifacts.manifest_path, manifest)

            result = job_executor(
                job,
                artifacts,
                repo_root,
                cancel_event=cancel_event,
            )
        except Exception as exc:  # noqa: BLE001
            result = JobResult(
                ordinal=job.ordinal,
                dataset_name=job.dataset_name,
                spec=job.spec_relative,
                spec_stem=job.spec_stem,
                run_number=job.run_number,
                effective_overrides=job.effective_overrides,
                command=[],
                status="failed",
                started_at=utc_now_iso(),
                completed_at=utc_now_iso(),
                duration_seconds=0.0,
                error=str(exc),
            )
        results.append(result)
        record_result(result)

    return results


def build_summary_payload(
    batch_id: str,
    plan: BatchPlan,
    batch_dir: Path,
    results: list[JobResult],
    *,
    started_at: str,
    completed_at: str | None = None,
    interrupted: bool = False,
) -> dict[str, Any]:
    completed_jobs = sum(1 for result in results if result.status == "completed")
    failed_jobs = sum(1 for result in results if result.status == "failed")
    cancelled_jobs = sum(1 for result in results if result.status == "cancelled")
    return {
        "batch_id": batch_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "interrupted": interrupted,
        "plan_path": str(plan.plan_path),
        "batch_dir": str(batch_dir),
        "runner": {
            "base_config": str(plan.runner.base_config),
            "max_parallel_datasets": plan.runner.max_parallel_datasets,
            "output_dir": str(plan.runner.output_dir),
            "failure_policy": plan.runner.failure_policy,
        },
        "jobs_total": len(results),
        "jobs_completed": completed_jobs,
        "jobs_failed": failed_jobs,
        "jobs_cancelled": cancelled_jobs,
        "results": [result.to_dict() for result in sorted(results, key=lambda item: item.ordinal)],
    }


def render_dry_run(plan: BatchPlan, jobs_by_queue: list[tuple[str, list[JobSpec]]]) -> str:
    lines = [
        f"Plan: {plan.plan_path}",
        f"Base config: {plan.runner.base_config}",
        f"Max parallel datasets: {plan.runner.max_parallel_datasets}",
        "",
    ]
    for queue_name, jobs in jobs_by_queue:
        lines.append(f"Queue: {queue_name} ({len(jobs)} job(s))")
        for job in jobs:
            lines.append(
                f"  - #{job.ordinal} spec={job.spec_relative} run={job.run_number} "
                f"overrides={json.dumps(job.effective_overrides, ensure_ascii=False, sort_keys=True)}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def run_batch(plan: BatchPlan, *, dry_run: bool = False) -> int:
    base_config = load_base_config(plan.runner.base_config)
    jobs = build_jobs(plan, base_config)
    jobs_by_queue = group_jobs_by_dataset_name(jobs)

    if dry_run:
        sys.stdout.write(render_dry_run(plan, jobs_by_queue))
        return 0

    batch_dir = build_batch_output_dir(plan)
    shutil.copy2(plan.plan_path, batch_dir / "plan.toml")

    batch_id = batch_dir.name
    started_at = utc_now_iso()
    results: list[JobResult] = []
    results_lock = threading.Lock()
    summary_write_lock = threading.Lock()
    cancel_event = threading.Event()
    summary_path = batch_dir / "summary.json"

    def write_summary(*, interrupted: bool = False) -> None:
        with results_lock:
            payload = build_summary_payload(
                batch_id,
                plan,
                batch_dir,
                list(results),
                started_at=started_at,
                completed_at=None if interrupted else utc_now_iso(),
                interrupted=interrupted,
            )
        with summary_write_lock:
            atomic_write_json(summary_path, payload)

    def record_result(result: JobResult) -> None:
        with results_lock:
            results.append(result)
        write_summary(interrupted=cancel_event.is_set())

    write_summary()

    try:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=plan.runner.max_parallel_datasets
        ) as executor:
            future_map = {
                executor.submit(
                    execute_dataset_queue,
                    queue_name,
                    queue_jobs,
                    batch_dir=batch_dir,
                    repo_root=plan.repo_root,
                    base_config=base_config,
                    cancel_event=cancel_event,
                    record_result=record_result,
                ): queue_name
                for queue_name, queue_jobs in jobs_by_queue
            }

            for future in concurrent.futures.as_completed(future_map):
                future.result()
    except KeyboardInterrupt:
        cancel_event.set()
        terminate_active_processes()
        write_summary(interrupted=True)
        return 130

    write_summary()
    return 0 if all(result.status == "completed" for result in results) else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.job_manifest:
        return run_child_job(Path(args.job_manifest))

    if not args.plan:
        parser.error("the following arguments are required: plan")

    plan = load_batch_plan(
        Path(args.plan),
        max_parallel_override=args.max_parallel,
    )
    return run_batch(plan, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
