from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence


JACOCO_VERSION = "0.8.7"
GN_MONGO_CONTAINER = "gn-mongo"
GN_MONGO_IMAGE = "genomenexus/gn-mongo:latest"


class ServiceError(RuntimeError):
    pass


@dataclass(frozen=True)
class ServiceConfig:
    public_name: str
    service_subdir: str
    default_port: int
    default_jacoco_port: int
    min_java_major: int
    preferred_java_homes: tuple[str, ...]
    jacoco_includes: str
    readiness_urls: tuple[str, ...]
    report_name: str
    report_classfiles: tuple[str, ...]
    start_command_builder: Callable[["RuntimeContext"], list[str]]
    report_excluded_paths: tuple[str, ...] = ()
    build_fn: Optional[Callable[["RuntimeContext", bool], None]] = None
    before_start_fn: Optional[Callable[["RuntimeContext"], None]] = None
    after_stop_fn: Optional[Callable[["RuntimeContext", bool], None]] = None
    startup_cleanup_fn: Optional[Callable[["RuntimeContext"], None]] = None


@dataclass
class RuntimeContext:
    config: ServiceConfig
    repo_root: Path
    service_dir: Path
    target_dir: Path
    runtime_file: Path
    log_dir: Path
    stdout_log: Path
    stderr_log: Path
    results_root: Path
    tool_name: str
    port: int
    jacoco_port: int
    timeout_seconds: int
    rebuild: bool
    force: bool
    java_cmd: str
    java_home: Optional[Path]
    mvn_cmd: str
    docker_cmd: Optional[str]
    jacoco_agent: Path
    jacoco_cli: Path
    extra_state: dict[str, object] = field(default_factory=dict)


def make_restcountries_config() -> ServiceConfig:
    return ServiceConfig(
        public_name="rest-countries",
        service_subdir="services/restcountries",
        default_port=9002,
        default_jacoco_port=6302,
        min_java_major=8,
        preferred_java_homes=("JAVA8_HOME",),
        jacoco_includes="eu.fayder.restcountries.*",
        readiness_urls=("http://localhost:{port}/rest/v2/all?fields=name",),
        report_name="REST Countries Coverage",
        report_classfiles=("target/classes",),
        build_fn=build_restcountries,
        start_command_builder=build_restcountries_start_command,
    )


def make_languagetool_config() -> ServiceConfig:
    return ServiceConfig(
        public_name="language-tool",
        service_subdir="services/LanguageTool-6.7-SNAPSHOT",
        default_port=9001,
        default_jacoco_port=6301,
        min_java_major=17,
        preferred_java_homes=("JAVA17_HOME",),
        jacoco_includes="org.languagetool.*",
        readiness_urls=("http://localhost:{port}/v2/languages",),
        report_name="LanguageTool Coverage",
        report_classfiles=("org",),
        start_command_builder=build_languagetool_start_command,
    )


def make_genome_nexus_config() -> ServiceConfig:
    return ServiceConfig(
        public_name="genome-nexus",
        service_subdir="services/genome-nexus",
        default_port=9000,
        default_jacoco_port=6300,
        min_java_major=8,
        preferred_java_homes=("JAVA8_HOME",),
        jacoco_includes="org.cbioportal.*",
        readiness_urls=(
            "http://localhost:{port}/actuator/health",
            "http://localhost:{port}/swagger-ui.html",
        ),
        report_name="Genome Nexus Coverage",
        report_classfiles=(
            "model/target/classes",
            "component/target/classes",
            "persistence/target/classes",
            "service/target/classes",
            "web/target/classes",
        ),
        build_fn=build_genome_nexus,
        before_start_fn=ensure_genome_nexus_mongo,
        after_stop_fn=stop_genome_nexus_mongo,
        startup_cleanup_fn=cleanup_failed_genome_nexus_start,
        start_command_builder=build_genome_nexus_start_command,
    )


