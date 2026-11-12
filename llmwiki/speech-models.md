---
status: SOURCE-DERIVED (vendor pages, model cards and project READMEs read on 2026-11-12; nothing here was auditioned or benchmarked by us unless it says so)
curated: 2026-11-12
---
# Speech models: online services, free allowances, local models and local servers

Read this before recommending a voice. It is what the plugin's `recommendations` come from
(`speech_catalog.json`, the same data). **The plugin never picks an engine for the user.** It shows this
information, asks, and uses only the route the user chose.

**Prices, free allowances and licences change often. Every figure below carries the page it came from and the
date it was read (2026-11-12). Before quoting a number to the user, open the source link again.** Anything marked
UNVERIFIED could not be found on a primary page; say so instead of guessing. "User-reported" means a number
posted in a project's issue tracker, not stated by the project.

## 1. Which online service to suggest (suggested order)

The maintainers' quality order for hosted speech: **Gemini 3.8 Flash TTS, then Inworld, then ElevenLabs.** It is a
suggestion shown to the user, not a benchmark and never an automatic choice.

| # | Service | Models | Needs | Notes |
|---|---|---|---|---|
| 1 | Google Gemini 3.8 Flash TTS | gemini-3.8-flash-tts (best quality, 130 languages); gemini-3.8-flash-lite-tts (cheaper, 101 languages) | Developer API: a Gemini API key (set in the plugin settings, never in chat). Vertex: a Cloud project with billing and the Hermes Google sign-in. | Rates are temporary promotional rates until 2026-12-31. Developer API and Vertex use different request schemas and voice namespaces. |
| 2 | Inworld TTS | Realtime TTS-2; Realtime TTS-2 Flash | An Inworld account and API credential (Base64 string from the portal), set in the plugin settings. | The terms grant Inworld a licence to inputs and outputs to operate and improve the service. Per-minute rate limits: UNVERIFIED (docs page needs a login). 2,000-character request cap. |
| 3 | ElevenLabs | eleven_v4; eleven_v4_turbo; eleven_v3; eleven_multilingual_v2; eleven_flash_v2_5 | An ElevenLabs API key, set in the plugin settings. | The pricing page carried an inconsistent expired-looking promotion banner; ignore the $1 first-month offer. PageCast notes the default voices are scheduled for retirement on 2026-12-31. |

Text sent to an online service leaves the computer. Each service has its own terms on retention and on using
inputs or outputs to improve its products; mention this when privacy matters to the user.

## 2. How much free speech each service gives (read 2026-11-12)

| Service | Free allowance | Paid price | Source |
|---|---|---|---|
| Google Gemini 3.8 Flash TTS | Gemini Developer API (API key from AI Studio): Standard tier is listed as "Free of charge" for both 3.8 TTS models; only an active project is needed, no credit card (a card is needed only for the paid Tier 1). Exact free-tier rate limit: UNVERIFIED (shown only in the AI Studio console). Free-tier content may be used to improve Google products. Vertex AI / Google Cloud: NO free tier for Gemini TTS; billing must be enabled; the $300 welcome credit cannot be used for Vertex AI Gemini services on accounts created or upgraded on or after 2026-11-16. | Flash TTS $0.50 per 1M input tokens and $9.00 per 1M audio output tokens (about $0.00225 per 10 s of audio) through 2026-12-31, doubling from 2027-01-01. Flash-Lite TTS $0.50 / $6.00, doubling too. Audio is 25 tokens per second. Batch/Flex half price, paid only. | https://aistudio.google.com/docs/pricing |
| Inworld TTS | On-Demand plan costs $0 and lists "Up to 70 min TTS included". Whether the 70 minutes is one-time or monthly: UNVERIFIED. Card requirement: the plan table shows payment "Not included" for On-Demand (inferred no card; not stated outright). | On-Demand: TTS-2 $25 per 1M characters, TTS-2 Flash $15 per 1M. Subscriptions lower the rate (Creator $25/mo: $20 and $10 per 1M). | https://inworld.ai/pricing |
| ElevenLabs | Free plan: $0, 10,000 credits per month, no rollover, 2 to 4 concurrent requests. Credits per character: UNVERIFIED. Card requirement: UNVERIFIED. NOT allowed for commercial use on the free plan, and published audio must be attributed to elevenlabs.io. | API list prices per 1K characters: v4 $0.08, v4 Turbo $0.04, v3 $0.08, v2 Multilingual $0.08, Flash/Turbo $0.04. Starter $6/mo for 30k credits (commercial licence starts here), Creator $22/mo for 121k. | https://elevenlabs.io/pricing |

### Other online services with a free tier (not built into this plugin)

| Service | Free allowance | Source | Status |
|---|---|---|---|
| Amazon Polly | Standard voices 5M characters per month; Neural 1M per month, Long-Form 500k per month and Generative 100k per month for the first 12 months of an AWS account. | https://aws.amazon.com/polly/pricing/ | robotic-to-good, not in this plugin; needs an AWS account |
| Microsoft Azure Speech | F0 free tier: 0.5M Neural characters per month. | https://azure.microsoft.com/en-us/pricing/details/cognitive-services/speech-services/ | not in this plugin |
| Google Cloud Text-to-Speech (older voices) | Per month: Standard 4M and WaveNet 4M characters; Neural2 1M; Chirp 3 HD 1M; Studio 1M. Billing must be enabled. Not the Gemini 3.8 voices. | https://cloud.google.com/text-to-speech/pricing | not in this plugin |
| Cartesia | Free plan: 20K credits per month (about 27 TTS minutes per PageCast notes). Commercial licence from the $5/mo Pro plan. Credits per character: UNVERIFIED. | https://cartesia.ai/pricing | not in this plugin |
| Deepgram | $200 free credit that does not expire, no card to start. TTS rate: UNVERIFIED. | https://deepgram.com/pricing | not in this plugin |

Older notes from the Hermes Contest project (PageCast, September 2026), kept as a cross-check only: Inworld
on-demand was $25 per million characters (matches today); Fish Audio's free model was a promotion to 2026-11-30
and must not be assumed to continue; Speechify advertised 500,000 free characters per month (not re-verified);
ElevenLabs' current default voices are scheduled for retirement on 2026-12-31. The Gemini Developer API and
Vertex AI use different request schemas, voices and billing (PageCast `llmwiki/providers.md`).

