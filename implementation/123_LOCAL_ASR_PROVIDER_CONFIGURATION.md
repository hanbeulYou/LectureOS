# Local ASR Provider Configuration — Previous-Text Conditioning

- Status: Implementation Reference
- Blueprint: `docs/040_TRANSCRIPT_PIPELINE.md` §15 L-7 (amended), L-14 (amended), **L-15**, **L-16**,
  Canonical Invariants (amended) / `PATCH-0040`
- Schema: unchanged (**v53**; no migration, no new record, no new identity kind)
- Supersedes nothing; extends `096_LOCAL_ASR_ADAPTER.md`

## What it is (and is not)

The decoding parameters LectureOS relies on, declared as a product contract instead of inherited from
the installed engine library. It fixes **one** parameter — `condition_on_previous_text = False` — and
makes that value part of the provider-result reference, so a transcription's configuration is legible
from the record and two transcriptions differing in it are not the same execution.

- It is **not** a settings framework. One field is represented because one decision was made; a
  parameter absent from it is one LectureOS has taken no position on and leaves to the engine.
- It is **not** hallucination removal. It reduces hallucination measurably and contracts nothing
  about eliminating it (`L-16` / P-9).
- It is **not** output filtering. The setting configures the provider **before** it decodes; no
  segment is deleted, no text edited, no timestamp adjusted (`L-15` / P-7).
- It does **not** adopt VAD. `vad_filter` and every VAD parameter stay deferred, with the reason
  recorded (`L-16` / P-8).

## Why it needed a PATCH

`§15` L-2 selects `faster-whisper` but states nothing about which library parameters LectureOS uses,
so the released adapter called `transcribe(path, language=...)` and inherited the rest. Two inherited
defaults decided whether the delivered subtitle contained text the instructor never said.

The product decision alone was not implementable. L-7 encoded the *semantic execution request* into
the provider-result reference and excluded `device`/`compute-type` as operational;
`condition_on_previous_text` appeared in neither list and the released grammar could not express it.
Since `§14` A-6 derives every identity from an anchor containing that reference, deciding where the
setting lives also decides whether two transcriptions differing only in it are one execution. That is
a Confirmed-contract question, so `PATCH-0040` decided it.

## The approved configuration

```python
APPROVED_LOCAL_ASR_CONFIGURATION = LocalAsrProviderConfiguration(
    condition_on_previous_text=False,
)
```

`LocalAsrProviderConfiguration` is an Application-owned frozen record. The service holds it **from
construction**, not per call, so no caller on the production path can select a different value, and
the CLI exposes no flag for it — an override is the bypass P-1 exists to prevent. Diagnostic
exploration happens outside the production path and admits nothing.

`FasterWhisperEngineRunner` passes the value explicitly to the library, so an upstream default change
cannot alter LectureOS behaviour. No VAD parameter is passed; the runner's tests assert that absence
by recording the full kwargs and naming `vad_filter`, `vad_parameters`,
`hallucination_silence_threshold`, `temperature` and `beam_size` as parameters that must not appear.

## Versioned provider-result reference

```text
v2 (current):   local-asr:v2:model=<model>:lang=<language-or-auto>:cond_prev_text=<true|false>:media=<source_media_id>
v1 (released):  local-asr:model=<model>:lang=<language-or-auto>:media=<source_media_id>
```

`device`/`compute-type` stay excluded on a stated criterion: they serve the same request faster
without changing the emitted text, whereas the configuration changes the text and therefore the
canonical Raw Transcript. v1 references stay valid and readable, are never rewritten, re-derived, or
re-interpreted as stating a configuration they do not, and are never generated again.

### Replay consequence (P-5), accepted rather than worked around

The reference participates in the `§14` A-6 anchor, so an intake holding a v1 admission does not
match a v2 anchor: `§15` L-8 reuse-before-rerun does not fire, the engine runs, and a **second**
Raw Transcript is admitted. `§14` A-7 already permits one intake to hold several provider results,
and `§16` Current Raw Transcript Selection — not the adapter — decides which is authoritative. The
prior result is not superseded, invalidated, deleted, or re-selected.

## Provenance

No additive extension was needed. `provider_result_ref` is already a canonical persisted field of
`ProviderTranscriptAdmission` and of the `ProviderTranscriptResult` evidence, so provider, model,
declared language and the conditioning setting are all recoverable from the record alone. The CLI
prints the reference and the configuration alongside the existing lines.

## Evidence

Measured on the preserved 305-second instructor-absence fixture (`slice-A-absence.wav`, source
2680.0–2985.0 s) through the **released** infrastructure runner with the approved configuration:

| metric | baseline (released default) | approved configuration | requirement |
|---|---|---|---|
| segments in the absence region | 12 | **1** | not worse |
| max repeats of one phrase | 7 | **2** | not worse |
| `고기와 함께 먹는 김치찌개` loop | 4× | **0** | removed |
| latin-only fragments | 0 | 0 | not worse |
| single-token fragments | 0 | 0 | not worse |
| longest segment | 30.0 s | **7.4 s** | no 200 s+ segment |
| segments over 200 s | 0 | **0** | must be 0 |
| `나 화장실 좀 갔다 올게` | preserved | **preserved** | must be preserved |

On the terminology fixture (`slice-B-terminology.wav`), the approved configuration recovered `사군자`
and `메란 국죽`, which the baseline did not — the classical-literature vocabulary class the M1 record
flagged. Nothing recognized by the baseline was lost.

The 195-second region that produced the original hallucination is the same region the released
pipeline recorded as an Analysis Finding and an approved `non_lecture_region` Edit Candidate; that
record is unchanged and this contract does not act on it.

## What this does not fix

`L-16` / P-9 states it: hallucination is reduced, not contracted away. One hallucinated segment
survived in the fixture, and the configuration remains non-deterministic across runs — which L-8
already anticipates through reuse-before-rerun. Residual hallucination is handled by contracts that
already exist (`§17` Correction Candidate admission, `§18` Human Authority, `042` analysis findings),
and no heuristic detection, scoring, or automatic deletion is introduced or may be inferred.

Reproducibility was the VAD variants' distinguishing property and it was declined with them; that
trade is recorded in `PATCH-0040` and `implementation/122`, not re-opened here.
