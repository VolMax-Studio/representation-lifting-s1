## Amendment 0.21-A1 r5: Pre-Execution Surface Amendment

**Status:** CANDIDATE — requires pre-ratification surface reconnaissance,
bridge implementation, candidate commit, independent review, and signed
annotated tag ratification BEFORE Gate 5, and BEFORE any executor sees blind
theorem content  
**Amendment class:** Execution-surface  
**Trigger:** The principal investigator does not hold funded API credits on
either the Anthropic (`api.anthropic.com`) or OpenAI (`api.openai.com`) direct
billing endpoints. The frozen v0.21 `executor_config.json` and
`smoke_test_executor.py` require direct paid API access with
`ANTHROPIC_API_KEY` / `OPENAI_API_KEY`, making Gate 5 and all subsequent
execution impossible under the frozen transport specification.  
**Date:** 2026-10-02  
**Author:** Ivan Nestorov (principal investigator)  

---

### A1.1 Nature and Scope of This Amendment

This is an **execution-surface amendment**. It changes four execution-layer
mechanisms:

1. **Transport:** The mechanism by which a prompt reaches the model and a
   response is returned (direct API HTTP POST → subscription-surface
   invocation via `tools/a1_surface_bridge.py`).
2. **Model identity evidence:** The method of verifying which model served a
   request (API JSON `body["model"]` → provider-displayed surface label
   checked against a frozen allowed-label set).
3. **Generation-control enforcement:** The experimenter's ability to set and
   verify sampling parameters and inference controls (API request body fields
   → surface-exposed settings, which may be absent or opaque).
4. **Transcript and operator mechanics:** The method of capturing prompts,
   responses, and timing (programmatic JSON extraction → hash-addressed
   canonical artifacts with semi-manual faithful-courier relay).

These changes may affect realized model behavior: a subscription surface
interposes provider-controlled runtime context (system prompt wrappers, tool
policies, output formatting) that the experimenter cannot inspect, suppress,
or normalize, and generation controls may not be settable to their
API-specified values. A1 preserves equality of investigator-controlled
settings within each model. It does not establish equality of opaque
provider-controlled backend state across sessions or time; this is a
limitation intrinsic to subscription-surface execution, documented as such
in the study report.

**What this amendment does NOT change:**

- Scientific hypotheses H0, H1, H2 — their definitions, falsification
  criteria, and evaluation logic
- Candidate pool, SHA-256 bindings, size (N = 362), anchor chain
- drand round (r = 32691613), randomness, selected sample
- S/D/L role definitions, role-transition state machine, branch sequencing
- Protocol-defined system prompts and neutral prompt text
- Turn budgets (S: 15, D: 30, L: 30) and wallclock budgets (S: 3600s,
  D/L: 10800s)
- primary_model_id: "claude-sonnet-4-6" and
  replication_model_id: "gpt-5.6-sol"
- Primary/replication role assignment
- Token metric (tools/count_lean_tokens.py)
- Scoring, aggregation, control veto, verdict governance
- Procedural branch-output non-persistence isolation (enforcement mechanism
  adapted in section A1.7; semantic guarantee identical)
- Negative control decision matrix
- Calibration cumulative-compilation rule (T1 prefix -> T2)
- tools/analyze.py scoring and verdict logic
- All custody, anchor, and selection replay logic
- tools/executor_config.json (frozen, unmodified; see section A1.15)
- tools/executor_harness.py (frozen, unmodified; see section A1.8)

---

### A1.2 Pinned Execution Surfaces (No Fallback)

Each execution surface is pinned. No fallback to an alternative surface is
permitted without a separate amendment carrying its own independent review
and signed-tag ratification.

| Role | Pinned Surface | Auth | Model Selection |
|---|---|---|---|
| Primary | **Claude Code CLI** (`claude` command) | Anthropic subscription (OAuth via `claude login`) | `--model claude-sonnet-4-6` flag |
| Replication | **ChatGPT web interface** (`chatgpt.com`) | OpenAI subscription (browser session) | Model picker selection per frozen allowed-label set (section A1.5) |

