from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from apache_trademark_mcp import protocol


class EnvelopeTests(unittest.TestCase):
    def test_jsonrpc_result_envelope(self) -> None:
        out = protocol.jsonrpc_result(1, {"ok": True})
        self.assertEqual(out, {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}})

    def test_jsonrpc_error_envelope_includes_data(self) -> None:
        out = protocol.jsonrpc_error(1, -32600, "bad", {"type": "invalid_request"})
        self.assertEqual(out["error"]["code"], -32600)
        self.assertEqual(out["error"]["data"]["type"], "invalid_request")


class DispatchTests(unittest.TestCase):
    def test_initialize_returns_server_info(self) -> None:
        out = protocol.handle_message(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}
        )
        self.assertEqual(out["result"]["serverInfo"]["name"], "apache-trademark-mcp")

    def test_tools_list_returns_known_tools(self) -> None:
        out = protocol.handle_message(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        )
        names = [tool["name"] for tool in out["result"]["tools"]]
        self.assertIn("validate_name", names)
        self.assertIn("get_naming_policy", names)

    def test_unknown_method_returns_method_not_found(self) -> None:
        out = protocol.handle_message(
            {"jsonrpc": "2.0", "id": 3, "method": "nope/method", "params": {}}
        )
        self.assertEqual(out["error"]["code"], -32601)

    def test_invalid_jsonrpc_version(self) -> None:
        out = protocol.handle_message(
            {"jsonrpc": "1.0", "id": 4, "method": "tools/list", "params": {}}
        )
        self.assertEqual(out["error"]["code"], -32600)

    def test_invalid_params_type(self) -> None:
        out = protocol.handle_message(
            {"jsonrpc": "2.0", "id": 5, "method": "tools/list", "params": []}
        )
        self.assertEqual(out["error"]["code"], -32602)


class ValidateToolArgumentsTests(unittest.TestCase):
    def test_missing_required_argument(self) -> None:
        err = protocol.validate_tool_arguments("validate_name", {})
        self.assertIsNotNone(err)
        self.assertIn("proposed_name", err or "")

    def test_unknown_argument(self) -> None:
        err = protocol.validate_tool_arguments(
            "validate_name", {"proposed_name": "Foo", "bogus": 1}
        )
        self.assertIsNotNone(err)
        self.assertIn("bogus", err or "")


if __name__ == "__main__":
    unittest.main()
