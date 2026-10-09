# Data Sources — ReefTriage Semporna Pipeline

> Download date: 2026-09-24
> Region: Semporna, Sabah, Malaysia — lon 118.0°E–119.8°E, lat 4.0°N–6.5°N
> CRS: WGS84 (EPSG:4326)

---

## 1. NOAA Coral Reef Watch (CRW) 5 km Daily

| Item | Detail |
|---|---|
| Product | NOAA CRW Operational Daily Near-Real-Time Sea Surface Temperature & Degree Heating Weeks, v3.1 |
| Variables | `CRW_DHW` (°C-weeks), `CRW_SST` (°C) |
| Resolution | 0.05° (~5 km), daily |
| Source | NOAA CoastWatch ERDDAP (PacIOOS redistribution) |
| Dataset ID | `NOAA_DHW` |
| URL | https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW |
| Current file | `data/processed/crw_current.nc` — 2026-08-24 to 2026-09-22 (30 days), DHW + SST |
| History file | `data/processed/crw_history.nc` — 2020-01-01 to 2025-12-31 (2187 days), DHW only |
| Region subset | lat 4.0–6.5, lon 118.0–119.8 (51 × 37 grid cells) |
| Access method | ERDDAP OPeNDAP netCDF subset (.nc) |
| Notes | Time coverage extends to 2026-09-22. DHW max over 2020–2025 used for `max_dhw_5yr`. Latest time step used for `current_dhw` / `current_sst`. |

## 2. ETOPO 2022 Bathymetry

| Item | Detail |
|---|---|
| Product | ETOPO 2022 Global Relief Model v1, 15 arc-second resolution |
| Variable | `z` (elevation/bathymetry in metres; negative = below sea level) |
| Resolution | 15 arc-sec (~300 m at equator) |
| Source | NOAA NCEI via CoastWatch ERDDAP |
| Dataset ID | `ETOPO_2022_v1_15s` |
| URL | https://www.ncei.noaa.gov/products/etopo-global-relief-model |
| File | `data/processed/depth.nc` — lat 4.0–6.5, lon 118.0–119.8 (601 × 433 cells) |
| Access method | ERDDAP OPeNDAP netCDF subset |
| Notes | Used for `mean_depth` and `min_depth` where shallow pixels (≤30 m) fall within reef segment polygons. For narrow offshore seamount reefs (Sipadan, Mabul, Kapalai) that ETOPO 15 s cannot resolve, literature-based depth estimates were used (see §6). |

## 3. OpenStreetMap Dive Sites & Reef Features

| Item | Detail |
|---|---|
| Source | OpenStreetMap via Overpass API |
| Endpoint | https://overpass-api.de/api/interpreter |
| Query bbox | (4.0, 118.0, 6.5, 119.8) |
| Tags queried | `natural=reef`, `leisure=marina`, `amenity=diving_center`, `place=islet/island`, plus known dive sites |
| File | `data/processed/dive_sites.geojson` — 346 features (114 reef, 181 coastline, 11 islet, 10 island, 4 marina, 10 known dive sites) |
| Access method | Overpass QL POST query, JSON output |
| Notes | Used for `distance_to_nearest_dive_site_km` and `dive_sites_within_5km`. Known dive sites (Barracuda Point, Coral Garden, etc.) were added manually as OSM coverage for named dive sites is incomplete. |

## 4. Allen Coral Atlas (ACA) — NOT DOWNLOADED

| Item | Detail |
|---|---|
| Status | **Not downloaded (degraded)** |
| Reason | ACA geomorphology GeoTIFF requires interactive download via web portal or ACAP tool; no direct OPeNDAP/ERDDAP regional subset endpoint was available for automated scripting. |
| Fallback used | Reef segment locations were derived from (a) known island/reef coordinates from literature and agent-provided references, and (b) OSM `natural=reef` points. ETOPO shallow-water pixels were used to inform segment placement where available. |
| Files | `data/output/reef_segments.geojson` — 28 circular segments (0.8–1.5 km² each) |