**Prohibited fallbacks (each requires a separate amendment):**
- Primary: claude.ai web chat, Claude mobile app, Claude desktop chat mode,
  any third-party Claude API proxy or gateway
- Replication: ChatGPT mobile app, ChatGPT desktop app, OpenAI Codex, OpenAI
  Playground, any third-party OpenAI API proxy or gateway

---

### A1.3 Pre-Ratification Surface Reconnaissance

Before the candidate commit, and before any inference prompt is sent or any
blind theorem content is visible, the principal investigator conducts a
**surface reconnaissance** for each pinned surface. This phase sends NO
inference prompts and sees NO blind content. Its sole purpose is to establish
the exact surface configuration that will be frozen in the A1 transport
config.

**A1.3.1 Reconnaissance procedure (per surface):**

1. Open the pinned surface and authenticate.
2. Record the exact surface version:
   - Claude Code: output of `claude --version`. Record the full version
     string. If feasible, record the SHA-256 of the `claude` binary.
   - ChatGPT web: record the visible build/version identifier or access date
     as **observed metadata**. Web builds may change without investigator
     action; this is observed at reconnaissance and again at Gate 5, but is
     not a strict pass/fail criterion (see section A1.16).
3. Verify the pinned model identifier is accepted by the surface:
   - Claude Code: confirm that `claude --model claude-sonnet-4-6` is accepted
     as a valid model configuration by the CLI (e.g., the CLI does not reject
     the identifier with an error). This establishes only that the CLI
     recognizes the identifier; actual model availability and routing are
     verified at Gate 5 when an inference prompt is sent.
   - ChatGPT: confirm the model picker lists a label for the pinned model.
4. Record the **exact provider model label(s)** displayed by the surface for
   the pinned model. Capture screenshot or terminal output.
5. Enumerate **all user-selectable inference controls** the surface exposes.
   For each, record: control name, available values/range, exact value to pin.
6. Enumerate **all tool/capability controls** the surface exposes. For each:
   whether disableable; if so pin to disabled; if not record
   TOOL_CAPABILITY_EXPOSED_BUT_INVOCATION_PROHIBITED (see section A1.6).
7. Determine the **system-prompt relay capability** of each surface:
   - Claude Code CLI: does the surface accept a caller-controlled system
     message (e.g., --system-prompt flag)? Record the mechanism.
   - ChatGPT web: does NOT support caller-controlled system messages separate
     from user content. Record DEGRADED_SYSTEM_ROLE_FLATTENED_TO_USER_CONTENT
     and freeze the exact flattening scheme (section A1.8.4).
8. For Claude Code: verify a sanitized working directory with no CLAUDE.md,
   .claude/, .mcp.json, or equivalent config is achievable. Record exact flags.

**A1.3.2 Outputs frozen pre-ratification:**

The reconnaissance produces a complete a1_transport_config.json (section A1.15)
with ALL fields populated, plus confirms feasibility of the surface bridge
(section A1.8). Both are committed as part of the candidate commit and reviewed
before ratification. After the signed tag, no configuration field may be
changed without a new amendment.

---

### A1.4 Allowed Model Label Sets

During pre-ratification reconnaissance (section A1.3), the investigator records
the exact model labels displayed by each surface. These are frozen into an
**exact allowed-label set** per surface in a1_transport_config.json. After
ratification, the model label displayed during Gate 5 and execution MUST be a
member of the frozen allowed-label set. Any label not in the set triggers
MODEL_IDENTITY_FAIL (section A1.10.2). No human judgment of equivalence is
required or permitted.

---

### A1.5 Inference-Control Pinning

All user-selectable inference controls exposed by the subscription surface are
identified during pre-ratification reconnaissance (section A1.3), pinned to
fixed values, and frozen in a1_transport_config.json before the candidate
commit. The same settings MUST be used for every S, D, and L run of a given
model.

**If a control is exposed by the surface but not pinned in the frozen config:
execution is BLOCKED.**