**Free is not unlimited.** Free tiers have rate limits, monthly caps and terms (attribution, no commercial use on
ElevenLabs free, Google may use free-tier Gemini content to improve its products). Estimate the characters of the
user's script, compare with the allowance and say plainly when it would not fit.

## 3. Local speech: how the plugin reads this computer

It reads, locally and without sending anything: operating system, CPU threads, RAM, NVIDIA GPUs with video memory
and compute capability (`nvidia-smi`), AMD GPUs (`rocm-smi`), and Apple Silicon (unified memory; about 70 percent
treated as usable). `recommend()` then lists the models below that fit, best first. It never downloads, installs
or starts anything; installing is a separate step the user must ask for.

How "fits" is decided: a model with a video-memory need fits if the biggest single GPU has at least that much; a
CPU-capable model fits if RAM covers its need. Each VRAM figure says where it came from: **stated** (the project's
own page), **user-reported** (an issue-tracker post) or **estimate** (derived from parameter count, 2 bytes per
parameter plus headroom, when nothing else exists). Order within what fits is a judgement (tier), not a benchmark.
If the GPU is older than the generation a model documents (bf16, FlashAttention 2, compute capability), the
recommendation carries a warning.

### Local model table (read 2026-11-12)

| Model | Hardware (basis) | GPU / platform notes | Smaller builds | Licence (commercial) | Cloning | Languages | How to run | OpenAI-style | Status | Source |
|---|---|---|---|---|---|---|---|---|---|---|
| Higgs TTS 3 (Boson AI, 4.65B) | 12 GB VRAM (estimate: the model card states no VRAM; weights are 9.31 GB in bf16. vLLM-Omni recipe runs it on one H100 (talker ~60% and codec ~25% of 80 GB). Higgs Audio v2 (3B, older) was user-reported at 10-12 GB, about 4 GB in 4-bit) | vLLM-Omni recipe: CUDA 12.x, Linux, Python 3.12+, vLLM 0.22.0; tested on an H100 only | - | Boson Higgs TTS 3 Research and Non-Commercial License; Creator Use Grant allows monetized content with credit; hosting, API or embedding needs a commercial licence (restricted) | yes, zero-shot from a reference clip (a transcript helps) | 100+ | SGLang-Omni (Docker) or vLLM-Omni server | yes | maintained | https://huggingface.co/bosonai/higgs-tts-3-4b |
| Qwen3-TTS 1.7B | 6 GB VRAM (estimate: no VRAM stated (weights 3.86 GB + 0.68 GB tokenizer). User-reported: runs on a 6 GB RTX 2060, but fp16 crashed with a device-side assert) | FlashAttention 2 recommended (needs an Ampere-class GPU or newer); bf16 in the examples; building flash-attn with under 96 GB RAM needs MAX_JOBS=4 | - | Apache-2.0 (yes) | yes, 3-second clip (Base models); also voice design | 10 (zh en ja ko de fr ru pt es it) | pip install qwen-tts; vLLM-Omni | unverified | maintained | https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-Base |
| VoxCPM2 (OpenBMB, 2.29B) | 8 GB VRAM (stated: about 8 GB VRAM) | - | - | Apache-2.0, free for commercial use (yes) | yes (clip length UNVERIFIED) | 30 languages at 48 kHz | pip; vLLM-Omni; GGUF via llama.cpp-omni or VoxCPM.cpp | yes (vLLM-Omni) | maintained (pushed 2026-11-09) | https://github.com/OpenBMB/VoxCPM |
| Fish Audio S2-Pro (4.56B) | 24 GB VRAM (stated: at least 24 GB (user-reported: used 22.15 GB, does not fit 16 GB; fits an RTX 4090 but needs about 32 GB RAM or swap). Fish Drama 3 needs at least 48 GB (FP8)) | bf16 needs SM80 or newer (older GPUs: --half); Intel Arc documented; --compile unsupported on macOS and Windows (WSL listed); ROCm not documented (user-reported RX 9070 works) | - | Fish Audio Research License: research and non-commercial free, commercial needs a separate licence (restricted) | yes, 10-30 s | ~100 | Docker API server, WebUI; vLLM-Omni or SGLang-Omni | unverified | maintained | https://huggingface.co/fishaudio/s2-pro |
| Fun-CosyVoice3-0.5B | 4 GB VRAM (estimate (0.5B model); no VRAM stated) | - | - | Apache-2.0 (yes) | yes, zero-shot / cross-lingual (clip length UNVERIFIED) | 9 languages plus 18+ Chinese dialects | git clone; pip; vLLM; Docker; official FastAPI and gRPC servers | yes via vLLM-Omni / SGLang-Omni; its own server is FastAPI/gRPC (OpenAI shape UNVERIFIED) | maintained (pushed 2026-05) | https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512 |
| Orpheus TTS 3B (Canopy Labs) | 8 GB VRAM (user-reported: vLLM log shows weights 6.18 GiB (fp16/bf16); README states none. The official HF checkpoint is 15.13 GB on disk. Community quantized builds are far smaller (see smaller_variants)); CPU possible | - | GGUF Q4_K_M 2.36 GB, Q8_0 4.03 GB (community); Unsloth GGUF from Q2_K 1.44 GB to F16 6.61 GB; MLX 4-bit 1.86 GB; bnb-4bit 2.46 GB | Apache-2.0 (yes) | prompt-conditioned only, not trained for cloning | English (multilingual research models) | pip install orpheus-speech (vLLM); orpheus-cpp (llama.cpp) for no-GPU | no | maintained | https://github.com/canopyai/Orpheus-TTS |
| Voxtral TTS 4B (Mistral) | 16 GB VRAM (stated: at least 16 GB GPU memory (BF16)) | - | - | CC-BY-NC-4.0 (no) | adaptation to new voices (clip length UNVERIFIED); 20 preset voices | en fr es de it pt nl ar hi | vLLM | yes via vLLM-Omni / SGLang-Omni | maintained (2026-03) | https://huggingface.co/mistralai/Voxtral-4B-TTS-2603 |
| Dia 1.6B (Nari Labs) | 6 GB VRAM (stated in the current README: bf16/fp16 about 4.4 GB on an RTX 4090 (fp32 about 7.9 GB); user-reported about 4-5 GB on a 3060; the older HF card still says about 10 GB) | PyTorch 2.0+, CUDA 12.6 tested; CPU support "to be added"; user-reported RTX 50-series (sm_120) problem | - | Apache-2.0 (yes) | yes, 5-10 s audio prompt plus its transcript | English only | pip or uv from GitHub; Gradio | no | maintained | https://github.com/nari-labs/dia |
| IndexTTS 2.5 (bilibili) | 6 GB VRAM (stated: roughly 6 GB VRAM, NVIDIA GPU) | - | - | bilibili Model Use License (contact bilibili for commercial use) (restricted) | yes, one reference clip (length UNVERIFIED); emotion control from a second clip | zh, en, ja, es, ar | uv; git clone | no (none stated) | maintained (pushed 2026-09-29) | https://github.com/index-tts/index-tts |
| Maya1 (3.3B) | 16 GB VRAM (stated: 16 GB or more recommended) | - | - | Apache-2.0 (yes) | UNVERIFIED | UNVERIFIED | transformers with SNAC | no (none stated) | maintained (2026-10); a newer maya2 exists | https://huggingface.co/maya-research/maya1 |
| Qwen3-TTS 0.6B | 4 GB VRAM (estimate: no VRAM stated (weights 1.83 GB + 0.68 GB tokenizer)) | FlashAttention 2 recommended (Ampere-class or newer); bf16 in the examples | - | Apache-2.0 (yes) | yes, 3-second clip | 10 languages | pip install qwen-tts; vLLM-Omni | unverified | maintained | https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base |
| Soprano 1.1 (80M) | CPU, about 1 GB RAM (CPU model: under 1 GB memory (stated)) | - | - | Apache-2.0 (yes) | no (stated) | English only | pip install soprano-tts; ONNX; WebUI; CLI | yes (official /v1/audio/speech) | maintained (2026-01) | https://huggingface.co/ekwek/Soprano-1.1-80M |
| Zonos 3 Mini (Zyphra) | CPU, about 4 GB RAM (GGUF for CPU, CUDA, Metal, Vulkan; memory UNVERIFIED) | - | - | Apache-2.0 (yes) | yes, reference clip up to 60 s | 43 | GGUF; MLX; CUDA; SGLang-Omni | yes (SGLang-Omni) | maintained (2026-11-11) | https://huggingface.co/Zyphra/ZONOS3-Mini |
| GPT-SoVITS | 4 GB VRAM (estimate; VRAM UNVERIFIED (RTF 0.014 on an RTX 4090, 0.028 on a 4060 Ti)); CPU possible | - | - | MIT (yes) | yes (clip length UNVERIFIED) | UNVERIFIED | install.sh with CPU, CUDA, ROCm or MPS options; Docker | no (none stated) | maintained (pushed 2026-11-11) | https://github.com/RVC-Boss/GPT-SoVITS |
| Kani-TTS 370M | 2 GB VRAM (stated: 2 GB VRAM; the basic example runs on GPU or CPU); CPU possible | - | - | HF says lfm1.0 (Liquid licence) but the README badge says Apache-2.0: conflict, so commercial use is unclear (check) | UNVERIFIED | en, de, zh, ko, ar, es | pip; MLX build | yes (kanitts-vllm wrapper named in the README) | maintained (2026-02) | https://huggingface.co/nineninesix/kani-tts-370m |
| Kokoro-82M | CPU, about 2 GB RAM (CPU model; user-reported under 1.5 GB on GPU and a real-time factor under 0.5 on CPU (weights 0.33 GB)) | MPS documented (PYTORCH_ENABLE_MPS_FALLBACK=1); espeak-ng install documented for Windows; user-reported ROCm slower than CPU | ONNX: fp32 0.33 GB, q4 0.31, uint8 0.18, fp16 0.16, q4f16 0.15 GB | Apache-2.0 (yes) | no (fixed voice packs) | 8 languages, 54 voices | pip install kokoro + espeak-ng; Kokoro-FastAPI (Docker CPU/GPU, Windows scripts, Apple MPS) | yes (Kokoro-FastAPI) | maintained | https://github.com/remsky/Kokoro-FastAPI |
| LuxTTS | 1 GB VRAM (stated: fits in 1 GB VRAM; faster than real time on CPU); CPU possible | - | - | Apache-2.0 (yes) | yes | UNVERIFIED | ONNX files in the repo | no (none stated) | maintained (2026-01) | https://huggingface.co/YatharthS/LuxTTS |
| MOSS-TTS-Nano 100M | CPU, about 2 GB RAM (CPU model: streams on a 4-core CPU (stated)) | - | - | Apache-2.0 (yes) | yes (clip length UNVERIFIED) | 20 | ONNX; llama.cpp; mlx-audio | yes via vLLM-Omni; community wrapper moss-tts-openai | maintained (2026-09) | https://huggingface.co/OpenMOSS-Team/MOSS-TTS-Nano-100M |
| OuteTTS 1.0 0.6B (GGUF) | CPU, about 2 GB RAM (CPU path via llama.cpp; no VRAM figure found) | - | - | 0.6B: Apache-2.0 (the 1B model is CC-BY-NC-SA-4.0) (yes (0.6B)) | yes, one-shot, about 10 s reference | 14 languages | pip install outetts; llama.cpp; official GGUF repos | no (none stated) | maintained (2026-03) | https://huggingface.co/OuteAI/OuteTTS-1.0-0.6B |
| Pocket TTS (Kyutai, 100M) | CPU, about 2 GB RAM (CPU model) | - | - | Code MIT; weights CC-BY-4.0 (gated: accept terms) (yes (attribution)) | yes, from a wav clip (minimum length UNVERIFIED) | en fr de pt it es | pip install pocket-tts or uvx pocket-tts; pocket-tts serve; Rust binaries for Linux, macOS, Windows | no (community wrappers only) | maintained | https://github.com/kyutai-labs/pocket-tts |
| Sesame CSM-1B | 6 GB VRAM (user-reported about 4 to 6 GB; the README states only "a CUDA-compatible GPU" (weights 6.21 GB)) | CUDA 12.4 or 12.6 tested; README code can select Apple mps; triton-windows documented for Windows | - | Apache-2.0 (yes) | via audio context | English | pip; Windows needs triton-windows; needs access to Llama-3.2-1B | no | maintained | https://github.com/SesameAILabs/csm |
| Sopro v2 Turbo (121.6M) | CPU, about 2 GB RAM (CPU model: RTF 0.24 on an M3 CPU, 0.07 on an H100) | - | - | Apache-2.0 (yes) | yes, 5-20 s | UNVERIFIED | pip; ONNX (browser); GGUF | no (none stated) | maintained (2026-10) | https://huggingface.co/samuel-vitorino/sopro-v2-turbo |
| Step-Audio-TTS-3B | 8 GB VRAM (stated: 8 GB (plus 1.5 GB tokenizer)) | - | - | Apache-2.0 (yes) | UNVERIFIED | UNVERIFIED | GitHub repo | no (none stated) | maintained (2026-03) | https://github.com/stepfun-ai/Step-Audio |
| VibeVoice-Realtime-0.5B (Microsoft) | 4 GB VRAM (estimate: VRAM UNVERIFIED (weights 2.04 GB); stated real time on an NVIDIA T4 and a Mac M4 Pro; user-reported slow on a 7900 XTX with ROCm on Windows) | - | - | MIT with "research purposes" use restrictions (check) | no, preset voices only | English + 9 experimental | pip install -e .[streamingtts] | no | maintained | https://github.com/microsoft/VibeVoice |
| Zonos v0.1 (1.62B) | 6 GB VRAM (stated: 6 GB+ VRAM (README)) | hybrid model needs an RTX 3000-series or newer NVIDIA GPU; transformer model needs 6 GB+; Linux only (an experimental Windows fork exists) | - | Apache-2.0 (yes) | yes, a few seconds of reference | UNVERIFIED | uv sync; Gradio; Docker | no | maintained | https://github.com/Zyphra/Zonos |
| F5-TTS | 4 GB VRAM (estimate; weights 1.35 GB; VRAM UNVERIFIED) | NVIDIA, AMD ROCm (6.2, 7.2) and Intel XPU install paths documented; Apple documented | - | Code MIT; weights CC-BY-NC-4.0 (non-commercial) (no) | yes, reference audio plus transcript | zh/en base, others via community | pip install f5-tts; Gradio; Docker | no | maintained | https://github.com/SWivid/F5-TTS |
| Gradium Phonon 31M (English) | CPU, about 1 GB RAM (CPU model: 64.5 MB q8 GGUF) | - | - | 31M English: Apache-2.0 (the 40M multilingual variants are CC-BY-NC-4.0) (yes (31M English only)) | no (named voices) | English (40M variants: fr, de, es, pt) | ollama pull phonon; or the ptts-openai-server | yes (Ollama, ptts-openai-server) | maintained (2026-10) | https://huggingface.co/gradium/phonon-31m-en |
| KittenTTS 2 (1.7B) | 8 GB VRAM (stated: a CUDA GPU with roughly 8 GB free, or a CPU with about 6 GB RAM (via vLLM at least 6 GB; 4 GB cards are insufficient)); CPU possible | vLLM path: NVIDIA driver 580+, compute capability 7.5+; MLX backend and Windows documented; real time on CPU via the llama.cpp fork (stated) | default 954 MB lossless, emb4 492 MB; ternary 0.95 GB; GGUF 1.03 GB | Stellon Labs Community License: limited commercial until $1M revenue/funding (limited) | yes, 5-30 s | 16 languages | pip install kittenml; CPU via kitten-tts-2-cpp (GGUF) | unverified | maintained | https://huggingface.co/KittenML/kitten-tts-2 |
| Kyutai TTS 1.6B (1.8B) | 8 GB VRAM (user-reported: the Rust TTS server used about 7.3 GB on an L40S; not stated by the project) | - | MLX --quantize 8 or 4 (size not stated) | CC-BY-4.0 (attribution) (yes) | no arbitrary cloning (precomputed voice embeddings only) | English, French | Rust moshi-server (CUDA); MLX on Mac | no | maintained | https://huggingface.co/kyutai/tts-1.6b-en_fr |
| Marvis TTS 250M | CPU, about 1 GB RAM (CPU/Apple: minimum 1 GB RAM (stated); GPU recommended for real time) | - | - | Apache-2.0 (yes) | UNVERIFIED | English-optimised | MLX (mlx-audio); transformers | yes via mlx-audio | last update 2025-08 | https://huggingface.co/Marvis-AI/marvis-tts-250m-v0.1 |
| Ming-3.0-TTS 0.5B | 6 GB VRAM (estimate; stated tests only on H800/H20); CPU possible | - | - | MIT (yes) | UNVERIFIED | zh en de es fr ko ja | PyTorch; GGUF at audio-cpp | yes via SGLang-Omni | maintained (2026-10) | https://huggingface.co/inclusionAI/Ming-3.0-tts-0.5B |
| Muyan-TTS (3.6B) | 10 GB VRAM (estimate from parameter count; UNVERIFIED) | - | - | Apache-2.0 (yes) | UNVERIFIED | UNVERIFIED | git clone; optional vLLM; HTTP API on port 8020 | UNVERIFIED | no updates since 2025-05 | https://github.com/MYZY-AI/Muyan-TTS |
| NeuTTS Nano / 2E (Neuphonic) | CPU, about 2 GB RAM (CPU model (GGUF via llama.cpp)) | - | - | NeuTTS Open License 1.0: limited commercial; paid licence at $5M+ annual revenue (limited) | Nano: yes from 3 s of audio. 2E: 4 fixed speakers | Nano: en fr de es | pip install neutts; GGUF Q4/Q8 via llama.cpp | unverified | maintained | https://github.com/neuphonic/neutts |
| OmniVoice (k2-fsa, 0.61B) | 4 GB VRAM (estimate; VRAM UNVERIFIED) | - | - | Code Apache-2.0; model weights CC-BY-NC (no) | yes, 3-10 s | 600+ | pip; community GGUF exists (not read) | yes via vLLM-Omni / LocalAI | maintained (2026-11-09) | https://github.com/k2-fsa/OmniVoice |
| ZipVoice (123M) | CPU, about 2 GB RAM (CPU model: ONNX CPU path) | - | - | Code Apache-2.0; weights CC-BY-NC (per the HF card) (no) | yes, prompt under 3 s recommended | zh, en | pip; ONNX; sherpa-onnx C++ | no (none stated) | maintained (2026-10) | https://huggingface.co/k2-fsa/ZipVoice |
| Echo-TTS base | 8 GB VRAM (stated: at least 8 GB VRAM) | - | - | Weights CC-BY-NC-SA-4.0 (code MIT) (no) | yes, up to 5 min reference (10 s works well) | UNVERIFIED | git | no (none stated) | maintained (2025-12) | https://huggingface.co/jordand/echo-tts-base |
| Kitten TTS 0.8 nano (15M) / mini (80M) | CPU, about 1 GB RAM (CPU model) | - | - | Apache-2.0 (yes) | UNVERIFIED | UNVERIFIED | pip wheel from the GitHub release | unverified | maintained | https://huggingface.co/KittenML/kitten-tts-mini-0.8 |
| Paradee 8M | CPU, about 1 GB RAM (CPU model: about 62x real time on one CPU thread (Apple M4 Pro, per v1.2 text)) | - | - | Apache-2.0 (yes) | UNVERIFIED | en, hi, fr, es | ONNX int8 | no (none stated) | maintained (2026-11) | https://huggingface.co/sahilmahendrakar/Paradee-8M-v1.3 |
| Spark-TTS 0.5B [not auto-recommended] | CPU, about 8 GB RAM (CPU UNVERIFIED; RTF 0.1362 on one L20 GPU) | - | - | CC-BY-NC-SA-4.0 on HF (the GitHub badge still says Apache-2.0: conflict) (no) | yes, zero-shot (clip length UNVERIFIED) | zh, en | git clone; web UI | no (none stated) | last push 2025-04 | https://huggingface.co/SparkAudio/Spark-TTS-0.5B |
| XTTS-v2 (Coqui) | 6 GB VRAM (estimate; the model card states no hardware figures (weights 1.87 GB + 0.21 GB)) | idiap fork has prebuilt wheels for macOS and Windows | - | Coqui Public Model License: non-commercial only (no) | yes, 6 s clip | 17 | pip coqui-tts (idiap fork) | no (only via the archived OpenedAI-Speech) | original repo unmaintained; fork active | https://huggingface.co/coqui/XTTS-v2 |
| Chatterbox / Chatterbox-Nano (Resemble AI) [not auto-recommended] | CPU, about 2 GB RAM (CPU for Nano (110M, 3x real time on 8 CPU cores, stated); the full model was user-reported at 6-7 GB, about 2.5 GB in half precision) | - | - | MIT (yes) | yes (~10 s clip) | English (Nano) | pip install chatterbox-tts | unverified | RETIRED (unmaintained since Aug 2026) | https://github.com/resemble-ai/chatterbox |
| Inflect-Micro v2 | CPU, about 1 GB RAM (CPU model: comfortably faster than real time with 4 threads) | - | - | Apache-2.0 (yes) | no (fixed voice) | English | PyTorch; ONNX export | no (none stated) | maintained (2026-10) | https://huggingface.co/owensong/Inflect-Micro-v2 |
| MeloTTS (MyShell) [not auto-recommended] | CPU, about 2 GB RAM (CPU model) | - | - | MIT (yes) | no | en (5 accents), es, fr, zh, ja, ko | Python library | no | unmaintained since 2024-12 | https://github.com/myshell-ai/MeloTTS |
| OpenVoice V2 [not auto-recommended] | CPU, about None GB RAM (UNVERIFIED) | - | - | MIT, free for commercial use (yes) | tone-colour clone (clip length UNVERIFIED) | multiple | pip | no (none stated) | last update 2025-04 | https://huggingface.co/myshell-ai/OpenVoiceV2 |
| Piper (OHF-Voice/piper1-gpl) | CPU, about 1 GB RAM (CPU model) | - | - | Engine GPL-3.0; each voice has its own model card licence (check before commercial use) (check) | no | many (VOICES.md) | pip install piper-tts; ONNX voices; python -m piper.http_server (own /synthesize API, not OpenAI-style) | no | maintained (the original rhasspy/piper is archived) | https://github.com/OHF-Voice/piper1-gpl |
| Supertonic 3 (~99M, ONNX) [not auto-recommended] | CPU, about 2 GB RAM (CPU model) | - | - | Code MIT; weights OpenRAIL-M (use restrictions) (check) | no (fixed voices) | 31 | pip install supertonic; supertonic serve (/v1/audio/speech) | yes | ARCHIVED, no support | https://github.com/supertone-inc/supertonic |
| Bark (Suno) [not auto-recommended] | 8 GB VRAM (stated: full model about 12 GB; small models fit 8 GB; under 4 GB with offload); CPU possible | - | - | MIT (yes) | no true cloning | multilingual, auto-detected | pip; transformers | no (none stated) | stale (last push 2024-08) | https://github.com/suno-ai/bark |
| Higgs Audio v2 (3B, older generation) [not auto-recommended] | 12 GB VRAM (user-reported: 10-12 GB, OOM at 16 GB when cloning with two speakers, about 4 GB in 4-bit (bitsandbytes) on an RTX 4060; one user said full precision needs 18-20 GB) | - | - | UNVERIFIED (listed as "other" on Hugging Face; not read) (check) | yes | UNVERIFIED | transformers; git clone | no (none stated) | superseded by Higgs TTS 3 | https://huggingface.co/bosonai/higgs-audio-v2-generation-3B-base |
| MARS5-TTS [not auto-recommended] | 20 GB VRAM (stated: at least 20 GB) | - | - | AGPL-3.0 (check) | yes, 2-12 s | UNVERIFIED | torch.hub | no (none stated) | stale (2024) | https://huggingface.co/CAMB-AI/MARS5-TTS |
| Flite | CPU, about 0.1 GB RAM (CPU, tiny) | - | - | BSD-like, free for commercial products (yes) | no | English voices (rms, slt, awb, kal16, kal) | apt/brew package; CLI | no | maintained (last push 2024-07) | https://github.com/festvox/flite |
| espeak-ng | CPU, about 0.1 GB RAM (CPU, tiny) | - | - | GPL-3.0 (yes (GPL terms)) | no | 100+ | apt/brew/winget package; CLI; SAPI5 on Windows | no | maintained | https://github.com/espeak-ng/espeak-ng |

