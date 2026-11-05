# Stage 5 — Local AI knowledge source selection and indexing preflight (experimental)

**Development status, 2026-11-05:** This is an isolated policy-library and static UI preview, not a working Local AI application. Stage 5 as a whole is still under user review. Nothing in this experiment installs a model, grants private file access, scans a folder, downloads Wikipedia, creates a vector database, moves a disk, or operates the Pi's real AI hardware.

## What was added

- [Policy module](../../tihulu_runtime/ai_sources.py) — pure standard-library multi-source selection, owner/scoped-grant checks, Wikipedia-last ordering and optional index admission checks.
- [Unit tests](../../tests/test_ai_sources.py) — 29 mock-only checks for source isolation, permissions and storage/resource-policy edge cases.
- [Dark UI preview](../../prototype/local_ai_sources.html) — checkbox source selector and optional keyword/semantic/background/SSD settings, in the compact mini-window visual language. Open the HTML locally in a browser. It is self-contained, cannot read any documents or start a model, and its displayed drives/selected sources are fictional examples.

### Independent sources and permissions

The source selector supports selected files, folders, named book collections, other owner-approved personal data, installed Kolibri/browser content and **Wikipedia as a separate last option**. It supports any combination, including Wikipedia only, books only, and combined book + Wikipedia citations. Selecting a source **does not grant filesystem read permissions**; the trusted server must provide its own owner identity and authorized source IDs. A selected private source belonging to someone else is rejected even if its ID is supplied as a purported grant. Do not expose this class directly to unauthenticated browser requests.

Wikipedia direct Kiwix search remains possible with index mode `none`. Local AI chat is a separate, not-yet-installed integration; the module never infers that a ZIM, a book, a model or a translator is present.

### Indexing switches

The user must independently choose whether to create a persistent **keyword/full-text** or **semantic/vector RAG** index. Both are **OFF by default**. Background indexing is another independent opt-in, with watched-folder updates and resume-after-reboot separate. The observed Stage 4 `Hard`, `Background`, and `Startup` service states are authoritative; none are overridden by a checkbox.

An optional index may be targeted to internal NVMe or a selected external SSD UUID. The preflight requires real trusted observations of mount identity, writable/supported filesystem, free space, reserve, estimated peak temporary bytes and index quota. It returns a status such as `storage_mismatch`, `storage_unavailable`, `insufficient_space` or `eligible_for_real_backend` and **never writes anything**. All large source-extraction scratch, embedding shards and resumable checkpoints must eventually use the selected SSD when explicitly chosen; never silently fall back to the Pi's OS disk.

A real index runner still needs: owner-authenticated API; per-root permissions and ACL checks; safe parsers for PDF/EPUB and OCR; stable mount identity **at each write**; index lock/journal/checkpoint/recovery; incremental ingest and source version tracking; real embedding model/LLM; shared Stage4 leases; pause/resume/true cancel with executor acknowledgment; source-grounded page/chapter citations; non-destructive reindex/delete; Pi5 measured RAM, temperature and power tests.

### Minimal expected integration route

1. The trusted backend constructs an inventory of available sources and verified owner grants.
2. `SourceSelector.select(owner_id, requested_ids, trusted_file_grants=...)` returns a validated, Wikipedia-last tuple. An empty tuple is legal, but a real chat should request at least one source if it needs retrieval.
3. An explicit owner action supplies a separate `IndexIntent` for a chosen selected source, including mode and optional background/storage policy.
4. A server-side storage registry provides `StorageObservation`. Then `prepare_index_job(...)` returns a policy decision, **not permission to bypass actual disk/path verification**.
5. Only a future tested backend may perform real parsing, writes, embedding and retrieval after additional independent authentication/service checks. Never trust the static HTML demo as authorization.

## User-visible truthfulness

The preview intentionally shows simulated private source checkboxes and a sample SSD choice, with a visible notice that **there are no connected files, models, Kiwix archives or active services**. The `Continue` button only explains required permissions; `Check indexing` only describes preflight. No implementation or default-on background AI is implied.

## Validation

Run in a developer checkout:

```bash
python3 -m unittest tests.test_ai_sources -v
python3 -m unittest discover -s tests -v
```

This tests policy, not real files or Pi hardware. CI results must be checked independently before claiming success. Do not merge this experimental Stage 5 prototype into `main` as a release based on mock tests.

## Related project decisions

Owner-approved **designs for Stages 1–4** are not software completion. Whole Stage 5 signoff remains separate. The private plan repo documents the authoritative source catalog, book archive, Wikipedia-only, external SSD, background, consent and UI decisions. Public code refers only to general product requirements, not private chat transcripts, device addresses or books.