| Control | Frozen API value | A1 pin rule |
|---|---|---|
| Temperature | 0.0 | Set to 0 / lowest / greedy if exposed. If not exposed: DEGRADED_NO_TEMPERATURE_CONTROL. |
| Max output tokens | 8192 | Set to 8192 if exposed. If not exposed: DEGRADED_SURFACE_DEFAULT_MAX_TOKENS. |
| Reasoning / thinking effort | N/A (not in frozen spec) | If exposed: pin to a single fixed value and record. |
| Any other control | N/A | Identify, pin, record. |

**Generation-control degradation:** If a surface does not expose a control that
the frozen API spec sets, this constitutes a generation-control degradation
introduced by A1 — a change in experimental conditions that may affect the
output distribution. A1 preserves equality of investigator-controlled settings
within each model; it does not guarantee opaque provider-controlled backend
behavior is identical across sessions. The study report MUST discuss all
generation-control degradations as methodological limitations.

Gate 5 (section A1.11) verifies the previously frozen configuration. It does
not choose, discover, or populate any configuration value.

---

### A1.6 Tool-Capability Isolation

**Distinction — exposure vs. invocation:**

- **Tool exposure:** The surface presents tool definitions or capabilities to
  the model. The model is aware tools exist.
- **Tool invocation:** The model or surface actually executes a tool during a run.

**Rules:**

1. **Tool invocation is prohibited.** No provider-native tool may be invoked
   during any S, D, or L run.

2. **Tool exposure — disableable:** Pin to disabled during reconnaissance.

3. **Tool exposure — not disableable:** Record
   TOOL_CAPABILITY_EXPOSED_BUT_INVOCATION_PROHIBITED pre-ratification. This
   constitutes an additional execution-surface degradation: mere exposure to
   tool definitions may affect model behavior even without invocation. Both
   branches of a given model share this degradation. The study report MUST
   discuss it.

4. **Invocation halt:** If any tool is actually invoked during a run, this is
   a protocol deviation. Halt immediately and classify as
   NOT_EVALUABLE_INFRA (UNAUTHORIZED_TOOL_INVOCATION).

**Claude Code CLI:** Sanitized working directory containing ONLY role-authorized
files (section A1.7.2). No CLAUDE.md, .claude/, .mcp.json, project config,
hooks, or MCP definitions. Use --tools "" and --safe-mode as determined during
reconnaissance. Record exact invocation command.

**ChatGPT web:** Fresh chat, non-Project context. Memory, conversation history,
custom instructions disabled to the strongest degree the surface allows. Web
browsing, code interpreter, and other tools disabled via toggles if available.

**Prohibition scope:** This section prohibits provider-native tools and
inherited/project/user custom instructions. It does NOT prohibit the
experiment's own protocol-defined system prompt (section A1.8.3), which is a
frozen experimental artifact relayed through the bridge.

---

### A1.7 Context Isolation, Blind Visibility, and Branch Evidence Sealing

**A1.7.1 Fresh context per S/D/L run:**

Every role invocation begins in a fresh context with zero carry-over.
- Claude Code CLI: new process in a freshly prepared sanitized directory. No
  --continue, --resume, or session-persistence.
- ChatGPT web: new conversation. Not a continuation, not within a Project,
  not in any context carrying cross-chat memory.

**A1.7.2 Authorized inputs per role:**

| Role | Authorized visible inputs |
|---|---|
| S (Search) | Target theorem statement for the CURRENT problem. Admissibility manifest. Protocol-defined system prompt for Role S. Neutral prompt. |
| D (Direct) | Target theorem statement for the CURRENT problem. Admissibility manifest. Protocol-defined system prompt for Role D. Neutral prompt. Zero access to S output or stub. |
| L (Lifted) | Target theorem statement for the CURRENT problem. Admissibility manifest. Frozen stub from S (current problem only). Protocol-defined system prompt for Role L. Neutral prompt. Zero access to D output. |

**Prohibited visibility (all roles):**
- Theorem statements, stubs, or proof code for OTHER selected blind problems
- Gate 4 selection evidence beyond the current problem's identity
- Sealed transcripts, outputs, or receipts from another role's execution
- Any part of the repository not listed as authorized input above

