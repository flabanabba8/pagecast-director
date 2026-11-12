---
status: SOURCE-DERIVED
curated: 2026-11-09
---
# Speech models and platforms

Knowledge is not installed support. The Director's native engine IDs are flite,
higgs, inworld, elevenlabs, gemini and host. Only the first five have dedicated
provider implementations; host requires a compatible registered speech tool.
Other families below are research/adapter choices, not fabricated native engines.
Project snapshots dated September must be refreshed before a November decision.

| Family | Models / route knowledge | Director integration and evidence boundary |
|---|---|---|
| Google Gemini | 3.8 Flash TTS, 3.8 Flash-Lite TTS; older 3.1 Flash TTS Preview and 2.5 Flash/Pro TTS in project history | Native gemini adapter. Developer API and Vertex are separate schema/auth/voice namespaces. 3.8 vendor reference dated Nov 8; project has separate actual chapter evidence. User's quality-oriented first recommendation, not a universal ranking. |
| Inworld | TTS-2 and TTS-2 Flash | Native inworld adapter. Steering, markup and controls are model-specific. Respect voice access and credit accounting; do not paste its markup into another provider. |
| ElevenLabs | Multilingual v2, Flash v2.5, Turbo v2.5; v3 in Android/evaluation history | Native elevenlabs adapter; the manifest's selected models and current implementation define supported IDs. Earlier Android live probes and short desktop probes are not book-quality benchmarks. Voice access and plan costs vary; refresh catalog retirement notices. |
| Boson Higgs | Higgs Audio/TTS 3, configured 4B server and approved references | Native higgs loopback adapter; a model server is separate from Director's Python runtime. Check GPU/resources and exact server revision. Preserve reference provenance, required attribution, timing and clone audition limits. Current contest production remains local Higgs3 with one take per cue. |
| Kokoro | Kokoro-82M / 1.0; FP32, FP16 and selectively quantized ONNX exports | Lightweight local candidate via a selected speech tool/adapter, not a native Director engine. Android project has sherpa-onnx/ONNX Runtime implementation and dated measurements. Same weights on different runtimes need fresh compatibility/quality checks. |
| KittenTTS | Legacy 0.8 Nano, Nano int8, Micro, Mini; separately KittenTTS 2 | Lightweight candidate via a selected speech tool/adapter; not installed or live-tested by this maintenance. Legacy models use ONNX and have different resources/features from KittenTTS 2. Do not treat every Kitten model as the smallest CPU model. |
| Flite | Installed voices rms, slt, awb, kal16, kal | Native flite local engine. Useful offline/resource-light baseline, subject to installed voices; no speech API charge. Do not claim comparable dramatic expressiveness. |
| Groq / Canopy Labs | Orpheus v1 English; retired PlayAI is historical | Android project speech adapter and live smoke-test evidence, not a native Director engine. Use a selected supported host speech tool or build the actual adapter. Fixed catalog is not Gemini voice design; do not transfer PlayHT clones. |
| Cartesia | Sonic 3.6 in project snapshot | Android project adapter with mock generation and live voice-list evidence; that is not live speech verification. No agent-paid Cartesia development generation is authorized. Confirm current schema/version, voice IDs and real account quota. |
| Deepgram | Flux TTS / voice-model catalog in September project snapshot | Android project /v2/speak adapter and short live-test record; not a native Director engine. Refresh exact current speech API/model names; do not confuse recognition products with TTS or reuse their schemas. |
| Speechify | Simba 3.2 in project snapshot | Android project adapter and short live test, not native Director integration. Verify account/voice access, current response format, billed characters and attribution. |
| Fish Audio | S2.1 Pro Free in project snapshot | Android project adapter and short live test, not native Director integration. Promotion in old notes is time-bounded; never assume lasting free generation. Recheck model/voice access, license, quota and current price. |
| OpenAI | Legacy gpt-4o-mini-tts, tts-1, tts-1-hd; migration target gpt-realtime-2.1-mini | Research/host-adapter candidate only. Current official speech guide marks the legacy models deprecated with shutdown Jan 6, 2027, and directs migration to Realtime. The new model is not accepted by /v1/audio/speech; a real Realtime adapter is required. Do not blindly reuse a multipart/Speech API wrapper. |
| Android system TTS | Installed engine packages, installed/offline or network voices | Android app's native TextToSpeech integration, not a desktop Director speech engine. A phone's installed engine is not automatically callable by the PC. Requires an explicit supported bridge if used as a remote synthesis resource. |

Free allowances, current prices and the full local-model table by hardware (read 2026-11-12) are in [speech models](speech-models.md); this page keeps the Director's engine-by-engine integration notes.

## Selecting the small local model

The Kitten upstream README checked Nov 9 distinguishes Nano int8 (15M, about
25 MB) from Nano, Micro and Mini, and the larger KittenTTS 2 family. Its default
constructor example selects KittenTTS 2, not Nano. Select the intended exact
model explicitly. Weights have their own licenses; repository code licensing
does not establish rights for every model. These are upstream properties, not
our measured performance or proof of a working Director adapter.

For Kokoro, the project's emulator comparison showed that FP16 saved disk but
not CPU-runtime RAM/latency; selective8 reduced peak RAM in that particular
fixture. Do not promise the same speed/RAM/quality on a different CPU/phone.
Read [project lessons](project-lessons.md) before choosing quantization.

## Refresh and entitlement

No hardcoded provider ranking, free allowance or price table is authoritative.
Verify current official model cards, endpoint, license, language, account access,
credit expiry and cost before recommendation or generation. Subscription chat
access and speech API entitlement are distinct. OpenAI's eligible Pro/Business
API benefit requires activation; Plus is excluded. Benefits can have side effects
on API-key Codex access; subscription-sign-in usage is a separate route.
Never claim or link an account automatically.

Primary refresh sources:

- Google: https://ai.google.dev/gemini-api/docs/speech-generation
- Google Vertex: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/text-to-speech/overview
- Inworld: https://docs.inworld.ai/api-reference/ttsAPI/texttospeech/synthesize-speech
- ElevenLabs: https://elevenlabs.io/docs/overview/models
- Higgs: https://www.boson.ai/higgs-audio
- Kokoro: https://huggingface.co/hexgrad/Kokoro-82M
- KittenTTS: https://github.com/KittenML/KittenTTS
- Groq: https://console.groq.com/docs/text-to-speech/orpheus
- Cartesia: https://docs.cartesia.ai/build-with-cartesia/tts-models/latest
- Deepgram: https://developers.deepgram.com/docs/flux-tts/batch
- Speechify: https://docs.speechify.ai/tts/api-reference/text-to-speech/audio/speech
- Fish Audio: https://docs.fish.audio/
- OpenAI: https://developers.openai.com/api/docs/guides/text-to-speech
- API credits: https://developers.openai.com/api/docs/guides/chatgpt-api-credits

Project lineage: wiki/kokoro.md, kokoro-benchmarks.md, groq.md, cartesia.md,
deepgram.md, inworld.md, speechify.md, fish.md, elevenlabs.md,
elevenlabs-evaluation.md, android-tts.md, gemini-3-8-tts.md and spending.md.
These are sanitized summaries; source private account/device details and book
text are deliberately not copied. See provenance.json for source hashes.
