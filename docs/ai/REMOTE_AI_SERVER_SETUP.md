# Remote AI server setup — Phase 5 developer guide

**Status (2026-11-05):** Tihulu now has an experimental Python RemoteAIClient library, **not** a working web wizard, installed Pi image, authenticated remote hardware agent, or real remote GPU benchmark. All connections are opt-in; no specific RTX card is required.

## Hardware classes and model suitability

Assess the exact model version, quantization, engine support, usable VRAM or unified RAM, KV/context overhead, license and real measured inference speed. Memory categories below are **guidance only**, not promises that a model fits:

| Host | Guidance |
|---|---|
| CPU only | Smaller quantized GGUF and sufficient system memory; lower speed likely. |
| 6–8 GB VRAM | Small quantized models; contexts can exceed VRAM. |
| 12 GB VRAM | More choices, still measure runtime buffers. |
| 16 GB VRAM | Midrange workloads with tested context/concurrency. |
| 24 GB VRAM | Larger models may fit; no guaranteed model or speed. |
| 32 GB+ VRAM | Higher memory capacity; still verify software support. |
| Apple Silicon | Unified memory is shared by CPU, GPU and OS. |

NVIDIA, supported AMD, Apple Silicon and CPU-only Linux, Windows and macOS machines may serve models. Runtime/platform compatibility is a separate check: vLLM is **not** automatically supported on every Windows/macOS/AMD configuration.

## 1. Inspect host and Raspberry Pi networking

On Linux use hostname -I, ip addr, free -h and where supported nvidia-smi or rocm-smi. On Windows use ipconfig, Task Manager > GPU, driver status and supported GPU vendor tools. On macOS use System Settings > About, system_profiler SPDisplaysDataType and ipconfig getifaddr en0 when en0 is actually Wi-Fi. On Pi use ip route and test private server IP/hostname. Example server address: 192.168.1.100. A successful ping is not proof of a compatible API, trusted TLS or GPU offload.

## 2. Install and test the inference service ON THE OTHER COMPUTER

**Ollama:** Install from https://ollama.com/download for Linux, Windows or macOS. Select a compatible **local** model after reviewing size, license and network downloads. Run ollama serve only if the local daemon/app is not already running. Check ollama list, ollama ps (shows actual CPU/GPU offload), and the local model API as below. Official OLLAMA_NO_CLOUD=1 disables cloud features.

**llama.cpp:** Build/install a supported CPU, CUDA, HIP/ROCm or Metal version following https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md . With a verified existing GGUF, llama-server can listen on loopback. Windows can use the suitable llama-server.exe release.

**vLLM:** Follow https://docs.vllm.ai/ on an actual supported backend/OS/GPU combination. Test the OpenAI-compatible /v1/models and /v1/chat/completions routes locally. Do not assume native Windows or macOS vLLM is available.

**Hailo-ollama:** Distinct from generic Ollama/GGUF and requires an explicitly verified Hailo-10H runtime/model catalogue.


```bash
# Ollama on the AI server:
curl http://127.0.0.1:11434/api/tags
# llama.cpp example, substitute a real installed GGUF:
llama-server -m /path/to/model.gguf -c 2048 --host 127.0.0.1 --port 9931
curl http://127.0.0.1:9931/v1/models
```

## 3. Protect transport before involving the Pi

Keep raw inference HTTP servers on 127.0.0.1. Use a **trusted private HTTPS reverse proxy** with authenticated access/device ACL or authorized Tailscale **Serve** HTTPS (not public Funnel). For example, the endpoint https://gpu.home.arpa (trusted by Pi) proxies to the GPU computer's 127.0.0.1:11434. Firewall to approved Pi/local devices/tailnet. Never turn on public port forwarding, UPnP, or unauthenticated all-interface inference.


```bash
# Run on Pi after configuring the private CA/proxy:
curl --fail --show-error https://gpu.home.arpa/api/tags
```

A TLS verification error must **not** be bypassed with insecure flags. The current Tihulu client refuses non-loopback plain HTTP even within LAN: http://192.168.1.100:11434 is intentionally NOT accepted. Only loopback localhost, 127.0.0.1 and ::1 may use HTTP. Tihulu does not currently auto-install a reverse proxy, CA or VPN.

## 4. Experimental Python adapter usage

This requires an explicitly selected private server and separate approval before sending user prompts/files to a different computer. Load credentials from a protected local secret store; NEVER embed tokens in public GitHub.


```python
from tihulu_runtime.ai_remote import RemoteAIClient, RemoteEndpoint

endpoint = RemoteEndpoint("https://gpu.home.arpa", "ollama",
                          bearer_token="OWNER_CONFIGURED_PRIVATE_SECRET")
client = RemoteAIClient(endpoint)
print(client.list_models())
# Only after authorization and choosing an installed model:
# print(client.generate(model="EXACT_MODEL_ID", prompt="Merhaba"))
```

Supported API flavors:
- ollama / hailo_ollama: /api/tags, /api/generate
- llamacpp / vllm: /v1/models, /v1/chat/completions

The current client is non-streaming. It has no automatic remote GPU inventory or hardware agent, no web pairing UI and no actual OS installation wizard. The model API alone cannot reliably report GPU VRAM/driver or host RAM; a future authenticated read-only hardware agent may provide that, without arbitrary remote shell access. An authenticated Pi owner service must authorize client use and data disclosure.

If the remote machine is sleeping/offline, the route policy can choose a separately installed, verified Pi CPU model. It must not pretend the exact remote model is on Pi; if no compatible fallback exists, report unavailable. Do not silently upload to cloud AI.

## 5. Troubleshooting

| Problem | Investigate |
|---|---|
| Connection refused | Process running, intended port and reverse-proxy listener. |
| Wrong hostname/address | Pi router LAN vs hotspot DNS; actual IP, private subnet, routing. |
| TLS certificate or 401/403 | Private CA trust, hostname, token/ACL, revocation. |
| No models/404 | Exact API flavor, server version, actual model installed and endpoint. |
| CPU used instead of GPU | ollama ps, NVIDIA/AMD driver support, accelerator backend, memory. |
| Slow or out of VRAM | KV/context, quantization, GPU utilization and real measured throughput. |
| Server sleeping/unreachable | Local verified CPU fallback; never fake successful remote inference. |
| SSD absent | Preserve model record; don't make a fake internal model directory/re-download. |

## Sources checked on 2026-11-05

- https://docs.ollama.com/quickstart
- https://docs.ollama.com/faq
- https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md
- https://docs.vllm.ai/
- https://www.raspberrypi.com/documentation/computers/ai.html

**Release gate:** Real model compatibility, OS/driver, protected network/TLS, measurable performance and remote loss/reconnect fallback remain unverified on physical hardware.