## 4. Local servers and runtimes (what runs which model, and how a program talks to it)

A server turns a local model into an endpoint. The ones with an OpenAI-style `/v1/audio/speech` endpoint can be used
by the plugin's speech-server route (Creator Studio) once the user has installed one. All entries were read from
the projects' own pages on 2026-11-12 and none was run by us.

| Server | Runs (catalog ids) | Platforms | Install | OpenAI-style endpoint | Cloning | Licence | Status | Source |
|---|---|---|---|---|---|---|---|---|
| Ollama | phonon | macOS confirmed for speech; Linux and Windows confirmed for the LFM3 audio models (Phonon there: UNVERIFIED) | ollama pull phonon (v0.40.9 or later) | yes: POST /v1/audio/speech (model, input up to 4096 chars, voice, response_format wav or pcm only; speed only 1; instructions rejected) | no | MIT | active; speech endpoint merged 2026-10-22, so very new | https://github.com/ollama/ollama/blob/main/docs/capabilities/speech.mdx |
| llama.cpp (llama-tts, llama-server) | qwen3-tts-1.7b, qwen3-tts-0.6b, pocket-tts, soprano-1.1-80m, chatterbox | anywhere llama.cpp builds: CPU, CUDA, Metal, Vulkan | release binary or build; llama-tts -hf ggml-org/Qwen3-TTS-12Hz-1.7B-Base-GGUF -p "Hello" --output out.wav | yes with limits: POST /v1/audio/speech, wav or pcm only, speed 1.0 only, voice names like alloy not mapped; cloning through the extra field speaker_ref_b64 | yes via speaker_ref_b64; the README recommends always giving a reference voice | MIT | very active (release v0.9.0, 2026-11-04) | https://github.com/ggml-org/llama.cpp/blob/master/tools/tts/README.md |
| vLLM-Omni | qwen3-tts-1.7b, qwen3-tts-0.6b, fish-s2-pro, voxtral-4b-tts, cosyvoice3-0.5b, voxcpm2, omnivoice, moss-tts-nano | NVIDIA CUDA (NPU mentioned); Docker nightly images | vllm serve <model> --omni --port 8091 | yes: POST /v1/audio/speech (input, voice, response_format wav/mp3/flac/pcm/opus, plus language, task_type, stream) | yes: ref_audio plus ref_text in the same request | Apache-2.0 | very active (v0.32.0, 2026-10-28) | https://github.com/vllm-project/vllm-omni/blob/main/docs/serving/speech_api.md |
| SGLang-Omni | higgs-tts-3, fish-s2-pro, qwen3-tts-1.7b, qwen3-tts-0.6b, cosyvoice3-0.5b, voxtral-4b-tts, ming-3.0-tts, zonos3-mini | NVIDIA CUDA default; Intel XPU; Apple Silicon experimental (documented for ASR) | uv pip install --prerelease=allow "sglang-omni==0.2.0" | yes: /v1/audio/speech (full request table not read; field parity UNVERIFIED) | yes per its TTS usage page | Apache-2.0 | active | https://sgl-project.github.io/sglang-omni/basic_usage/tts.html |
| Kokoro-FastAPI | kokoro-82m | Docker CPU and NVIDIA (amd64, arm64); AMD ROCm experimental; Apple Silicon natively with start-gpu_mac.sh | docker run -p 8880:8880 ghcr.io/remsky/kokoro-fastapi-cpu:latest (GPU image: -gpu with --gpus all) | yes: POST /v1/audio/speech (also voice mixing such as af_bella+af_sky) | no | Apache-2.0 | active (v0.10.0, 2026-11-08) | https://github.com/remsky/Kokoro-FastAPI |
| Speaches | kokoro-82m, piper | Docker CPU or CUDA (amd64, arm64); Python via uv | docker run ghcr.io/speaches-ai/speaches:latest-cpu, then uvx speaches-cli model download speaches-ai/Kokoro-82M-v1.0-ONNX | yes: matches OpenAI (opus and aac unsupported); loads models on demand | none stated | MIT | active (pushed 2026-11-12; latest tagged release is a 2025 release candidate) | https://speaches.ai/usage/text-to-speech/ |
| LocalAI | qwen3-tts-1.7b, qwen3-tts-0.6b, fish-s2-pro, piper, pocket-tts, omnivoice | macOS DMG; Docker for CPU, NVIDIA CUDA 12/13, AMD ROCm, Intel, Vulkan, Jetson (Windows UNVERIFIED) | docker run -ti --name local-ai -p 8080:8080 localai/localai:latest | yes: POST /v1/audio/speech (model, input, voice, instructions) | yes: upload a reference with /api/voice-profiles, then voice: localai://voice-profiles/<id> | MIT | active (v4.12.1, 2026-10-23) | https://localai.io/docs/features/text-to-audio/ |
| mlx-audio (Apple Silicon) | kokoro-82m, qwen3-tts-1.7b, chatterbox, sesame-csm-1b, dia-1.6b, soprano-1.1-80m, kitten-tts-2, voxcpm2, higgs-tts-3, omnivoice, zonos3-mini, voxtral-4b-tts | macOS Apple Silicon only (MLX) | pip install -U mlx-audio; mlx_audio.server --port 8000 | yes: POST /v1/audio/speech (model, input, voice); cloning over HTTP UNVERIFIED | in the CLI and Python API for many models; over HTTP UNVERIFIED | MIT | very active (v0.6.5, 2026-11-09) | https://github.com/Blaizzy/mlx-audio |
| Orpheus-FastAPI | orpheus-3b | Docker GPU (NVIDIA CUDA 12.4+, Linux or Windows), ROCm, CPU compose files; needs a separate llama.cpp or LM Studio inference server | docker compose -f docker-compose-gpu.yml up | partial: POST /v1/audio/speech on port 5005, wav only | none stated | Apache-2.0 | stale (last push 2025-07) | https://github.com/Lex-au/Orpheus-FastAPI |
| Chatterbox-TTS-Server (devnen) | chatterbox | NVIDIA CUDA, AMD ROCm, Apple MPS, CPU; Windows portable mode | start.bat / start.sh or docker compose up -d | yes: /v1/audio/speech (request schema not fully read) | proven through its own /tts; through /v1/audio/speech UNVERIFIED | MIT | maintained (2026-05); the Chatterbox model itself is retired | https://github.com/devnen/Chatterbox-TTS-Server |
| sherpa-onnx | kokoro-82m, piper, kitten-tts-0.8, pocket-tts, zipvoice | Linux, macOS, Windows, Android, iOS, WASM; CPU focus | pip / prebuilt binaries / language SDKs | no: no OpenAI-style TTS server found in the repo (UNVERIFIED that none exists) | ZipVoice and Pocket TTS | Apache-2.0 | active (2026-11-11) | https://k2-fsa.github.io/sherpa/onnx/tts/index.html |
| Piper HTTP server | piper | Linux, macOS, Windows | pip install piper-tts; python3 -m piper.http_server -m en_US-lessac-medium (port 5000) | no: POST /synthesize (text, voice, speaker) returning WAV | no | GPL-3.0 | active (v1.8.0, 2026-09-04) | https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_HTTP.md |
| OpenedAI-Speech | - | Docker | - | yes but ARCHIVED ("mostly obsolete"); recommends Speaches, Kokoro-FastAPI, Auralis, LitServe | XTTS cloning | AGPL-3.0 | ARCHIVED (2025-02) | https://github.com/matatonic/openedai-speech |

