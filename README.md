# PageCast Director

Make an editable cast audiobook from a chapter or EPUB. Assign quotations to
characters, lock their voices, render in resumable batches, and regenerate only
the audio affected by a text or voice change. Export chaptered M4B or WAV.

The unified Desktop page includes import, passage editing, casting, voice locks,
render progress, previews and export. Enable both the Python plugin and its
Desktop half through Hermes's normal controls. The tools also work through chat.

## Workflow

1. Import supplied text or an explicit absolute TXT/EPUB path. The source stays
   unchanged; PageCast stores an editable copy with source coordinates and quote IDs.
2. Inspect passages and assign quoted lines to speakers. Narrator is the initial
   fallback; the parser does not infer character identities or claim perfect attribution.
3. Choose voices. Flite provides lightweight English demonstration voices. Higgs
   TTS 3 uses your existing local server and optional user-owned reference WAVs.
   Inworld TTS-2/TTS-2 Flash uses your hosted account and existing voice IDs.
4. Render a batch. Call again to resume a partial book; unchanged passages reuse
   accepted audio. Voice locks prevent incidental replacement by later casting.
5. Preview an existing rendered passage, edit a line or voice, and render the change.
6. Optionally call `pagecast_timeline` to obtain paginated passage boundaries from verified cached WAV durations. Metadata-only pages can contain up to 1,000 passages; pages including text are limited to 100. Each page rechecks the entire requested prefix, so long books can take substantial local disk I/O; later passages may still be missing. Set `include_text` only when you explicitly need the potentially sensitive, untrusted passage text for captions. WAV export concatenates passages in that order, but other encoding and edits can change playback timing.
7. Export the current revision. Every audio hash is checked; missing or altered
   cache entries prevent export. M4B has verified chapter metadata; WAV is mono24kHz.

An explicit `pagecast_retry` preserves previous takes in the book archive and
invalidates only selected audio signatures. Identical text/voice passages can
share a cached take, so retry reports all passages affected by that shared take.
No speech-generation failure is retried automatically.

## Inworld

Set the complete copied Base64 credential in **Hermes Settings → Plugins →
PageCast Director → Inworld API credential**. Hermes stores it as
`INWORLD_API_KEY`; the plugin reads it only through `agent.secret_scope.get_secret`.
The optional key does not disable local Flite/Higgs use when absent. The plugin
never reads the Android app, an Inworld CLI login, or credential files directly.

Select Inworld for Narrator or any character, then choose a current voice ID.
The editor can load the authenticated system-voice catalog; custom voice IDs can
be entered directly. The tool's explicit custom-voice option includes workspace
voices. New speakers inherit the current narrator provider, so an Inworld book
does not unexpectedly require Flite.

Uses synchronous `POST https://api.inworld.ai/tts/v1/voice` with Basic authorization,
explicit model/voice IDs, BALANCED delivery and LINEAR16 WAV at 48 kHz, normalized
into the book's 24 kHz cache. It does not use the streaming response shape.
The 2,000-UTF-16-unit limit is checked before sending. No Inworld SDK is required.

Synthesis sends passage text and voice IDs to Inworld and may consume credits.
Provider-reported character usage is separate from estimated input units; neither
is an account balance or dollar invoice. Cache replay sends no request. If an
attempt may have been billed but produced no usable cache, another paid attempt
is blocked until an explicit `pagecast_retry`. Previous usage/takes remain recorded.
Authentication errors, redirects and malformed audio do not trigger automatic
paid retries. Keys never enter cache identities, book data, receipts or logs.
Redirects are never followed.

Sources: [synthesis API](https://docs.inworld.ai/api-reference/ttsAPI/texttospeech/synthesize-speech),
[voice catalog](https://docs.inworld.ai/api-reference/voiceAPI/voiceservice/list-voices).

## Requirements

Linux, Python3.11+, FFmpeg/ffprobe, and Flite for the default offline voices.
mpv is optional for audio-only previews on the Hermes host. No Python package
dependencies. The plugin installs no software and downloads no models.

For neural speech, configure the already-running loopback Higgs service in plugin
settings. Set the served model ID and revision. Each speaker can use a local
reference WAV (up to5MiB/30 seconds) and transcript. References are sent as immutable
audio data to the loopback server so a changing source file cannot alter a request
after its cache identity was computed. Use only references you have rights to use.

Higgs model licensing is separate. Qualifying creator content requires the Boson
credit; narrated exports include a credit file. Other model uses may require a
separate license. See [Higgs model/license](https://huggingface.co/bosonai/higgs-tts-3-4b).

## Reliability and scope

- Audio and its hash receipt are installed together by an atomic directory rename.
  Complete staging entries for the same revision are recovered without another
  synthesis request after an interrupted installation.
- The Linux book database is opened with owner-only permissions before SQLite
  initialization; a symlinked database is rejected. Existing regular databases
  have their permissions restricted as well.
- Every batch is limited to1–100 newly generated passages. Completed passages
  survive interruption. Cancellation is checked between bounded speech calls.
- Editing the cast or text during synthesis stops that render as stale, preserving
  its cached output without attaching it as the current revision's audio.
- Export verifies complete audio hashes. Batch resume reuses unchanged size/mtime
  receipts to avoid rereading an entire audiobook on every small batch.
- Flite runtime bytes, text, effective voice, reference bytes and declared Higgs
  model revision contribute to cache identity. Identical reference files at new
  paths retain the same audio identity.
- Source files are limited to16MiB, EPUB expansion to32MiB/2000 entries, imported
  text to1 million characters and20,000 passages. Import is UTF-8 and text-first:
  complex layout, illustrations, DRM and scanned PDFs are not supported.
- Short English examples are the verification target. Audio format/duration checks
  do not establish transcription accuracy or subjective performance. Review speech.

## Disclosure

Reads only explicitly named book/reference files plus the installed Flite binary
for cache identity. Refuses configuration/credential directories as book sources.
Calls local Flite, FFmpeg/ffprobe and optional mpv without shell command strings.
Stores imported book text, cast, voice-reference paths, audio, failure receipts
and archived takes in the active profile's `plugin-data/pagecast-director`.

Higgs sends passage text, selected voice and optional reference audio/transcript
to the configured loopback endpoint; remote origins, redirects and proxies are
disabled. Explicit Inworld selection sends text/voice IDs over verified HTTPS to
api.inworld.ai and uses the profile-scoped key described above. No telemetry,
automatic provider switch, model download, self-update or publication. Previews
play sound on the machine running Hermes.
Book/audio/reference content is not bundled in the plugin.

GPL-3.0-or-later. Adapted from [PageCast](https://github.com/flabanabba8/PageCast)'s
source-preserving segmentation, voice locks, prepared-audio recovery and export
design. This is an independent Python Hermes implementation, not the Android app.

If Inworld voice-list access is denied, enter a known voice ID directly; the voice-list endpoint can require permission even when speech synthesis works. A live four-passage test used Inworld for narration and a local Flite dialogue voice, then exported M4B. Actual voice availability depends on your account.

To import a selected TXT or EPUB produced by another plugin in the active profile, explicitly enable `allow_profile_books`. Files in unrelated private configuration remain blocked. The Desktop import form exposes the same opt-in.
