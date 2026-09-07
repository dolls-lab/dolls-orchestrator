## Context

The project now has sixteen synchronized executable capability specs and no active implementation changes. Earlier phase notes are useful historical evidence but contain forward-looking statements that have since been completed. External API, device, and product-threshold work must remain visibly unverified.

## Goals / Non-Goals

**Goals:**

- Provide one current status matrix grounded in committed specs, tests, and operator commands.
- Mark the automatic no-API/no-hardware plan complete without claiming external validation.
- Keep historical documents useful by redirecting obsolete next-step language to completed artifacts.

**Non-Goals:**

- Change runtime behavior or redefine MVP product acceptance.
- Claim DeepSeek correctness, Atom VoiceS3R compatibility, LAN playback latency, or character quality scores.

## Decisions

The status document will separate `completed automatically` from `external evidence required`, and each completed row will link to its detailed baseline. This is clearer than editing historical test dates or converting unverified items into checkmarks. README will link to the matrix, while obsolete future-tense statements will point to their completed successors.

## Risks / Trade-offs

- [Status can become stale] → Require evidence links and update it through later OpenSpec changes.
- [Readers may confuse offline success with MVP product acceptance] → Give external blockers their own prominent section and prohibit inferred pass claims.

## Migration Plan

No migration is required. Later API or hardware changes update the matrix with their own archived evidence.

## Open Questions

External validation dates and product thresholds remain intentionally unresolved.
