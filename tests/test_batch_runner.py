from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import tomli as tomllib


TOOL_PATH = (
    Path(__file__).resolve().parents[1] / "tools" / "autoresttest_batch_runner.py"
)


def load_batch_runner_module():
    spec = importlib.util.spec_from_file_location(
        "autoresttest_batch_runner",
        TOOL_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load autoresttest_batch_runner module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def batch_runner():
    return load_batch_runner_module()


def write_toml(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_load_batch_plan_rejects_same_spec_stem_under_different_names(
    tmp_path: Path,
    batch_runner,
) -> None:
    write_toml(
        tmp_path / "configurations.toml",
        """
[spec]
location = "datasets/demo.json"
recursion_limit = 1
strict_validation = false

[llm]
engine = "fake"
creative_temperature = 1
strict_temperature = 1
api_base = "https://example.test"
max_tokens = 1

[agent]
max_combinations = 1
max_total_combinations = 1
base_samples_per_size = 1
combination_seed = 1

[agent.value]
parallelize = false
max_workers = 1

[agents.header]
enabled = false

[cache]
use_cached_graph = true
use_cached_table = true

[q_learning]
learning_rate = 0.1
discount_factor = 0.9
max_exploration = 1

[request_generation]
time_duration = 5
mutation_rate = 0.1
""".strip()
        + "\n",
    )
    (tmp_path / "datasets").mkdir()
    (tmp_path / "datasets" / "api.json").write_text("{}", encoding="utf-8")
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "api.json").write_text("{}", encoding="utf-8")
    plan_path = write_toml(
        tmp_path / "plan.toml",
        """
[runner]
base_config = "configurations.toml"

[[datasets]]
name = "first"
spec = "datasets/api.json"

[[datasets]]
name = "second"
spec = "other/api.json"
""".strip()
        + "\n",
    )

    with pytest.raises(ValueError, match="multiple dataset names"):
        batch_runner.load_batch_plan(plan_path, repo_root=tmp_path)


def test_execute_dataset_queue_serializes_jobs_and_writes_artifacts(
    tmp_path: Path,
    batch_runner,
) -> None:
    batch_dir = tmp_path / "batch"
    batch_dir.mkdir()
    repo_root = tmp_path
    base_config = {
        "spec": {
            "location": "datasets/demo.json",
            "recursion_limit": 1,
            "strict_validation": False,
        },
        "request_generation": {"time_duration": 5, "mutation_rate": 0.1},
        "cache": {"use_cached_graph": True, "use_cached_table": True},
        "q_learning": {
            "learning_rate": 0.1,
            "discount_factor": 0.9,
            "max_exploration": 1.0,
        },
        "agent": {
            "max_combinations": 1,
            "max_total_combinations": 1,
            "base_samples_per_size": 1,
            "combination_seed": 1,
            "value": {"parallelize": False, "max_workers": 1},
        },
        "agents": {"header": {"enabled": False}},
        "llm": {
            "engine": "fake",
            "creative_temperature": 1,
            "strict_temperature": 1,
            "api_base": "https://example.test",
            "max_tokens": 1,
        },
    }
    jobs = [
        batch_runner.JobSpec(
            ordinal=1,
            dataset_name="rest-countries",
            spec_relative="datasets/rest-countries.json",
            spec_path=repo_root / "datasets" / "rest-countries.json",
            spec_stem="rest-countries",
            run_number=1,
            effective_overrides={
                "cache.use_cached_graph": True,
                "cache.use_cached_table": True,
                "request_generation.time_duration": 7,
                "spec.location": "datasets/rest-countries.json",
            },
        ),
        batch_runner.JobSpec(
            ordinal=2,
            dataset_name="rest-countries",
            spec_relative="datasets/rest-countries.json",
            spec_path=repo_root / "datasets" / "rest-countries.json",
            spec_stem="rest-countries",
            run_number=2,
            effective_overrides={
                "cache.use_cached_graph": True,
                "cache.use_cached_table": True,
                "request_generation.time_duration": 9,
                "spec.location": "datasets/rest-countries.json",
            },
        ),
    ]

    observed_starts: list[float] = []
    observed_ends: list[float] = []
    recorded_results = []

    def fake_job_executor(job, artifacts, _repo_root, *, cancel_event):
        start = time.perf_counter()
        observed_starts.append(start)
        artifacts.stdout_log_path.write_text(f"job {job.ordinal}\n", encoding="utf-8")
        artifacts.stderr_log_path.write_text("", encoding="utf-8")
        time.sleep(0.05)
        observed_ends.append(time.perf_counter())
        return batch_runner.JobResult(
            ordinal=job.ordinal,
            dataset_name=job.dataset_name,
            spec=job.spec_relative,
            spec_stem=job.spec_stem,
            run_number=job.run_number,
            effective_overrides=job.effective_overrides,
            command=["fake"],
            status="completed",
            started_at=batch_runner.utc_now_iso(),
            completed_at=batch_runner.utc_now_iso(),
            duration_seconds=0.05,
            exit_code=0,
            stdout_log=str(artifacts.stdout_log_path),
            stderr_log=str(artifacts.stderr_log_path),
            effective_config=str(artifacts.effective_config_path),
            manifest_path=str(artifacts.manifest_path),
        )

    batch_runner.execute_dataset_queue(
        "rest-countries",
        jobs,
        batch_dir=batch_dir,
        repo_root=repo_root,
        base_config=base_config,
        cancel_event=threading.Event(),
        record_result=recorded_results.append,
        job_executor=fake_job_executor,
    )

    assert len(recorded_results) == 2
    assert observed_starts[1] >= observed_ends[0]

    first_job_dir = batch_dir / "jobs" / "001-rest-countries-run1"
    first_effective_config = tomllib.loads(
        (first_job_dir / "effective_config.toml").read_text(encoding="utf-8")
    )
    assert first_effective_config["request_generation"]["time_duration"] == 7
    assert (first_job_dir / "job_manifest.json").exists()
    assert (first_job_dir / "stdout.log").read_text(encoding="utf-8") == "job 1\n"


def test_run_batch_limits_parallel_queues(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    batch_runner,
) -> None:
    write_toml(
        tmp_path / "configurations.toml",
        """
[spec]
location = "datasets/default.json"
recursion_limit = 1
strict_validation = false

[llm]
engine = "fake"
creative_temperature = 1
strict_temperature = 1
api_base = "https://example.test"
max_tokens = 1

[agent]
max_combinations = 1
max_total_combinations = 1
base_samples_per_size = 1
combination_seed = 1

[agent.value]
parallelize = false
max_workers = 1

[agents.header]
enabled = false

[cache]
use_cached_graph = true
use_cached_table = true

[q_learning]
learning_rate = 0.1
discount_factor = 0.9
max_exploration = 1

[request_generation]
time_duration = 5
mutation_rate = 0.1
""".strip()
        + "\n",
    )
    (tmp_path / "datasets").mkdir()
    for name in ("a.json", "b.json", "c.json"):
        (tmp_path / "datasets" / name).write_text("{}", encoding="utf-8")
    plan_path = write_toml(
        tmp_path / "plan.toml",
        """
[runner]
base_config = "configurations.toml"
max_parallel_datasets = 2
output_dir = "batch-output"

[[datasets]]
name = "A"
spec = "datasets/a.json"
runs = 2

[[datasets]]
name = "B"
spec = "datasets/b.json"

[[datasets]]
name = "C"
spec = "datasets/c.json"
""".strip()
        + "\n",
    )
    plan = batch_runner.load_batch_plan(plan_path, repo_root=tmp_path)

    active_queues = 0
    peak_active_queues = 0
    lock = threading.Lock()

    def fake_execute_dataset_queue(dataset_name, jobs, **kwargs):
        nonlocal active_queues, peak_active_queues
        with lock:
            active_queues += 1
            peak_active_queues = max(peak_active_queues, active_queues)
        try:
            for job in jobs:
                time.sleep(0.05)
                kwargs["record_result"](
                    batch_runner.JobResult(
                        ordinal=job.ordinal,
                        dataset_name=job.dataset_name,
                        spec=job.spec_relative,
                        spec_stem=job.spec_stem,
                        run_number=job.run_number,
                        effective_overrides=job.effective_overrides,
                        command=["fake"],
                        status="completed",
                    )
                )
            return []
        finally:
            with lock:
                active_queues -= 1

    monkeypatch.setattr(batch_runner, "execute_dataset_queue", fake_execute_dataset_queue)

    exit_code = batch_runner.run_batch(plan)

    assert exit_code == 0
    assert peak_active_queues == 2
    batch_dir = next((tmp_path / "batch-output").iterdir())
    summary = json.loads((batch_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["jobs_completed"] == 4


def test_run_batch_dry_run_prints_schedule(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    batch_runner,
) -> None:
    write_toml(
        tmp_path / "configurations.toml",
        """
[spec]
location = "datasets/default.json"
recursion_limit = 1
strict_validation = false

[llm]
engine = "fake"
creative_temperature = 1
strict_temperature = 1
api_base = "https://example.test"
max_tokens = 1

[agent]
max_combinations = 1
max_total_combinations = 1
base_samples_per_size = 1
combination_seed = 1

[agent.value]
parallelize = false
max_workers = 1

[agents.header]
enabled = false

[cache]
use_cached_graph = true
use_cached_table = true

[q_learning]
learning_rate = 0.1
discount_factor = 0.9
max_exploration = 1

[request_generation]
time_duration = 5
mutation_rate = 0.1
""".strip()
        + "\n",
    )
    (tmp_path / "datasets").mkdir()
    (tmp_path / "datasets" / "rest-countries.json").write_text(
        "{}",
        encoding="utf-8",
    )
    plan_path = write_toml(
        tmp_path / "plan.toml",
        """
[runner]
base_config = "configurations.toml"

[defaults]
overrides = { "request_generation.time_duration" = 20 }

[[datasets]]
name = "rest-countries"
spec = "datasets/rest-countries.json"
runs = 2
""".strip()
        + "\n",
    )
    plan = batch_runner.load_batch_plan(plan_path, repo_root=tmp_path)

    exit_code = batch_runner.run_batch(plan, dry_run=True)

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Queue: rest-countries (2 job(s))" in captured.out
    assert '"request_generation.time_duration": 20' in captured.out


def test_child_mode_patches_config_before_runtime_import(tmp_path: Path) -> None:
    repo_root = tmp_path / "fake_repo"
    src_root = repo_root / "src" / "autoresttest"
    (src_root / "config").mkdir(parents=True)
    (src_root / "tui").mkdir(parents=True)
    (src_root / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "config" / "__init__.py").write_text("", encoding="utf-8")
    (src_root / "tui" / "__init__.py").write_text(
        "from .display import TUIDisplay\n",
        encoding="utf-8",
    )
    (src_root / "config" / "config.py").write_text(
        """
from functools import lru_cache
from pathlib import Path
import tomli as tomllib

CONFIG_PATH = None

def _load_raw_config():
    with Path(CONFIG_PATH).open("rb") as handle:
        return tomllib.load(handle)

@lru_cache(maxsize=1)
def get_config():
    return _load_raw_config()
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (src_root / "tui" / "display.py").write_text(
        """
class TUIDisplay:
    def confirm(self, message, default=True):
        return False
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (src_root / "autoresttest.py").write_text(
        """
import json
from pathlib import Path
import autoresttest.config.config as config_module
from autoresttest.tui.display import TUIDisplay

IMPORTED_SPEC = config_module.get_config()["spec"]["location"]

def main():
    payload = {
        "config_path": str(config_module.CONFIG_PATH),
        "imported_spec": IMPORTED_SPEC,
        "runtime_spec": config_module.get_config()["spec"]["location"],
        "confirm_result": TUIDisplay().confirm("run?"),
    }
    Path("child_result.json").write_text(json.dumps(payload), encoding="utf-8")
    return 0
""".strip()
        + "\n",
        encoding="utf-8",
    )

    effective_config_path = write_toml(
        repo_root / "effective_config.toml",
        """
[spec]
location = "datasets/child.json"
""".strip()
        + "\n",
    )
    manifest_path = repo_root / "job_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "repo_root": str(repo_root),
                "effective_config_path": str(effective_config_path),
                "job": {
                    "ordinal": 1,
                    "dataset_name": "child",
                    "spec": "datasets/child.json",
                    "spec_stem": "child",
                    "run_number": 1,
                    "effective_overrides": {"spec.location": "datasets/child.json"},
                },
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(TOOL_PATH), "--job-manifest", str(manifest_path)],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads((repo_root / "child_result.json").read_text(encoding="utf-8"))
    assert payload["config_path"] == str(effective_config_path)
    assert payload["imported_spec"] == "datasets/child.json"
    assert payload["runtime_spec"] == "datasets/child.json"
    assert payload["confirm_result"] is True
