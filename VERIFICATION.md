# PageCast Director verification

Development checks on 2026-11-06. No publication; bounded live Inworld synthesis requests were made using the configured account.

## Passed

- The database is owner-only before SQLite opens it, including with a permissive
  umask, and a symlinked database is rejected. Twenty-seven Python tests and
  Hermes validation passed; synthetic PageCast restore and podcast-to-video
  workflows also passed after this change. No new hosted voice request occurred.
- EPUB spine order, escaped/unescaped filename spaces, excluded script/style text,
  archive traversal rejection, quote/source offsets, apostrophes and scene breaks.
- Real local Flite synthesis with three voices. A one-passage batch resumed using
  its existing audio; replacing one locked character voice regenerated exactly
  one passage and preserved other WAV bytes. Editing one line regenerated one line.
- Atomic assignment rejects mixed valid/invalid passage IDs without partial edits.
- Cache tampering is detected by audio hashes; an explicit new take preserves the
  previous cache entry. Completed staging entries can be recovered after interruption.
- Cast changes during synthesis stop the old render as stale. Current text/cast
  must be rendered before export. M4B export preserves title and chapter metadata;
  exported audio is decoded with FFmpeg. WAV output is validated normalized PCM.
- Inworld contract fixtures: Basic authorization, native TTS-2 request fields,
  LINEAR16/WAV/base64 handling, UTF-16 limits, fixed HTTPS destination, no redirects,
  system voice listing, reported usage, no key material in cache/data, no extra
  request on cache replay, and a blocked paid retry after malformed paid audio.
- Hermes profile secret isolation: a missing key in another active profile does
  not inherit the first profile's credential. New speakers inherit the selected
  narrator provider, and unused Flite voices do not block Inworld-only books.
- Native backend route settings and Desktop React/jsdom flow: import does not
  synthesize; speaker assignment, explicit Inworld selection, voice catalog,
  manual voice lock, explicit render and export dispatch work; polling cleans up.
- Hermes catalog validation and Plugin Doctor load/register the 13 tools cleanly.

## Remaining / limitations

- The user supplied an Inworld credential, stored through Hermes's credential lifecycle. A six-character smoke test and a four-passage original
  mini-book using Inworld Ashley for narration and local Flite for dialogue passed
  synthesis and M4B export. The mini-book made three Inworld requests, reporting
  63 characters and zero unknown outcomes. Independent cached Whisper ASR matched
  the expected normalized word sequence exactly; no human listening was done.
  Its live voice-catalog request returned
  HTTP 403; manual voice IDs remain available. Multiple live Inworld voices, a
  long book, and subjective listening quality remain unverified. No Android/CLI
  credential store was read.
- A separate live local Higgs test used an existing synthetic narration WAV as
  a reference, rendered one new PageCast passage, reused the cache and exported
  M4B. Voice similarity and listening quality were not judged. No model weights
  or reference clips are bundled.
- Actual Hermes Desktop visual review, human voice-quality review, a full-length
  audiobook, Windows support and a public demo remain unverified.
- UTF-8 text-first TXT/EPUB only; generic chapter names follow spine order. Complex
  layout, DRM, scanned PDF/OCR and series-wide cast sharing are outside this version.
- Public source/history/artifact audit, repository/catalog PR, X video and contest
  submission remain. Detailed local receipts live outside the plugin package.
- The paginated timeline checks cached WAV hashes and durations for the requested prefix. A synthetic multi-voice test checked page continuity, rejected missing cached audio, and matched the final boundary to a WAV export. Encoded formats and later edits can change playback timing.
- Timeline text is omitted by default and is included only on explicit request; a fixture confirmed both behaviors. Passage text may be sensitive and is not evidence that speech matches it.
