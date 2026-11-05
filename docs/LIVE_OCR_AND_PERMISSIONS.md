# Live Phone-Camera OCR and Device Permissions

> **Status (November 5, 2026):** This is a proposed **feature specification and user guide**, not an operational OCR service. There is currently **no working Tihulu live-OCR camera web interface, completed HTTPS trust setup, or tested Tihulu language worker** in this repository. Performance must be validated on a Raspberry Pi 5 (8 GB), iPhone Safari and Android Chrome.

## Overview

**Live OCR** aims to recognize text appearing **right now in a permitted phone camera or computer webcam preview**, at a controlled sampling interval, without requiring the user to take a separate still photograph first. If requested, the recognized text can then be passed to the shared on-device **Translator** or **Local AI** services.

Possible examples include signs, posters, medicine labels, a paragraph in a book, map text, documents in foreign languages and text displayed on another screen. **OCR or translation may be incorrect, especially for medical or emergency information: keep the original image/text and consult authoritative sources.**

## Planned user experience

1. Open **Home → OCR / Camera** or **Scan with Camera → Live OCR** inside Browser, PDF, Files or Translator.
2. Explain **“Allow camera access on this device?”** before requesting browser/OS permission in response to a user action. If denied, offer **Take Photo / Choose from Gallery / Choose File**.
3. Offer **front/rear camera** selection, supported torch/focus/zoom controls, rotation, automatic/manual language, **region of interest (ROI)**, image-stability/contrast tips, and explicit Start/Stop.
4. On **Start Live OCR**, process selected image regions from periodically sampled frames via a genuinely installed OCR engine. Show text boxes, recognized text, quality/confidence warnings, the most recently processed frame and queued/idle state.
5. Avoid repeating identical frames as new text. Provide **Clear**, **Freeze/Lock**, **Process This Frame**, **Append New Line**, and manual correction of weak OCR output.
6. Let the user explicitly choose **Copy Text**, **Share / Save File**, **Translate** (English, Turkish, German and other installed pairs), **Summarize / Explain / Ask Local AI**, and **Save to PDF / Notes** when those integrations exist. Linking source frame, time and document is optional.
7. **Stop / Close** should stop camera capture and release the session's OCR/Translator/LLM leases safely once unused by any other active task. **Original video and frames are not permanently recorded by default**; saving requires separate permission.

## How real-time processing should work

- The browser captures the explicitly opened client-camera stream using `navigator.mediaDevices.getUserMedia({video: ...})`. The camera physically belongs to the **client**, not the Pi.
- Rather than continuously saving the full video to NVMe, the UI samples controlled frames/ROI with clear status and user controls. Sampling adapts to real Pi/network load. A proposed **0.5–2 frames/second** is **only an experimental target, not a verified FPS or latency**.
- Under congestion, skip stale frames and use bounded queues instead of accumulating every frame.
- If a Pi-hosted OCR worker is installed and selected, send only necessary frame data over authenticated, trusted **local HTTPS**. If an OCR language pack is absent, show that status and offer a permissioned package/USB-import path; never invent recognized text.
- Some devices may eventually support **client-side OCR**, but it must not be advertised as universally available. State clearly whether frames and intermediate text are handled in memory, sent to Pi, stored or deleted.
- Candidate OCR engines include **Tesseract** or comparable ARM64-compatible implementations. Initial language-pack candidates include `eng`, `tur`, `deu`. Chinese, Arabic, Russian and other scripts require appropriate trained data and a separate Translator pack where translation is desired. Handwriting, tiny/angled text, motion and poor lighting can yield unreliable results.
- Text-region tracking, stable overlays, translation overlays, face/private-data safeguards and long-document stitching must be added and validated on real devices; **continuous AR translation is not a shipped feature**.

## OCR, translation and AI are separate stages

1. **OCR:** Converts visible characters into text. **It does not translate**.
2. **Translator:** Converts recognized text from the detected/specified source language into an **installed supported target language**.
3. **Local AI:** Only on an **additional explicit user request**, summarizes, explains or answers questions about the recognized/translated text, preserving relevant source context.

Example: **Chinese sign → Chinese OCR pack → Chinese-to-Turkish/English translation pack → optional local AI explanation.** If any engine, model or permission is absent, show an accurate limitation rather than fabricating a result.

### Service-manager rules (approved Stage 4 design, experimental code only)

