# Data Provenance Summary — ReefTriage Reef Lab (micro page)

> Generated: 2026-09-28. This document summarizes the sources for the new deliverables
> added for the Reef Lab micro-page. All values are tagged `data_source` in each JSON.

## 1. Environmental data (`data/output/environmental/R*.json`)

| Variable | Source | Type |
|---|---|---|
| `dhw_history`, `dhw_max_observed` | NOAA Coral Reef Watch v3.1, 5 km daily, from `data/processed/crw_history.nc` (2020-01 to 2025-12) and `crw_current.nc` (2026-08 to 2026-09) | **Observed** |
| `sst.monthly`, `sst.mean/min/max` | Literature Sulu Sea surface climatology (~27.4–29.8 °C), NOAA OI SST-based | Literature |
| `sst.observed_snapshot_aug_sep_2026` | CRW current file, 30-day mean SST at each segment grid cell | **Observed** |
| `salinity` | Literature: Sulu Sea surface ~33–34 PSU; offshore vs. coastal offset | Literature |
| `ph` | Literature: tropical surface seawater ~8.0 | Literature |
| `do` | Literature: well-oxygenated tropical reef water ~4.5 ml/L | Literature |
| `chlorophyll` | Literature: oligotrophic Sulu Sea ~0.15 mg/m³ offshore, higher near coast | Literature |
| `current` | Literature: Sulu Sea surface circulation ~SE, 0.2–0.3 m/s | Literature |
| `arag` (aragonite saturation) | Literature/simulated: tropical Ω_ar ~3.0–3.5 | Literature |

### Copernicus Marine — attempted, degraded

- Datasets requested: `GLOBAL_ANALYSIS_FORECAST_PHY_001_024` (physics) and
  `GLOBAL_MULTIYEAR_BGC_001_029` (biogeochemistry).
- Method attempted: `copernicusmarine` Python toolbox (installed into `.venv`),
  `copernicusmarine subset` for the Semporna box (lat 4.0–5.0, lon 118.5–119.5).
- Result: **requires a registered Copernicus Marine username/password** (free sign-up at
  https://data.marine.copernicus.eu/register). Per project instructions, we did not attempt
  login and degraded to CRW-observed + literature values.
- To upgrade later: register a free account, then run
  `copernicusmarine login` and re-run a subset download for SST/salinity/pH/DO/chl-a.

## 2. Monitoring data (`data/output/monitoring/R*.json`)

| Field | Source | Type |
|---|---|---|
| `rhi_score`, `rhi_components` | Literature-anchored estimates per reef group (Sipadan/Mabul/Kapalai/Tun Sakaran/Eastern/Western/Bum Bum/Kalampunian/Semporna Port); weights documented in each file | Literature estimate |
| `cover_trend` | Hard coral cover 2018–2025; shows 2024 bleaching dip (×0.72) and 2025 partial recovery (×0.80) | Literature estimate |
| `bleaching_events` | 2010 (moderate, DHW 5.2), 2016 (severe, DHW 10.5), 2024 (severe, DHW 11.3) — from Reef Check Malaysia 2026, NOAA CRW, published Malaysia bleaching literature | Literature |
| `images` | Reference illustrations in `app/frontend/img/coral/`; see `SOURCES.md` for attribution | Reference images |

### Key literature references

- Reef Check Malaysia, *Malaysia Bleaching Response Plan 2026–2030*: 2024 4th global bleaching
  event affected ~90 % of surveyed Malaysian sites, 34.1 % average mortality.
- Coralku, *The 4th global coral bleaching event in Malaysia*: 2024 event details.
- NOAA CRW DHW thresholds: 4 = bleaching expected, 8 = widespread bleaching, 16 = mortality.

## 3. Coral reference images (`app/frontend/img/coral/`)

See `app/frontend/img/coral/SOURCES.md` for per-file attribution. Images are reference
illustrations retrieved from public web sources during the demo build; replace with CC-licensed
imagery (CoralNet, Allen Coral Atlas, Wikimedia Commons, NOAA CRCP) before public release.

## 4. AI model research (`docs/ai_model_research.md`)

- Best browser-feasible option identified: `akridge/yolo11n-cls-noaa-esd-coral-bleaching`
  (ONNX, ~5 MB, 85 % accuracy, AGPL-3.0, binary healthy/bleached).
- CoralNet Deploy API is cloud-only (requires account, server-side inference).
- Implemented fallback: `app/frontend/lib/color_analyzer.js` (HSV white-fraction heuristic,
  calibrated against the 4 reference images: healthy ~25 %, mild ~53 %, moderate ~82 %,
  severe ~98 %).

## 5. What is observed vs. simulated

- **Observed (real, from NOAA satellites):** daily DHW 2020–2026, 30-day SST snapshot 2026-08/09.
- **Literature-anchored (estimated):** monthly SST climatology, salinity, pH, DO, chl-a, current,
  aragonite, RHI components, cover trend, bleaching event history.
- All simulated/literature values are explicitly labeled in each JSON's `provenance_note` and
  `source` fields.