Not TTS servers, or not what they seem:
- **LM Studio:** Its OpenAI-compatibility page lists no /v1/audio/speech endpoint. (https://lmstudio.ai/docs/developer/openai-compat)
- **Open WebUI:** A client, not a server: set its TTS engine to OpenAI with an API base such as http://localhost:8880/v1 (Kokoro-FastAPI). (https://github.com/open-webui/docs)
- **Pinokio one-click launchers:** Launchers exist for Kokoro, Orpheus-FastAPI, E2-F5-TTS, AllTalk, Dia and StyleTTS2 (pinokiofactory on GitHub); their endpoints are mostly UNVERIFIED. (https://github.com/pinokiofactory)

### Which server for which model and hardware

| Model | Hardware | Server | Caveat |
|---|---|---|---|
| Kokoro-82M | CPU or NVIDIA | Kokoro-FastAPI or Speaches | Both OpenAI-shaped; Speaches loads models on demand |
| Kokoro-82M | Apple Silicon | mlx-audio, or Kokoro-FastAPI's start-gpu_mac.sh | MLX or native MPS |
| Piper voices | CPU | Speaches | Piper's own server is not OpenAI-shaped |
| Phonon (English) | Mac | Ollama | wav and pcm only, no cloning |
| Qwen3-TTS with cloning | NVIDIA | vLLM-Omni or SGLang-Omni | ref_audio and ref_text on the endpoint |
| Qwen3-TTS with cloning | CPU or mixed | llama.cpp llama-server (GGUF) | cloning through speaker_ref_b64; wav and pcm only |
| Higgs TTS 3 | NVIDIA, 12 GB+ | SGLang-Omni or vLLM-Omni | non-commercial licence apart from the Creator Use Grant |
| Fish S2-Pro, Voxtral, VoxCPM2, CosyVoice3 | NVIDIA | vLLM-Omni or SGLang-Omni | check the licence; several are non-commercial |
| Many models behind one API | any LocalAI target | LocalAI | voice profiles for cloning |
| Orpheus 3B | NVIDIA, ROCm or CPU | Orpheus-FastAPI | stale since 2025-07; needs llama.cpp or LM Studio behind it |
| Chatterbox | NVIDIA, ROCm, MPS, CPU | Chatterbox-TTS-Server | the model is retired |
| Anything tiny, no GPU | CPU, ARM, mobile | sherpa-onnx | a library, not an OpenAI-style server |

### What to suggest for what hardware

- **Almost nothing (old laptop, no GPU):** espeak-ng or Flite (robotic but instant, no server needed), then Kitten TTS 0.8,
  Soprano 80M (English, Apache-2.0, 20x real time on CPU by its own page), Phonon 31M, Paradee 8M.
- **CPU only, nicer voice:** Kokoro-82M (Kokoro-FastAPI; its README cites about 3.5 s to first audio on an older CPU,
  test on the user's CPU), Pocket TTS (CC-BY-4.0, cloning, about 6x real time on an M4 Air), MOSS-TTS-Nano, Sopro v2.
- **CPU only, many languages:** Piper (plain voices, each with its own licence), Supertonic 3 (31 languages, but archived).
- **4 to 6 GB VRAM:** Kani-TTS 370M (2 GB stated), LuxTTS (1 GB stated), Qwen3-TTS 0.6B, Zonos v0.1 (6 GB stated),
  Orpheus Q4 GGUF (2.4 GB), Dia 1.6B (about 4.4 GB stated).
- **8 to 12 GB:** Qwen3-TTS 1.7B (Apache-2.0, 10 languages, 3 s cloning), VoxCPM2 (about 8 GB stated, 30 languages,
  Apache-2.0), IndexTTS 2.5 (about 6 GB stated; restricted commercial), CosyVoice3 0.5B, KittenTTS 2 (8 GB stated).
- **16 to 24 GB or more:** Higgs TTS 3 (broadest languages; non-commercial apart from the Creator grant), Maya1 (16 GB+),
  Voxtral TTS 4B (16 GB+, non-commercial), Fish S2-Pro (24 GB+, non-commercial). Qwen3-TTS 1.7B and VoxCPM2 are the
  commercially safe large options.
- **Apple Silicon:** mlx-audio (runs Kokoro, Qwen3-TTS, CSM, Dia, Soprano, Kitten, VoxCPM2, Higgs and more), Pocket TTS,
  NeuTTS, Kyutai (MLX), Ollama for Phonon.
- **Windows:** Kokoro-FastAPI (PowerShell scripts), Pocket TTS (standalone binary), NeuTTS, KittenTTS 2, and the built-in
  Windows speech the plugin can use directly.

### Licence cautions (say these out loud)

- **Non-commercial:** Higgs TTS 3 (research licence; the Creator Use Grant allows monetized content with credit; hosting,
  an API or embedding needs a commercial licence), Fish S2-Pro and Drama 3, F5-TTS weights, XTTS-v2, Voxtral TTS,
  OmniVoice weights, ZipVoice weights, Echo-TTS weights, Spark-TTS, Llasa, MaskGCT, ChatTTS, OuteTTS 1B.
- **Limited commercial:** NeuTTS (paid licence from $5M annual revenue), KittenTTS 2 (until $1M revenue or funding),
  IndexTTS (contact bilibili), VibeVoice (research-use restrictions).
- **Unclear (conflicting pages):** Kani-TTS (HF says a Liquid licence, README says Apache-2.0), Spark-TTS (HF CC-BY-NC-SA,
  GitHub badge Apache-2.0). Treat as non-commercial until the owner clarifies.
- **Retired or unmaintained:** Chatterbox (retired Aug 2026), Supertonic (archived Sep 2026), original rhasspy/piper (moved
  to OHF-Voice/piper1-gpl), MeloTTS, Bark, MARS5, OpenedAI-Speech. They are not recommended automatically.
- Cloning a real person's voice needs their permission; tell the user.

## 5. What this plugin can use today

- Installed programs used directly (no server): espeak-ng, Flite, Piper (needs a voice model set in `piper_model`),
  macOS `say`, Windows speech. `say`, Windows speech and Piper were written but not run on those systems by us.
- Any local server that answers OpenAI-style `/v1/audio/speech` on this computer (Kokoro-FastAPI, Speaches, LocalAI,
  llama.cpp, Ollama, vLLM-Omni, SGLang-Omni, mlx-audio, Soprano's server) through the speech-server route. PageCast's own
  `higgs` engine is Higgs-specific and needs a reference clip per speaker.
- Online: Gemini (API key, or Vertex with the Hermes sign-in); in PageCast also Inworld and ElevenLabs.
- Anything else in the tables needs a server or an adapter first. Say so; never claim support that is not there.

## 6. Staleness: how the plugin checks its own knowledge, and how it is refreshed

The setup tools return `knowledge_freshness`. Knowledge counts as **stale** when it was last checked more than 30
days ago (counting any research the user approved) or when a known deadline has passed. Deadlines the catalog knows:

| Date | What changes | Source |
|---|---|---|
| 2026-11-16 | Google Cloud $300 welcome credit can no longer pay for Vertex AI Gemini services on accounts created or upgraded on or after this date | https://cloud.google.com/free/docs/free-cloud-features |
| 2026-11-30 | Fish Audio free-model promotion ends (per PageCast notes of 2026-09-15; not re-verified) | https://fish.audio/blog/s2-1-pro-free-api/ |
| 2026-12-31 | Gemini 3.8 TTS promotional prices end and double on 2027-01-01 (Developer API and Vertex) | https://aistudio.google.com/docs/pricing |
| 2026-12-31 | ElevenLabs retires its current default voices | https://help.elevenlabs.io/hc/en-us/articles/26942950589969-What-are-Default-voices |
| 2027-01-06 | OpenAI legacy text-to-speech models (gpt-4o-mini-tts, tts-1, tts-1-hd) shut down, per PageCast notes (not re-verified) | https://developers.openai.com/api/docs/guides/text-to-speech |

When something is stale or a deadline is within 30 days, the plugin tells the user what may be old and **asks whether
they want you to research the current facts online. Never research without their yes.** If they agree:

1. Open the source link of each affected row (primary pages only) and read the current figure and its date.
2. Save only what you verified with the setup tool's `knowledge_updates` argument: `{id, field, value, source, date}`
   (id from the tables above). These are stored as dated overrides in the user's plugin data and shown in place of the
   shipped values; the shipped catalog file is not modified. Unknown ids or fields, non-https sources and future dates
   are refused.
3. Tell the user what changed and what you could not verify; leave those rows as they are.
4. To refresh the shipped catalog for everyone, update `speech_catalog.json` and regenerate this page from it.

Primary pages used for the shipped data: aistudio.google.com/docs/pricing, cloud.google.com/text-to-speech/pricing,
cloud.google.com/free/docs/free-cloud-features, inworld.ai/pricing, elevenlabs.io/pricing and its legal help page,
aws.amazon.com/polly/pricing, azure.microsoft.com Speech pricing, cartesia.ai/pricing, deepgram.com/pricing, plus each
model's Hugging Face card or GitHub README and each server's README (links in the tables).

Still UNVERIFIED on 2026-11-12: the Gemini 3.8 TTS free-tier rate limit (shown only in the AI Studio console), whether
Inworld's 70 free minutes are one-time or monthly, ElevenLabs credits per character and whether its free plan needs a
card, TTS rates for OpenAI, Hume, Cartesia and Deepgram, a stated VRAM for Higgs TTS 3, Qwen3-TTS, Kyutai, F5-TTS,
XTTS-v2 and VibeVoice-Realtime, OpenAI-style cloning over HTTP for mlx-audio and Chatterbox-TTS-Server, and Windows
support for LocalAI and for Phonon in Ollama.

## 7. Evidence boundary

This is documentation review of about 51 local models and 13 servers. Nobody here listened to these models or ran these
servers except where a dated project note says so (PageCast's Kokoro phone measurements, the contest's Higgs TTS 3 runs).
Provider claims are vendor claims; user-reported numbers are anecdotes. A catalog entry is not an installation and not
authorization to spend.