**A1.7.3 Branch evidence sealing:**

Upon completion of each branch (S, D, or L):

1. The complete verbatim transcript (all hash-addressed request_N.json,
   surface_input_N.txt, and response_N.txt artifacts per section A1.8) is
   assembled into a sealed evidence file under evidence/ with a filename
   encoding model, role, problem-id, and timestamp.
2. SHA-256 of the sealed file is computed and recorded BEFORE the next branch begins.
3. The sealed file is NOT opened, read, or made accessible to the executor
   context of any subsequent role.
4. Joint receipts are assembled only after ALL branches for a given problem
   complete, by reading the individually sealed transcripts.

---

### A1.8 Surface Bridge and Canonical Request/Response Artifacts

The frozen tools/executor_harness.py is NOT modified. It continues to call
call_model_api_with_resilience() as its inference boundary. A1 introduces a
**surface bridge** (tools/a1_surface_bridge.py) that intercepts this
boundary, translates the API call into a subscription-surface relay, and
returns the response to the unchanged state machine.

**A1.8.1 Bridge architecture:**

The frozen harness is the SOLE AUTHORITY that:
- Constructs protocol-defined system prompts and message sequences
- Parses model responses
- Invokes Lean verification
- Constructs compiler feedback turns
- Advances the state machine
- Increments turn counters and enforces budgets
- Generates the next turn's content
- Emits execution receipts

The bridge and the human operator MUST NOT perform any of these functions.

**A1.8.2 Canonical request envelope (request_N.json):**

```json
{
  "schema_version": "representation-lifting-a1-request/v1",
  "turn_number": "N",
  "model_id": "<pinned_model_id>",
  "system_prompt": "<exact protocol-defined system prompt for this role>",
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ],
  "timestamp_utc": "<ISO 8601>",
  "sha256": "<self-hash after all other fields populated>"
}
```

**A1.8.3 Protocol-defined system prompt:**

The frozen harness constructs a role-specific system prompt for each
invocation. This is a frozen experimental artifact and MUST be relayed to the
model. What section A1.6 prohibits is inherited/project/user custom instructions
— the provider's or user's persistent configuration NOT part of the frozen
protocol. The protocol-defined system prompt is explicitly authorized.

**A1.8.4 Surface relay serialization:**

The surface relay artifact (surface_input_N.txt) is the exact text sent to
the subscription surface.

**Surfaces with caller-controlled system-message semantics** (e.g., Claude Code
CLI with --system-prompt flag):
- system_prompt is passed via the surface's system-message mechanism.
- surface_input_N.txt contains only the current user-turn content.
- Record: system_role_handling: "NATIVE_SYSTEM_MESSAGE"

**Surfaces WITHOUT caller-controlled system-message semantics** (e.g., ChatGPT web):
- Record: system_role_handling: "DEGRADED_SYSTEM_ROLE_FLATTENED_TO_USER_CONTENT"
- Deterministic flattening scheme (frozen pre-ratification):

```
=== PROTOCOL SYSTEM INSTRUCTIONS (DO NOT MODIFY) ===

<exact system_prompt text>

=== END PROTOCOL SYSTEM INSTRUCTIONS ===

=== CONVERSATION HISTORY ===

[Turn N - USER]:
<content>

[Turn N - ASSISTANT]:
<content>

=== END CONVERSATION HISTORY ===

=== CURRENT REQUEST ===

<current user-turn content>
```

The exact flattening scheme is frozen in a1_transport_config.json.

**A1.8.5 Bridge implementation requirements:**

tools/a1_surface_bridge.py MUST:
- Accept the exact (model_id, messages, system_prompt, remaining_wallclock,
  config, transcript) signature of call_model_api_with_resilience()
