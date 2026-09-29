#!/usr/bin/env python3
"""
tests/test_pool_custody.py
Adversarial tests for the v0.21 (r2) pre-randomness custody contract (tools/pool_custody.py).

Chain: signed freeze (T_COMMIT_UNIX, ratifier key) -> pool_commitment/v2 (anchor subject, contains the
freeze tag object id) -> ratifier SSH signature -> ONE Rekor `rekord` entry -> T1 <= T_COMMIT_UNIX;
drand round = compute_scheduled_round(T_COMMIT_UNIX). No Rekor index search anywhere.
"""

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

T_COMMIT = 1790000000
POOL_BYTES = ("case_id\tsource_name\n" + "".join(f"proofnet-{i:03d}\tname_{i}\n" for i in range(1, 11))).encode()
POOL_SIZE = 10
REAL_FIXTURE = os.path.join(TESTS_DIR, "fixtures", "rekor_real_entry_dryrun.json")


class TestPoolCustodyV2(unittest.TestCase):

    def setUp(self):
        self.manifest, self.evidence, self.commitment, self.anchor = fx.make_valid_custody(POOL_BYTES, POOL_SIZE, T_COMMIT)
        self.m = fx.sha(self.manifest)
        self.p = fx.sha(POOL_BYTES)

    def validate(self, manifest=None, pool_sha=None, pool_size=None, commitment=None, anchor=None,
                 evidence=None, expected=None, t_commit=T_COMMIT, key=fx.RATIFIER_KEY):
        return pool_custody.validate_pool_custody_v2(
            self.manifest if manifest is None else manifest,
            self.p if pool_sha is None else pool_sha,
            POOL_SIZE if pool_size is None else pool_size,
            self.commitment if commitment is None else commitment,
            self.anchor if anchor is None else anchor,
            self.evidence if evidence is None else evidence,
            expected_manifest_sha256=self.m if expected is None else expected,
            t_commit=t_commit, ratifier_key=key,
        )

    def assertRejects(self, **kw):
        with self.assertRaises(pool_custody.CustodyError):
            self.validate(**kw)

    def _subject(self, commitment):
        return fx.sha(pool_custody.canonical_json_bytes(commitment))

    def _rebind(self, commitment=None, entry_kw=None, requested_uuid=None, evidence_overrides=None):
        """Re-signs/re-uploads consistently for a (possibly mutated) commitment; returns (commitment, anchor, evidence)."""
        c = self.commitment if commitment is None else commitment
        kw = dict(uuid=fx.uuid_n(1), artifact_sha=self._subject(c), integrated_time=T_COMMIT - 3600, log_index=1000)
        kw.update(entry_kw or {})
        ev = fx.make_evidence_bytes(fx.make_rekor_entry(**kw), requested_uuid, **(evidence_overrides or {}))
        a = dict(self.anchor, subject_sha256=self._subject(c), anchor_evidence_sha256=fx.sha(ev),
                 rekor_uuid=kw["uuid"][-64:], rekor_log_index=kw["log_index"], integrated_time_unix=kw["integrated_time"])
        return c, a, ev

    # ---- valid chain -------------------------------------------------------
    def test_valid_chain_returns_t1(self):
        self.assertEqual(self.validate(), T_COMMIT - 3600)
        self.assertEqual(self.commitment["published_at_unix"], T_COMMIT)
        self.assertEqual(self.commitment["freeze_tag_object_id"], fx.FREEZE_TAG)
        self.assertNotIn("commitment_sha256", self.anchor)

    def test_anchor_exactly_at_deadline_accepted(self):
        c, a, ev = self._rebind(entry_kw={"integrated_time": T_COMMIT})
        self.assertEqual(self.validate(commitment=c, anchor=a, evidence=ev), T_COMMIT)

    # ---- deadline / precommitted round (anti-grinding) ---------------------
    def test_anchor_after_deadline_rejected(self):
        c, a, ev = self._rebind(entry_kw={"integrated_time": T_COMMIT + 1})
        self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_published_at_must_equal_frozen_t_commit(self):
        for t in (T_COMMIT - 1, T_COMMIT + 1, T_COMMIT - 3600):
            c, a, ev = self._rebind(commitment=dict(self.commitment, published_at_unix=t))
            self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_unset_freeze_parameters_fail_closed(self):
        with self.assertRaises(pool_custody.CustodyError):
            pool_custody.validate_pool_custody_v2(self.manifest, self.p, POOL_SIZE, self.commitment, self.anchor,
                                                  self.evidence, expected_manifest_sha256=self.m)
        with self.assertRaises(pool_custody.CustodyError):
            pool_custody.require_freeze_parameters(t_commit=None, ratifier_key=None) \
                if (pool_custody.T_COMMIT_UNIX is None or pool_custody.RATIFIER_SSH_PUBLIC_KEY is None) \
                else pool_custody.require_freeze_parameters(t_commit=0, ratifier_key="not-a-key")

    def test_non_integer_times(self):
        c, a, ev = self._rebind(commitment=dict(self.commitment, published_at_unix=float(T_COMMIT)))
        self.assertRejects(commitment=c, anchor=a, evidence=ev)
        self.assertRejects(anchor=dict(self.anchor, integrated_time_unix=True))

    # ---- subject binding ---------------------------------------------------
    def test_subject_hash_mismatch(self):
        self.assertRejects(anchor=dict(self.anchor, subject_sha256="9" * 64))

    def test_entry_for_other_artifact_rejected(self):
        c, a, ev = self._rebind(entry_kw={"artifact_sha": "6" * 64})
        self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_bare_manifest_anchor_is_not_a_subject_anchor(self):
        # A (pre-existing, third-party) Rekor entry for the bare manifest hash M is irrelevant.
        c, a, ev = self._rebind(entry_kw={"artifact_sha": self.m})
        self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_wrong_freeze_tag_changes_subject(self):
        c, _, _ = self._rebind(commitment=dict(self.commitment, freeze_tag_object_id="2e" * 20))
        self.assertRejects(commitment=c)   # anchor/evidence still bound to the original subject

    def test_malformed_freeze_tag_rejected(self):
        c, a, ev = self._rebind(commitment=dict(self.commitment, freeze_tag_object_id="HEAD"))
        self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_wrong_protocol_rejected(self):
        c, a, ev = self._rebind(commitment=dict(self.commitment, protocol="representation-lifting-s1/v0.20"))
        self.assertRejects(commitment=c, anchor=a, evidence=ev)

    # ---- signer binding ----------------------------------------------------
    def test_entry_signed_by_other_key_rejected(self):
        c, a, ev = self._rebind(entry_kw={"key_line": fx.OTHER_KEY})
        self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_receipt_names_other_key_rejected(self):
        self.assertRejects(anchor=dict(self.anchor, ratifier_ssh_public_key=fx.OTHER_KEY))

    def test_key_comment_ignored(self):
        c, a, ev = self._rebind(entry_kw={"key_line": fx.RATIFIER_KEY + " volmax.core@gmail.com"})
        self.assertEqual(self.validate(commitment=c, anchor=a, evidence=ev), T_COMMIT - 3600)

    def test_hashedrekord_and_non_ssh_rejected(self):
        for kw in ({"kind": "hashedrekord"}, {"kind": "intoto"}, {"sig_format": "x509"}, {"sig_format": "pgp"}):
            c, a, ev = self._rebind(entry_kw=kw)
            self.assertRejects(commitment=c, anchor=a, evidence=ev)

    # ---- manifest / pool binding (carried-forward pool) ---------------------
    def test_carried_forward_pin_rejects_any_other_manifest(self):
        with self.assertRaises(pool_custody.CustodyError):
            pool_custody.validate_pool_custody_v2(self.manifest, self.p, POOL_SIZE, self.commitment, self.anchor,
                                                  self.evidence, t_commit=T_COMMIT, ratifier_key=fx.RATIFIER_KEY)

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

    def test_manifest_sha_changed_in_commitment_or_anchor(self):
        c, a, ev = self._rebind(commitment=dict(self.commitment, manifest_sha256="3" * 64))
        self.assertRejects(commitment=c, anchor=a, evidence=ev)
        self.assertRejects(anchor=dict(self.anchor, manifest_sha256="3" * 64))

    def test_pool_sha_changed_in_commitment_or_anchor(self):
        c, a, ev = self._rebind(commitment=dict(self.commitment, pool_sha256="4" * 64))
        self.assertRejects(commitment=c, anchor=a, evidence=ev)
        self.assertRejects(anchor=dict(self.anchor, pool_sha256="4" * 64))

    def test_pool_size_changed(self):
        c, a, ev = self._rebind(commitment=dict(self.commitment, pool_size=POOL_SIZE + 1))
        self.assertRejects(commitment=c, anchor=a, evidence=ev)
        self.assertRejects(pool_size=POOL_SIZE - 1)

    # ---- receipt contract --------------------------------------------------
    def test_status_not_verified(self):
        self.assertRejects(anchor=dict(self.anchor, verification_status="PENDING"))

    def test_non_rekor_anchor_types_inadmissible(self):
        for t in ("git_push", "opentimestamps", "rfc3161"):
            self.assertRejects(anchor=dict(self.anchor, anchor_type=t))

    def test_other_rekor_url(self):
        self.assertRejects(anchor=dict(self.anchor, rekor_url="https://rekor.example.org"))

    def test_empty_verifier(self):
        self.assertRejects(anchor=dict(self.anchor, verifier="  "))

    def test_evidence_hash_mismatch(self):
        self.assertRejects(anchor=dict(self.anchor, anchor_evidence_sha256="5" * 64))

    def test_receipt_uuid_index_time_must_match_entry(self):
        self.assertRejects(anchor=dict(self.anchor, rekor_uuid=fx.uuid_n(9)))
        self.assertRejects(anchor=dict(self.anchor, rekor_log_index=999))
        self.assertRejects(anchor=dict(self.anchor, integrated_time_unix=T_COMMIT - 3599))

    def test_reintroduced_commitment_sha256_field_rejected(self):
        self.assertRejects(anchor=dict(self.anchor, commitment_sha256="0" * 64))

    def test_extra_commitment_field_rejected(self):
        self.assertRejects(commitment=dict(self.commitment, note="x"))

    # ---- raw evidence integrity -------------------------------------------
    def test_archived_entry_must_be_requested_uuid(self):
        c, a, ev = self._rebind(requested_uuid=fx.uuid_n(7))
        self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_tree_prefixed_uuid_accepted(self):
        c, a, ev = self._rebind(entry_kw={"uuid": "24296fb24b8ad77a" + fx.uuid_n(1)})
        self.assertEqual(self.validate(commitment=c, anchor=a, evidence=ev), T_COMMIT - 3600)

    def test_missing_signed_entry_timestamp_rejected(self):
        c, a, ev = self._rebind(entry_kw={"with_set": False})
        self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_inclusion_proof_consistency(self):
        # {"logIndex": 999} is intentionally absent: proof.logIndex may differ from entry.logIndex
        # (Rekor v1 sharding; confirmed by Gate-3a real-Rekor fixture).
        for po in ({"treeSize": 1000}, {"treeSize": 10}, {"rootHash": "zz"}, {"hashes": None}):
            c, a, ev = self._rebind(entry_kw={"proof_overrides": po})
            self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_sharded_proof_log_index_accepted(self):
        """proof.logIndex may differ from the global entry logIndex (Rekor v1 sharding)."""
        # entry logIndex = 1000; proof logIndex = 500 (different shard position) — must be accepted
        c, a, ev = self._rebind(entry_kw={"proof_overrides": {"logIndex": 500, "treeSize": 501}})
        self.assertEqual(self.validate(commitment=c, anchor=a, evidence=ev), T_COMMIT - 3600)

    def test_proof_log_index_negative_rejected(self):
        for bad_idx in (-1, -999):
            c, a, ev = self._rebind(entry_kw={"proof_overrides": {"logIndex": bad_idx, "treeSize": 5}})
            self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_proof_tree_size_not_greater_than_proof_log_index_rejected(self):
        # treeSize must be strictly greater than proof.logIndex (not entry.logIndex)
        for po in ({"logIndex": 100, "treeSize": 100},   # equal — reject
                   {"logIndex": 100, "treeSize": 99},    # less — reject
                   {"logIndex": 100, "treeSize": 101}):  # strictly greater — accept
            c, a, ev = self._rebind(entry_kw={"proof_overrides": po})
            if po["treeSize"] > po["logIndex"]:
                self.assertEqual(self.validate(commitment=c, anchor=a, evidence=ev), T_COMMIT - 3600)
            else:
                self.assertRejects(commitment=c, anchor=a, evidence=ev)

    def test_no_clock_skew_rejection(self):
        # retrieved_at_unix is informational: a local clock behind Rekor must not fail custody.
        c, a, ev = self._rebind(evidence_overrides={"retrieved_at_unix": 1})
        self.assertEqual(self.validate(commitment=c, anchor=a, evidence=ev), T_COMMIT - 3600)

    def test_index_search_evidence_schema_not_admissible(self):
        ev = pool_custody.canonical_json_bytes({
            "schema_version": "representation-lifting-rekor-evidence/v1", "rekor_url": pool_custody.REKOR_LOG_URL,
            "query_sha256": self.m, "retrieved_at_unix": 1, "index_retrieve_response": [fx.uuid_n(1)],
            "log_entries": [fx.make_rekor_entry(fx.uuid_n(1), self._subject(self.commitment), T_COMMIT - 3600, 1000)]})
        self.assertRejects(anchor=dict(self.anchor, anchor_evidence_sha256=fx.sha(ev)), evidence=ev)

    # ---- regression: retired v0.20 contract --------------------------------
    def test_v020_circular_fixture_not_accepted(self):
        v1_commitment = {"schema_version": "representation-lifting-pool-commitment/v1",
                         "pool_sha256": self.p, "pool_size": POOL_SIZE, "published_at_unix": T_COMMIT}
        v1_anchor = {"schema_version": "representation-lifting-pool-anchor/v1", "pool_sha256": self.p,
                     "commitment_sha256": fx.sha(json.dumps(v1_commitment, sort_keys=True).encode()),
                     "anchor_type": "rekor", "anchor_proof_id": fx.uuid_n(1),
                     "verified_timestamp_unix": T_COMMIT, "verifier": "x", "verification_status": "ANCHOR_VERIFIED"}
        self.assertRejects(commitment=v1_commitment)
        self.assertRejects(anchor=v1_anchor)

    # ---- tools ---------------------------------------------------------------
    def test_fetch_uses_single_get_and_no_search(self):
        calls = []

        def fake_get(url):
            calls.append(url)
            return fx.make_rekor_entry(fx.uuid_n(1), self._subject(self.commitment), T_COMMIT - 3600, 1000)

        ev = fetch_rekor_evidence.build_evidence(fx.uuid_n(1), get=fake_get, now=T_COMMIT)
        self.assertEqual(calls, [f"https://rekor.sigstore.dev/api/v1/log/entries/{fx.uuid_n(1)}"])
        entry = pool_custody.parse_rekor_entry_evidence(pool_custody.canonical_json_bytes(ev),
                                                        self._subject(self.commitment), fx.RATIFIER_KEY)
        self.assertEqual(entry["integrated_time"], T_COMMIT - 3600)

    def test_no_index_search_code_path_exists(self):
        for rel in ("tools/pool_custody.py", "tools/fetch_rekor_evidence.py", "tools/derive_pool_commitment.py"):
            with open(os.path.join(PROJECT_ROOT, rel), encoding="utf-8") as f:
                src = f.read()
            self.assertNotIn('"/api/v1/index', src, rel)
            self.assertNotIn("index/retrieve\"", src, rel)

    # ---- freeze gates ---------------------------------------------------------
    @unittest.skipUnless(pool_custody.T_COMMIT_UNIX is not None and pool_custody.RATIFIER_SSH_PUBLIC_KEY is not None,
                         "FREEZE GATE PENDING: set T_COMMIT_UNIX and RATIFIER_SSH_PUBLIC_KEY in tools/pool_custody.py")
    def test_freeze_parameters_set_and_well_formed(self):
        t, k = pool_custody.require_freeze_parameters()
        self.assertGreater(t, 1790000000)
        self.assertEqual(len(pool_custody.ssh_key_identity(k)), 2)

    @unittest.skipUnless(os.path.exists(REAL_FIXTURE),
                         "FREEZE GATE 3a PENDING: capture a real Rekor dry-run entry (dummy subject, ratifier key) "
                         "into tests/fixtures/rekor_real_entry_dryrun.json (+ .meta.json) before v0.21 freeze")
    def test_real_rekor_dryrun_entry_parses(self):
        with open(REAL_FIXTURE, "rb") as f:
            evidence = f.read()
        with open(REAL_FIXTURE.replace(".json", ".meta.json"), encoding="utf-8") as f:
            meta = json.load(f)   # {"subject_sha256": <sha256 of dummy subject>, "ratifier_ssh_public_key": "<type> <blob>"}
        self.assertNotEqual(meta["subject_sha256"], pool_custody.CARRIED_FORWARD_MANIFEST_SHA256)
        entry = pool_custody.parse_rekor_entry_evidence(evidence, meta["subject_sha256"], meta["ratifier_ssh_public_key"])
        self.assertGreater(entry["integrated_time"], 1790000000)
        if pool_custody.RATIFIER_SSH_PUBLIC_KEY is not None:
            self.assertEqual(pool_custody.ssh_key_identity(meta["ratifier_ssh_public_key"]),
                             pool_custody.ssh_key_identity(pool_custody.RATIFIER_SSH_PUBLIC_KEY),
                             "Dry run must use the same ratifier key as the real anchor.")

if __name__ == "__main__":
    unittest.main()