def make_spring_petclinic_rest_config() -> ServiceConfig:
    return ServiceConfig(
        public_name="spring-petclinic-rest",
        service_subdir="services/spring-petclinic-rest",
        default_port=9966,
        default_jacoco_port=6306,
        min_java_major=21,
        preferred_java_homes=("JAVA21_HOME",),
        jacoco_includes="org.springframework.samples.petclinic.*",
        readiness_urls=(
            "http://localhost:{port}/petclinic/actuator/health",
            "http://localhost:{port}/petclinic/v3/api-docs",
        ),
        report_name="Spring PetClinic REST Coverage",
        report_classfiles=("target/classes",),
        report_excluded_paths=(
            "org/springframework/samples/petclinic/rest/api",
            "org/springframework/samples/petclinic/rest/dto",
        ),
        build_fn=build_spring_petclinic_rest,
        start_command_builder=build_spring_petclinic_rest_start_command,
    )


def run_start(config: ServiceConfig, script_path: Path) -> int:
    parser = build_parser(config, "start", script_path)
    args = parser.parse_args()
    context: Optional[RuntimeContext] = None
    process: Optional[subprocess.Popen[bytes]] = None
    try:
        context = create_context(config, script_path, args)
        print(f"Preparing {config.public_name}...")
        clear_stale_runtime(context)
        ensure_port_available(context.port, f"{config.public_name} service port")
        ensure_port_available(context.jacoco_port, f"{config.public_name} JaCoCo port")
        if config.before_start_fn is not None:
            config.before_start_fn(context)
        if config.build_fn is not None:
            config.build_fn(context, context.rebuild)
        remove_path(context.target_dir / "jacoco.exec")
        process = start_process(context, config.start_command_builder(context))
        readiness_url = wait_for_readiness(context, process)
        write_runtime_metadata(context, process.pid, readiness_url)
        print(f"{config.public_name} is ready at {readiness_url}")
        return 0
    except ServiceError as exc:
        if process is not None and process.poll() is None:
            terminate_process(process.pid)
        if context is not None and config.startup_cleanup_fn is not None:
            try:
                config.startup_cleanup_fn(context)
            except ServiceError:
                pass
        print(str(exc), file=sys.stderr)
        return 1


def run_stop(config: ServiceConfig, script_path: Path) -> int:
    parser = build_parser(config, "stop", script_path)
    args = parser.parse_args()
    try:
        context = create_context(config, script_path, args)
        metadata = load_runtime_metadata(context)
        if metadata is None:
            if is_port_open(context.port):
                raise ServiceError(
                    f"{config.public_name} appears to be listening on port {context.port}, "
                    "but runtime metadata is missing. Refusing to stop an unknown process."
                )
            print(f"No running {config.public_name} instance was found.")
            return 0
        if context.tool_name == "manual":
            context.tool_name = str(metadata.get("tool_name") or context.tool_name)
        stop_service(context, metadata, generate_report=True)
        print(f"{config.public_name} stopped cleanly.")
        return 0
    except ServiceError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def build_parser(config: ServiceConfig, action: str, script_path: Path) -> argparse.ArgumentParser:
    repo_root = script_path.resolve().parents[2]
    parser = argparse.ArgumentParser(
        description=f"{action.capitalize()} {config.public_name} with JaCoCo."
    )
    parser.add_argument("--port", type=int, default=config.default_port)
    parser.add_argument("--jacoco-port", type=int, default=config.default_jacoco_port)
    parser.add_argument("--java", help="Path to a java executable or JAVA_HOME directory.")
    parser.add_argument("--mvn", help="Path to the mvn executable.")
    parser.add_argument("--docker", help="Path to the docker executable.")
    parser.add_argument("--rebuild", action="store_true", help="Force a clean rebuild before start.")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=300,
        help="Maximum time to wait for readiness or shutdown.",
    )
    parser.add_argument(
        "--tool-name",
        default="manual",
        help="Results subfolder name under results/<service>/<tool-name>/jacoco/.",
    )
    parser.add_argument(
        "--results-root",
        default=str(repo_root / "results"),
        help="Base directory for copied JaCoCo HTML reports.",
    )
    parser.add_argument("--force", action="store_true", help="Stop an existing managed instance before start.")
    return parser


