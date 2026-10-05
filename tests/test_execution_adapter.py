#!/usr/bin/env python3

import ast
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

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
    def _audit_tree(self, root, model_id="local-test-model", seal_count=29, omit_receipt=None):
        block = root / "block"
        (block / "branch_artifacts" / "case-001" / "D" / "turn_0000").mkdir(parents=True)
        (block / "SEALED_BLOCK_INDEX.json").write_text("{}\n", encoding="utf-8")
        receipt_dir = block / "receipts"
        receipt_dir.mkdir()
        for name in neutral.expected_execution_receipts(model_id):
            if name != omit_receipt:
                (receipt_dir / name).write_text("{}\n", encoding="utf-8")
        sealed_dir = block / "sealed_transcripts"
        sealed_dir.mkdir()
        for index in range(seal_count):
            seal = sealed_dir / f"sealed_branch_{index:02d}.tar"
            payload = f"sealed-{index}".encode()
            seal.write_bytes(payload)
            Path(str(seal) + ".sha256").write_text(
                hashlib.sha256(payload).hexdigest() + "\n", encoding="utf-8"
            )
        return block

    def test_default_contract_is_provider_neutral_and_secret_free(self):
        config = json.loads(neutral.DEFAULT_ADAPTER.read_text(encoding="utf-8"))
        result = validate_adapter_config(config)
        self.assertTrue(result["contract_pass"], result["errors"])
        self.assertFalse(config["direct_api_required"])
        self.assertEqual(config["trust_role"], "TRANSPORT_ONLY_NOT_TRUST_ROOT")
        self.assertEqual(config["kind"], "command")
        self.assertIn("codex_subscription_adapter.py", " ".join(config["command"]))

    def test_codex_adapter_uses_isolated_tool_free_cli_profile(self):
        source = (REPO_ROOT / "tools" / "codex_subscription_adapter.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
        command_literals = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertIn("--ignore-user-config", command_literals)
        self.assertIn("shell_tool", command_literals)
        self.assertIn("plugins", command_literals)
        self.assertIn("apps", command_literals)
        self.assertIn("remote_plugin", command_literals)
        self.assertIn('web_search="disabled"', command_literals)
        self.assertIn("CODEX_APP_TOOLS_PIPE_PATH", command_literals)
        self.assertIn("--ignore-rules", command_literals)

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

    def test_audit_custody_does_not_hide_same_named_turn_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            block = root / "block"
            bad = block / "branch_artifacts" / "case-001" / "a_bad" / "turn_0000"
            good = block / "branch_artifacts" / "case-001" / "z_good" / "turn_0000"
            bad.mkdir(parents=True)
            good.mkdir(parents=True)
            (block / "SEALED_BLOCK_INDEX.json").write_text("{}\n", encoding="utf-8")

            def custody(turn):
                return {"custody_pass": turn != bad}

            with mock.patch.object(neutral, "require_gate5"), mock.patch.object(
                neutral, "verify_turn_custody", side_effect=custody
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "TURN_CUSTODY_FAIL:.*branch_artifacts/case-001/a_bad/turn_0000",
                ):
                    neutral.audit_custody(
                        root, neutral.DEFAULT_ADAPTER, "execution-test", "local-test-model"
                    )

    def test_audit_custody_rejects_missing_sealed_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._audit_tree(root, seal_count=28)
            with mock.patch.object(neutral, "require_gate5"), mock.patch.object(
                neutral, "verify_turn_custody", return_value={"custody_pass": True}
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "SEALED_BRANCH_COUNT_MISMATCH:expected=29:actual=28"
                ):
                    neutral.audit_custody(
                        root, neutral.DEFAULT_ADAPTER, "execution-test", "local-test-model"
                    )

    def test_audit_custody_rejects_missing_execution_receipt(self):
        missing = "execution_receipt_blind_proofnet-267_local-test-model.json"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._audit_tree(root, omit_receipt=missing)
            with mock.patch.object(neutral, "require_gate5"), mock.patch.object(
                neutral, "verify_turn_custody", return_value={"custody_pass": True}
            ):
                with self.assertRaisesRegex(RuntimeError, f"EXPECTED_RECEIPT_MISSING:{missing}"):
                    neutral.audit_custody(
                        root, neutral.DEFAULT_ADAPTER, "execution-test", "local-test-model"
                    )

    def test_abort_manual_relay_preserves_hash_inventory_and_visibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gate = root / "gate5"
            turn = root / "block" / "branch_artifacts" / "control" / "D" / "turn_0001"
            gate.mkdir(parents=True)
            turn.mkdir(parents=True)
            manual = json.loads((REPO_ROOT / "execution" / "manual-relay-debug.json").read_text())
            (gate / "adapter_contract.json").write_text(json.dumps(manual), encoding="utf-8")
            (turn / "request.json").write_text('{"sealed":"bytes"}', encoding="utf-8")
            receipt = neutral.abort_manual_relay(root, "execution-test")
            self.assertEqual(receipt["execution_status"], "ABORTED_MANUAL_RELAY")
            self.assertEqual(receipt["admissibility"], "NOT_ADMISSIBLE")
            self.assertEqual(receipt["outcome_visibility"], "NONE")
            self.assertFalse(receipt["outcome_content_opened"])
            self.assertIn(
                "block/branch_artifacts/control/D/turn_0001/request.json",
                receipt["preserved_file_sha256"],
            )
            self.assertEqual((turn / "request.json").read_text(), '{"sealed":"bytes"}')

    def test_turn_custody_rejects_tampered_transport_evidence(self):
        program = (
            "import hashlib,json,os,sys; r=json.load(sys.stdin); "
            "p=os.path.join(os.environ['EXECUTION_ADAPTER_TURN_DIR'],'identity.json'); "
            "open(p,'w').write('observed'); h=hashlib.sha256(b'observed').hexdigest(); "
            "json.dump({'schema_version':'%s','response_text':'answer',"
            "'observed_model_id':r['declared_model_id'],'delivery_status':'DELIVERED',"
            "'started_at_utc':'start','completed_at_utc':'end',"
            "'transport_metadata':{'evidence_files':{'identity.json':h}}},sys.stdout)"
        ) % RESULT_SCHEMA
        adapter = CommandAdapter(command_config([sys.executable, "-c", program]))
        request = ModelRequest("test-run", 0, "model", "system", [], "now")
        with tempfile.TemporaryDirectory() as tmp:
            turn = Path(tmp) / "turn"
            adapter.execute(request, turn, 10)
            self.assertTrue(verify_turn_custody(turn)["custody_pass"])
            (turn / "identity.json").write_text("tampered", encoding="utf-8")
            self.assertFalse(verify_turn_custody(turn)["custody_pass"])

    def test_abort_inference_control_preserves_partial_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            gate = root / "gate5"
            turn = root / "block" / "branch_artifacts" / "control" / "D" / "turn_0000"
            gate.mkdir(parents=True)
            turn.mkdir(parents=True)
            (gate / "adapter_contract.json").write_text('{"kind":"command"}', encoding="utf-8")
            (turn / "codex_events.jsonl").write_text("tool event", encoding="utf-8")
            receipt = neutral.abort_inference_control(root, "execution-test")
            self.assertEqual(receipt["execution_status"], "ABORTED_INFERENCE_CONTROL")
            self.assertEqual(receipt["admissibility"], "NOT_ADMISSIBLE")
            self.assertEqual(receipt["outcome_visibility"], "NONE")
            self.assertIn(
                "block/branch_artifacts/control/D/turn_0000/codex_events.jsonl",
                receipt["preserved_file_sha256"],
            )

    def test_skipped_control_flow_branches_are_explicitly_sealed(self):
        with tempfile.TemporaryDirectory() as tmp:
            block = Path(tmp) / "block"
            sealed = block / "sealed_transcripts"
            sealed.mkdir(parents=True)
            existing = sealed / "sealed_control_D_model.tar"
            existing.write_bytes(b"executed")
            Path(str(existing) + ".sha256").write_text(
                hashlib.sha256(b"executed").hexdigest() + "  " + existing.name + "\n",
                encoding="utf-8",
            )
            created = neutral.materialize_skipped_branch_seals(block, "execution-test", "model")
            self.assertEqual(created, neutral.EXPECTED_SEALED_BRANCHES - 1)
            self.assertEqual(len(list(sealed.glob("*.tar"))), neutral.EXPECTED_SEALED_BRANCHES)
            marker = json.loads((
                block / "branch_artifacts" / "proofnet-267" / "L" / "SKIPPED_BRANCH.json"
            ).read_text())
            self.assertEqual(marker["execution_status"], "NOT_EXECUTED_FROZEN_CONTROL_FLOW")
            self.assertFalse(marker["model_contacted"])
            self.assertEqual(marker["outcome_visibility"], "NONE")

    def test_skipped_seal_refuses_executed_unsealed_branch(self):
        with tempfile.TemporaryDirectory() as tmp:
            block = Path(tmp) / "block"
            (block / "branch_artifacts" / "control" / "D" / "turn_0000").mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, "EXECUTED_BRANCH_SEAL_MISSING:control:D"):
                neutral.materialize_skipped_branch_seals(block, "execution-test", "model")


if __name__ == "__main__":
    unittest.main(verbosity=2)
