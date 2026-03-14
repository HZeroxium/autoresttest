from __future__ import annotations

import json
import socket
import subprocess
import sys
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
RESULTS_ROOT = REPO_ROOT / "results"


def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def latest_report_dir(service_name: str, tool_name: str) -> Path | None:
    report_root = RESULTS_ROOT / service_name / tool_name / "jacoco"
    if not report_root.exists():
        return None
    candidates = [path for path in report_root.iterdir() if path.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.stat().st_mtime)


class _OkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class ServiceSmokeTests(unittest.TestCase):
    maxDiff = None

    def run_script(
        self,
        relative_script: str,
        *,
        timeout: int = 900,
        expect_success: bool = True,
        args: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [PYTHON, str(REPO_ROOT / relative_script)]
        if args:
            command.extend(args)
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if expect_success and result.returncode != 0:
            self.fail(
                f"Command failed: {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
            )
        return result

    def get_status(self, url: str) -> int:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.status

    def request_json(
        self,
        url: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], object | None]:
        request_headers = dict(headers or {})
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                raw_body = response.read().decode("utf-8")
                body = json.loads(raw_body) if raw_body else None
                return response.status, dict(response.headers.items()), body
        except urllib.error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            self.fail(f"HTTP {exc.code} for {url}: {raw_body}")
        except json.JSONDecodeError as exc:
            self.fail(f"Invalid JSON returned by {url}: {exc}")
        raise AssertionError("unreachable")

    def authenticate_jhipster(self, base_url: str) -> str:
        status, headers, body = self.request_json(
            f"{base_url}/api/authenticate",
            method="POST",
            payload={"username": "admin", "password": "admin", "rememberMe": False},
            headers={"Accept": "application/json"},
        )
        self.assertEqual(status, 200)
        if isinstance(body, dict) and isinstance(body.get("id_token"), str):
            return body["id_token"]
        authorization = headers.get("Authorization") or headers.get("authorization")
        self.assertIsNotNone(authorization, "Authentication response did not include a JWT token.")
        prefix = "Bearer "
        return authorization[len(prefix) :] if authorization.startswith(prefix) else authorization

    def assert_report_exists(self, service_name: str, tool_name: str) -> None:
        report_dir = latest_report_dir(service_name, tool_name)
        self.assertIsNotNone(report_dir, f"No JaCoCo report directory found for {service_name}/{tool_name}")
        self.assertTrue((report_dir / "index.html").exists(), f"Missing index.html under {report_dir}")

    def test_01_restcountries_start_stop_with_jacoco(self) -> None:
        tool_name = "windows-smoke-restcountries"
        self.run_script(
            "services/restcountries/start_with_jacoco.py",
            timeout=600,
            args=["--tool-name", tool_name, "--rebuild", "--timeout-seconds", "240"],
        )
        self.addCleanup(
            lambda: self.run_script(
                "services/restcountries/stop_with_jacoco.py",
                timeout=300,
                args=["--tool-name", tool_name],
                expect_success=False,
            )
        )
        self.assertEqual(self.get_status("http://localhost:9002/rest/v2/all?fields=name"), 200)
        self.run_script(
            "services/restcountries/stop_with_jacoco.py",
            timeout=300,
            args=["--tool-name", tool_name],
        )
        self.assertFalse(is_port_open(9002))
        self.assertTrue((REPO_ROOT / "services/restcountries/target/jacoco.exec").exists())
        self.assertTrue((REPO_ROOT / "services/restcountries/target/site/jacoco/index.html").exists())
        self.assert_report_exists("rest-countries", tool_name)

    def test_02_languagetool_start_stop_with_jacoco(self) -> None:
        tool_name = "windows-smoke-languagetool"
        self.run_script(
            "services/LanguageTool-6.7-SNAPSHOT/start_with_jacoco.py",
            timeout=300,
            args=["--tool-name", tool_name, "--timeout-seconds", "180"],
        )
        self.addCleanup(
            lambda: self.run_script(
                "services/LanguageTool-6.7-SNAPSHOT/stop_with_jacoco.py",
                timeout=300,
                args=["--tool-name", tool_name],
                expect_success=False,
            )
        )
        self.assertEqual(self.get_status("http://localhost:9001/v2/languages"), 200)
        self.run_script(
            "services/LanguageTool-6.7-SNAPSHOT/stop_with_jacoco.py",
            timeout=300,
            args=["--tool-name", tool_name],
        )
        self.assertFalse(is_port_open(9001))
        self.assertTrue((REPO_ROOT / "services/LanguageTool-6.7-SNAPSHOT/target/jacoco.exec").exists())
        self.assertTrue((REPO_ROOT / "services/LanguageTool-6.7-SNAPSHOT/target/site/jacoco/index.html").exists())
        self.assert_report_exists("language-tool", tool_name)

    def test_03_genome_nexus_start_stop_with_jacoco(self) -> None:
        tool_name = "windows-smoke-genome-nexus"
        self.run_script(
            "services/genome-nexus/start_with_jacoco.py",
            timeout=1800,
            args=["--tool-name", tool_name, "--rebuild", "--timeout-seconds", "900"],
        )
        self.addCleanup(
            lambda: self.run_script(
                "services/genome-nexus/stop_with_jacoco.py",
                timeout=600,
                args=["--tool-name", tool_name],
                expect_success=False,
            )
        )
        health_url = "http://localhost:9000/actuator/health"
        self.assertIn(self.get_status(health_url), (200, 204))
        self.run_script(
            "services/genome-nexus/stop_with_jacoco.py",
            timeout=600,
            args=["--tool-name", tool_name],
        )
        self.assertFalse(is_port_open(9000))
        self.assertTrue((REPO_ROOT / "services/genome-nexus/target/jacoco.exec").exists())
        self.assertTrue((REPO_ROOT / "services/genome-nexus/target/site/jacoco/index.html").exists())
        self.assert_report_exists("genome-nexus", tool_name)
        docker_ps = subprocess.run(
            ["docker", "ps", "-q", "-f", "name=^gn-mongo$"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(docker_ps.stdout.strip(), "")

    def test_04_spring_petclinic_rest_start_stop_with_jacoco(self) -> None:
        tool_name = "windows-smoke-spring-petclinic-rest"
        self.run_script(
            "services/spring-petclinic-rest/start_with_jacoco.py",
            timeout=1200,
            args=["--tool-name", tool_name, "--rebuild", "--timeout-seconds", "600"],
        )
        self.addCleanup(
            lambda: self.run_script(
                "services/spring-petclinic-rest/stop_with_jacoco.py",
                timeout=300,
                args=["--tool-name", tool_name],
                expect_success=False,
            )
        )
        self.assertEqual(self.get_status("http://localhost:9966/petclinic/actuator/health"), 200)
        self.assertEqual(self.get_status("http://localhost:9966/petclinic/api/pettypes"), 200)
        self.run_script(
            "services/spring-petclinic-rest/stop_with_jacoco.py",
            timeout=300,
            args=["--tool-name", tool_name],
        )
        self.assertFalse(is_port_open(9966))
        self.assertTrue((REPO_ROOT / "services/spring-petclinic-rest/target/jacoco.exec").exists())
        self.assertTrue((REPO_ROOT / "services/spring-petclinic-rest/target/site/jacoco/index.html").exists())
        self.assert_report_exists("spring-petclinic-rest", tool_name)

    def test_05_jhipster_sample_app_start_stop_with_jacoco(self) -> None:
        tool_name = "windows-smoke-jhipster-sample-app"
        export_path = REPO_ROOT / "services/jhipster-sample-app/target/jhipster-openapi-smoke.json"
        if export_path.exists():
            export_path.unlink()
        self.run_script(
            "services/jhipster-sample-app/start_with_jacoco.py",
            timeout=2400,
            args=["--tool-name", tool_name, "--rebuild", "--timeout-seconds", "1200"],
        )
        self.addCleanup(
            lambda: self.run_script(
                "services/jhipster-sample-app/stop_with_jacoco.py",
                timeout=600,
                args=["--tool-name", tool_name],
                expect_success=False,
            )
        )
        base_url = "http://localhost:8080"
        self.assertEqual(self.get_status(f"{base_url}/management/health"), 200)
        token = self.authenticate_jhipster(base_url)
        status, _, body = self.request_json(
            f"{base_url}/api/account",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        self.assertEqual(status, 200)
        self.assertIsInstance(body, dict)
        self.assertEqual(body.get("login"), "admin")
        self.run_script(
            "services/jhipster-sample-app/export_openapi.py",
            timeout=300,
            args=["--port", "8080", "--output", str(export_path), "--timeout-seconds", "30"],
        )
        self.assertTrue(export_path.exists())
        self.run_script(
            "services/jhipster-sample-app/stop_with_jacoco.py",
            timeout=600,
            args=["--tool-name", tool_name],
        )
        self.assertFalse(is_port_open(8080))
        self.assertTrue((REPO_ROOT / "services/jhipster-sample-app/target/jacoco.exec").exists())
        self.assertTrue((REPO_ROOT / "services/jhipster-sample-app/target/site/jacoco/index.html").exists())
        self.assert_report_exists("jhipster-sample-app", tool_name)

    def test_06_stop_is_idempotent(self) -> None:
        tool_name = "windows-smoke-idempotent"
        self.run_script(
            "services/restcountries/start_with_jacoco.py",
            timeout=600,
            args=["--tool-name", tool_name, "--rebuild", "--timeout-seconds", "240"],
        )
        self.run_script(
            "services/restcountries/stop_with_jacoco.py",
            timeout=300,
            args=["--tool-name", tool_name],
        )
        second_stop = self.run_script(
            "services/restcountries/stop_with_jacoco.py",
            timeout=120,
            args=["--tool-name", tool_name],
        )
        self.assertEqual(second_stop.returncode, 0)
        self.assertIn("No running rest-countries instance was found.", second_stop.stdout)

    def test_07_stale_runtime_metadata_is_repaired(self) -> None:
        runtime_file = REPO_ROOT / "services/restcountries/target/runtime.json"
        runtime_file.parent.mkdir(parents=True, exist_ok=True)
        runtime_file.write_text(
            json.dumps(
                {
                    "service_name": "rest-countries",
                    "pid": 999999,
                    "port": 9002,
                    "jacoco_port": 6302,
                    "tool_name": "stale-runtime",
                }
            ),
            encoding="utf-8",
        )
        tool_name = "windows-smoke-stale-runtime"
        self.run_script(
            "services/restcountries/start_with_jacoco.py",
            timeout=600,
            args=["--tool-name", tool_name, "--rebuild", "--timeout-seconds", "240"],
        )
        self.addCleanup(
            lambda: self.run_script(
                "services/restcountries/stop_with_jacoco.py",
                timeout=300,
                args=["--tool-name", tool_name],
                expect_success=False,
            )
        )
        metadata = json.loads(runtime_file.read_text(encoding="utf-8"))
        self.assertNotEqual(metadata["pid"], 999999)
        self.run_script(
            "services/restcountries/stop_with_jacoco.py",
            timeout=300,
            args=["--tool-name", tool_name],
        )

    def test_08_port_conflict_is_reported(self) -> None:
        server = HTTPServer(("127.0.0.1", 9102), _OkHandler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = self.run_script(
                "services/restcountries/start_with_jacoco.py",
                timeout=120,
                expect_success=False,
                args=["--port", "9102", "--jacoco-port", "6402", "--tool-name", "windows-smoke-port-conflict"],
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("already in use", result.stderr)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
