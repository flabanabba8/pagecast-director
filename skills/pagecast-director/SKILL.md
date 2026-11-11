---
name: pagecast-director
description: Create or edit cast audiobooks from user-selected TXT or EPUB, choose speech resources with the user, direct performances with the current host model, and export offline read-along audio for PageCast Android.
---

On first use read the [bundled LLM wiki](../../llmwiki/index.md), then load
only the domain references needed for this task.


Before first-run speech setup, read `pagecast_knowledge(topic="index")`, then the
providers/runtimes/project-lessons topics relevant to the user's resources. Follow
next_offset for bounded continuation. Call `pagecast_setup` with no arguments. Ask the
user in ordinary persistent chat about missing information, preferably together:
local OS/CPU/RAM/GPU/VRAM, installed models and runtimes; remote machines/services
and available host tools; subscriptions and separately usable API credits,
expiry/limits; maximum additional API dollars per book AND per month (zero is a
valid answer); permission to send book text remotely; languages, voice acting,
cloning, latency and quality preferences. Never use a question/popup tool. Offer
read-only hardware discovery with the host's supported tools; do not scrape
credential stores, start services or download weights to discover resources.
Do not ask again for known answers. Save the complete confirmed non-secret
profile with `pagecast_setup(preferences=...)`; users can revise it later.
An existing install without a profile needs this interview only before new
speech configuration/spending, not to inspect/export its accepted audio.

Recommend from the user's actual resources, not a fixed model ladder. For this
user, start the quality-oriented comparison with Gemini 3.8 Flash TTS, and the
free/lightweight local comparison with Kokoro-82M and KittenTTS legacy Nano.
KittenTTS is confirmed as the intended small model. Distinguish its tiny legacy
CPU models from newer KittenTTS 2 variants; check the exact model's hardware,
languages, license and voice features. Do not claim universal quality rankings
or promise CPU throughput from parameter counts. Verify current primary model
cards/pricing before recommending. Resources and budget can change the choice.
Subscriptions do not imply API entitlement: verify claimed credits, supported
endpoint, expiry, overage and effects of claiming before planning paid use.

Explain the recommended model/runtime/tool, existing vs needed installation,
local and remote text handling, estimated book cost, and viable alternatives.
Get the user's choice in ordinary chat before new installs, uploads or paid
speech. Zero budget rules out new API charges; free grants still need verified
remaining quota. Saved budget is a preference, not an authorization or universal
meter. Before a paid batch require a conservative estimate and an enforceable
remaining per-book/month cap via the selected provider/host tool; if unavailable,
report the blocked spending guard and offer an eligible local alternative.
Never silently switch providers, models, runtimes or locked casts.

For any selected speech model supported by a registered native host tool, use
`engine: host` with configured tool arguments, explicit backend/model revision,
WAV result field and applicable attribution. Keep credentials/approvals in that
tool. Validate one authorized bounded result before a book run. Host speech
requires PCM WAV; other formats need an explicitly selected compatible adapter.
If no compatible tool exists, build and offline-test the smallest authorized
adapter against the actual provider/runtime contract; do not pretend a model
name is sufficient or silently fall back. Existing native engines remain options.

Use the model running this harness for analysis, speaker attribution, casting,
pronunciation, scene interpretation, direction and user-requested rewrites. Keep
its model selection and authentication in the harness. Do not ask for an LLM API
key, extract subscription tokens, launch another model or call an LLM endpoint.
Subscription availability, usage limits and permitted authentication are governed
by the harness/provider. Inworld and other speech generation remain separately
billed. Do not describe this as unlimited or free speech generation.

Spoiler safety is the default. Normal chat contains progress, counts, technical
issues and neutral Voice labels only. Do not reveal character names, relationships,
disguised identities, events, chapter titles, quotations, plot summaries or reasons
for casting unless the user explicitly asks. Store identities and reasoning with
`pagecast_cast_note`, behind opaque role IDs. Never infer how far the user has read
from how much audio is rendered. Do not let an early shared voice identify a masked
character: use a separate performance role until the source reveal. The host may
retain source tool results in expandable logs; do not promise those logs are hidden.

