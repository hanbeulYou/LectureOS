# PATCH-0040

- Title: Local ASR Previous-Text Conditioning Policy and Provider Configuration Identity (040 §15)
- Status: Accepted
- Priority: High
- Trigger: Product Owner Decision, on the 4-way diagnostic recorded in
  `implementation/122_FULL_LENGTH_REAL_MEDIA_E2E_VALIDATION.md`
- Created: 2026-08-06
- Target Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` (§15 L-7 amended; new §15 L-15 and L-16; L-14
  Deferred list amended; §15 Canonical Invariants amended)

---

## Status

Accepted. This PATCH encodes a Product Owner decision and **requires a corresponding implementation
slice** in the `§15` local ASR adapter. It introduces no schema change, no migration, no new record,
no new aggregate, and no new repository. The SQLite schema remains **v53**. `§14` is not amended.

## Context

`PATCH-0022` fixed the first concrete local ASR adapter (`040 §15`, L-1…L-14). L-2 selects
`faster-whisper` as the engine but states nothing about which of the library's decoding parameters
LectureOS uses, so the released adapter calls `transcribe(path, language=...)` and inherits every
other parameter from the installed library. Two of those inherited defaults determine whether the
delivered subtitle contains text the instructor never said.

Full-length validation (`implementation/122`) recorded the consequence on real media. Across a
195-second region where the instructor had left the room, the released configuration emitted
foreign-language fragments, single-character segments, and a four-fold repetition of one sentence,
all of which reached the published SRT.

A 4-way diagnostic over a preserved 305-second slice measured the two candidate parameters:

| configuration | hallucinated segments | real speech | segment duration | reproducible |
|---|---|---|---|---|
| released default | 12 | preserved | normal | no |
| `vad_filter=True` | 0 | **lost** | **212 s cue** | yes |
| `condition_on_previous_text=False` | 1 | preserved | normal (max 7.4 s) | no |
| both | 0 | **lost** | **214 s cue** | yes |

The VAD variants removed every hallucination and were the only reproducible configurations, but they
dropped the instructor utterance `나 화장실 좀 갔다 올게` at the speech/silence boundary and emitted a
single caption spanning 212 seconds for a two-second utterance.

## Product Owner Decision

> 강의 자막에서는 없는 말을 넣는 것보다 실제 발화를 삭제하는 것이 더 위험하다.

On that principle the Product Owner selected `condition_on_previous_text=False` and declined
`vad_filter`. The decision is recorded as made; this PATCH contracts it and does not re-open it.

## Architect Decision required

The product decision alone does not tell the implementation where the setting lives, whether two
transcriptions of one lecture that differ only in this setting are the same provider execution, or
what the delivered result must disclose. Three points need deciding, and all three touch a Confirmed
`§15` decision, so none can be resolved at implementation level:

1. **Is the setting semantic or operational?** L-7 encodes the *semantic execution request* into the
   provider-result reference and explicitly excludes `device` and `compute-type` as operational
   performance settings. `condition_on_previous_text` is named in neither list, and the released
   grammar cannot express it.
2. **How is a released reference preserved while a new one is introduced?** `§14` A-6 derives every
   identity from `(intake_id, provider, model, provider_result_ref)`, so changing what the reference
   contains changes admission identity for future runs and must not silently re-interpret existing
   rows.
3. **What does declining the VAD commit LectureOS to?** L-14 lists deferred concepts; VAD is not
   among them, so its non-adoption is currently unstated rather than decided.

## Decision

**P-1 (Confirmed) — Provider configuration is Application-owned and explicit.** The decoding
parameters LectureOS relies on are a product contract, not an engine detail. The approved values are
declared in Application and passed explicitly to the engine on every production invocation. The
adapter never relies on an installed library's default for a parameter LectureOS has an opinion
about, so an upstream default change cannot alter LectureOS behaviour. `§15` L-2's engine selection
and L-11's replaceability are unchanged: a replacement engine must accept the same declared
configuration or the substitution is not equivalent.

**P-2 (Confirmed) — The approved production configuration is
`condition_on_previous_text = False`.** It is the sole approved value on the production path. There
is no CLI flag, environment variable, or configuration file that selects a different value, because
an override is exactly the bypass P-1 exists to prevent. Diagnostic exploration happens outside the
production path and admits nothing.

**P-3 (Confirmed) — The configuration is semantic, not operational.** It changes the emitted text
and therefore the canonical Raw Transcript, which is categorically different from `device` and
`compute-type` — those change only how fast the same request is served. It participates in the
provider-result reference. L-7 is amended accordingly; its exclusion of `device`/`compute-type` is
unchanged.

**P-4 (Confirmed) — Reference grammar is versioned; the released grammar is preserved.** The local
ASR provider-result reference gains a version token and the configuration:

```text
v2 (this contract):  local-asr:v2:model=<model>:lang=<language-or-auto>:cond_prev_text=<true|false>:media=<source_media_id>
v1 (released):       local-asr:model=<model>:lang=<language-or-auto>:media=<source_media_id>
```

v1 references already stored stay valid, stay readable, and keep their meaning. LectureOS never
rewrites them, never re-derives an existing record under v2, and never re-interprets a v1 reference
as carrying a configuration it does not state. v1 is never generated again.

**P-5 (Confirmed) — Consequence on replay is accepted, not worked around.** Because the reference
participates in the `§14` A-6 anchor, an intake holding a v1 admission does **not** match the v2
anchor, so L-8's reuse-before-rerun does not fire and the engine runs again, producing a second
admitted Raw Transcript under the v2 reference. This is correct and already contracted: `§14` A-7
permits one intake to hold several provider results, and `§16` Current Raw Transcript Selection —
not the adapter — decides which one is authoritative. The prior result is not superseded,
invalidated, or deleted, and no automatic re-selection occurs.

**P-6 (Confirmed) — Provenance reuses the released structure.** The configuration is legible from the
persisted result alone because `provider_result_ref` is already a canonical persisted field of
`ProviderTranscriptAdmission` and of the `ProviderTranscriptResult` evidence. Provider, model,
declared language and the conditioning setting are therefore all recoverable from the record without
a new column, table, or migration. Additive extension is unnecessary and is not performed.

**P-7 (Confirmed) — Raw preservation is untouched.** This is a configuration applied to the provider
*before* it decodes, not a filter over what it returned. Whatever text the provider emits under the
approved configuration is admitted verbatim and preserved as the canonical Raw Transcript. LectureOS
deletes no segment, edits no text, and adjusts no timestamp on the basis of this decision. `§15` L-6
and `§14` A-11 are unchanged and are the reason this PATCH cannot be read as authorizing output
filtering.

**P-8 (Confirmed) — VAD is declined and deferred, with the reason recorded.** `vad_filter` is not
enabled on the production path, and no VAD parameter — `vad_parameters`, `threshold`,
`min_silence_duration_ms`, `speech_pad_ms`, `max_speech_duration_s` — is introduced by this contract.
The ground is that the measured behaviour deletes real instructor speech and emits segments whose
duration is unusable downstream; **zero hallucinations does not by itself justify losing recorded
speech**, and a 212-second segment for a two-second utterance is not an acceptable subtitle unit.
This is a deferral with a stated reason, not a permanent prohibition: a future contract may adopt
VAD if it also resolves speech loss and segment duration.

**P-9 (Confirmed) — Hallucination is reduced, not contracted away.** This decision does not promise
hallucination-free transcription. The diagnostic left one hallucinated segment under the approved
configuration, and the configuration remains non-deterministic across runs — which `§15` L-8 already
anticipates and handles. Remaining hallucination is handled by contracts that already exist:
`§17` Correction Candidate admission, `§18` human authority, and `042` analysis findings. No
heuristic detection, scoring, or automatic deletion of suspected hallucination is introduced here,
and none may be inferred from this PATCH.

## Non-goals

Not addressed, not approved, and each needing its own gate evaluation: enabling `vad_filter` or
tuning any VAD parameter; introducing `hallucination_silence_threshold`; changing `temperature`,
`beam_size`, `no_speech_threshold`, `log_prob_threshold`, or `compression_ratio_threshold`;
heuristic hallucination removal; subtitle split, merge, or readability rules; minimum playable cue
duration; transcription checkpoint/resume under L-10; batch correction or a terminology dictionary;
`U+FFFD` handling; automatic edit-candidate detection; and any `§14`, `041`, `042`, `043`, or `044`
change.

## Consequences

- `§15` L-7 is amended, L-14's deferred list gains VAD, two decisions (L-15, L-16) are added, and the
  section's Canonical Invariants are amended.
- One implementation slice realizes P-1…P-4 and P-8 in the adapter, the engine port, the composition
  root, and the CLI.
- No schema change, no migration, no released row rewritten, and no released identity re-interpreted.
- Transcriptions produced after this contract are not anchor-compatible with those produced before
  it, by design (P-5).
