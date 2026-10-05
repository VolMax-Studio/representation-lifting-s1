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

The production default is an automated command adapter backed by the installed
Codex CLI and its existing ChatGPT subscription authentication. It requires no
direct OpenAI or Anthropic API key and creates per-turn runtime identity evidence
from Codex's `session_meta` and `turn_context` records. The command adapter uses
the same JSON contract as every other transport. Credentials remain outside the
repository. Direct Anthropic and OpenAI APIs are not used by this path. The CLI
runs with user configuration ignored, disables plugins/apps, and removes the
desktop app-tools pipe so installed plugins and MCP servers are not exposed;
native web search and the shell tool are also explicitly disabled. Any model
tool event is a fail-closed transport error, preserving the frozen no-tool
inference regime.
Branches not instantiated because of the frozen harness's preregistered
control flow receive custody-only `NOT_EXECUTED_FROZEN_CONTROL_FLOW` seals
before the block index is written. Thus all 29 registered branch positions are
cryptographically accounted for without fabricating a model response.

The operator-courier adapter is retained only in
`execution/manual-relay-debug.json` as an explicit fallback for debugging. It is
not the production default and a run which used it cannot be silently continued
as an automated admissible execution.

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

The default command performs every turn without operator courier steps. After
the block seals, run `--audit-custody` with the same arguments before opening
outcomes.