Simple request, first time, a speech route already usable: when the user hands you one text
file (a short chapter) and asks for an audiobook with a different voice per character, call
`pagecast_speech_options` FIRST (before any question). If it shows Gemini configured (the user's
own saved route with a spend guard) or a speech server answering on this computer (the user may or
may not have said so), skip the spending interview entirely; a `pagecast_setup` result of
"setup required" does not block it and you must not ask the user about hardware, services,
budget or preferences. (Gemini sends the chapter text to Google under the user's own saved settings and costs a few cents inside its guard: say so plainly in your final report.) A loopback server
sends no text off the computer and costs nothing, so nothing needs approval. Do this in
one pass, without asking the user anything: the server is at http://localhost:8000 (the plugin's
default `higgs_url`) with model bosonai/higgs-tts-3-4b; its built-in voice list is not needed; the
computer's hardware, remote services and spending limits do not matter for a loopback server, and a
setup status of "speech configuration required" does not block it. Needing a locked reference per
speaker (rule in step 5) is something YOU solve with the user's samples and `pagecast_voice_audition`,
not a reason to ask the user for details or more samples. Stop only at the finished export and phone step.
(1) `pagecast_setup` with no arguments, then `pagecast_speech_options` (read-only: which routes work
right now). If it reports Gemini configured (route, spend guard, credentials found) that is the user's own saved
choice: use it without asking, within its spend guard, and cast by NAMED voices (no reference clips
needed: a named voice sounds the same on every request): pick for each speaker one voice from its list
whose gender and trait fit the part and whose listed `median_pitch_hz` keeps the three speakers at least
20 percent apart (the narrator clearly apart from both characters) (a bright young woman: female, bright or youthful; a low gruff man:
male, gravelly or firm; a steady narrator: a mature or even voice), say in one line why, lock it with
`pagecast_voice` (`engine: gemini`, `voice` = the name), and render; report `pagecast_usage` at the
end and never print project or account values. The reference-clip rules in step 5 are for Higgs only.
If Gemini is not configured and a Higgs server answers, continue with the Higgs steps below. Then, then `pagecast_books`; (2) list the
workspace for voice sample folders (WAV plus transcript text; the server only needs
the sample and what is said in it); (3) `pagecast_import` the file; (4) read the
direction context, assign every passage to Narrator or a character by who speaks (quoted
speech goes to the character; everything else, including tags such as "said Pim, bouncing on her
toes" or "Mr. Grum muttered", is the Narrator's);
(5) cast, with ONE RULE FIRST: a reference-based speech server (Higgs) invents a different
voice on every request that has no reference clip, so the built-in voice with no reference is
NOT a voice, and you must never render any speaker, the Narrator included, on an unreferenced
voice. Before any rendering every speaker needs one locked reference (`pagecast_voice` with
`engine: higgs`, `reference_audio` = a real WAV path (not a symlink, at most 30 seconds) and
`reference_text` = the exact words spoken in that file) and every passage of that speaker uses
it. Cast to fit the character: decide from the text who is a woman, a man or a neutral
narrator, and give each a voice that fits (a gruff old man needs a low voice, a cheerful girl
a bright one); never give a man's part to a woman's clip or the reverse without saying so.
Take references from the user's samples when they fit (note whether each sounds like a woman or a
man from its notes or name; if you cannot tell, say so). For every speaker whose part has no
fitting sample, call `pagecast_voice_audition` (about six candidates; it asks the server for
short neutral takes with no reference, measures each one's pitch and keeps them all in the book
folder), pick the candidate whose measured pitch fits (a deep man roughly 80 to 125 Hz, a typical
woman roughly 165 to 255 Hz, the narrator steady and clearly apart from the characters), give
every speaker a different candidate with the measured pitches at least 20 percent apart (spread
them over the range: the gruff man lowest, the cheerful character highest, the narrator in between);
all candidates are just voices, so one audition round of 8 can supply all speakers (audition the
first speaker with 8 candidates and choose the other speakers' voices from the same list, or
audition again if the list has no fit); lock it with `pagecast_voice` (candidate path as
`reference_audio`, its `reference_text` exactly). Say honestly that pitch is a rough guide, not
a listening review. Invented voices cluster around 170 to 240 Hz and low ones are rare, so audition 12
candidates at a time and keep going (new rounds add to the list) until a measured pitch below
about 140 Hz exists for a gruff man: that counts as a man's voice. Never ask the user for a
sample or voice details; you have the tools to find a fitting voice. Also check after
assigning: every passage whose text is outside quotation marks belongs to the Narrator, only the
words inside quotation marks to the character. (6) `pagecast_render` in bounded batches (60 words or fewer per
request, one take per passage, no retries or rerolls), then `pagecast_timeline` to
confirm every passage has audio; (7) export the audiobook (and `readalong`), then do the phone step below. Final
report: passage count, which voice each role got, how many takes were generated, total
seconds, files saved. Say that the voices are different clone samples, not a listening
review. For a short chapter the user just handed over, naming the speakers in your
replies is fine (spoiler safety is for books someone is still reading).
For original characters there is nothing to research online: take gender from the text.

Phone step (the default ending of every chapter-to-audiobook job): the read-along
package plays in the PageCast Android app with the text highlighted as it is read.
After exporting `format: "readalong"`, tell the user that in one sentence, call
`pagecast_android_app` with `action: "status"` and report plainly what it says (adb
present, one phone connected, app installed or not, installed vs latest version).
If the user asked for the audiobook on their phone, or a phone with the app is
connected, call `pagecast_android_install` with `readalong_path` set to the exported
package: it asks the user for approval, installs the app only if it is missing, and
copies the package into the phone's Download folder. If the app is missing, run
`pagecast_android_app` `action: "download"` first (verified official release, installs
nothing). If `update_available` is true, say so and offer the update; pass `update:
true` only if the user agrees. Never run adb commands yourself and never print device
identifiers. Finish by telling the user to open PageCast, choose Import book, then PC
audiobook, and pick the package from Download. If there is no adb or phone the tool
returns plain sideload steps: pass them on.

