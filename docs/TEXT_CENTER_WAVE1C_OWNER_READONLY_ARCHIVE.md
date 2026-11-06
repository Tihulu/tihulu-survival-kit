# Text & Data Center Wave1C — read-only independent SQLite archive

**Review date:** 2026-11-06. **Status:** synthetic CI-verified source archive adapter and read-only portal client. NO Pi5 physical/deployment release, no source RF scan, no live official alert, no multi-user BBS.

## Upstream source baseline

Independent source: https://github.com/Tihulu/TIHULU-TEXT-CENTER at reviewed **main d47337fe58d773af8733e1303500d35bed703d40**. Its present textcenter/core.py includes read methods and SQLite source tables for PAGES (actual imported Teletext/Journaline page and subpage), EVENTS (received RDS/DAB etc), and ARTICLES (cached RSS/Atom/JSON Feed). This integration **never invokes the independent Store() constructor**, because that could create/update a database; it reads an existing file only. Independent source remains live and unmodified, including FM audio, DAB, DVB and media code added since earlier handoffs.

## Actual added code

- tihulu_runtime/text_center_archive.py: exactly one *trusted configured owner* and absolute existing SQLite file. Read-only SQLite mode=ro, PRAGMA query_only, schema-column verification, all queries parameterized, and no file creation/migration. A missing database, symlink, unrelated schema or unauthenticated account blocks access. Only approved metadata returned; no arbitrary SQL/DB path from HTTP.
- tihulu_runtime/text_center_http.py: optional archive constructor, existing trusted gateway and owner sessions, 403 on wrong owner **before query validation**, GET-only, strict recognized parameters and bounded JSON.
- prototype/text_center_kit_preview.js: source HTML/CSS from the independently installed package; Kit GET-only JavaScript presents genuine saved page body and subpage, station, source ID, frequency, timestamp, provenance, archived RF event excerpts and saved Internet feed headlines/article bodies. All untrusted content renders with textContent; no unsafe HTML injection or active device/news fetch; Modern/Classic local view mode preserved.
- tests/test_text_center_archive.py and tests/test_text_center_archive_http.py: local synthetic SQLite fixtures with clearly marked no-RF data, source Unicode, admin-only boundary, stale/cached classification, invalid IDs, missing source, non-existent file, symlink and schema protection, POST blocked.

## Authenticated local GET paths (not a deployed gateway)

| API path, mounted under /text-center/api | Data | Bounds / provenance |
|---|---|---|
| archive/status | Saved pages/events/articles counts | Only if owner DB exists; no false live indication |
| archive/pages | Imported Teletext/Journaline page/subpage index | 60 most recently received pages; imported_not_live |
| archive/page?source_id=...&number=...&subpage=... | Original decoder page and full text | Exact source/page/subpage; original station, timestamp, frequency, provenance |
| archive/articles | RSS/Atom/JSON Feed saved headlines | 30 newest, 1800-character excerpts; cached_internet |
| archive/article?id=... | One complete saved Internet article | Exact 32-character digest ID; cached_internet |
| archive/events | Receiver-imported text metadata | 40 newest, 1800-character excerpts; imported_not_live, never official alert |

**Future trusted server assembly, schematic only:** secure image/user setup must explicitly create TextCenterArchive(existing_private_db_path, owner_id=real_authenticated_kit_owner), pass it to TextCenterWSGI with the real TLS/session authorize callback, and pass that API to TextCenterPortalWSGI with the installed upstream web asset directory. Never accept a path or owner ID from a browser header, share a standalone single-owner database with guest accounts, expose the upstream loopback port 8787, or claim the schematic equals running Pi5 deployment.

**Missing archive behavior:** GET archive routes return 503; UI shows an honest unconfigured archive, not synthetic pages. No BBS posting, network feeds refresh, live scan, receiver event transmission or bookmarks writes are enabled. News source updates must eventually share the original News & Politics state/retention and not duplicate independent downloads.

## Evidence and QA

[GitHub Actions run 42150958398](https://github.com/Tihulu/tihulu-survival-kit/actions/runs/42150958398) PASS Python 3.11/3.12 full prototype unittest suite and Text Center preview JavaScript syntax, no receiver access. Earlier run 42150841876 FAIL due to authorization response priority on malformed query. Fixed in commit a24058f7d742a8fb9a89018f143715d5df557191: wrong-owner archives reject with HTTP 403 **before** query parsing; regression PASS thereafter.

**Not yet performed:** real user's existing Text Center database migration, production Tihulu HTTPS/host and phone UI, Nooelec USB/WinTV decoder, full shared SDR process control, real source licensing, source-native complete interactive history/bookmarks, Power/RAM, offline Pi5 boot. All tests here use synthetic SQLite and source contract inspection.

**Next:** real portal mount, one owner-scoped and CSRF-protected writable future BBS/News shared store, cross-process supervised RF capture that respects readsb/Gqrx and protected original media, real device/mobile screen tests. Preserve original source independently, Stages1–9 design approvals, ongoing Stage10 design review, 338 stable requirements and 53 existing MW UI designs; NO merge to public main.