## 5. UNEP-WCMC Global Coral Reef Distribution — NOT DOWNLOADED

| Item | Detail |
|---|---|
| Status | **Not downloaded (not needed)** |
| Reason | ACA was the preferred reef-map source; when ACA proved inaccessible, known reef coordinates + OSM reef points were sufficient to define 28 segments covering all major reef groups. UNEP-WCMC polygons would refine segment shapes but are not required for the feature pipeline. |

## 6. Literature Depth Estimates (21 of 28 segments)

For segments where ETOPO 15 s did not resolve shallow reef pixels (narrow seamount crests, island fringing reefs), depths were estimated from published dive-site descriptions:

| Segment | Est. mean depth (m) | Est. min depth (m) | Basis |
|---|---|---|---|
| R01–R04 Sipadan | 5–8 | 1–2 | Known wall dives: reef crest at 1–5 m, wall drops to 30 m+ |
| R05–R07 Mabul | 3–10 | 1–3 | House reef / muck dive sites, shallow flat |
| R08–R09 Kapalai | 2–3 | 0.5 | Sand cay, shallow reef flat |
| R10–R11 Bodgaya | 5–8 | 1–2 | Fringing reef in Tun Sakaran |
| R14 Sibuan | 3 | 1 | Sandbar reef |
| R15 Mantabuan | 10 | 3 | Patch reef |
| R16 Tetagan | 5 | 1 | Fringing reef |
| R17 Maiga | 5 | 1 | Fringing reef |
| R18 Tagbalatang | 8 | 2 | Offshore reef |
| R20 Eastern Patch 1 | 15 | 5 | Offshore patch reef |
| R22 Church Reef | 12 | 4 | Known reef |
| R24 Western North | 15 | 5 | Offshore reef |
| R27 Kalampunian | 10 | 3 | Offshore island reef |
| R28 Semporna Port | 5 | 2 | Coastal reef |

**Depth source per segment is recorded in the `depth_source` column of `reef_features.csv`** (`etopo_2022` = 7 segments measured, `literature_estimate` = 21 segments estimated).

---

## 7. Output Files

| File | Description |
|---|---|
| `data/output/reef_segments.geojson` | 28 reef segment polygons (WGS84), properties: segment_id, name, group, area_km2 |
| `data/output/reef_features.csv` | 28 rows × 13 columns: segment_id, name, current_dhw, current_sst, max_dhw_5yr, mean_depth, min_depth, reef_area_km2, distance_to_nearest_dive_site_km, dive_sites_within_5km, lat, lon, depth_source |
| `data/processed/crw_current.nc` | CRW DHW+SST, last 30 days |
| `data/processed/crw_history.nc` | CRW DHW, 2020–2025 |
| `data/processed/depth.nc` | ETOPO 2022 regional bathymetry |
| `data/processed/dive_sites.geojson` | OSM POIs + known dive sites |

## 8. Data Quality & Limitations

1. **CRW resolution (5 km)**: Each reef segment (~1 km²) is much smaller than the CRW pixel. All segments within ~25 km share nearly identical DHW/SST values. This is expected — CRW is a regional thermal stress indicator, not a segment-scale measurement.
2. **Bathymetry resolution (300 m)**: ETOPO 15 s cannot resolve narrow reef crests on offshore seamounts (Sipadan rises from 500 m to <5 m). 21/28 segments use literature depth estimates.
3. **Reef segments are circular buffers**: Without ACA geomorphology polygons, segments are approximate circles around known reef locations. Future work should replace these with ACA-derived reef boundaries.
4. **Current DHW ≈ 0**: As of 2026-09-22, the region is in cool-season conditions with negligible heat stress. Historical max DHW (2020–2025) shows the expected 2024 bleaching event signature (max 11.3 °C-weeks).
