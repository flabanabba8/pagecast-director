---
status: SOURCE-DERIVED
curated: 2026-11-09
---
# Reusable PageCast project knowledge

## Casting and spoilers

Keep source text and directed performance separate. Read bounded context with
the active host model; uncertainty stays Narrator. Stable role IDs, voice locks,
source-reveal boundaries and explicit series inheritance protect identity and
continuity. Rendering is not reading progress. A shared voice can reveal a
masked identity too early. Record casting evidence privately, including source
pronouns/gender, and do not infer gender from pitch or actor names. Maintain the
render hold until known roles are actually cast; never silently replace a lock.

## Provider direction and voices

Google's Developer and Vertex routes use different request schemas, auth and
stored-voice namespaces. The Nov 8 research separates Vertex GenerateContent
from Developer Interactions for 3.8. Recheck before composing a request; do not
combine examples from the two. Stored custom voices, voice design/replication,
prebuilt IDs and reference cloning are distinct capabilities. Some custom-voice
operations are global-region-only in the captured Google docs.

Inworld markup/steering is provider/model-specific. A provider that accepts only
verbatim text must not receive Inworld tags or English instructions embedded in
spoken text. Speech models can read such directions aloud. Reference-based
Higgs cloning requires a clean complete single-speaker reference and matching
transcript; matching a reference does not prove the clone sounds right. Preserve
reviewed identities and provenance. Current project bans long_pause and forced
whisper/slow tags for Higgs, bounds requests and forbids automatic rerolls.

## Cache, retries and cost

Cache identity includes effective source text, backend/model revision, voice,
reference/direction and relevant audio configuration. Credentials rotating alone
should not destroy accepted audio. Inspect receipts/hashes before reuse/export;
unknown or failed paid attempts retain uncertainty. No provider switching,
rerolling a cue or changing a voice to fix a network failure automatically.

Successful-response usage estimates are not invoices. Older Android accounting
excludes some failed/timed-out requests and does not infer grants, tax or account
balance. Missing rates remain unpriced. A request might be billed without useful
audio; retain a reservation/attempt receipt rather than treating it as free.
Changing a model or render setting does not itself authorize extra spending.

## Local runtime and quantization evidence

The September Android emulator Kokoro comparison used one voice, three texts,
CPU sherpa-onnx and a particular run order. FP16 reduced model disk size but did
not materially reduce RAM/latency. Selective8 lowered peak RAM for that fixture;
phone observations were unmatched real-use sessions, not a controlled speed test.
A narrow-tone regression check detects the known quantization ringing pattern,
not intelligibility, character fit or naturalness. Do not extrapolate emulator
memory, real-time factor, battery life or quality to another machine.

Kokoro's Android model/runtime install is explicit, checksum-pinned and atomic;
base APK and downloaded native/model assets are separate. The phonemizer,
language data, model weights and runtime have distinct licensing/build inputs.
Do not assume the Android installation is already present on the Director PC.

## Timing and delivery

Measured passage audio supports readalong timing; it is not word alignment.
Provider WAV containers can have streaming length placeholders or differing
sample rates. Normalize only recognized formats and validate actual PCM frames,
not merely a RIFF prefix. Preserve source passage IDs and exact accepted audio.
Readalong ZIP import is an Android consumer contract; it does not turn Android
TTS into a PC speech server. Playback/export checks are not human listening.

## Knowledge hygiene

The project wiki contains vendor references, prior experiments and newer observed
chapter evidence. A date on a research page is not proof a provider was tested;
a source page can also retain a stale header superseded by later work. Prefer
specific dated receipts, report contradictions, and never carry forward a private
account, device, book, cast or deployment setting as a public default. Keep user
pauses and accepted artifacts intact while preparing new adapters or advice.
