# Stage 5 — Explicit local CPU GGUF inference smoke test (experimental)

**Status 2026-11-05:** First executable llama.cpp smoke-test adapter in Draft PR #1, not a released setup wizard, a production model runtime, or a Pi/Hailo hardware acceptance result. No actual GGUF or Raspberry Pi inference was run as part of this development. **17 unit tests** passed in an isolated local developer environment, using mocks and a deliberately fake executable; this does **not** verify a real LLM. All-repository GitHub Actions, additional CLI integration tests and ARM64/power/thermal hardware checks are still unverified.

## Purpose and exact scope

Check the *already registered*, consented Base **CPU** model separately from file presence and SHA checks. The preflight invokes **llama-cli** in a local, bounded, **offline, CPU-only** mode; it asks a fixed short sentinel prompt and only records whether the marker is observed. It is a basic *execution smoke observation*, not a general language quality score or proof of CPU-only energy efficiency, physical HAT-removal viability, source-grounded RAG, or robust model behavior.

Code: [ai_cpu_smoke.py](../../tihulu_runtime/ai_cpu_smoke.py). Related policy: [ai_base_readiness.py](../../tihulu_runtime/ai_base_readiness.py), [ai_boot_topology.py](../../tihulu_runtime/ai_boot_topology.py), [ai_model_storage.py](../../tihulu_runtime/ai_model_storage.py).

## Explicit operator use, NEVER automatic at Pi startup

Example for an already installed/local, owner-approved registry and model (replace placeholders):

\`\`\`bash
python3 -m tihulu_runtime.ai_setup \
  --boot-topology --base-readiness \
  --model-registry /owner-approved/model-registry.json \
  --base-model-id your-base-cpu-gguf \
  --run-base-cpu-smoke \
  --smoke-service-allowed \
  --smoke-resource-budget-ok \
  --smoke-timeout 90 --smoke-threads 2
\`\`\`

The above does **not** create a model registry, install llama.cpp, download weights, mount drives or request help from a remote GPU. The three explicit run/service/resource choices are local **operator attestations**, **not** automatic checks of running protected radio/TV recording, Pi temperature, battery charge or Stage4 job leases. A future authenticated task runner **must verify** those resource and policy states server-side before invoking this function. Never expose raw user-supplied executable paths or model IDs as authorization over unauthenticated HTTP. The model ID is looked up only in the existing registry; its real file is rechecked by stable mount/UUID and SHA256 before execution. This can read a multi-GB GGUF; explicit invocation is required.

The program requires a trusted, executable, non-symlink **llama-cli** binary (discovered locally or passed by a trusted operator). It reads a short \`llama-cli --version\` response and executes with a bounded token count (default 16, maximum 32), a fixed context, limited CPU threads (1–4), a wall-clock timeout (5–180 seconds), and exact options \`--device none --n-gpu-layers 0 --no-kv-offload --no-op-offload --offline\`. Environment variables from the caller (including proxy/HF tokens and \`LLAMA_ARG_*\`) are not inherited. **No shell** is used.

Flag compatibility must match the installed llama.cpp version; an unsupported option should fail closed rather than silently permit remote/GPU offload. See upstream CLI documentation: https://github.com/ggml-org/llama.cpp/blob/master/tools/cli/README.md .

## Result and privacy semantics

The result includes: model ID, registered model SHA-256, a truncated local runner version, a status string, observed wall-clock seconds, marker flag, and explicit \`current_boot_only=true\`, \`physical_swap_approved=false\`, \`energy_measured=false\`. **Raw generated text, prompt transcripts and errors are not written to a database or returned by the helper.** The fixed prompt contains no personal source material. The runner itself is expected to be a separately trusted local installation; a malicious fake executable could spoof a marker. No cryptographic attestation of runner provenance or model reasoning quality is claimed.

Important statuses:
- \`owner_consent_required\`, \`service_disabled\`, \`resource_budget_not_approved\`: no model access or subprocess.
- \`unregistered_model\`, \`model_unavailable\`, \`not_gguf\`, \`untrusted_model_digest\`: fail closed before inference; no hidden SSD fallback.
- \`cpu_runner_unavailable\`, \`runner_version_unavailable\`, \`runner_failed_to_start\`: no actual inference; do not count a smoke execution.
- \`runner_failed\`, \`timed_out\`, \`generation_unverified\`: attempted but not verified.
- \`marker_observed\`: the local subprocess returned exit code 0 and produced the expected marker, with source model SHA and runtime version recorded; **not** a complete benchmark or proof of authenticity.

CLI \`base_readiness\` remains a **current boot candidate only** even with an observed marker. The root drive may be on the PCIe NVMe HAT removed to install AI HAT+2. No automated change of EEPROM, hardware wiring, OS boot, model drive, background service, external index storage or power profile occurs. Always shut down and disconnect power before physically changing HAT.

## Testing and remaining gates

\`\`\`bash
python3 -m unittest tests.test_ai_cpu_smoke tests.test_ai_setup -v
python3 -m unittest discover -s tests -v
\`\`\`

**17 smoke policy/runner tests passed locally**, including one fake \`llama-cli\` script; the CLI integration mock additions and whole repository were committed but have **not** been observed passing in GitHub Actions. CI results must be checked before merging. Other missing acceptance gates: verified local llama.cpp build+binary provenance, actual low-memory Pi5 CPU GGUF inference, peak RAM/CPU/temp/electrical measurement, cancellation honoring protected apps, two real powered-off HAT physical boot configurations, and restored Wiki/Books RAG/source permissions. Model and client paths in diagnostic JSON are private; do not paste unredacted output into public issues.

**Release rule:** Experimental code stays in Draft PR #1, not automatically merged to \`main\`, and does not approve whole Stage5.

## Checkpoint 070 — Supervised Stage4 route versus manual CLI

The existing `ai_setup --run-base-cpu-smoke` CLI remains **operator-controlled**, not an authenticated Stage4 queue and not live-cancellable. A separate library-only [Stage4 coordinator and admission](STAGE4_CPU_SMOKE_ADMISSION.md) now supports real MemAvailable/thermal measurements, trusted model peak RAM check, independent power-source verification, protected recording/Emergency job checks and foreground ServiceManager lease. It passes a cancellation Event into the Linux Popen process-group path and waits for child termination before acknowledging `cancelled`; stdout is limited to 8 KiB. This is **not** a fully hardened systemd/cgroup or global priority scheduler, and a newly started recording after smoke admission still needs guaranteed preemption. Added mock/fake tests are not yet confirmed passing in full CI or tested on Pi5 hardware. Neither route proves HAT+2 physical dual-boot or lower energy.