def create_context(config: ServiceConfig, script_path: Path, args: argparse.Namespace) -> RuntimeContext:
    repo_root = script_path.resolve().parents[2]
    service_dir = repo_root / config.service_subdir
    target_dir = service_dir / "target"
    target_dir.mkdir(parents=True, exist_ok=True)
    log_dir = target_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    java_cmd, java_home = resolve_java_command(args.java, config.preferred_java_homes, config.min_java_major)
    mvn_cmd = resolve_maven_command(args.mvn, service_dir)
    docker_cmd = resolve_executable(args.docker, "docker") if config.public_name == "genome-nexus" else None
    jacoco_agent, jacoco_cli = ensure_jacoco_artifacts(repo_root, mvn_cmd, java_home)
    results_root = resolve_results_root(repo_root, args.results_root)
    return RuntimeContext(
        config=config,
        repo_root=repo_root,
        service_dir=service_dir,
        target_dir=target_dir,
        runtime_file=target_dir / "runtime.json",
        log_dir=log_dir,
        stdout_log=log_dir / f"{config.public_name}.stdout.log",
        stderr_log=log_dir / f"{config.public_name}.stderr.log",
        results_root=results_root,
        tool_name=args.tool_name,
        port=args.port,
        jacoco_port=args.jacoco_port,
        timeout_seconds=args.timeout_seconds,
        rebuild=args.rebuild,
        force=args.force,
        java_cmd=java_cmd,
        java_home=java_home,
        mvn_cmd=mvn_cmd,
        docker_cmd=docker_cmd,
        jacoco_agent=jacoco_agent,
        jacoco_cli=jacoco_cli,
    )


def resolve_results_root(repo_root: Path, raw_value: str) -> Path:
    candidate = Path(raw_value).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate.resolve()


def resolve_java_command(
    override: Optional[str], preferred_java_homes: Sequence[str], min_java_major: int
) -> tuple[str, Optional[Path]]:
    candidates: list[tuple[str, Optional[Path]]] = []
    seen: set[str] = set()
    ordered_values: list[Optional[str]] = [override]
    ordered_values.extend(os.environ.get(name) for name in preferred_java_homes)
    ordered_values.append(os.environ.get("JAVA_HOME"))
    ordered_values.append(shutil.which("java"))
    ordered_values.append(shutil.which("java.exe"))
    for raw_value in ordered_values:
        candidate = normalize_java_candidate(raw_value)
        if candidate is None:
            continue
        key = os.path.normcase(str(candidate[0]))
        if key in seen:
            continue
        seen.add(key)
        candidates.append(candidate)
    for command, java_home in candidates:
        major = detect_java_major(command)
        if major >= min_java_major:
            return command, java_home
    homes_text = ", ".join(preferred_java_homes) if preferred_java_homes else "JAVA_HOME"
    raise ServiceError(
        f"Could not find a Java runtime with major version >= {min_java_major}. "
        f"Set {homes_text}, pass --java, or add a compatible java to PATH."
    )


def normalize_java_candidate(raw_value: Optional[str]) -> Optional[tuple[str, Optional[Path]]]:
    if raw_value is None:
        return None
    value = raw_value.strip().strip('"')
    if not value:
        return None
    path = Path(value)
    if path.exists():
        if path.is_dir():
            executable = path / "bin" / executable_name("java")
            if executable.exists():
                return str(executable), path
            return None
        return str(path), path.parent.parent if path.parent.name.lower() == "bin" else None
    resolved = shutil.which(value)
    if resolved:
        resolved_path = Path(resolved)
        java_home = resolved_path.parent.parent if resolved_path.parent.name.lower() == "bin" else None
        return resolved, java_home
    return None