Simple request, saved work: when the user asks to turn an already imported book
into an audiobook and says to use their saved voices, do not run the setup interview
and do not ask about fields, voices or providers. Call `pagecast_books` and
`pagecast_overview`, keep every locked voice exactly as saved, and treat the saved
cast and accepted cache as the user's answers. Check coverage first with `pagecast_timeline` (it verifies cached audio without
generating anything). If every passage has verified audio, call `pagecast_render`
once to reconcile: it reuses cached takes and its result gives `reused` and
`generated` counts. If some passage lacks audio, stop and tell the user a new take is
needed instead of choosing a provider or synthesizing. Export `format: "readalong"` and also the default audiobook, then end with
one short report: files saved, passage count, total seconds, how many takes were
reused, how many were newly synthesized (zero is a normal answer; say it plainly) and
that locked voices were not changed. Do not claim a listening review.

1. Use `pagecast_books` and `pagecast_overview` to reconcile existing work. Import
   only an explicitly selected source with `pagecast_import`; leave that file intact.
2. Read bounded `pagecast_direction_context` pages privately, then assign exact
   passage IDs with `pagecast_assign`. Use the returned role ID in subsequent calls.
   Keep uncertainty as Narrator. Preserve voice locks and use available voice IDs.
Character gender is a mandatory casting check for every role, including the
viewpoint narrator. Record explicit source pronouns or a reliable character
reference privately. Use the internet to research uncertain genders and traits;
prefer official character material, and distinguish confirmed facts from vocal
design choices. A name, title, voice actor's gender, pitch or rough/gruff delivery
is not evidence of the character's gender. Preserve a woman's feminine voice
when adding rasp or throat fry. If gender or speaker identity remains uncertain,
record that uncertainty instead of inventing an answer. Report only neutral voice
labels unless the user explicitly requests identities.

For Higgs 3 continuation, reuse a complete clean single-speaker clip and matching
transcript from the approved previous chapter for each returning performance.
Keep its source hash and character-gender evidence. Higgs uses reference-based
zero-shot cloning; preparing references does not prove the resulting clone sounds
right. Audition gender, character fit and naturalness before a full run. Keep
provider-specific cast variants separate so preparing Higgs cannot invalidate an
accepted Gemini chapter. Do not start a model or chapter generation for a
preparation-only request.

Higgs direction follows the applicable Breach Protocol audio safeguards. NEVER use
`long_pause` or its control token. Do not add forced slow-delivery or whispering
tags; those are banned for pacing/clone stability. Keep output requests bounded
at 60 words with sentence boundaries where practical. Check transcripts for word
drops/repeats, bad endings and extra onset words. Preserve reviewed reference
clips and the source text. The current user's retry limits apply; a failed check
does not authorize automatic rerolls or an engine fallback.

Known uncast roles must not silently inherit another role's voice. Record a
spoiler-safe `render-block.json` in the book folder while casting is incomplete;
overview exposes it and native rendering refuses to start. Clear that hold only
after all pending roles have a confirmed, approved cast and the private plan is
updated. Do not create voices for characters that are merely mentioned, imagined
crowd speech, or quotations spoken by an already identified speaker.

3. Record private casting reasons with `pagecast_cast_note`. Its `reveal_after` is
   a source passage AFTER which the identity is established; default to hidden
   rather than guessing. Advance `pagecast_reading_position` only when the user
   explicitly provides a reading boundary. Render progress is not reading progress.
4. Use `pagecast_voice.inworld_options` for model-supported controls. Use
   `pagecast_direct` with the inspected revision for separate performance scripts;
   keep source words unchanged. Its instructions explain persistent steering,
   reset, nonverbals, breaks, language/verbatim markup and optional IPA mappings.
   Use the provider-aware guidance returned by pagecast_direction_context for limits and prompting.
For Gemini 3.8 stored designed voices, configure `gemini_route: vertex`, the user's
private `gemini_project`, `gemini_model: gemini-3.8-flash-tts`, and a per-book
`gemini_max_usd` guard through Hermes settings. Vertex uses Google Application
Default Credentials, not a Developer API key. Keep project IDs, credentials and
stored voice IDs out of reports. The native renderer sends unchanged source words
without Inworld markup or identity instructions and accepts the returned WAV.
Use the already approved private cast; do not redesign voices during rendering.
The private Vertex ledger tracks actual token usage at conservative full list
rates and reserves the maximum for uncertain responses. Stop on a failed speech
call; connection/auth failures before transmission are distinct from paid retries.

5. Render only the authorized scope in bounded batches with `pagecast_render`.
   Reuse accepted cache. Stop after a failed speech call; diagnose it and retain
   the receipt. Never automatically call `pagecast_retry` or switch voices/models.
   Cancellation is checked between speech calls. Preview only when requested.
6. Export `format: "readalong"`. The user copies the resulting `.readalong.zip`
   into PageCast Android via Import book → PC audiobook. Existing M4B/WAV exports
   remain available. Report saved locations and counts without story content.

The native Hermes plugin and the MCP adapters expose the same tools and shared
book engine. If no PageCast tools are loaded, explain that the local adapter must
be enabled; do not replace it with an improvised API-based LLM workflow.