- Return the exact (response_text, stop_reason, is_infra_failure) tuple
- Emit request_N.json and surface_input_N.txt with SHA-256 before relay
- Emit response_N.txt with SHA-256 after relay
- Enforce request timeout capped by remaining_wallclock
- NOT parse response content, NOT invoke Lean, NOT construct feedback,
  NOT advance state machine, NOT generate prompt content

The bridge implementation SHA-256 is frozen in a1_transport_config.json.

---

### A1.9 Bridge Test Contract

The candidate commit includes tests/test_a1_surface_bridge.py demonstrating:

1. Interface compatibility — bridge accepts and returns exact
   call_model_api_with_resilience signature; frozen harness exercises correctly.
2. Canonical request fidelity — request_N.json faithfully records system_prompt
   and messages unchanged; SHA-256 is correct.
3. Surface input native system — for CLI surfaces, surface_input_N.txt contains
   only user-turn content.
4. Surface input flattened — for ChatGPT-type surfaces, deterministic flattening
   with frozen delimiters.
5. Flattening determinism — identical input produces byte-identical output.
6. Response artifact emission — response_N.txt written with correct SHA-256.
7. No control-logic leakage — bridge does not invoke Lean, parse content beyond
   raw text, modify turn counts, or generate prompt content.
8. Timeout enforcement — bridge returns is_infra_failure=True on pre-response timeout.
9. Transport failure classification — connection/timeout failures retryable;
   delivered responses (including empty) not retryable.
10. Multi-turn history serialization.
11. Full mock execution — 3-turn mock run; turn count, wallclock, receipt fields,
    Lean invocation identical to frozen harness with direct API.
12. Frozen harness SHA unchanged.
13. Frozen executor config SHA unchanged.

---

### A1.10 Model Identity Evidence

**A1.10.1 Evidence standard under A1:**

| Property | API Transport (v0.21) | Subscription Surface (A1) |
|---|---|---|
| Machine-readable model ID per response | YES (body["model"]) | NO |
| Programmatic exact-match verification | YES (harness code) | NO (human check against frozen label set) |
| Provider names served model | YES (per-response JSON) | PARTIAL (session-level UI label) |
| Silent substitution detectable | YES | NO |

**A1.10.2 Fail-closed triggers:**

Execution halts with MODEL_IDENTITY_FAIL if:
- Provider model label is **absent**
- Provider model label **changes** during a session
- Provider model label is **not a member** of the frozen allowed-label set

These are objective set-membership criteria. No subjective assessment is used.

**A1.10.3 Per-session captures:**

Screenshot or terminal output of the active model label at session start. For
sessions exceeding 30 minutes, at least one additional mid-session capture.

---

### A1.11 Gate 5: Neutral Pre-Execution Surface Verification

Gate 5 replaces tools/smoke_test_executor.py. Executed AFTER signed tag
ratification and BEFORE any executor sees blind content. Gate 5 VERIFIES the
configuration frozen during reconnaissance. It does not choose, discover, or
populate any value.

**A1.11.1 Procedure (per surface):**

1. Open surface, authenticate, apply ALL frozen settings from a1_transport_config.json.
2. Record surface version as observed.
3. Confirm model label is in the frozen allowed-label set. Capture evidence.
4. Send neutral probe prompt via a1_surface_bridge.py:
   - system_prompt: "Gate 5 smoke test. Follow the user instruction exactly."
   - messages: [{"role": "user", "content": "Respond with exactly the following JSON and nothing else:\n{\"status\": \"ok\", \"probe\": \"representation-lifting-s1-gate5\"}"}]
5. Verify response EXACT MATCH: strip whitespace and code-fence wrappers; remaining
   text MUST be byte-identical to:
   {"status": "ok", "probe": "representation-lifting-s1-gate5"}
   Any other response — wrong content, refusal, additional text, empty: FAIL. No retry.
6. Verify bridge artifacts emitted (request_0.json, surface_input_0.txt,
   response_0.txt with valid SHA-256).
7. Verify all frozen settings active and matching.

**A1.11.2 Pass criteria (per surface):**
- Surface responded without error or timeout
- Model label in frozen allowed-label set
- Response passes exact-match criterion
- Bridge artifacts emitted correctly
- All frozen settings active and matching