def resolve_executable(override: Optional[str], name: str) -> str:
    if override:
        candidate = Path(override)
        if candidate.exists():
            if candidate.is_dir():
                executable = candidate / "bin" / executable_name(name)
                if executable.exists():
                    return str(executable)
                raise ServiceError(f"Could not find {name} under {candidate}.")
            return str(candidate)
        resolved = shutil.which(override)
        if resolved:
            return resolved
        raise ServiceError(f"Could not resolve executable for --{name}: {override}")
    resolved = shutil.which(name) or shutil.which(executable_name(name))
    if resolved:
        return resolved
    raise ServiceError(f"Required executable '{name}' was not found on PATH.")


def resolve_maven_command(override: Optional[str], service_dir: Path) -> str:
    if override:
        return resolve_executable(override, "mvn")
    for wrapper_name in ("mvnw.cmd", "mvnw"):
        wrapper = service_dir / wrapper_name
        if wrapper.exists():
            return str(wrapper)
    return resolve_executable(None, "mvn")


def executable_name(name: str) -> str:
    return f"{name}.exe" if os.name == "nt" else name


def detect_java_major(java_cmd: str) -> int:
    result = subprocess.run(
        [java_cmd, "-version"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    match = re.search(r'version "(?P<version>[^"]+)"', output)
    if not match:
        raise ServiceError(f"Could not detect java version for {java_cmd}.")
    version = match.group("version")
    if version.startswith("1."):
        return int(version.split(".")[1])
    return int(version.split(".")[0])


def ensure_jacoco_artifacts(repo_root: Path, mvn_cmd: str, java_home: Optional[Path]) -> tuple[Path, Path]:
    agent = (
        Path.home()
        / ".m2"
        / "repository"
        / "org"
        / "jacoco"
        / "org.jacoco.agent"
        / JACOCO_VERSION
        / f"org.jacoco.agent-{JACOCO_VERSION}-runtime.jar"
    )
    cli = (
        Path.home()
        / ".m2"
        / "repository"
        / "org"
        / "jacoco"
        / "org.jacoco.cli"
        / JACOCO_VERSION
        / f"org.jacoco.cli-{JACOCO_VERSION}-nodeps.jar"
    )
    if agent.exists() and cli.exists():
        return agent, cli
    env = build_java_env(java_home)
    if not agent.exists():
        run_command(
            [mvn_cmd, "dependency:get", f"-Dartifact=org.jacoco:org.jacoco.agent:{JACOCO_VERSION}:jar:runtime"],
            cwd=repo_root,
            env=env,
            description="Downloading JaCoCo agent",
        )
    if not cli.exists():
        run_command(
            [mvn_cmd, "dependency:get", f"-Dartifact=org.jacoco:org.jacoco.cli:{JACOCO_VERSION}:jar:nodeps"],
            cwd=repo_root,
            env=env,
            description="Downloading JaCoCo CLI",
        )
    if not agent.exists() or not cli.exists():
        raise ServiceError("JaCoCo artifacts were not downloaded successfully.")
    return agent, cli


def build_java_env(java_home: Optional[Path]) -> dict[str, str]:
    env = os.environ.copy()
    if java_home is not None:
        env["JAVA_HOME"] = str(java_home)
        env["PATH"] = str(java_home / "bin") + os.pathsep + env.get("PATH", "")
    return env


def build_restcountries(context: RuntimeContext, rebuild: bool) -> None:
    artifact = context.service_dir / "target" / "restcountries-sut.jar"
    if artifact.exists() and not rebuild:
        return
    goals = ["clean", "package"] if rebuild else ["package"]
    run_command(
        [context.mvn_cmd, "-DskipTests", *goals],
        cwd=context.service_dir,
        env=build_java_env(context.java_home),
        description="Building REST Countries",
    )
    if not artifact.exists():
        raise ServiceError("REST Countries build completed but target/restcountries-sut.jar was not created.")


def build_genome_nexus(context: RuntimeContext, rebuild: bool) -> None:
    artifact = resolve_latest_file(context.service_dir / "web" / "target", "web-*.war")
    if artifact is not None and not rebuild:
        return
    goals = ["clean", "package"] if rebuild else ["package"]
    run_command(
        [context.mvn_cmd, "-DskipTests", *goals],
        cwd=context.service_dir,
        env=build_java_env(context.java_home),
        description="Building Genome Nexus",
    )
    artifact = resolve_latest_file(context.service_dir / "web" / "target", "web-*.war")
    if artifact is None:
        raise ServiceError("Genome Nexus build completed but no web-*.war artifact was produced.")


def build_spring_petclinic_rest(context: RuntimeContext, rebuild: bool) -> None:
    artifact = resolve_latest_file(context.service_dir / "target", "spring-petclinic-rest-*.jar")
    if artifact is not None and not rebuild:
        return
    goals = ["clean", "package"] if rebuild else ["package"]
    run_command(
        [context.mvn_cmd, *goals, "-DskipTests"],
        cwd=context.service_dir,
        env=build_java_env(context.java_home),
        description="Building Spring PetClinic REST",
    )
    artifact = resolve_latest_file(context.service_dir / "target", "spring-petclinic-rest-*.jar")
    if artifact is None:
        raise ServiceError(
            "Spring PetClinic REST build completed but no spring-petclinic-rest-*.jar artifact was produced."
        )


def build_restcountries_start_command(context: RuntimeContext) -> list[str]:
    jar_file = context.service_dir / "target" / "restcountries-sut.jar"
    if not jar_file.exists():
        raise ServiceError("REST Countries jar not found. Re-run with --rebuild or fix the Maven build.")
    return [
        context.java_cmd,
        jacoco_agent_argument(context),
        "-jar",
        str(jar_file),
        f"--server.port={context.port}",
    ]


def build_languagetool_start_command(context: RuntimeContext) -> list[str]:
    jar_file = context.service_dir / "languagetool-server.jar"
    if not jar_file.exists():
        raise ServiceError("LanguageTool server jar was not found.")
    return [
        context.java_cmd,
        jacoco_agent_argument(context),
        "-jar",
        str(jar_file),
        "--port",
        str(context.port),
    ]


def build_genome_nexus_start_command(context: RuntimeContext) -> list[str]:
    jar_file = resolve_latest_file(context.service_dir / "web" / "target", "web-*.war")
    if jar_file is None:
        raise ServiceError("Genome Nexus WAR was not found. Re-run with --rebuild or fix the build.")
    return [
        context.java_cmd,
        jacoco_agent_argument(context),
        "-jar",
        str(jar_file),
        f"--server.port={context.port}",
    ]


def build_spring_petclinic_rest_start_command(context: RuntimeContext) -> list[str]:
    jar_file = resolve_latest_file(context.service_dir / "target", "spring-petclinic-rest-*.jar")
    if jar_file is None:
        raise ServiceError(
            "Spring PetClinic REST jar was not found. Re-run with --rebuild or fix the Maven build."
        )
    return [
        context.java_cmd,
        jacoco_agent_argument(context),
        "-jar",
        str(jar_file),
        f"--server.port={context.port}",
    ]


def jacoco_agent_argument(context: RuntimeContext) -> str:
    session_id = context.config.public_name.replace("-", "_")
    return (
        f"-javaagent:{context.jacoco_agent}"
        f"=output=tcpserver,address=127.0.0.1,port={context.jacoco_port},"
        f"sessionid={session_id},includes={context.config.jacoco_includes},dumponexit=false"
    )


def ensure_genome_nexus_mongo(context: RuntimeContext) -> None:
    assert context.docker_cmd is not None
    if not docker_image_exists(context, GN_MONGO_IMAGE):
        run_command(
            [context.docker_cmd, "pull", GN_MONGO_IMAGE],
            cwd=context.repo_root,
            description="Pulling Genome Nexus Mongo image",
        )
    if docker_container_running(context, GN_MONGO_CONTAINER):
        context.extra_state["mongo_started_by_script"] = False
        return
    if docker_container_exists(context, GN_MONGO_CONTAINER):
        run_command(
            [context.docker_cmd, "rm", "-f", GN_MONGO_CONTAINER],
            cwd=context.repo_root,
            check=False,
            description="Removing stale Genome Nexus Mongo container",
        )
    run_command(
        [
            context.docker_cmd,
            "run",
            "--name",
            GN_MONGO_CONTAINER,
            "--restart=always",
            "-p",
            "27017:27017",
            "-d",
            GN_MONGO_IMAGE,
        ],
        cwd=context.repo_root,
        description="Starting Genome Nexus Mongo container",
    )
    context.extra_state["mongo_started_by_script"] = True
    wait_for_mongo_ready(context)


def cleanup_failed_genome_nexus_start(context: RuntimeContext) -> None:
    if context.extra_state.get("mongo_started_by_script"):
        stop_genome_nexus_mongo(context, only_if_started=True)


def stop_genome_nexus_mongo(context: RuntimeContext, only_if_started: bool = False) -> None:
    assert context.docker_cmd is not None
    if only_if_started and not context.extra_state.get("mongo_started_by_script"):
        return
    if docker_container_running(context, GN_MONGO_CONTAINER):
        run_command(
            [context.docker_cmd, "stop", GN_MONGO_CONTAINER],
            cwd=context.repo_root,
            description="Stopping Genome Nexus Mongo container",
        )


def docker_container_exists(context: RuntimeContext, container_name: str) -> bool:
    result = run_command(
        [context.docker_cmd, "ps", "-aq", "-f", f"name=^{container_name}$"],
        cwd=context.repo_root,
        capture_output=True,
        check=False,
    )
    return bool(result.stdout.strip())


def docker_container_running(context: RuntimeContext, container_name: str) -> bool:
    result = run_command(
        [context.docker_cmd, "ps", "-q", "-f", f"name=^{container_name}$"],
        cwd=context.repo_root,
        capture_output=True,
        check=False,
    )
    return bool(result.stdout.strip())


def docker_image_exists(context: RuntimeContext, image_name: str) -> bool:
    result = run_command(
        [context.docker_cmd, "image", "inspect", image_name],
        cwd=context.repo_root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def wait_for_mongo_ready(context: RuntimeContext) -> None:
    deadline = time.time() + min(context.timeout_seconds, 180)
    last_error = "MongoDB did not respond yet."
    while time.time() < deadline:
        for shell_name in ("mongo", "mongosh"):
            result = run_command(
                [
                    context.docker_cmd,
                    "exec",
                    GN_MONGO_CONTAINER,
                    shell_name,
                    "--quiet",
                    "--eval",
                    "db.adminCommand({ ping: 1 })",
                ],
                cwd=context.repo_root,
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                return
            last_error = result.stderr.strip() or result.stdout.strip() or last_error
        time.sleep(5)
    raise ServiceError(f"MongoDB container did not become ready in time. Last error: {last_error}")


def clear_stale_runtime(context: RuntimeContext) -> None:
    metadata = load_runtime_metadata(context)
    if metadata is None:
        return
    pid = int(metadata.get("pid", 0))
    if pid and is_pid_running(pid):
        if not context.force:
            raise ServiceError(
                f"{context.config.public_name} is already running with PID {pid}. "
                "Use --force to stop the managed instance first."
            )
        stop_service(context, metadata, generate_report=False)
    elif context.runtime_file.exists():
        print(f"Removing stale runtime metadata for {context.config.public_name}.")
        context.runtime_file.unlink(missing_ok=True)


def start_process(context: RuntimeContext, command: Sequence[str]) -> subprocess.Popen[bytes]:
    context.target_dir.mkdir(parents=True, exist_ok=True)
    context.log_dir.mkdir(parents=True, exist_ok=True)
    remove_path(context.stdout_log)
    remove_path(context.stderr_log)
    print("Starting:", format_command(command))
    stdout_handle = context.stdout_log.open("wb")
    stderr_handle = context.stderr_log.open("wb")
    creationflags = 0
    popen_kwargs: dict[str, object] = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["preexec_fn"] = os.setsid
    try:
        process = subprocess.Popen(
            list(command),
            cwd=context.service_dir,
            stdout=stdout_handle,
            stderr=stderr_handle,
            env=build_java_env(context.java_home),
            creationflags=creationflags,
            **popen_kwargs,
        )
    finally:
        stdout_handle.close()
        stderr_handle.close()
    return process


def wait_for_readiness(context: RuntimeContext, process: subprocess.Popen[bytes]) -> str:
    deadline = time.time() + context.timeout_seconds
    last_error = f"{context.config.public_name} did not become ready."
    while time.time() < deadline:
        if process.poll() is not None:
            raise ServiceError(
                f"{context.config.public_name} exited before it became ready.\n{tail_logs(context)}"
            )
        for url_template in context.config.readiness_urls:
            url = url_template.format(port=context.port)
            status = http_status(url)
            if status is not None and 200 <= status < 400:
                return url
            last_error = f"Last readiness status for {url}: {status}"
        time.sleep(2)
    raise ServiceError(f"{last_error}\n{tail_logs(context)}")


def http_status(url: str) -> Optional[int]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
    except (urllib.error.URLError, TimeoutError):
        return None


def load_runtime_metadata(context: RuntimeContext) -> Optional[dict[str, object]]:
    if not context.runtime_file.exists():
        return None
    try:
        return json.loads(context.runtime_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ServiceError(f"Runtime metadata is corrupted: {exc}") from exc


def write_runtime_metadata(context: RuntimeContext, pid: int, readiness_url: str) -> None:
    context.target_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "service_name": context.config.public_name,
        "pid": pid,
        "port": context.port,
        "jacoco_port": context.jacoco_port,
        "tool_name": context.tool_name,
        "results_root": str(context.results_root),
        "stdout_log": str(context.stdout_log),
        "stderr_log": str(context.stderr_log),
        "readiness_url": readiness_url,
        "started_at": datetime.now().isoformat(timespec="seconds"),
    }
    context.runtime_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def stop_service(context: RuntimeContext, metadata: dict[str, object], generate_report: bool) -> None:
    pid = int(metadata.get("pid", 0))
    if pid and is_pid_running(pid):
        dump_coverage(context)
        terminate_process(pid)
        wait_for_shutdown(context, pid)
    elif generate_report and not (context.target_dir / "jacoco.exec").exists():
        raise ServiceError(
            f"{context.config.public_name} is not running and no JaCoCo exec file is available."
        )
    if context.config.after_stop_fn is not None:
        context.config.after_stop_fn(context, False)
    context.runtime_file.unlink(missing_ok=True)
    if generate_report:
        report_dir = generate_jacoco_report(context)
        destination = copy_report_tree(context, report_dir)
        print(f"JaCoCo HTML report copied to {destination}")


def dump_coverage(context: RuntimeContext) -> None:
    exec_file = context.target_dir / "jacoco.exec"
    remove_path(exec_file)
    run_command(
        [
            context.java_cmd,
            "-jar",
            str(context.jacoco_cli),
            "dump",
            "--address",
            "127.0.0.1",
            "--port",
            str(context.jacoco_port),
            "--destfile",
            str(exec_file),
            "--reset",
        ],
        cwd=context.service_dir,
        env=build_java_env(context.java_home),
        description=f"Dumping JaCoCo coverage for {context.config.public_name}",
    )
    if not exec_file.exists():
        raise ServiceError("JaCoCo dump completed but target/jacoco.exec was not created.")


def wait_for_shutdown(context: RuntimeContext, pid: int) -> None:
    deadline = time.time() + context.timeout_seconds
    while time.time() < deadline:
        if not is_pid_running(pid) and not is_port_open(context.port):
            return
        time.sleep(2)
    raise ServiceError(f"{context.config.public_name} did not shut down within the timeout window.")


def terminate_process(pid: int) -> None:
    if os.name == "nt":
        run_command(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            cwd=Path.cwd(),
            check=False,
        )
        return
    try:
        os.killpg(pid, 15)
    except ProcessLookupError:
        return


def is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout.strip()
        if not output or output.startswith("INFO:"):
            return False
        return str(pid) in output
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def ensure_port_available(port: int, label: str) -> None:
    if is_port_open(port):
        raise ServiceError(f"{label} {port} is already in use.")


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def generate_jacoco_report(context: RuntimeContext) -> Path:
    exec_file = context.target_dir / "jacoco.exec"
    if not exec_file.exists():
        raise ServiceError("target/jacoco.exec does not exist; cannot generate JaCoCo report.")
    report_dir = context.target_dir / "site" / "jacoco"
    if report_dir.exists():
        shutil.rmtree(report_dir)
    report_dir.parent.mkdir(parents=True, exist_ok=True)
    command = [
        context.java_cmd,
        "-jar",
        str(context.jacoco_cli),
        "report",
        str(exec_file),
    ]
    classfiles = resolve_report_classfiles(context)
    if not classfiles:
        raise ServiceError("No compiled classfiles were found for JaCoCo report generation.")
    for classfile in classfiles:
        command.extend(["--classfiles", str(classfile)])
    command.extend(["--html", str(report_dir), "--name", context.config.report_name])
    run_command(
        command,
        cwd=context.service_dir,
        env=build_java_env(context.java_home),
        description=f"Generating JaCoCo HTML report for {context.config.public_name}",
    )
    index_file = report_dir / "index.html"
    if not index_file.exists():
        raise ServiceError(f"JaCoCo report generation did not create {index_file}.")
    return report_dir


def resolve_report_classfiles(context: RuntimeContext) -> list[Path]:
    classfiles: list[Path] = []
    if context.config.report_excluded_paths:
        stage_dir = context.target_dir / "jacoco-report-classfiles"
        remove_path(stage_dir)
        stage_dir.mkdir(parents=True, exist_ok=True)
    for relative_path in context.config.report_classfiles:
        candidate = context.service_dir / relative_path
        if candidate.exists():
            if not context.config.report_excluded_paths:
                classfiles.append(candidate)
                continue
            staged_candidate = stage_filtered_classfiles(
                candidate,
                stage_dir / sanitize_report_stage_name(relative_path),
                context.config.report_excluded_paths,
            )
            classfiles.append(staged_candidate)
    return classfiles


def stage_filtered_classfiles(source_dir: Path, target_dir: Path, excluded_paths: Sequence[str]) -> Path:
    shutil.copytree(source_dir, target_dir)
    for excluded_path in excluded_paths:
        remove_path(target_dir / excluded_path)
    return target_dir


def sanitize_report_stage_name(relative_path: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", relative_path.strip("/\\"))


def copy_report_tree(context: RuntimeContext, report_dir: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = (
        context.results_root
        / context.config.public_name
        / context.tool_name
        / "jacoco"
        / timestamp
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(report_dir, destination)
    return destination


def resolve_latest_file(directory: Path, pattern: str) -> Optional[Path]:
    matches = list(directory.glob(pattern))
    if not matches:
        return None
    return max(matches, key=lambda candidate: candidate.stat().st_mtime)


def run_command(
    command: Sequence[str],
    cwd: Path,
    env: Optional[dict[str, str]] = None,
    *,
    capture_output: bool = False,
    check: bool = True,
    description: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    if description:
        print(description)
    result = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        capture_output=capture_output,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        output = (result.stdout or "") + (result.stderr or "")
        raise ServiceError(
            f"Command failed ({result.returncode}): {format_command(command)}\n{output.strip()}"
        )
    return result


def format_command(command: Sequence[str]) -> str:
    return " ".join(shlex_quote(part) for part in command)


def shlex_quote(value: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_./:\\=-]+", value):
        return value
    return f'"{value}"'


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def tail_logs(context: RuntimeContext, limit: int = 40) -> str:
    sections: list[str] = []
    for label, path in (("stdout", context.stdout_log), ("stderr", context.stderr_log)):
        if not path.exists():
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        if lines:
            excerpt = "\n".join(lines[-limit:])
            sections.append(f"{label} log tail ({path}):\n{excerpt}")
    return "\n\n".join(sections) if sections else "No logs were captured."
