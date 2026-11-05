# News & Politics — Multi-Source, Offline Translator and Local AI

**Status: development-only shared-worker orchestration (November 5, 2026).** No actual installed offline Translator, GGUF model, live RSS API, DVB Teletext decoder, FM/DAB SDR decoder or authenticated frontend has been deployed in Tihulu. Unit-test fake engines are not real translation or inference.

## Independent multi-select at all levels

- Allow **Internet + TV Antenna + Radio Antenna simultaneously**, or any subset/none. Both the broad media checkboxes and **individual sources across media** support multi-select; do not impose radio-button exclusivity.
- Optional multiple article/feed cards (up to 12 per model task in this prototype) selected by checkbox, with source type and provenance retained. Internet text, actual decoded DVB Teletext pages, and actual FM/DAB metadata may be combined.
- Unchecked media and unselected source IDs cannot enter the scan or assistant context. Country/region determines suggested terrestrial candidates, not a forced UI language and not actual proven reception. Use the existing verified source scanner; the candidate directory never proves an antenna signal or a feed.
- **Translation target languages** can be multi-select (at most 3 per task in prototype), independently of original language. Every target requires the actual installed offline language pair. Preserve the original text, language, page number/source URL, original time, and explicit text type.
- **AI actions are independently selectable**: Summarize selected articles; Ask a source-grounded question; Compare two or more **different sources**. Multiple actions can be requested together. Responses must cite/reference the original source and distinguish a political claim from verified reportage; no ranking or political endorsement.

## Language-aware processing

Example: A **German Teletext** extract and an **English verified RSS** item are selected, and the user asks for Turkish analysis.

```text
Selected original source texts (DE / EN / Radio)
           |
   User-selected output languages
           |
    Shared offline Translator
     (only needed language pairs)
           |
    Selected local AI model
    (supports analysis language)
           |
  Source-labelled summary / question answer / comparison
           |
     Unmodified originals and provenance remain available
```

When AI does not support a source language, text is first converted with an actually installed Translator pair into the user-selected supported AI language. **If no model or language pair exists, show a missing-package state instead of fabricating text or running a hidden remote service.** Selecting English and Turkish together does not duplicate the Translator model for each browser tab: use the shared Stage4 worker lease.

This workflow must not be silently kicked off by opening News Center, by a routine Internet sync, or by turning on an antenna source. **Translation and AI are explicit user actions** and their optional workers remain background/startup OFF unless owner authorizes otherwise.

## Prototype implementation

- `tihulu_runtime/news_assist.py`: typed `NewsText`, `NewsAssistRequest` and `NewsAssistCoordinator`. Validates selected source IDs, media, provenance, original text, translation pairs, model language support and comparison source diversity. Acquires/releases the **existing Stage4 Translator/Local AI leases** independently in `finally`.
- `tests/test_news_assist.py`: fake-engine tests for multi-media multi-item analysis, multiple translation output languages, translator-before-AI, missing language packs/models, Hard OFF restrictions, private source selection and crash cleanup.
- `prototype/news_inputs.html`: client-only checkbox UX; **no live translation, inference or scanning**. Actual UI will need an authenticated backend and installed local-model adapters.

**Security/release notes:** This Python coordinator assumes the calling API has already authenticated the owner, validated genuine source adapter output and enforced per-user access to article texts. The boolean `explicit_user_action` is an internal trusted call parameter, **not something a client may set to impersonate authorization**. Model output is not fact-checking. Future implementation needs source size/context/token limits, anti-prompt-injection policies, deduplication, durable job state and cancellation, legal news content handling, actual CPU/RAM measurements on Pi5, and 24-hour article cache enforcement without erasing user files/recordings/BBS posts.

**License:** Project-original code AGPL-3.0-only; third-party model weights, Teletext broadcasts, journals, feeds, news articles and radio messages retain their individual terms.
