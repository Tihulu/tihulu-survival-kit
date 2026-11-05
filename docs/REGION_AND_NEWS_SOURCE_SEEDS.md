# Region and News Source Seed Catalogs — Experimental Data, Not Live Feeds

**Last edited: November 5, 2026. No transmitter scan, official account link verification, source ingestion or background news service has been implemented.**

Files:
- `data/region_profiles.json` — Germany's 16 federal states and Turkey's 81 provinces, with a schema for independent UI language, owner-initiated scan, and honest channel availability states.
- `data/news_sources_candidates.json` — a diverse *candidate* list of German/Turkish publishers, party-operated publications, public figures, and international institutions. Each initially has `feed_status=candidate_not_verified` and `official_account_uri=null`.

No candidate list entry implies that a news outlet is currently broadcasting, independently owned, associated with any current political post, or legally accessible in the user's region. The app must validate all source identities, rights, live streams, RSS/APIs and politician accounts before enabling subscription. User can select/hide sources; candidate entry is not an endorsement.

## Requirements for the actual News Center

1. **No unsolicited work:** Hard Enabled / Background Enabled / Start at Boot are distinct. Default News background and startup are OFF. Opening the app may perform an authorized foreground refresh; user can separately opt into short-lived timer refresh with bandwidth/API quotas.
2. **24-hour rolling expiry:** Cached news and social posts expire based on trustworthy publication timestamp. Source time missing/untrustworthy must be labeled and assigned a bounded fallback TTL, not treated as permanent. Expired entries disappear immediately from the UI and are purged from local SQLite and temporary media files. Target 30 MB cap, no video download by default. This functionality is **not** implemented by these JSON files.
3. **Protect permanent data:** Never apply temporary-news deletion to Local BBS posts, Emergency history/original audio, TV recordings, uploaded source documents, saved personal AI chats or saved source preferences.
4. **First-class provenance:** Explicitly tag journalists' news articles, original party declarations and politicians' public statements. AI comparison is opt-in and source-grounded. Do not create subjective editorial rankings or promote selected political positions.
5. **Worldwide official social accounts:** Platform APIs and account URLs may be missing, restricted or inaccessible; do not fabricate verified account IDs or pretend X/Instagram/Telegram/TikTok data has been fetched. Plan integration adapters only where permitted.
6. **Country and language independence:** A user can select Turkish UI with German broadcasting or choose Turkish state channels and international accounts while living outside Turkey. Online source != DVB terrestrial reception.

These are source catalog *seeds*, not production claims or pre-verified public URLs. Candidate names represent requested inclusion in a user-configurable directory, not a definitive list of currently active channels.

## Acceptance tests and pending integrations

- All 16 DE states and 81 TR provinces present exactly once; no RF frequency included unless separately proven.
- Every candidate publisher/figure has `candidate_not_verified`, no populated invented stream or social profile URL.
- Actual ingestion/cache engine, task-lifecycle integration, consented API adapters, web UI, Pi5 RAM measurements and legal source review must be implemented separately.
- Experimental code remains on [Draft PR #1](https://github.com/Tihulu/tihulu-survival-kit/pull/1) until reviewed; no `main` release claims.
