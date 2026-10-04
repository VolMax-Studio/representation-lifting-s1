# Amendment A1 r8 Post-Ratification Execution Deviation

## Classification

`INVALID_INSTRUMENTATION_PRE_OUTCOME`

`OUTCOME VISIBILITY: NONE`

This record contains transport and custody metadata only. No scientific outcome,
proof body, verified code, token metric, verdict, or sealed transcript content was
opened in making this decision.

## Ratification and execution provenance

- Amendment A1 candidate r8 was independently reviewed.
- Ivan Nestorov approved the signed annotated tag interactively; Git verified tag
  `representation-lifting-s1-amendment-a1` and it dereferenced exactly to
  `9fbd8d067c728cf2a63348e60152bb2e84afa4f7`.
- Post-ratification Gate 5 passed, including its frozen-binding preflight and exact
  neutral-response check. The Gate 5 evidence commit is
  `b878a3becf4f5e185f26a38f0692a2216b900f4b`.
- The complete post-ratification execution block was attempted in the frozen order.
- The metadata-only pre-outcome protocol audit exited with code 23 and halted before
  outcome opening.

## Observed r8 transport defect

The twelve post-control turn-zero invocations were the D1 and S1 branches of each
calibration family (`fibonacci`, `pell`, `roots_of_unity`) and the D and S branches
of each blind case (`proofnet-108`, `proofnet-083`, `proofnet-267`). Every one had:

- `model_returned = "claude-sonnet-4-6"`;
- `assistant_model = "<synthetic>"`;
- `stop_reason = "MODEL_IDENTITY_FAIL"`;
- `is_infra_failure = true`;
- an empty tool list;
- an empty MCP-server list;
- a valid transport-metadata hash; and
- no `response_0.txt` artifact.

The control turns had ordinary provider metadata, the pinned model label, and
`stop_reason = "end_turn"`.

In r8, the bridge evaluated the synthetic assistant model label before resolving
`result.is_error` and related provider/client error semantics. It therefore
classified a client-side synthetic/error assistant envelope as
`MODEL_IDENTITY_FAIL`. That classification was non-retryable, so the already-frozen
transport retry allowance was not exercised. The raw provider error envelope,
stderr, CLI return code, and result-error fields were not preserved sufficiently to
determine whether the underlying cause was quota, rate limit, authentication,
Claude CLI failure, or another transport error.

## Binding disposition

- No r8 control, calibration, or blind receipt is admissible for H0, H1, or H2.
- No r8 result may supplement, pool with, rescue, or otherwise contribute to r9.
- After r9 review, human ratification, and Gate 5, the complete experimental block
  must restart from the negative control.
- The same control, calibration families, blind cases, case order, and
  `claude-sonnet-4-6` model remain frozen.
- No resampling or case substitution is authorized.
- Existing r8 evidence is preserved without rewrite or deletion.

This disposition was made before outcome opening, with
`OUTCOME VISIBILITY: NONE`.
