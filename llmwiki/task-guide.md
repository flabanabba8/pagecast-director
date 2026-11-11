---
status: SOURCE-REVIEWED
curated: 2026-11-09
---
# pagecast-director setup and task guide

This is a source-reviewed operating guide, not a claim of a new live test.
Resolve exact parameter shapes from [tool contracts](tools.md) and
[registration schemas](contracts.json) before calling a tool.

## Setup decisions

Read index, providers, runtimes and project-lessons through pagecast_knowledge, then reconcile pagecast_setup. Gather missing local/remote resources, subscriptions vs actual usable API grants, privacy and per-book/month limits. Choose a configured speech route; native and host adapters have different execution requirements. Existing accepted casts/audio remain usable without recasting.

## Worked task flow

For a user-selected chapter, pagecast_import retains the source. Read bounded pagecast_direction_context, assign exact passage IDs, record private cast evidence and lock approved voices. Resolve known pending roles before rendering. Render only the authorized bounded batch, inspect overview/usage, then export an accepted current revision as readalong or WAV. Reading progress advances only from a user-provided boundary.

## Reference voices: every speaker needs one

Reference-based speech (Higgs) gives a new voice to every request without a reference clip, so the built-in voice with no reference is not a voice: a Narrator cast that way changed voice on every passage (measured median pitch of six Narrator passages: 90, 185, 147, 168, 139 and 178 Hz), and a gruff man voiced by a woman's clip measured 184 to 229 Hz. Lock one reference per speaker, the Narrator included, with pagecast_voice before pagecast_render, and use it for every passage of that speaker. Fit the voice to the part. When the user's samples do not fit a speaker, call pagecast_voice_audition: it requests a few neutral takes with no reference, measures their median pitch (rough autocorrelation, no model) and keeps them in the book folder; choose the candidates that fit (a deep man about 80 to 125 Hz, a typical woman about 165 to 255 Hz, a steady narrator in between), with the speakers' median pitches at least 20 percent apart; one audition round can supply all speakers. Tags such as said Pim belong to the Narrator, lock its path with its exact text. Acceptance: median pitch per passage stays within about 15 percent of that speaker's median and the speakers differ; this is still not a listening review.

## Named Gemini voices

When pagecast_speech_options reports Gemini configured, cast by name: Gemini's 30 prebuilt voices keep the same sound on every request, so no reference clip is needed. The tool lists each voice with Google's gender and trait label (vendor labels, not a listening review); choose one voice per speaker that fits the part with median pitches (our measurement, rough) at least 20 percent apart, lock it with pagecast_voice (engine gemini), and keep tags and description outside quotation marks with the Narrator. Spending is bounded by gemini_max_usd; read pagecast_usage at the end.

## Honest speech and locked voices (0.3.4)
Render and audition results state the engine and voice actually used and whether anything was billed: repeat `speech_summary`. The Narrator defaults to local Flite; asking for a Gemini voice means casting it (or passing `engine`/`voice` to `pagecast_render`, which refuses instead of substituting). `pagecast_voice_audition` with `voices` makes one paid line per named Gemini voice under the same spend guard and adds nothing to the book. Replacing a locked voice (`replace_locked`) asks the user, naming the character, the locked voice and the new one; without approval the lock stays. `pagecast_preview` plays nothing unless `play=true` is approved.

## Failure diagnosis

Wrong model/voice namespace needs contract diagnosis, not fallback or recasting. An uncertain paid request retains its attempt state. pagecast_retry is an explicit new-take request, including affected identical cached passages; it must never run automatically. Standalone MCP has no reverse generic-host speech dispatcher. Saved spending preferences are not an enforceable account-wide cap.

## Acceptance and evidence limits

Accept source/voice/cache fingerprints, bounded authorized generation, verified export bytes and required credits, with pronunciation/character-fit/listening review stated honestly. Passage-timed readalong is not word alignment. Keep spoilers, private casts and book text out of ordinary progress replies.

## Source trail

Derived from the packaged [README](../README.md), [manifest](../plugin.yaml),
registered tool schemas and the tests listed in provenance.json. Existing
verification records describe their own dated scope; no new live capability
was inferred from this documentation review.