- If OCR/Translator/AI is **installed and Hard ON**, but **Background OFF / Startup OFF**, workers may still start **on the user's explicit Live OCR request**, and unload when no longer leased.
- If any required worker is **Hard OFF**, offer **Enable for this task / Enable persistently / Continue without it**. Hard OFF must never be silently overridden.
- When another Browser, Radio, PDF or different user's task still uses a shared worker, closing this camera view must **not stop that other task**.
- Any original image/video/text must be stored only under a separately agreed **user save and retention policy**. No permanent original-frame/video archive by default.

## Camera and file permissions

| Action | Required user choice and permission |
|---|---|
| Open live camera | Explicit Start + browser/OS camera permission |
| Choose front/rear camera | Only when the client device/browser supports this control |
| Capture a still photo | User chooses Take Photo or a standard camera-capture picker |
| Select from gallery | User-operated gallery/photo selection |
| Select a phone document | **Choose File**; no silent full-phone filesystem access |
| Select a PC document | **Drag and drop** or explicit file picker |
| Run OCR | User-visible purpose, local data handling and installed language pack |
| Translate / ask AI | Separate request, installed model and any Hard OFF exception approval |
| Save photo/video/text | Explicit choice of saved content, destination and retention |
| Live location | A separate client geolocation/GPS permission; not implied by camera consent |

Permissions are **specific to each browser origin and client device**. Permitting a phone camera does not grant access to a PC webcam. A Pi connected to a PC over Ethernet does **not** automatically access that computer's camera, files or full storage.

## HTTPS and secure contexts

Browsers generally require a **secure context** for `getUserMedia()` and Geolocation. Opening `https://tihulu.lan`, `https://tihulu.local` or a private-IP URL is **not enough** if the TLS certificate/hostname is invalid or the client does not trust its issuing CA. Self-signed certificates are not automatically trusted by iOS, Android or desktop browsers.

- **Pi hotspot:** Correct local access via `tihulu.lan` or its IP. A live camera may remain unavailable until a trustworthy HTTPS/certificate setup is verified.
- **Router LAN:** `tihulu.local` where mDNS works, or the Pi's actual router-assigned address, with independently verified HTTPS trust.
- **Direct PC Ethernet:** Actual Pi link address or supported hostname from the computer's browser, with matching trusted certificate.
- When camera permission is denied, **do not repeatedly re-prompt**. Explain the limitation and offer photo/file selection.
- **Stop** should call `MediaStreamTrack.stop()` on active tracks. Loss of connection, lock-screen, app suspension or page navigation should also stop or safely abandon the camera stream. **Do not promise background camera capture** on mobile clients.

Browser specifications:
- [MDN MediaDevices.getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)
- [MDN input type=file](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/input/file)
- [MDN capture attribute](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Attributes/capture)
- [MDN Geolocation](https://developer.mozilla.org/en-US/docs/Web/API/Geolocation_API)

## Acceptance tests on real devices

- On **iPhone Safari** and **Android Chrome** with trusted HTTPS, request consent, select front/rear camera if supported, choose ROI, read clearly printed English/Turkish/German text and ensure **Stop** releases capture.
- When permission is denied, offer **Choose File / Gallery / Take Photo**; never record without authorization.
- For a **Chinese sign/document**, require actual Chinese OCR data followed by a compatible translation pack and an explicit optional AI summary. Missing models must not be masked by invented content.
- On **Pi 5 8 GB**, measure CPU/RAM/temperature and network latency while dynamically adapting capture intervals. Concurrent authorized original radio/emergency recording must be protected; slow OCR rather than interrupting the protected capture.
- Test bad lighting, rotated/damaged pages, multi-line text, motion, multiple writing systems and private documents, preserving originals and differentiating processed versus saved data.
- Verify the same on Pi hotspot, router via secondary USB Wi-Fi, router via Ethernet, and direct PC Ethernet while respecting each origin's HTTPS and permission state.
- A phone must **not** be able to activate an unattended remote PC webcam unless the PC owner explicitly opens a compatible consenting client/session.
- Closing without saving must not silently leave original frames or video in disk, backups or AI project history; saving must preserve only the user's specified scope.

## Related guides

- [Getting Started](START_HERE.md)
- [Installation](INSTALLATION.md)
- [Network Access](NETWORK_ACCESS.md)
- [Features & Architecture](FEATURES_AND_ARCHITECTURE.md)
- [Main README](../README.md)
- [Turkish translation](tr/LIVE_OCR_AND_PERMISSIONS.md)
