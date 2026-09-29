#!/usr/bin/env python3
"""
tests/test_analyze.py
Comprehensive regression tests for tools/analyze.py covering all pre-frozen analytical decision paths.
"""

import unittest
import sys
import os
import json
import hashlib

TOOLS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools"))
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, TOOLS_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from unittest import mock
import analyze
import pool_custody
import custody_fixtures

class TestAnalyzeCustody(unittest.TestCase):

    def test_classify_completion(self):
        # 1. BOTH
        self.assertEqual(analyze.classify_completion("COMPLETE", "COMPLETE"), "BOTH")
        # 2. D-ONLY
        self.assertEqual(analyze.classify_completion("COMPLETE", "FAILED"), "D-ONLY")
        self.assertEqual(analyze.classify_completion("COMPLETE", "SKIPPED_LIFT_NOT_FOUND"), "D-ONLY")
        # 3. L-ONLY
        self.assertEqual(analyze.classify_completion("FAILED", "COMPLETE"), "L-ONLY")
        # 4. NEITHER
        self.assertEqual(analyze.classify_completion("FAILED", "FAILED"), "NEITHER")
        self.assertEqual(analyze.classify_completion("FAILED", "SKIPPED_LIFT_NOT_FOUND"), "NEITHER")
        # 5. INFRA_FAILURE
        self.assertEqual(analyze.classify_completion("INFRA_FAILURE", "COMPLETE"), "NOT_EVALUABLE_INFRA")
        self.assertEqual(analyze.classify_completion("COMPLETE", "INFRA_FAILURE"), "NOT_EVALUABLE_INFRA")
        self.assertEqual(analyze.classify_completion("INFRA_FAILURE", "INFRA_FAILURE"), "NOT_EVALUABLE_INFRA")

    def test_blind_case_adjudication(self):
        # BOTH with WL < WD (negative delta)
        r_both_neg = {
            "case_id": "test_case_1",
            "receipt_type": "blind_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 150},
            "representation_search": {"final_status": "COMPLETE"},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 110}
        }
        res = analyze.analyze_blind_case(r_both_neg)
        self.assertEqual(res["o_completion"], "BOTH")
        self.assertEqual(res["representation_search_outcome"], "LIFT_FOUND")
        self.assertEqual(res["delta_w"], -40)
        self.assertTrue(res["delta_w_evaluated"])

        # BOTH with WL >= WD (positive delta)
        r_both_pos = {
            "case_id": "test_case_2",
            "receipt_type": "blind_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 100},
            "representation_search": {"final_status": "COMPLETE"},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 130}
        }
        res = analyze.analyze_blind_case(r_both_pos)
        self.assertEqual(res["o_completion"], "BOTH")
        self.assertEqual(res["delta_w"], 30)

        # D-ONLY (LIFT_NOT_FOUND) -> delta_w MUST BE NONE
        r_d_only = {
            "case_id": "test_case_3",
            "receipt_type": "blind_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 90},
            "representation_search": {"final_status": "LIFT_NOT_FOUND"},
            "lifted": {"final_status": "SKIPPED_LIFT_NOT_FOUND", "verified_footprint_tokens": None}
        }
        res = analyze.analyze_blind_case(r_d_only)
        self.assertEqual(res["o_completion"], "D-ONLY")
        self.assertEqual(res["representation_search_outcome"], "LIFT_NOT_FOUND")
        self.assertIsNone(res["delta_w"])
        self.assertFalse(res["delta_w_evaluated"])

        # NEITHER -> delta_w MUST BE NONE
        r_neither = {
            "case_id": "test_case_4",
            "receipt_type": "blind_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "FAILED", "verified_footprint_tokens": None},
            "representation_search": {"final_status": "LIFT_NOT_FOUND"},
            "lifted": {"final_status": "SKIPPED_LIFT_NOT_FOUND", "verified_footprint_tokens": None}
        }
        res = analyze.analyze_blind_case(r_neither)
        self.assertEqual(res["o_completion"], "NEITHER")
        self.assertIsNone(res["delta_w"])

        # INFRA_FAILURE on direct
        r_infra = {
            "case_id": "test_case_5",
            "receipt_type": "blind_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "INFRA_FAILURE", "verified_footprint_tokens": None},
            "representation_search": {"final_status": "COMPLETE"},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        res = analyze.analyze_blind_case(r_infra)
        self.assertEqual(res["o_completion"], "NOT_EVALUABLE_INFRA")
        self.assertIsNone(res["delta_w"])

        # Missing model_id must raise ValueError
        r_no_model = {
            "case_id": "test_case_6",
            "receipt_type": "blind_case_execution_receipt",
            "direct": {"final_status": "COMPLETE"},
            "representation_search": {"final_status": "COMPLETE"},
            "lifted": {"final_status": "COMPLETE"}
        }
        with self.assertRaises(ValueError):
            analyze.analyze_blind_case(r_no_model)

    def test_calibration_family_h1(self):
        # 1. Full PASS: 2 * delta_l <= delta_d AND w_l_t1_t2 < w_d_t1_t2
        # delta_l = 20, delta_d = 50 -> 2*20 = 40 <= 50 (OK)
        # w_l = 180, w_d = 200 -> 180 < 200 (OK)
        r_pass = {
            "family_name": "fibonacci",
            "receipt_type": "calibration_family_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
            "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 180, "delta_l_2": 20}
        }
        res = analyze.analyze_calibration_family(r_pass)
        self.assertEqual(res["verdict"], "PASS")
        self.assertTrue(res["marginal_dividend_satisfied"])
        self.assertTrue(res["cumulative_amortization_satisfied"])

        # 2. Marginal PASS, Cumulative FAIL: 2*20 <= 50, but w_l (210) >= w_d (200) -> REJECT
        r_cum_fail = {
            "family_name": "pell",
            "receipt_type": "calibration_family_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
            "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 210, "delta_l_2": 20}
        }
        res = analyze.analyze_calibration_family(r_cum_fail)
        self.assertEqual(res["verdict"], "REJECT")
        self.assertTrue(res["marginal_dividend_satisfied"])
        self.assertFalse(res["cumulative_amortization_satisfied"])

        # 3. Marginal FAIL, Cumulative PASS: 2*30 = 60 > 50 -> REJECT
        r_marg_fail = {
            "family_name": "roots_of_unity",
            "receipt_type": "calibration_family_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
            "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 190, "delta_l_2": 30}
        }
        res = analyze.analyze_calibration_family(r_marg_fail)
        self.assertEqual(res["verdict"], "REJECT")
        self.assertFalse(res["marginal_dividend_satisfied"])
        self.assertTrue(res["cumulative_amortization_satisfied"])

        # 4. Zero Delta_D (delta_d = 0): handled via integer check without division by zero
        r_zero_d = {
            "family_name": "fibonacci",
            "receipt_type": "calibration_family_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 100, "delta_d_2": 0},
            "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 90, "delta_l_2": 0}
        }
        res = analyze.analyze_calibration_family(r_zero_d)
        # 2*0 <= 0 is True, 90 < 100 is True -> PASS
        self.assertEqual(res["verdict"], "PASS")
        self.assertIsNone(res["ratio_delta_l_over_delta_d"])

        # 5. Incomplete proof on T1: NOT_EVALUABLE
        r_incompl = {
            "family_name": "fibonacci",
            "receipt_type": "calibration_family_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
            "lifted": {"s1_status": "FAILED", "l1_status": "SKIPPED_S1_FAILED", "s2_status": "SKIPPED_S1_FAILED", "l2_status": "SKIPPED_S1_FAILED", "w_l_t1_t2": None, "delta_l_2": None}
        }
        res = analyze.analyze_calibration_family(r_incompl)
        self.assertEqual(res["verdict"], "NOT_EVALUABLE")

        # 6. Infrastructure failure: NOT_EVALUABLE_INFRA
        r_infra_fam = {
            "family_name": "fibonacci",
            "receipt_type": "calibration_family_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"d1_status": "INFRA_FAILURE", "d2_status": "SKIPPED", "w_d_t1_t2": None, "delta_d_2": None},
            "lifted": {"s1_status": "SKIPPED", "l1_status": "SKIPPED", "s2_status": "SKIPPED", "l2_status": "SKIPPED", "w_l_t1_t2": None, "delta_l_2": None}
        }
        res = analyze.analyze_calibration_family(r_infra_fam)
        self.assertEqual(res["verdict"], "NOT_EVALUABLE_INFRA")

    def test_h1_aggregation_and_independence(self):
        # All 3 required families present and PASS -> PASS
        all_pass = [
            {"family_name": "fibonacci", "verdict": "PASS"},
            {"family_name": "pell", "verdict": "PASS"},
            {"family_name": "roots_of_unity", "verdict": "PASS"}
        ]
        self.assertEqual(analyze.aggregate_h1(all_pass), "PASS")

        # 2 PASS, 1 REJECT -> REJECT
        one_reject = [
            {"family_name": "fibonacci", "verdict": "PASS"},
            {"family_name": "pell", "verdict": "REJECT"},
            {"family_name": "roots_of_unity", "verdict": "PASS"}
        ]
        self.assertEqual(analyze.aggregate_h1(one_reject), "REJECT")

        # 2 PASS, 1 NOT_EVALUABLE -> NOT_EVALUABLE
        one_incompl = [
            {"family_name": "fibonacci", "verdict": "PASS"},
            {"family_name": "pell", "verdict": "NOT_EVALUABLE"},
            {"family_name": "roots_of_unity", "verdict": "PASS"}
        ]
        self.assertEqual(analyze.aggregate_h1(one_incompl), "NOT_EVALUABLE")

        # 2 PASS, 1 NOT_EVALUABLE_INFRA -> NOT_EVALUABLE_INFRA
        one_infra = [
            {"family_name": "fibonacci", "verdict": "PASS"},
            {"family_name": "pell", "verdict": "NOT_EVALUABLE_INFRA"},
            {"family_name": "roots_of_unity", "verdict": "PASS"}
        ]
        self.assertEqual(analyze.aggregate_h1(one_infra), "NOT_EVALUABLE_INFRA")

        # Missing family (e.g. only 2 families provided) -> NOT_EVALUABLE
        missing_fam = [
            {"family_name": "fibonacci", "verdict": "PASS"},
            {"family_name": "pell", "verdict": "PASS"}
        ]
        self.assertEqual(analyze.aggregate_h1(missing_fam), "NOT_EVALUABLE")

    def test_negative_control_matrix_and_veto(self):
        # 1. D-ONLY -> CONTROL_PASS
        r_d_only = {
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "FAILED", "verified_footprint_tokens": None}
        }
        res = analyze.analyze_control_case(r_d_only)
        self.assertEqual(res["verdict"], "CONTROL_PASS")
        self.assertFalse(res["veto_active"])

        # 2. BOTH & WD < WL -> CONTROL_PASS
        r_both_pass = {
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 42},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 125}
        }
        res = analyze.analyze_control_case(r_both_pass)
        self.assertEqual(res["verdict"], "CONTROL_PASS")
        self.assertFalse(res["veto_active"])

        # 3. L-ONLY -> COMPROMISED (VETO)
        r_l_only = {
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "FAILED", "verified_footprint_tokens": None},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        res = analyze.analyze_control_case(r_l_only)
        self.assertEqual(res["verdict"], "COMPROMISED")
        self.assertTrue(res["veto_active"])

        # 4. BOTH & WL <= WD -> COMPROMISED (VETO)
        r_both_compromised = {
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 130},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        res = analyze.analyze_control_case(r_both_compromised)
        self.assertEqual(res["verdict"], "COMPROMISED")
        self.assertTrue(res["veto_active"])

        # 5. NEITHER -> CONTROL_INCONCLUSIVE
        r_neither = {
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "FAILED", "verified_footprint_tokens": None},
            "lifted": {"final_status": "FAILED", "verified_footprint_tokens": None}
        }
        res = analyze.analyze_control_case(r_neither)
        self.assertEqual(res["verdict"], "CONTROL_INCONCLUSIVE")
        self.assertFalse(res["veto_active"])

        # 6. INFRA_FAILURE -> CONTROL_NOT_EVALUABLE_INFRA
        r_infra = {
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "INFRA_FAILURE", "verified_footprint_tokens": None},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        res = analyze.analyze_control_case(r_infra)
        self.assertEqual(res["verdict"], "CONTROL_NOT_EVALUABLE_INFRA")
        self.assertFalse(res["veto_active"])

    def test_missing_control_and_missing_family_fail_closed(self):
        # 1. Missing control receipt -> veto active, CONTROL_MISSING, H1 & H2 invalidated
        calib_receipts = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "family_name": "fibonacci", "receipt_type": "calibration_family_execution_receipt", "model_id": "claude-sonnet-4-6",
                "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
                "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 180, "delta_l_2": 20}
            },
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "family_name": "pell", "receipt_type": "calibration_family_execution_receipt", "model_id": "claude-sonnet-4-6",
                "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
                "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 180, "delta_l_2": 20}
            },
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "family_name": "roots_of_unity", "receipt_type": "calibration_family_execution_receipt", "model_id": "claude-sonnet-4-6",
                "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
                "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 180, "delta_l_2": 20}
            }
        ]
        blind_receipts = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "case_id": "b1", "receipt_type": "blind_case_execution_receipt", "model_id": "claude-sonnet-4-6",
                "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 100},
                "representation_search": {"final_status": "COMPLETE"},
                "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 80}
            }
        ]

        # Call with control_receipt = None
        study_no_ctrl = analyze.adjudicate_study(control_receipt=None, calibration_receipts=calib_receipts, blind_receipts=blind_receipts)
        self.assertTrue(study_no_ctrl["study_adjudication"]["veto_active"])
        self.assertEqual(study_no_ctrl["study_adjudication"]["negative_control"]["verdict"], "CONTROL_MISSING")
        self.assertEqual(study_no_ctrl["study_adjudication"]["h1_amortization"]["verdicts_by_model"]["claude-sonnet-4-6"]["verdict"], "INVALIDATED_CONTROL_MISSING")
        self.assertEqual(study_no_ctrl["study_adjudication"]["h2_blind_transfer"]["summaries_by_model"]["claude-sonnet-4-6"]["status"], "INVALIDATED_CONTROL_MISSING")

        # 2. Control passes, but only 2 families provided for a model -> NOT_EVALUABLE
        control_pass = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        study_missing_fam = analyze.adjudicate_study(
            control_receipt=control_pass,
            calibration_receipts=calib_receipts[:2],  # Only fibonacci and pell
            blind_receipts=blind_receipts
        )
        self.assertFalse(study_missing_fam["study_adjudication"]["veto_active"])
        h1_res = study_missing_fam["study_adjudication"]["h1_amortization"]["verdicts_by_model"]["claude-sonnet-4-6"]
        self.assertEqual(h1_res["verdict"], "NOT_EVALUABLE")
        self.assertIn("MISSING_CALIBRATION_FAMILIES", h1_res["reason"])

    def test_prereg_model_config_consistency(self):
        """
        Asserts that tools/executor_config.json is the single source of truth for models,
        and that PREREGISTRATION_v0.15_CANDIDATE.md accurately references these exact models
        without historical version regressions (e.g. claude-3-5-sonnet-20241022 or gpt-4o-2024-08-06).
        """
        cfg_path = os.path.join(TOOLS_DIR, "executor_config.json")
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        self.assertEqual(cfg.get("schema_version"), "representation-lifting-executor-config/v1")
        primary_id = cfg.get("primary_model_id")
        repl_id = cfg.get("replication_model_id")

        self.assertEqual(primary_id, "claude-sonnet-4-6")
        self.assertEqual(repl_id, "gpt-5.6-sol")

        # Check preregistration document v0.15 (or v0.14)
        for prereg_name in ["PREREGISTRATION_v0.15_CANDIDATE.md", "PREREGISTRATION_v0.14_CANDIDATE.md"]:
            prereg_path = os.path.join(PROJECT_ROOT, prereg_name)
            if os.path.exists(prereg_path):
                with open(prereg_path, "r", encoding="utf-8") as f:
                    prereg_text = f.read()

                self.assertIn("claude-sonnet-4-6", prereg_text)
                self.assertIn("gpt-5.6-sol", prereg_text)
                self.assertNotIn("claude-3-5-sonnet-20241022", prereg_text)
                self.assertNotIn("gpt-4o-2024-08-06", prereg_text)

    def test_claude_blocker_1_primary_without_receipt_gets_not_evaluable(self):
        """
        1. Primarni model bez ijednog receipt-a mora uvek imati unos sa statusom NOT_EVALUABLE.
           Replikacija ne sme da preglasa niti sakrije primarni model.
        """
        control_repl = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "gpt-5.6-sol",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        calib_repl = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "calibration_family_execution_receipt",
                "family_name": fam,
                "model_id": "gpt-5.6-sol",
                "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
                "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 180, "delta_l_2": 20}
            }
            for fam in ["fibonacci", "pell", "roots_of_unity"]
        ]
        blind_repl = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "blind_case_execution_receipt",
                "case_id": "c1",
                "model_id": "gpt-5.6-sol",
                "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 100},
                "representation_search": {"final_status": "COMPLETE"},
                "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 80}
            }
        ]

        study = analyze.adjudicate_study(
            control_receipts=[control_repl],
            calibration_receipts=calib_repl,
            blind_receipts=blind_repl
        )

        h1_models = study["study_adjudication"]["h1_amortization"]["verdicts_by_model"]
        h2_models = study["study_adjudication"]["h2_blind_transfer"]["summaries_by_model"]

        # Primary model MUST be present and fail closed (NOT_EVALUABLE / INVALIDATED_CONTROL_MISSING because control is also missing)
        self.assertIn("claude-sonnet-4-6", h1_models)
        self.assertIn("gpt-5.6-sol", h1_models)
        self.assertEqual(h1_models["claude-sonnet-4-6"]["role"], "primary")
        self.assertEqual(h1_models["gpt-5.6-sol"]["role"], "replication")
        # Primary control was missing -> invalidated
        self.assertEqual(h1_models["claude-sonnet-4-6"]["verdict"], "INVALIDATED_CONTROL_MISSING")

        # Now test with primary control passing, but 0 primary calibration/blind receipts
        control_primary = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        study2 = analyze.adjudicate_study(
            control_receipts=[control_primary, control_repl],
            calibration_receipts=calib_repl,
            blind_receipts=blind_repl
        )
        h1_2 = study2["study_adjudication"]["h1_amortization"]["verdicts_by_model"]
        self.assertEqual(h1_2["claude-sonnet-4-6"]["verdict"], "NOT_EVALUABLE")
        self.assertIn("NO_RECEIPTS_PROVIDED", h1_2["claude-sonnet-4-6"]["reason"])
        self.assertEqual(h1_2["gpt-5.6-sol"]["verdict"], "PASS")

    def _make_valid_selection_custody(self, pool_size=100, t_pub=1790000000):
        # Quicknet G1 signature is strictly 48 bytes (96 hex characters)
        sig_bytes = bytes.fromhex("a1" * 48)
        sig_hex = sig_bytes.hex()
        rand_bytes = hashlib.sha256(sig_bytes).digest()
        rand_hex = rand_bytes.hex()
        
        from drand_schedule import compute_scheduled_round, QUICKNET_CHAIN_HASH
        from select_indices import select_indices
        
        rnd = compute_scheduled_round(t_pub)
        
        pool_lines = [f"case_{i}\tproofnet_thm_{i}\n" for i in range(pool_size)]
        pool_tsv = "".join(pool_lines)
        pool_hash = hashlib.sha256(pool_tsv.encode("utf-8")).hexdigest()
        
        indices = select_indices(rand_bytes, pool_size, count=3)
        selected = [{"index": idx, "case_id": f"case_{idx}"} for idx in indices]
        
        # v0.21 custody: manifest -> Rekor evidence -> derived commitment/v2 + anchor/v2 (T1 = t_pub)
        pool_manifest, pool_anchor_evidence, pool_commitment, pool_anchor = custody_fixtures.make_valid_custody(
            pool_tsv.encode("utf-8"), pool_size, t_pub)
        self._anchor_extras = {"pool_manifest": pool_manifest, "pool_anchor_evidence": pool_anchor_evidence}
        patcher = mock.patch.object(pool_custody, "CARRIED_FORWARD_MANIFEST_SHA256",
                                    hashlib.sha256(pool_manifest).hexdigest())
        patcher.start()
        self.addCleanup(patcher.stop)

        selection_record = {
            "schema_version": "representation-lifting-selection/v1",
            "quicknet_chain_hash": QUICKNET_CHAIN_HASH,
            "round": rnd,
            "signature_hex": sig_hex,
            "randomness_hex": rand_hex,
            "selected": selected
        }

        beacon_verification = {
            "schema_version": "representation-lifting-beacon-verification/v1",
            "quicknet_chain_hash": QUICKNET_CHAIN_HASH,
            "round": rnd,
            "signature_hex": sig_hex,
            "scheme_id": "bls-unchained-g1-rfc9380",
            "public_key_hex": analyze.DRAND_QUICKNET_PUBLIC_KEY_HEX,
            "verifier_tool": "drand-client/v1.5.8",
            "verifier_binary_sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
            "verification_status": "BLS_VERIFIED"
        }
        
        return pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected

    def test_selection_custody_full_chain_and_matching(self):
        """
        Validates complete selection custody chain, external anchors, and case matching:
        - validate_selection succeeds and recomputes exact indices and case_ids
        - Missing 1 case in blind receipts gives NOT_EVALUABLE (MISSING_BLIND_CASES)
        - Extra case gives InputContractError
        - Exact match gives VALID_DESCRIPTIVE_SERIES
        """
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected = self._make_valid_selection_custody()
        
        # 1. Direct validation of selection custody chain
        val_selected = analyze.validate_selection(
            pool_tsv,
            pool_commitment,
            selection_record,
            pool_anchor=pool_anchor, **self._anchor_extras,
            beacon_verification=beacon_verification
        )
        self.assertEqual(val_selected, selected)

        control_receipt = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }

        # Case A: Missing 1 case (only 2 of 3 provided) -> H2 is NOT_EVALUABLE
        cids = [item["case_id"] for item in selected]
        blind_missing_one = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "blind_case_execution_receipt",
                "case_id": cid,
                "model_id": "claude-sonnet-4-6",
                "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 100},
                "representation_search": {"final_status": "COMPLETE"},
                "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 80}
            }
            for cid in cids[:2]
        ]

        study = analyze.adjudicate_study(
            control_receipts=[control_receipt],
            blind_receipts=blind_missing_one,
            selection_record=selection_record,
            pool_commitment=pool_commitment,
            pool_tsv=pool_tsv,
            pool_anchor=pool_anchor, **self._anchor_extras,
            beacon_verification=beacon_verification
        )
        h2_res = study["study_adjudication"]["h2_blind_transfer"]["summaries_by_model"]["claude-sonnet-4-6"]
        self.assertEqual(h2_res["status"], "NOT_EVALUABLE")
        self.assertIn("MISSING_BLIND_CASES", h2_res["reason"])

        # Case B: Extra case not in selection record -> InputContractError
        blind_with_extra = blind_missing_one + [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "blind_case_execution_receipt",
                "case_id": "unselected_case_delta",
                "model_id": "claude-sonnet-4-6",
                "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 100},
                "representation_search": {"final_status": "COMPLETE"},
                "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 80}
            }
        ]
        with self.assertRaises(analyze.InputContractError):
            analyze.adjudicate_study(
                control_receipts=[control_receipt],
                blind_receipts=blind_with_extra,
                selection_record=selection_record,
                pool_commitment=pool_commitment,
                pool_tsv=pool_tsv,
                pool_anchor=pool_anchor, **self._anchor_extras,
                beacon_verification=beacon_verification
            )

        # Case C: Exact match of all 3 selected cases -> VALID_DESCRIPTIVE_SERIES
        blind_exact = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "blind_case_execution_receipt",
                "case_id": cid,
                "model_id": "claude-sonnet-4-6",
                "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 100},
                "representation_search": {"final_status": "COMPLETE"},
                "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 80}
            }
            for cid in cids
        ]
        study_exact = analyze.adjudicate_study(
            control_receipts=[control_receipt],
            blind_receipts=blind_exact,
            selection_record=selection_record,
            pool_commitment=pool_commitment,
            pool_tsv=pool_tsv,
            pool_anchor=pool_anchor, **self._anchor_extras,
            beacon_verification=beacon_verification
        )
        h2_exact = study_exact["study_adjudication"]["h2_blind_transfer"]["summaries_by_model"]["claude-sonnet-4-6"]
        self.assertEqual(h2_exact["status"], "VALID_DESCRIPTIVE_SERIES")

    def test_selection_custody_missing_record_gives_not_evaluable(self):
        """
        Missing selection custody artifacts when blind receipts are present must fail closed:
        H2 is NOT_EVALUABLE with reason indicating MISSING_SELECTION_CUSTODY.
        """
        control_receipt = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        blind_receipts = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "blind_case_execution_receipt",
                "case_id": "case_1",
                "model_id": "claude-sonnet-4-6",
                "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 100},
                "representation_search": {"final_status": "COMPLETE"},
                "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 80}
            }
        ]
        study = analyze.adjudicate_study(
            control_receipts=[control_receipt],
            blind_receipts=blind_receipts,
            selection_record=None
        )
        h2_res = study["study_adjudication"]["h2_blind_transfer"]["summaries_by_model"]["claude-sonnet-4-6"]
        self.assertEqual(h2_res["status"], "NOT_EVALUABLE")
        self.assertIn("MISSING_SELECTION_CUSTODY", h2_res["reason"])

    def test_missing_pool_anchor_gives_not_evaluable_pool_timestamp(self):
        """
        When blind receipts and selection record are provided, but external pool anchor is missing,
        H2 fails closed as NOT_EVALUABLE_POOL_TIMESTAMP.
        """
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected = self._make_valid_selection_custody()
        control_receipt = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        blind_receipts = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "blind_case_execution_receipt",
                "case_id": item["case_id"],
                "model_id": "claude-sonnet-4-6",
                "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 100},
                "representation_search": {"final_status": "COMPLETE"},
                "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 80}
            }
            for item in selected
        ]
        study = analyze.adjudicate_study(
            control_receipts=[control_receipt],
            blind_receipts=blind_receipts,
            selection_record=selection_record,
            pool_commitment=pool_commitment,
            pool_tsv=pool_tsv,
            pool_anchor=None,
            beacon_verification=beacon_verification
        )
        h2_res = study["study_adjudication"]["h2_blind_transfer"]["summaries_by_model"]["claude-sonnet-4-6"]
        self.assertEqual(h2_res["status"], "NOT_EVALUABLE_POOL_TIMESTAMP")
        self.assertIn("MISSING_POOL_ANCHOR_RECEIPT", h2_res["reason"])

    def test_missing_beacon_verification_gives_not_evaluable_beacon_authenticity(self):
        """
        When blind receipts, selection record, and pool anchor are provided, but beacon verification is missing,
        H2 fails closed as NOT_EVALUABLE_BEACON_AUTHENTICITY.
        """
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected = self._make_valid_selection_custody()
        control_receipt = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        blind_receipts = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "blind_case_execution_receipt",
                "case_id": item["case_id"],
                "model_id": "claude-sonnet-4-6",
                "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 100},
                "representation_search": {"final_status": "COMPLETE"},
                "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 80}
            }
            for item in selected
        ]
        study = analyze.adjudicate_study(
            control_receipts=[control_receipt],
            blind_receipts=blind_receipts,
            selection_record=selection_record,
            pool_commitment=pool_commitment,
            pool_tsv=pool_tsv,
            pool_anchor=pool_anchor, **self._anchor_extras,
            beacon_verification=None
        )
        h2_res = study["study_adjudication"]["h2_blind_transfer"]["summaries_by_model"]["claude-sonnet-4-6"]
        self.assertEqual(h2_res["status"], "NOT_EVALUABLE_BEACON_AUTHENTICITY")
        self.assertIn("MISSING_BEACON_AUTHENTICITY_RECEIPT", h2_res["reason"])

    def test_adversarial_quicknet_signature_length_violation(self):
        """Adversarial check: Quicknet BLS signature not exactly 48 bytes (e.g. 96 bytes) is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        selection_record["signature_hex"] = "a1" * 96  # 96 bytes instead of 48 bytes
        selection_record["randomness_hex"] = hashlib.sha256(bytes.fromhex("a1" * 96)).hexdigest()
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_pool_anchor_verification_status_failed(self):
        """Adversarial check: pool_anchor with non-verified status is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        pool_anchor["verification_status"] = "FAILED"
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record, pool_anchor=pool_anchor, **self._anchor_extras)

    def test_adversarial_pool_anchor_timestamp_mismatch(self):
        """Adversarial check: pool_anchor timestamp mismatch against published_at_unix is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        pool_anchor["verified_timestamp_unix"] += 10
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record, pool_anchor=pool_anchor, **self._anchor_extras)

    def test_adversarial_beacon_verification_status_failed(self):
        """Adversarial check: beacon_verification with non-verified status is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        beacon_verification["verification_status"] = "INVALID_SIGNATURE"
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record, beacon_verification=beacon_verification)

    def test_adversarial_beacon_verification_signature_mismatch(self):
        """Adversarial check: beacon_verification signature not matching selection_record is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        beacon_verification["signature_hex"] = "b2" * 48
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record, beacon_verification=beacon_verification)

    def test_adversarial_beacon_verification_round_mismatch(self):
        """Adversarial check: beacon_verification round not matching selection_record is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        beacon_verification["round"] += 1
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record, beacon_verification=beacon_verification)

    def test_adversarial_selection_wrong_chain_hash(self):
        """Adversarial check: Selection record with wrong quicknet chain hash is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        selection_record["quicknet_chain_hash"] = "52db9290a61cbeacfa75d64301734a82e9a0280acacd36322b657d82448d075a"
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_selection_only_two_cases(self):
        """Adversarial check: Selection record with only 2 selected items is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected = self._make_valid_selection_custody()
        selection_record["selected"] = selected[:2]
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_selection_signature_tampered_randomness_unchanged(self):
        """
        Adversarial check: signature changed by one byte while randomness_hex remains unchanged
        must be caught and rejected by SHA256(signature) == randomness_hex.
        """
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        sig_bytes = bytearray(bytes.fromhex(selection_record["signature_hex"]))
        sig_bytes[0] ^= 0xFF  # Flip bits of first byte
        selection_record["signature_hex"] = sig_bytes.hex()
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_selection_wrong_pool_hash(self):
        """Adversarial check: pool_commitment with wrong pool_sha256 is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        pool_commitment["pool_sha256"] = "0000000000000000000000000000000000000000000000000000000000000000"
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_selection_wrong_pool_size(self):
        """Adversarial check: pool_commitment specifying wrong pool_size is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        pool_commitment["pool_size"] = 99  # Actual pool has 100 rows
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_selection_wrong_round(self):
        """Adversarial check: selection_record specifying round not matching published_at_unix is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        selection_record["round"] += 1
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_selection_duplicate_index(self):
        """Adversarial check: selection_record with duplicate selected index is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected = self._make_valid_selection_custody()
        selection_record["selected"] = [selected[0], selected[0], selected[2]]
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_selection_case_id_mismatch_with_pool(self):
        """Adversarial check: selection_record with case_id not matching POOL row is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected = self._make_valid_selection_custody()
        selection_record["selected"][0]["case_id"] = "forged_case_id"
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_selection_altered_index(self):
        """Adversarial check: selection_record with altered index is rejected."""
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected = self._make_valid_selection_custody()
        selection_record["selected"][0]["index"] = (selection_record["selected"][0]["index"] + 1) % 100
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record)

    def test_adversarial_selection_incomplete_custody_artifacts(self):
        """Adversarial check: providing only selection_record without pool_commitment/pool_tsv is rejected."""
        cfg = {"schema_version": "representation-lifting-executor-config/v1", "primary_model_id": "claude-sonnet-4-6", "replication_model_id": "gpt-5.6-sol"}
        _, _, selection_record, _, _, _ = self._make_valid_selection_custody()
        blind = [{
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "blind_case_execution_receipt",
            "case_id": "case_1",
            "model_id": "claude-sonnet-4-6",
            "direct": {}, "lifted": {}
        }]
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_study_inputs(cfg, blind_receipts=blind, selection_record=selection_record)
        blind = [{
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "blind_case_execution_receipt",
            "case_id": "case_1",
            "model_id": "claude-sonnet-4-6",
            "direct": {}, "lifted": {}
        }]
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_study_inputs(cfg, blind_receipts=blind, selection_record=selection_record)

    def test_study_verdict_primary_model_governance(self):
        """
        Validates study_verdict governance:
        - Top-level study_verdict is derived strictly from primary model.
        - When primary model negative control is compromised and replication passes,
          study_verdict is INVALIDATED_BY_CONTROL_VETO with basis PRIMARY_MODEL_ONLY,
          and replication is marked as SECONDARY_REPLICATION_ONLY.
        """
        ctrl_prim_compromised = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 150},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}  # WL <= WD -> COMPROMISED
        }
        ctrl_repl_pass = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "gpt-5.6-sol",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        calib_both = []
        for mid in ["claude-sonnet-4-6", "gpt-5.6-sol"]:
            for fam in ["fibonacci", "pell", "roots_of_unity"]:
                calib_both.append({
                    "schema_version": "representation-lifting-execution-receipt/v1",
                    "receipt_type": "calibration_family_execution_receipt",
                    "family_name": fam,
                    "model_id": mid,
                    "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
                    "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 180, "delta_l_2": 20}
                })

        study = analyze.adjudicate_study(
            control_receipts=[ctrl_prim_compromised, ctrl_repl_pass],
            calibration_receipts=calib_both
        )

        # Assert top-level fields
        self.assertEqual(study["study_verdict"], "INVALIDATED_BY_CONTROL_VETO")
        self.assertEqual(study["basis"], "PRIMARY_MODEL_ONLY")
        self.assertEqual(study["replication"]["status"], "PASS")
        self.assertEqual(study["replication"]["interpretation"], "SECONDARY_REPLICATION_ONLY")

    def test_claude_blocker_3_duplicates_rejected(self):
        """
        3. Duplikati se odbijaju sa InputContractError:
           - dva receipt-a za istu porodicu za isti model
           - dva receipt-a za isti blind case za isti model
           - dva receipt-a za kontrolu za isti model
        """
        cfg = {"schema_version": "representation-lifting-executor-config/v1", "primary_model_id": "claude-sonnet-4-6", "replication_model_id": "gpt-5.6-sol"}

        # Duplicate calibration
        dup_calib = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "calibration_family_execution_receipt",
                "family_name": "fibonacci", "model_id": "claude-sonnet-4-6",
                "direct": {}, "lifted": {}
            },
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "calibration_family_execution_receipt",
                "family_name": "fibonacci", "model_id": "claude-sonnet-4-6",
                "direct": {}, "lifted": {}
            }
        ]
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_study_inputs(cfg, calibration_receipts=dup_calib)

        # Duplicate blind
        dup_blind = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "blind_case_execution_receipt",
                "case_id": "c1", "model_id": "claude-sonnet-4-6",
                "direct": {}, "lifted": {}
            },
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "blind_case_execution_receipt",
                "case_id": "c1", "model_id": "claude-sonnet-4-6",
                "direct": {}, "lifted": {}
            }
        ]
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_study_inputs(cfg, blind_receipts=dup_blind)

        # Duplicate control
        dup_ctrl = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "control_case_execution_receipt",
                "model_id": "claude-sonnet-4-6", "direct": {}, "lifted": {}
            },
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "control_case_execution_receipt",
                "model_id": "claude-sonnet-4-6", "direct": {}, "lifted": {}
            }
        ]
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_study_inputs(cfg, control_receipts=dup_ctrl)

    def test_claude_blocker_4_unregistered_model_rejected(self):
        """
        4. Nepoznat model se ne sme tiho prihvatiti kao 'unregistered' već diže InputContractError.
        """
        cfg = {"schema_version": "representation-lifting-executor-config/v1", "primary_model_id": "claude-sonnet-4-6", "replication_model_id": "gpt-5.6-sol"}
        bad_receipt = [
            {
                "schema_version": "representation-lifting-execution-receipt/v1",
                "receipt_type": "calibration_family_execution_receipt",
                "family_name": "fibonacci",
                "model_id": "unregistered-unknown-llm",
                "direct": {}, "lifted": {}
            }
        ]
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_study_inputs(cfg, calibration_receipts=bad_receipt)

    def test_claude_blocker_5_missing_or_invalid_config_fails_closed(self):
        """
        5. Nedostajući ili neispravan config mora biti fatalna greška; nema tihog fallback-a.
        """
        with self.assertRaises(FileNotFoundError):
            analyze.load_executor_config("/nonexistent/dummy/path.json")

    def test_claude_blocker_6_per_model_negative_control_governance(self):
        """
        6. Kontrola se vodi po modelu:
           - primary control COMPROMISED -> invalidira primarni H1 i H2
           - replication control COMPROMISED -> invalidira replikaciju, ali primarni ishod OSTAJE VAŽEĆI
           - primary control PASS, replication control MISSING -> primarni validan, replikacija CONTROL_MISSING
        """
        ctrl_prim_pass = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "claude-sonnet-4-6",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 40},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}
        }
        ctrl_repl_compromised = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "control_case_execution_receipt",
            "model_id": "gpt-5.6-sol",
            "direct": {"final_status": "COMPLETE", "verified_footprint_tokens": 140},
            "lifted": {"final_status": "COMPLETE", "verified_footprint_tokens": 120}  # WL <= WD -> COMPROMISED
        }

        calib_both = []
        for mid in ["claude-sonnet-4-6", "gpt-5.6-sol"]:
            for fam in ["fibonacci", "pell", "roots_of_unity"]:
                calib_both.append({
                    "schema_version": "representation-lifting-execution-receipt/v1",
                    "receipt_type": "calibration_family_execution_receipt",
                    "family_name": fam,
                    "model_id": mid,
                    "direct": {"d1_status": "COMPLETE", "d2_status": "COMPLETE", "w_d_t1_t2": 200, "delta_d_2": 50},
                    "lifted": {"s1_status": "COMPLETE", "l1_status": "COMPLETE", "s2_status": "COMPLETE", "l2_status": "COMPLETE", "w_l_t1_t2": 180, "delta_l_2": 20}
                })

        # Adjudicate with primary passing control and replication compromised control
        study = analyze.adjudicate_study(
            control_receipts=[ctrl_prim_pass, ctrl_repl_compromised],
            calibration_receipts=calib_both
        )
        h1_res = study["study_adjudication"]["h1_amortization"]["verdicts_by_model"]

        # Primary is unaffected by replication failure: PASS!
        self.assertEqual(h1_res["claude-sonnet-4-6"]["verdict"], "PASS")
        # Replication is invalidated by its own compromised control:
        self.assertEqual(h1_res["gpt-5.6-sol"]["verdict"], "INVALIDATED_BY_CONTROL_VETO")

    def test_freeze_blocker_0_end_to_end_real_receipt_to_analysis_pipeline(self):
        """
        Freeze Blocker #0:
        Asserts that the receipt schema emitted by run_calibration_family in executor_harness
        (with family_name, schema_version, receipt_type, d1_status, d2_status, etc.)
        is 100% compliant with validate_study_inputs and cleanly parsed by analyze_calibration_family.
        """
        real_harness_output = {
            "schema_version": "representation-lifting-execution-receipt/v1",
            "receipt_type": "calibration_family_execution_receipt",
            "family_name": "fibonacci",
            "model_id": "claude-sonnet-4-6",
            "timestamp_utc": "2026-09-25T21:00:00+00:00",
            "direct": {
                "d1_status": "COMPLETE",
                "w_d_t1": 100,
                "d2_status": "COMPLETE",
                "w_d_t1_t2": 200,
                "delta_d_2": 100
            },
            "lifted": {
                "s1_status": "COMPLETE",
                "l1_status": "COMPLETE",
                "w_l_t1": 90,
                "s2_status": "COMPLETE",
                "l2_status": "COMPLETE",
                "w_l_t1_t2": 130,
                "delta_l_2": 40
            },
            "marginal_dividend_satisfied": True,
            "cumulative_amortization_satisfied": True,
            "h1_dividend_satisfied": True,
            "ratio_delta_l_over_delta_d": 0.4
        }

        # Must not raise any InputContractError
        cfg = analyze.load_executor_config()
        analyze.validate_study_inputs(cfg, calibration_receipts=[real_harness_output])

        # analyze_calibration_family must evaluate PASS without UNKNOWN or NOT_EVALUABLE
        analysis = analyze.analyze_calibration_family(real_harness_output)
        self.assertEqual(analysis["verdict"], "PASS")
        self.assertTrue(analysis["marginal_dividend_satisfied"])
        self.assertTrue(analysis["cumulative_amortization_satisfied"])
        self.assertEqual(analysis["delta_d_2"], 100)
        self.assertEqual(analysis["delta_l_2"], 40)

    def test_adversarial_beacon_verification_public_key_mismatch(self):
        """
        Adversarial check: beacon_verification with wrong public_key_hex is rejected.
        """
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected = self._make_valid_selection_custody()
        # Tamper public key (wrong 96-byte hex key)
        beacon_verification["public_key_hex"] = "b" * 192

        with self.assertRaises(analyze.InputContractError) as ctx:
            analyze.validate_selection(
                pool_tsv, pool_commitment, selection_record,
                pool_anchor=pool_anchor, **self._anchor_extras, beacon_verification=beacon_verification
            )
        self.assertIn("public_key_hex mismatch", str(ctx.exception))

    def test_adversarial_beacon_verification_public_key_length_violation(self):
        """
        Adversarial check: beacon_verification with wrong public key length (e.g. 48 bytes) is rejected.
        """
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, selected = self._make_valid_selection_custody()
        # Length violation: 48 bytes (96 hex chars) instead of 96 bytes (192 hex chars)
        beacon_verification["public_key_hex"] = "b" * 96

        with self.assertRaises(analyze.InputContractError) as ctx:
            analyze.validate_selection(
                pool_tsv, pool_commitment, selection_record,
                pool_anchor=pool_anchor, **self._anchor_extras, beacon_verification=beacon_verification
            )
        self.assertIn("Quicknet public key length violation", str(ctx.exception))

    def test_drand_quicknet_constants_against_archived_root(self):
        """
        Verifies that all 6 drand quicknet fields in analyze.py and drand_schedule.py
        match the archived raw /info API response, including groupHash which caught
        the v0.18 manual-copy provenance error.
        """
        root_path = os.path.join(PROJECT_ROOT, "external_roots", "drand_quicknet_info_api.raw.json")
        self.assertTrue(os.path.exists(root_path), "external_roots/drand_quicknet_info_api.raw.json must exist")
        
        with open(root_path, "rb") as f:
            content = f.read()
        
        # Verify SHA-256 of archived raw file (byte-for-byte from curl)
        file_hash = hashlib.sha256(content).hexdigest()
        self.assertEqual(file_hash, "3e690bc527c8a4e78232bc06b5a3cff057c51c68f51b208a1a21b2abd6d6b194")

        data = json.loads(content.decode("utf-8"))
        self.assertEqual(data["hash"], analyze.QUICKNET_CHAIN_HASH)
        self.assertEqual(data["period"], 3)
        self.assertEqual(data["genesis_time"], 1692803367)
        self.assertEqual(data["schemeID"], analyze.DRAND_QUICKNET_SCHEME_ID)
        self.assertEqual(data["public_key"], analyze.DRAND_QUICKNET_PUBLIC_KEY_HEX)
        self.assertEqual(len(bytes.fromhex(data["public_key"])), 96)
        # groupHash: pinned constant proving archive authenticity against drand network
        self.assertEqual(data["groupHash"], analyze.QUICKNET_GROUP_HASH)
        self.assertEqual(data["groupHash"], analyze.DRAND_QUICKNET_GROUP_HASH)
        self.assertEqual(data["groupHash"], "f477d5c89f21a17c863a7f937c6a6d15859414d2be09cd448d4279af331c5d3e")

    # ---- Amendment v0.21: pre-randomness custody at the analyzer boundary ----
    def test_v021_anchor_without_manifest_and_evidence_rejected(self):
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record, pool_anchor=pool_anchor)
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record, pool_anchor=pool_anchor,
                                       pool_manifest=self._anchor_extras["pool_manifest"])

    def test_v021_retired_v1_commitment_rejected(self):
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        v1 = {"schema_version": "representation-lifting-pool-commitment/v1",
              "pool_sha256": pool_commitment["pool_sha256"], "pool_size": pool_commitment["pool_size"],
              "published_at_unix": pool_commitment["published_at_unix"]}
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, v1, selection_record)

    def test_v021_manifest_not_carried_forward_rejected_without_test_pin(self):
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        mock.patch.stopall()  # restore the real pin aef332...; synthetic manifest must now fail
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record,
                                       pool_anchor=pool_anchor, **self._anchor_extras)

    def test_v021_round_must_derive_from_anchor_t1(self):
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        from drand_schedule import compute_scheduled_round
        selection_record["round"] = compute_scheduled_round(pool_commitment["published_at_unix"] + 60)
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record,
                                       pool_anchor=pool_anchor, **self._anchor_extras)

    def test_v021_manifest_supplied_without_anchor_still_bound(self):
        pool_tsv, pool_commitment, selection_record, pool_anchor, beacon_verification, _ = self._make_valid_selection_custody()
        bad_manifest = self._anchor_extras["pool_manifest"].replace(b'"tools/build_pool.py"', b'"tools/build_pool.pY"')
        with self.assertRaises(analyze.InputContractError):
            analyze.validate_selection(pool_tsv, pool_commitment, selection_record, pool_manifest=bad_manifest)

    def test_parse_pool_tsv_rejects_duplicate_case_id(self):
        """Asserts that parse_pool_tsv globally rejects duplicate case_ids fail-closed."""
        tsv_content = (
            "case_id\tsource_name\n"
            "proofnet-001\tArtin_exercise_2_2_9\n"
            "proofnet-001\tRudin_exercise_4_8a\n"
        )
        with self.assertRaises(analyze.InputContractError) as ctx:
            analyze.parse_pool_tsv(tsv_content)
        self.assertIn("Duplicate case_id 'proofnet-001' detected in POOL.tsv data row 2", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()

