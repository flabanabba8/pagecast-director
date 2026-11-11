---
status: SOURCE-DERIVED
curated: 2026-11-09
---
# Execution resources and interfaces

## Keep four choices separate

1. Analysis model: the user's active host/harness model performs attribution,
   casting and direction. No second LLM client, copied subscription token or
   separate reasoning worker is required.
2. Agent runtime: native Hermes registration, or the standalone Python MCP/CLI
   adapter for a supported MCP client. Pi/OpenCode/Codex/Claude Code are potential
   clients when their actual configuration enables these tools and the skill.
   A client name is not proof its tools or permissions are connected.
3. Speech execution: dedicated native provider engine, already-running loopback
   service, or explicitly selected native registered speech tool.
4. Playback/export: offline WAV/readalong packages and Android import. M4B or
   normalization may require a compatible installed converter; preview currently
   uses mpv. These utilities are not the analysis model or speech model runtime.

## Local model runtimes

- ONNX Runtime / sherpa-onnx: project-proven Android Kokoro route; desktop exports
  and Kitten legacy ONNX require matching input/phonemizer/voice assets, not just
  loading any .onnx file.
- PyTorch / CUDA: possible selected model runtime for heavier local speech;
  inspect actual CPU/GPU/VRAM/driver/model requirements before loading anything.
- KittenTTS 2 documents CPU C++ inference, optional Apple MLX and vLLM paths;
  these are model-specific upstream alternatives, not generic proof that any
  llama.cpp/vLLM installation supports every speech model.
- Python is Director's plugin/adapter implementation runtime; its interpreter
  does not decide which model runtime produces audio. Respect environment
  isolation and use the user's chosen compatible runtime.
- Containers, remote machines and existing HTTP services are resources to
  negotiate, not defaults. The shipped higgs client is loopback-only. Remote
  authenticated services need the selected supported interface or an explicit
  secured adapter; never weaken loopback guards to gain remote access.

## Generic host speech contract and current limitation

`engine: host` requires `host_tts_tool`, explicit provider/runtime/model revision
identity, configured arguments containing {text}, optional {voice}/{model}, and
an actual local PCM WAV result. Native dispatch owns credentials, approvals and
refusals. Preserve required attribution and backend identity in the cache.
Compatible mono24k16bit WAV can be used without FFmpeg; other PCM needs the
selected normalizer or installed FFmpeg. A JSON path to a missing, private-config,
symlinked, unstable or malformed file is not audio success.

The current Hermes plugin can provide native dispatch. The standalone MCP/CLI
server does not have a supported reverse dispatcher into arbitrary client tools,
so host speech is unavailable there without a real bridge. Its dedicated native
speech engines remain separate options. Do not invent reverse MCP calls, scrape
client tools or claim generic host speech works merely because MCP initialized.

## First-run resource record

Use pagecast_setup to ask/reuse local OS/CPU/RAM/GPU/VRAM, installed models and
runtimes, remote machines/services/tools, subscriptions, verified API grants,
privacy/language/voice needs and per-book/month spending ceilings. Discover
read-only capabilities with the host's actual tools; do not scan credential
stores. Software presence, account access, fixture compatibility and human
listening are different kinds of evidence. Setup stores non-secret preferences,
not keys or a universal money meter. Require actual quota/spending enforcement
before paid batches and explain a blocked route when that is unavailable.
