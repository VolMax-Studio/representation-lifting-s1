#!/usr/bin/env python3
"""
tests/test_pool_custody.py
Adversarial tests for the v0.21 pre-randomness custody contract (tools/pool_custody.py).
Every mutation of the chain manifest -> POOL.tsv -> commitment/v2 -> anchor/v2 -> Rekor evidence
must be rejected; anchor grinding (using a later anchor while an earlier one exists) must be rejected.
"""

import copy
import hashlib
import json
import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(TESTS_DIR, ".."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "tools"))
sys.path.insert(0, TESTS_DIR)

import pool_custody  # noqa: E402
import fetch_rekor_evidence  # noqa: E402
import custody_fixtures as fx  # noqa: E402

T1 = 1790000000
POOL = "".join(f"proofnet-{i:03d}\tname_{i}\n" for i in range(1, 11))
POOL_BYTES = ("case_id\tsource_name\n" + POOL).encode("utf-8")
POOL_SIZE = 10
REAL_FIXTURE = os.path.join(TESTS_DIR, "fixtures", "rekor_real_entry_dryrun.json")


class TestPoolCustodyV2(unittest.TestCase):

    def setUp(self):
        self.manifest, self.evidence, self.commitment, self.anchor = fx.make_valid_custody(POOL_BYTES, POOL_SIZE, T1)
        self.m = fx.sha(self.manifest)
        self.p = fx.sha(POOL_BYTES)

    def validate(self, manifest=None, pool_sha=None, pool_size=None, commitment=None, anchor=None,
                 evidence=None, expected=None):
        return pool_custody.validate_pool_custody_v2(
            self.manifest if manifest is None else manifest,
            self.p if pool_sha is None else pool_sha,
            POOL_SIZE if pool_size is None else pool_size,
            self.commitment if commitment is None else commitment,
            self.anchor if anchor is None else anchor,
            self.evidence if evidence is None else evidence,
            expected_manifest_sha256=self.m if expected is None else expected,
        )

    def assertRejects(self, **kw):
        with self.assertRaises(pool_custody.CustodyError):
            self.validate(**kw)

    # ---- valid chain -------------------------------------------------------
    def test_valid_chain_returns_t1(self):
        self.assertEqual(self.validate(), T1)
        self.assertEqual(self.commitment["published_at_unix"], T1)
        self.assertEqual(self.anchor["verified_timestamp_unix"], T1)
        self.assertNotIn("commitment_sha256", self.anchor)

    # ---- carried-forward pool pin -------------------------------------------
    def test_carried_forward_pin_rejects_any_other_manifest(self):
        with self.assertRaises(pool_custody.CustodyError):
            pool_custody.validate_pool_custody_v2(self.manifest, self.p, POOL_SIZE, self.commitment,
                                                  self.anchor, self.evidence)  # default = aef332...

    def test_carried_forward_constants(self):
        self.assertEqual(pool_custody.CARRIED_FORWARD_MANIFEST_SHA256,
                         "aef332f69fb7bf70c0032dc05a383f8fea0085fecbd2ba22281c48ef4c36f7f6")
        self.assertEqual(pool_custody.CARRIED_FORWARD_POOL_SHA256,
                         "398ddcb3d9e915edce681c0d59138950177d7eb096200795f927741fb9743212")
        self.assertEqual(pool_custody.CARRIED_FORWARD_POOL_SIZE, 362)

    def test_frozen_builder_and_filter_untouched_by_amendment(self):
        for rel, want in (("tools/build_pool.py", pool_custody.FROZEN_BUILDER_SHA256),
                          ("tools/nontriviality_filter.py", pool_custody.FROZEN_FILTER_SHA256)):
            with open(os.path.join(PROJECT_ROOT, rel), "rb") as f:
                self.assertEqual(hashlib.sha256(f.read()).hexdigest(), want, rel)

    # ---- manifest / pool binding ------------------------------------------
    def test_manifest_byte_changed(self):
        self.assertRejects(manifest=self.manifest.replace(b'"builder_name"', b'"builder_nam3"'))

    def test_manifest_pool_hash_changed(self):
        bad = fx.make_manifest_bytes(POOL_BYTES, bundle_files={"POOL.tsv": "1" * 64})
        self.assertRejects(manifest=bad, expected=fx.sha(bad))

    def test_manifest_wrong_builder(self):
        bad = fx.make_manifest_bytes(POOL_BYTES, builder_sha256="2" * 64)
        self.assertRejects(manifest=bad, expected=fx.sha(bad))

    def test_actual_pool_changed(self):
        self.assertRejects(pool_sha=fx.sha(POOL_BYTES + b"proofnet-999\tx\n"))

    def test_manifest_sha256_changed_in_commitment(self):
        c = dict(self.commitment, manifest_sha256="3" * 64)
        self.assertRejects(commitment=c)

    def test_manifest_sha256_changed_in_anchor(self):
        a = dict(self.anchor, manifest_sha256="3" * 64)
        self.assertRejects(anchor=a)

    def test_commitment_pool_sha_changed(self):
        self.assertRejects(commitment=dict(self.commitment, pool_sha256="4" * 64))

    def test_anchor_pool_sha_changed(self):
        self.assertRejects(anchor=dict(self.anchor, pool_sha256="4" * 64))

    def test_pool_size_changed(self):
        self.assertRejects(commitment=dict(self.commitment, pool_size=POOL_SIZE + 1))
        self.assertRejects(pool_size=POOL_SIZE - 1)

    # ---- timestamp semantics ----------------------------------------------
    def test_published_at_not_t1(self):
        self.assertRejects(commitment=dict(self.commitment, published_at_unix=T1 + 1))
        self.assertRejects(commitment=dict(self.commitment, published_at_unix=T1 - 1))

    def test_anchor_timestamp_not_t1(self):
        self.assertRejects(anchor=dict(self.anchor, verified_timestamp_unix=T1 + 1))

    def test_non_integer_timestamps(self):
        self.assertRejects(commitment=dict(self.commitment, published_at_unix=float(T1)))
        self.assertRejects(anchor=dict(self.anchor, verified_timestamp_unix=True))

    # ---- anchor receipt contract ------------------------------------------
    def test_status_not_verified(self):
        self.assertRejects(anchor=dict(self.anchor, verification_status="PENDING"))

    def test_non_rekor_anchor_types_inadmissible(self):
        for t in ("git_push", "opentimestamps", "rfc3161", "rekor_transparency_log"):
            self.assertRejects(anchor=dict(self.anchor, anchor_type=t))

    def test_other_rekor_url(self):
        self.assertRejects(anchor=dict(self.anchor, rekor_url="https://rekor.example.org"))

    def test_empty_verifier(self):
        self.assertRejects(anchor=dict(self.anchor, verifier="  "))

    def test_evidence_hash_mismatch(self):
        self.assertRejects(anchor=dict(self.anchor, anchor_evidence_sha256="5" * 64))

    def test_reintroduced_commitment_sha256_field_rejected(self):
        a = dict(self.anchor, commitment_sha256=fx.sha(pool_custody.canonical_json_bytes(self.commitment)))
        self.assertRejects(anchor=a)

    def test_extra_commitment_field_rejected(self):
        self.assertRejects(commitment=dict(self.commitment, note="x"))

    # ---- earliest-entry rule (anti-grinding) -------------------------------
    def _two_entry_evidence(self, t_early, idx_early, t_late, idx_late):
        return fx.make_evidence_bytes(self.m, [
            fx.make_rekor_entry(fx.uuid_n(2), self.m, t_late, idx_late),
            fx.make_rekor_entry(fx.uuid_n(3), self.m, t_early, idx_early),
        ])

    def test_later_anchor_cannot_define_t1(self):
        ev = self._two_entry_evidence(T1 - 3600, 900, T1, 1000)
        a = dict(self.anchor, anchor_proof_id=fx.uuid_n(2), anchor_log_index=1000,
                 verified_timestamp_unix=T1, anchor_evidence_sha256=fx.sha(ev))
        self.assertRejects(anchor=a, evidence=ev)

    def test_earliest_anchor_is_selected_by_derivation(self):
        ev = self._two_entry_evidence(T1 - 3600, 900, T1, 1000)
        c, a = pool_custody.derive_custody_records(self.manifest, self.p, POOL_SIZE, ev, "v",
                                                   expected_manifest_sha256=self.m)
        self.assertEqual(c["published_at_unix"], T1 - 3600)
        self.assertEqual(a["anchor_proof_id"], fx.uuid_n(3))

    def test_same_second_tie_broken_by_log_index(self):
        ev = self._two_entry_evidence(T1, 999, T1, 1000)
        _, a = pool_custody.derive_custody_records(self.manifest, self.p, POOL_SIZE, ev, "v",
                                                   expected_manifest_sha256=self.m)
        self.assertEqual(a["anchor_log_index"], 999)

    # ---- raw evidence integrity -------------------------------------------
    def _anchor_for(self, ev):
        return dict(self.anchor, anchor_evidence_sha256=fx.sha(ev))

    def test_entry_for_other_artifact_rejected(self):
        ev = fx.make_evidence_bytes(self.m, [fx.make_rekor_entry(fx.uuid_n(1), "6" * 64, T1, 1000)])
        self.assertRejects(anchor=self._anchor_for(ev), evidence=ev)

    def test_unarchived_indexed_entry_rejected(self):
        ev = fx.make_evidence_bytes(self.m, [fx.make_rekor_entry(fx.uuid_n(1), self.m, T1, 1000)],
                                    index_uuids=[fx.uuid_n(1), fx.uuid_n(7)])
        self.assertRejects(anchor=self._anchor_for(ev), evidence=ev)

    def test_empty_index_rejected(self):
        ev = fx.make_evidence_bytes(self.m, [], index_uuids=[])
        self.assertRejects(anchor=self._anchor_for(ev), evidence=ev)

    def test_query_hash_mismatch_rejected(self):
        ev = fx.make_evidence_bytes(self.m, [fx.make_rekor_entry(fx.uuid_n(1), self.m, T1, 1000)],
                                    query_sha256="7" * 64)
        self.assertRejects(anchor=self._anchor_for(ev), evidence=ev)

    def test_entry_after_retrieval_rejected(self):
        ev = fx.make_evidence_bytes(self.m, [fx.make_rekor_entry(fx.uuid_n(1), self.m, T1, 1000)],
                                    retrieved_at=T1 - 1)
        self.assertRejects(anchor=self._anchor_for(ev), evidence=ev)

    def test_entry_without_signed_entry_timestamp_rejected(self):
        ev = fx.make_evidence_bytes(self.m, [fx.make_rekor_entry(fx.uuid_n(1), self.m, T1, 1000, with_set=False)])
        self.assertRejects(anchor=self._anchor_for(ev), evidence=ev)

    def test_unsupported_kind_rejected(self):
        ev = fx.make_evidence_bytes(self.m, [fx.make_rekor_entry(fx.uuid_n(1), self.m, T1, 1000, kind="intoto")])
        self.assertRejects(anchor=self._anchor_for(ev), evidence=ev)

    def test_rekord_kind_and_tree_prefixed_uuid_accepted(self):
        long_uuid = "24296fb24b8ad77a" + fx.uuid_n(1)
        ev = fx.make_evidence_bytes(self.m, [fx.make_rekor_entry(long_uuid, self.m, T1, 1000, kind="rekord")])
        c, a = pool_custody.derive_custody_records(self.manifest, self.p, POOL_SIZE, ev, "v",
                                                   expected_manifest_sha256=self.m)
        self.assertEqual(a["anchor_proof_id"], fx.uuid_n(1))
        self.assertEqual(self.validate(commitment=c, anchor=a, evidence=ev), T1)

    # ---- regression: retired v0.20 contract --------------------------------
    def test_v020_circular_fixture_not_accepted(self):
        v1_commitment = {"schema_version": "representation-lifting-pool-commitment/v1",
                         "pool_sha256": self.p, "pool_size": POOL_SIZE, "published_at_unix": T1}
        v1_anchor = {"schema_version": "representation-lifting-pool-anchor/v1", "pool_sha256": self.p,
                     "commitment_sha256": fx.sha(json.dumps(v1_commitment, sort_keys=True).encode()),
                     "anchor_type": "rekor", "anchor_proof_id": fx.uuid_n(1),
                     "verified_timestamp_unix": T1, "verifier": "x", "verification_status": "ANCHOR_VERIFIED"}
        self.assertRejects(commitment=v1_commitment)
        self.assertRejects(anchor=v1_anchor)

    # ---- fetch tool ---------------------------------------------------------
    def test_fetch_builds_parseable_evidence(self):
        m = self.m
        calls = []

        def fake_http(method, url, body):
            calls.append((method, url))
            if url.endswith("/api/v1/index/retrieve"):
                self.assertEqual(json.loads(body), {"hash": f"sha256:{m}"})
                return [fx.uuid_n(1)]
            return fx.make_rekor_entry(fx.uuid_n(1), m, T1, 1000)

        ev = fetch_rekor_evidence.build_evidence(self.manifest, http=fake_http, now=T1 + 60)
        entries = pool_custody.parse_rekor_evidence(pool_custody.canonical_json_bytes(ev), m)
        self.assertEqual(entries[0]["integrated_time"], T1)
        self.assertEqual(calls[0], ("POST", "https://rekor.sigstore.dev/api/v1/index/retrieve"))

    # ---- freeze gate 3a: parser against a REAL Rekor response ----------------
    @unittest.skipUnless(os.path.exists(REAL_FIXTURE),
                         "FREEZE GATE 3a PENDING: capture a real Rekor dry-run entry (dummy artifact) "
                         "into tests/fixtures/rekor_real_entry_dryrun.json before v0.21 freeze")
    def test_real_rekor_dryrun_entry_parses(self):
        with open(REAL_FIXTURE, "rb") as f:
            data = f.read()
        ev = json.loads(data)
        entries = pool_custody.parse_rekor_evidence(data, ev["query_sha256"])
        self.assertGreaterEqual(len(entries), 1)
        self.assertNotEqual(ev["query_sha256"], pool_custody.CARRIED_FORWARD_MANIFEST_SHA256,
                            "Dry run must use a dummy artifact, never the pool manifest.")


if __name__ == "__main__":
    unittest.main()