**A1.11.3 Fail-closed:**
- Primary fails: ALL primary execution BLOCKED: NOT_EVALUABLE_INFRA (PRIMARY_SURFACE_GATE5_FAIL).
- Replication fails: replication BLOCKED: NOT_EVALUABLE_INFRA (REPLICATION_SURFACE_GATE5_FAIL).
  Primary proceeds independently.
- Gate 5 failure does NOT invalidate pool, anchor, or selection.

---

### A1.12 No-Regeneration / No-Selection / Retry Rule

**A1.12.1** Each protocol-defined turn produces exactly one usable model response.
No regenerate, retry, "try again", edit-and-resubmit, or alternative-answer feature.

**A1.12.2 Retryable transport failures (exhaustive):**

Retry is permitted ONLY when the transport fails BEFORE any response message is
produced by the surface:
- Network connection failure (TCP reset, DNS failure, TLS error)
- Timeout before any response content appears on the surface
- Surface crash, freeze, or session termination before a response is delivered

**A1.12.3 Non-retryable:** Any response that the surface has produced —
regardless of content quality, including empty textual content — is final for
that turn.

**A1.12.4** Every retry and its cause logged with UTC timestamps.

---

### A1.13 Human Operator Protocol (Semi-Manual Execution)

The operator is a faithful courier within the boundary defined in section A1.8:

1. Copy exact content of surface_input_N.txt into the surface. Zero modification.
2. Copy complete surface response into response_N.txt exactly as received.
   Compute SHA-256 before returning to bridge.
3. MUST NOT independently formulate, modify, or supplement any prompt.
4. No response selection per section A1.12.
5. Surface-generated content preserved verbatim and annotated as surface-generated.

---

### A1.14 Fail-Closed Model Availability

1. Primary: if not recognized by CLI or label outside frozen allowed set: BLOCKED,
   NOT_EVALUABLE_INFRA. No substitute permitted.
2. Replication: if no label in frozen allowed set: BLOCKED, NOT_EVALUABLE_INFRA.
   No substitute permitted.
3. No silent substitution. Label absent/changed/outside allowed set: halt.
4. No model-family migration without a separate amendment.

---

### A1.15 A1 Transport Configuration Record

tools/executor_config.json is NOT modified.
tools/executor_harness.py is NOT modified.

A1 configuration is in evidence/amendment_a1/a1_transport_config.json,
populated completely during reconnaissance and committed as part of the candidate
commit. Gate 5 verifies; it does not populate.

Key fields:
- frozen_executor_config_sha256
- frozen_executor_harness_sha256
- bridge_sha256
- bridge_tests_sha256
- all surface versions, allowed_model_labels, inference_controls_pinned,
  tool_capabilities, flattening_scheme
- degradations_introduced_by_a1 (collected list of all DEGRADED_* flags)

---

### A1.16 Version Metadata Policy

**Claude Code CLI:** Exact version string and binary SHA-256 frozen in
a1_transport_config.json. If binary updates between reconnaissance and Gate 5,
noted in Gate 5 receipt but NOT automatic fail — model identity and
configuration-match checks are operative criteria.

**ChatGPT web:** Observed build/version recorded at reconnaissance and Gate 5
as observed metadata. Web builds may change without investigator action. Changes
noted but NOT a strict fail criterion. Operative criteria: model label membership,
inference-control settings, response exact-match.

---

### A1.17 Evidence Preservation

Each execution session under A1 MUST produce:

1. Hash-addressed artifacts per turn — request_N.json + surface_input_N.txt +
   response_N.txt, each with SHA-256 (section A1.8).
2. Sealed transcript — assembled from artifacts, SHA-256 hashed on branch
   completion (section A1.7.3).
3. Model label captures — screenshot/terminal at session start, plus mid-session
   if > 30 min.
