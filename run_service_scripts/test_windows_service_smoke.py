from __future__ import annotations

import json
import socket
import subprocess
import sys
import unittest
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

    def test_04_stop_is_idempotent(self) -> None:
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

    def test_05_stale_runtime_metadata_is_repaired(self) -> None:
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

    def test_06_port_conflict_is_reported(self) -> None:
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
