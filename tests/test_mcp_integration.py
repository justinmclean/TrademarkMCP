from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
SERVER_SCRIPT = ROOT / "server.py"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apache_trademark_mcp import projects  # noqa: E402
from tests.fixtures import FAKE_PROJECTS  # noqa: E402


class McpProtocolTests(unittest.TestCase):
    def _make_cache_dir(self) -> tempfile.TemporaryDirectory[str]:
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name)
        cache = projects.cache_file(path)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(FAKE_PROJECTS))
        return temp

    def _run_session(self, messages: list[Any], cache_dir: str) -> list[Any]:
        lines = [json.dumps(msg) for msg in messages]
        return self._run_raw_session(lines, cache_dir)

    def _run_raw_session(self, lines: list[str], cache_dir: str) -> list[Any]:
        env = dict(os.environ)
        env["APACHE_TRADEMARK_MCP_CACHE_DIR"] = cache_dir
        proc = subprocess.Popen(
            [sys.executable, str(SERVER_SCRIPT), "--cache-dir", cache_dir],
            cwd=str(ROOT),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )
        try:
            responses = []
            assert proc.stdin is not None
            assert proc.stdout is not None
            assert proc.stderr is not None

            for line in lines:
                proc.stdin.write(line + "\n")
                proc.stdin.flush()
                responses.append(json.loads(proc.stdout.readline()))

            proc.stdin.close()
            proc.terminate()
            proc.wait(timeout=5)
            proc.stdout.close()
            proc.stderr.close()
            return responses
        finally:
            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()
            if proc.stderr and not proc.stderr.closed:
                proc.stderr.close()
            if proc.poll() is None:
                proc.kill()

    def test_initialize_and_tools_list(self) -> None:
        with self._make_cache_dir() as cache_dir:
            responses = self._run_session(
                [
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"},
                    },
                    {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                ],
                cache_dir,
            )

        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "apache-trademark-mcp")
        names = [tool["name"] for tool in responses[1]["result"]["tools"]]
        self.assertIn("validate_name", names)
        self.assertIn("perform_name_search", names)

    def test_validate_name_pass(self) -> None:
        with self._make_cache_dir() as cache_dir:
            responses = self._run_session(
                [
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"},
                    },
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "validate_name",
                            "arguments": {
                                "proposed_name": "Stratusnova",
                                "technical_description": "test podling",
                            },
                        },
                    },
                ],
                cache_dir,
            )

        payload = responses[1]["result"]["structuredContent"]
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["apache_form"], "Apache Stratusnova")

    def test_validate_name_fails_on_native_american_name(self) -> None:
        with self._make_cache_dir() as cache_dir:
            responses = self._run_session(
                [
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"},
                    },
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "validate_name",
                            "arguments": {"proposed_name": "Cherokee"},
                        },
                    },
                ],
                cache_dir,
            )

        payload = responses[1]["result"]["structuredContent"]
        self.assertEqual(payload["verdict"], "FAIL")
        self.assertTrue(any("Native American" in i for i in payload["blocking_issues"]))

    def test_unknown_tool_returns_jsonrpc_error(self) -> None:
        with self._make_cache_dir() as cache_dir:
            responses = self._run_session(
                [
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"},
                    },
                    {
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {"name": "missing_tool", "arguments": {}},
                    },
                ],
                cache_dir,
            )

        self.assertEqual(responses[1]["error"]["code"], -32602)
        self.assertIn("Unknown tool", responses[1]["error"]["message"])

    def test_malformed_json_returns_parse_error(self) -> None:
        with self._make_cache_dir() as cache_dir:
            responses = self._run_raw_session(['{"broken"'], cache_dir)
        self.assertEqual(responses[0]["error"]["code"], -32700)
        self.assertEqual(responses[0]["error"]["data"]["type"], "parse_error")


if __name__ == "__main__":
    unittest.main()
