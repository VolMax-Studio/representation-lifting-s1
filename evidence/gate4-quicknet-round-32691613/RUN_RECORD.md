# Gate 4 — Quicknet Blind Selection

Protocol: representation-lifting-s1/v0.21

Precommitted Quicknet round:
32691613

Scheduled publication time:
2026-10-01 18:10:03 UTC

Primary raw relay:
api.drand.sh
SHA-256: 5850719c9c86648924058b89395211e8a41cd93902e489a5a57f7f00317d233c

Independent relay:
drand.cloudflare.com
SHA-256: f4529951512e05be03c4c06beffd59acf353c84b09b88049e449ed4f677cebd0

Canonical relay payloads agree on round, signature and randomness.

Quicknet signature:
818caf5437ecdbfc89f9c2ccfd831d1d15fa2b4e41707cdfbbbff839dad1fae24193eef9089bdd85d187c76600a27a33

Randomness = SHA256(signature):
3d8063ce46d40438e9f24b2a3a927005d38d8a433edcea118a21922c5e1832ab

External BLS verifier:
official drand/drand-client npm package v1.4.2
Git tag commit: ef8c9260294f8699b5e8c27a6b764f8f0d768bea
Package tarball SHA-256: 81de34afba38520b461152bf032cfb5139bb6ced205bf9f50bc8216fdc394eef
Verifier CJS bundle SHA-256: 45cb65d533cc7e8527e9bba92df875c066511c3d6286adc7fcb293f0d03c7566
Verification: BLS_VERIFIED / exit code 0

Frozen selector SHA-256:
88fe461dc686ad40ab853926834fdbc7af236709df1a8758aa5cd46c3e36a9c8

Frozen pool SHA-256:
398ddcb3d9e915edce681c0d59138950177d7eb096200795f927741fb9743212
Pool size: 362

Selected indices, in order:
105, 80, 261

Selected blind cases, in order:
- index 105: proofnet-108 — Munkres_exercise_13_5a
- index 80: proofnet-083 — Herstein_exercise_2_11_22
- index 261: proofnet-267 — Herstein_exercise_2_11_7

Frozen analyzer full custody replay:
PASS

No theorem-solving output was used to choose or alter the selected cases.

## Post-review append-only notes

Independent Gate 4 review returned `SURVIVES-REVIEW (with limitations)`.

1. The previously external run2 `POOL.tsv` and `pool_bundle_manifest.json` have now been published byte-for-byte under `evidence/pool-build-local-002/`, together with the run2 exclusion tables, report, execution log, and exit code. Their SHA-256 values remain `398ddcb3d9e915edce681c0d59138950177d7eb096200795f927741fb9743212` and `aef332f69fb7bf70c0032dc05a383f8fea0085fecbd2ba22281c48ef4c36f7f6` respectively.

2. Before adopting `drand/drand-client` v1.4.2 as the normative Gate 4 verifier, an attempted build of the preregistration example `drand v1.5.8` was abandoned after network/DNS failures while fetching Go dependencies. It produced no verifier binary and did not contribute to the beacon verdict, randomness, selection, or case mapping.

3. The archived `verify_with_official_drand_client.cjs` is an execution transcript helper, not a portable replay script: it references the original `custody/gate4-quicknet-round-32691613/` path, prints the pinned Quicknet hash/public key as literals for its output record, and fetched the beacon live before comparing it with the archived primary relay copy. The official package bundle independently pins the same Quicknet chain hash and public key and performs beacon verification; the review treated these helper-script details as non-blocking.
