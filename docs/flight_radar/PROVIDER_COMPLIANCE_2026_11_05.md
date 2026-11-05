# Flight Radar Center — Provider compliance and source labeling (2026-11-05)

**Status:** An experimental policy patch stacked on Flight Radar Draft PR #4; source availability, licenses, rate limits and credential grants are **not** deployment acceptance. No external live API call or Raspberry Pi antenna test was made by this patch.

## Current official sources checked

| Provider | Official documentation | Current policy implemented |
|---|---|---|
| **ADSB.lol** | https://www.adsb.lol/docs/open-data/api and https://www.adsb.lol/request | Public API under **ODbL 1.0**; limits are dynamic and may require an API key in the future. For production deployment coordinate with operator and implement attributed licensing/share-alike compliance where applicable. Explicit owner online opt-in; no unlimited requests. |
| **ADSB.fi** | https://github.com/adsbfi/opendata/blob/main/README.md | Public **v3** geographic API at `https://opendata.adsb.fi/api/v3/lat/{lat}/lon/{lon}/dist/{radius}`. **Personal, non-commercial only**, with visible source attribution and link. Public API rate limit documented as 1 request/second, but Survival Kit uses its stricter **30s minimum**, default 60s interval. Do not enable unless the operator has *verified* permitted use. Commercial and higher request rates require direct operator contact. |
| **OpenSky Network** | https://opensky-network.org/about/terms-of-use and https://opensky-network.org/about/faq | **Operational REST API use requires a prior written agreement**, including live products/internal operational systems. OAuth2 client credentials alone do NOT authorize such use. No source request unless a trusted operator has verified the written agreement **and** the trusted OAuth2 token is present. The app cannot obtain or represent the operator's agreement by merely displaying an unchecked or user-clicked checkbox. |

## Enforced source policy in the experimental library

- `tihulu_runtime/flight_radar_sources.py`: allowed HTTPS URL families are hard-coded. Arbitrary browser-supplied provider URLs are never accepted; redirects are denied. No raw API credentials returned in errors.
- `ProviderConfig` now accepts `adsb.fi`, with explicit trusted operator flags `personal_noncommercial_verified` and `operational_agreement_verified` for ADSB.fi/OpenSky respectively. Default is **False**. The restrictions run **before** cache and any network request, so permission revocation cannot silently serve cached internet data.
- No automatic provider or HTTP availability is assumed. Source manager also checks the owner online-enable state, fresh timestamps, response size and per-provider cooldown. Provider result records carry source ID/position freshness and cannot be mistaken for local MLAT.
- `provider_attributions` in each snapshot includes only configured sources when owner online access is authorized. The responsive Flight Radar UI renders a preapproved provider-link list using a fixed local allowlist, not arbitrary remote hyperlinks supplied in feed JSON.
- A linked provider must be disabled or legally reviewed if terms change; no deployment-ready acceptance until someone checks the current terms *again* at deployment time.
- If all internet feeds are disabled/unavailable, **Antenna Only** continues to use real local readsb observations if the USB/decoder and local network are working. Internet Only must say unavailable rather than invent an empty sky.
- Approval flag assignment and secrets provisioning are trusted-installation tasks, **not** anonymous web client options or a claim the user currently has a provider contract.

## Implementation and verification

Modified in branch `feature/flight-radar-provider-policy-2026-11-05` (stacked on `feature/flight-radar-center-2026-11-05`):
- `tihulu_runtime/flight_radar_sources.py`: third allowlisted provider, compliance checks, advertised attribution.
- `tests/test_flight_radar.py`: 5 new synthetic/mock-only consent, provider route, source-link and token tests, plus adjustment of the invalid-provider test. No live provider requests in test fixtures.
- `prototype/flight_radar.html` and `prototype/flight_radar.js`: network-source label and safe external provider terms links.

**Testing:** The parent Flight Radar Draft PR #4 had passing Python 3.11/3.12 mocked CI as observed before this patch. These new branch changes have NOT yet been observed passing in GitHub Actions; do not treat existing PR #4 CI as proof of this branch. Physical Pi5 receiver, ADS-B 1090 MHz traffic, offline map tiles, authenticated parent gateway and actual provider licensing/credential activation remain unresolved.

**Do not merge this patch to public main or into the independent standalone desktop repo without integration tests and review.**
