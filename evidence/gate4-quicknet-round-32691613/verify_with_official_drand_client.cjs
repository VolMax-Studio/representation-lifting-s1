const fs = require('fs');
const crypto = require('crypto');
const { quicknetClient, fetchBeacon } = require('/tmp/rls1-drand-client-1.4.2/node_modules/drand-client');

(async () => {
  const round = 32691613;
  const archived = JSON.parse(fs.readFileSync('custody/gate4-quicknet-round-32691613/drand_round_api.raw.json', 'utf8'));
  const client = quicknetClient();
  const verified = await fetchBeacon(client, round); // official client performs chain pin + BLS verification
  if (verified.round !== round) throw new Error(`round mismatch ${verified.round}`);
  if (verified.signature !== archived.signature) throw new Error('verified signature != archived primary response');
  if (verified.randomness !== archived.randomness) throw new Error('verified randomness != archived primary response');
  const recomputed = crypto.createHash('sha256').update(Buffer.from(verified.signature, 'hex')).digest('hex');
  if (recomputed !== verified.randomness) throw new Error('SHA256(signature) != randomness');
  if (Buffer.from(verified.signature, 'hex').length !== 48) throw new Error('signature length != 48 bytes');
  console.log(JSON.stringify({
    verification_status: 'BLS_VERIFIED',
    verifier: 'official drand/drand-client npm package',
    verifier_version: '1.4.2',
    verifier_git_tag_commit: 'ef8c9260294f8699b5e8c27a6b764f8f0d768bea',
    round: verified.round,
    signature_hex: verified.signature,
    signature_length_bytes: Buffer.from(verified.signature, 'hex').length,
    randomness_hex: verified.randomness,
    quicknet_chain_hash: '52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971',
    public_key_hex: '83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a',
    scheme_id: 'bls-unchained-g1-rfc9380'
  }, null, 2));
})().catch(e => { console.error(e && e.stack || e); process.exit(1); });
