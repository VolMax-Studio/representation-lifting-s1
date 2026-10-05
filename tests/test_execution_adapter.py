#!/usr/bin/env python3

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.execution_adapter import (
    CONTRACT_SCHEMA, REQUEST_SCHEMA, RESULT_SCHEMA, CommandAdapter, ModelRequest,
    validate_adapter_config, verify_turn_custody,
)
from tools import provider_neutral_execution as neutral


def command_config(command):
    return {
        "schema_version": CONTRACT_SCHEMA,
        "adapter_id": "test-command",
        "kind": "command",
        "trust_role": "TRANSPORT_ONLY_NOT_TRUST_ROOT",
        "credentials": "OPERATOR_SUPPLIED_OUTSIDE_REPOSITORY",
        "direct_api_required": False,
        "request_schema": REQUEST_SCHEMA,
        "result_schema": RESULT_SCHEMA,
        "command": command,
    }


class TestExecutionAdapter(unittest.TestCase):
    def test_default_contract_is_provider_neutral_and_secret_free(self):
        config = json.loads(neutral.DEFAULT_ADAPTER.read_text(encoding="utf-8"))
        result = validate_adapter_config(config)
        self.assertTrue(result["contract_pass"], result["errors"])
        self.assertFalse(config["direct_api_required"])
        self.assertEqual(config["trust_role"], "TRANSPORT_ONLY_NOT_TRUST_ROOT")

    def test_contract_rejects_embedded_credentials(self):
        config = command_config(["/bin/true"])
        config["api_key"] = "must-not-be-committed"
        result = validate_adapter_config(config)
        self.assertFalse(result["contract_pass"])
        self.assertIn("api_key", " ".join(result["errors"]))

    def test_command_adapter_hashes_request_response_and_identity(self):
        program = (
            "import json,sys,datetime; r=json.load(sys.stdin); "
            "now=datetime.datetime.now(datetime.timezone.utc).isoformat(); "
            "json.dump({'schema_version':'%s','response_text':'answer',"
            "'observed_model_id':r['declared_model_id'],'delivery_status':'DELIVERED',"
            "'started_at_utc':now,'completed_at_utc':now,'transport_metadata':{}},sys.stdout)"
        ) % RESULT_SCHEMA
        adapter = CommandAdapter(command_config([sys.executable, "-c", program]))
        request = ModelRequest("test-run", 0, "local-test-model", "system", [
            {"role": "user", "content": "request"}
        ], "2026-10-05T00:00:00+00:00")
        with tempfile.TemporaryDirectory() as tmp:
            turn = Path(tmp) / "turn_0000"
            result = adapter.execute(request, turn, 10)
            self.assertEqual(result.response_text, "answer")
            self.assertEqual(result.observed_model_id, "local-test-model")
            self.assertTrue(verify_turn_custody(turn)["custody_pass"])

    def test_delivered_identity_mismatch_fails_closed(self):
        program = (
            "import json,sys; json.load(sys.stdin); "
            "json.dump({'schema_version':'%s','response_text':'answer',"
            "'observed_model_id':'other','delivery_status':'DELIVERED',"
            "'started_at_utc':'x','completed_at_utc':'y','transport_metadata':{}},sys.stdout)"
        ) % RESULT_SCHEMA
        adapter = CommandAdapter(command_config([sys.executable, "-c", program]))
        request = ModelRequest("test-run", 0, "expected", "system", [], "now")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, "model identity mismatch"):
                adapter.execute(request, Path(tmp) / "turn", 10)

    def test_gate5_is_contract_only_and_has_no_availability_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = neutral.gate5(
                neutral.DEFAULT_ADAPTER, Path(tmp), "execution-test", "declared-model"
            )
            self.assertTrue(receipt["gate5_pass"])
            self.assertFalse(receipt["provider_contacted"])
            self.assertFalse(receipt["provider_availability_checked"])
            self.assertNotIn("not_before", json.dumps(receipt))
            neutral.require_gate5(
                Path(tmp), neutral.DEFAULT_ADAPTER, "execution-test", "declared-model"
            )

    def test_harness_boundary_partitions_turns_by_case_and_branch(self):
        program = (
            "import json,sys; r=json.load(sys.stdin); "
            "json.dump({'schema_version':'%s','response_text':'answer',"
            "'observed_model_id':r['declared_model_id'],'delivery_status':'DELIVERED',"
            "'started_at_utc':'start','completed_at_utc':'end','transport_metadata':{}},sys.stdout)"
        ) % RESULT_SCHEMA
        adapter = CommandAdapter(command_config([sys.executable, "-c", program]))
        context = SimpleNamespace(
            _CURRENT_CASE_ID="case-001", _CURRENT_BRANCH_LABEL="D", _CURRENT_ROLE="D"
        )
        with tempfile.TemporaryDirectory() as tmp:
            boundary = neutral.adapter_call(adapter, "execution-test", Path(tmp), context)
            transcript = []
            response, stop, failed = boundary(
                "local-test-model", [{"role": "user", "content": "request"}],
                "system", 10.0, {}, transcript,
            )
            branch = Path(tmp) / "branch_artifacts" / "case-001" / "D"
            self.assertEqual((response, stop, failed), ("answer", "end_turn", False))
            self.assertTrue(verify_turn_custody(branch / "turn_0000")["custody_pass"])
            metadata = json.loads((
                branch / "transport_metadata" / "transport_metadata_0.json"
            ).read_text(encoding="utf-8"))
            self.assertEqual(metadata["declared_model_id"], "local-test-model")
            self.assertEqual(metadata["observed_model_id"], "local-test-model")
            self.assertTrue(metadata["response_delivered"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