4. Surface metadata — type, version, plan tier.
5. Execution receipt — JSON per representation-lifting-execution-receipt/v1 with
   additional A1 fields: transport_amendment, transport_surface,
   model_identity_evidence, model_label_displayed, model_label_in_allowed_set,
   a1_transport_config_sha256, bridge_sha256, inference_controls,
   system_role_handling, message_history_handling, transcript_sealed_sha256.

---

### A1.18 Ratification Chain

```
Pre-ratification surface reconnaissance (section A1.3)
  -- NO inference prompt, NO blind content
  -- populate a1_transport_config.json completely
  -- implement tools/a1_surface_bridge.py
  -- implement tests/test_a1_surface_bridge.py
-> Candidate commit:
    AMENDMENT_A1_TRANSPORT.md
    evidence/amendment_a1/a1_transport_config.json
    tools/a1_surface_bridge.py
    tools/a1_activate.py
    tests/test_a1_surface_bridge.py
-> Independent review of exact candidate commit
-> Ivan Nestorov: signed annotated git tag on reviewed commit
-> Gate 5 (section A1.11) -- verifies frozen config, sends neutral probe
    -> PASS: proceed to S/D/L execution
    -> FAIL: BLOCKED (NOT_EVALUABLE_INFRA)
```

No other ratification form is sufficient.

---

### A1.19 Zero Protocol Drift

This amendment supersedes four execution-layer mechanisms:

1. **Transport:** API HTTP POST -> subscription-surface invocation via bridge
2. **Model identity evidence:** API JSON field -> surface label against frozen allowed set
3. **Generation-control enforcement:** API request body -> surface settings (with degradation)
4. **Transcript/operator mechanics:** Programmatic JSON -> hash-addressed artifacts
   with semi-manual faithful-courier relay

The following remain identical to frozen v0.21:

- H0, H1, H2 definitions, falsification criteria, evaluation logic
- State-machine role/transition semantics (S->D->L sequencing, branch non-persistence,
  cumulative T1->T2 compilation, LIFT-NOT-FOUND classification, budget enforcement,
  turn counting)
- Protocol-defined system prompts and neutral prompt text
- Scoring, aggregation, control veto, verdict governance
- Pool, anchor, selection custody, tools/analyze.py
- tools/executor_config.json, tools/executor_harness.py (both frozen, unmodified)

---

## Reconnaissance Record (Claude Code CLI)

**Performed:** 2026-10-02 (pre-candidate commit, no inference prompt sent)

| Item | Value |
|---|---|
| Surface type | claude-code-cli |
| CLI version | 2.1.197 |
| Executable path | /home/volmax-studio/.npm-global/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe |
| Executable SHA-256 | f54e69cbc89b2da61a415700af7ff52a147e862517d4f1b0eecf768448cf7f83 |
| Authentication | Anthropic subscription (Claude.ai Pro), first-party OAuth, active |
| Model identifier accepted by CLI | claude-sonnet-4-6 |
| System-prompt mechanism | --system-prompt flag (NATIVE_SYSTEM_MESSAGE) |
| Tool restriction flags | --tools "" (empty allowlist) |
| Safe mode flag | --safe-mode |
| Effort control | --effort low|medium|high|xhigh|max; pinned to: high |
| Output mode | --print (non-interactive, single response) |
| Model routing verified? | NO — CLI accepts identifier only; actual routing verified at Gate 5 |
| Allowed model labels | To be confirmed at Gate 5 from CLI output |

## Reconnaissance Record (ChatGPT Web)

**Status: REQUIRES IVAN MANUAL INPUT**

The following fields require visual reconnaissance from the investigator:

1. **Exact model label displayed** in the ChatGPT model picker for "GPT-5.6 Sol"
   (screenshot required).
2. **Available inference controls** exposed in the UI (reasoning effort, temperature
   toggle if any, response length if any) — screenshot of settings panel.
3. **Tool/capability toggles** available (web search, code interpreter, etc.) —
   screenshot showing what can be disabled.
4. **Memory/custom instructions disable** — confirm these can be disabled and that
   the fresh conversation context is achievable.
5. **Observed ChatGPT build/version** visible in the UI.

Do not proceed to candidate commit until Ivan provides these five items.
