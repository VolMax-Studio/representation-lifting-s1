# Provider-Neutral Execution Architecture

The audit core is provider-neutral. Its trust path consists of the frozen
scientific harness, request/response bytes, hashes, custody records, sealed
transcripts, deterministic replay, pre-outcome audit, and verdict semantics.
No model provider, product, subscription, billing account, or availability
window is a trust root.

`tools/execution_adapter.py` defines the stable boundary:

- exact system prompt and message bytes;
- a declared model identity for the execution instance;
- response bytes when delivery occurred;
- declared and observed model identity;
- `DELIVERED`, `NOT_DELIVERED`, or `AMBIGUOUS` delivery status;
- start/completion timestamps and transport metadata;
- SHA-256 custody for every request, result, and delivered response.

The default adapter is an operator-courier manual relay. It works with an
available web surface and requires no personal API billing. A command adapter
supports a local model or an operator-selected provider CLI using the same JSON
contract. Credentials, when a chosen surface needs them, are supplied by the
operator outside the repository. Direct Anthropic and OpenAI APIs are optional,
not dependencies.

Gate 5 now validates the selected adapter contract, the custody guarantees, and
the bound scientific files. It deliberately performs no provider call and no
provider-availability check. The chosen model is bound to its execution receipt,
not to audit validity.

Historical A1 r8/r9, `INFRA_RECOVERY_01`, and A2/`EXECUTION_02` evidence remains
unaltered. A2 is a historical, superseded Claude-specific execution instance;
its 7 October availability window is not a project-wide obligation.

## Start a provider-neutral execution

Contract Gate 5 can run immediately:

```bash
python3 tools/provider_neutral_execution.py \
  --gate5 \
  --execution-id execution-03 \
  --model-id MODEL_ID_SHOWN_BY_THE_CHOSEN_SURFACE \
  --run-root execution-runs/execution-03
```

Then launch the sealed block with the same identity and run root:

```bash
python3 tools/provider_neutral_execution.py \
  --execute-block \
  --execution-id execution-03 \
  --model-id MODEL_ID_SHOWN_BY_THE_CHOSEN_SURFACE \
  --run-root execution-runs/execution-03
```

For each turn, copy the generated `relay_input.txt` verbatim to the chosen
surface, save the complete response to `incoming_response.txt`, and record the
surface-displayed identity in `incoming_identity.json`. After the block seals,
run `--audit-custody` with the same arguments before opening outcomes.
