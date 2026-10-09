"""
Fallback: Copernicus Marine anonymous download is NOT possible (requires free
registered account). We keep all literature values and only update the
provenance_note + add a copernicus_attempt metadata block so downstream
consumers know exactly what was tried and why.

dhw_history (NOAA CRW observed) is untouched.
"""
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(r"C:\Users\biyyl234\Desktop\AI4Climatedemo")
ENV_DIR = ROOT / "data" / "output" / "environmental"

ATTEMPT_UTC = "2026-09-28T03:56Z"
ATTEMPT_NOTE = (
    "Copernicus Marine download attempted 2026-09-28 by scripts/probe_cmems.py "
    "(copernicusmarine v2.4.1). Anonymous access rejected: "
    "'Downloading Copernicus Marine data requires a Copernicus Marine username "
    "and password' (free signup at https://data.marine.copernicus.eu/register). "
    "No ~/.copernicusmarine credentials file, no COPERNICUSMARINE_SERVICE_USERNAME/"
    "PASSWORD env vars on this machine. SST/salinity/pH/DO/chl-a/current/aragonite "
    "therefore remain literature-estimated; only dhw_history is NOAA CRW observed. "
    "To upgrade to real Copernicus data: (1) register at the URL above, "
    "(2) run `copernicusmarine login` or set env vars, "
    "(3) re-run scripts/download_copernicus.py (TODO)."
)

NEW_PROVENANCE = (
    "DHW time series: NOAA CRW v3.1 5km daily (observed, 2020-2025). "
    "SST/salinity/pH/DO/chl-a/current/aragonite: literature typical values "
    "with per-segment offsets (offshore vs coastal) — NOT Copernicus. "
    + ATTEMPT_NOTE
)

report = []
for p in sorted(ENV_DIR.glob("R*.json")):
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)

    sid = data.get("segment_id", p.stem)
    n_dhw = len(data.get("dhw_history", []))

    data["provenance_note"] = NEW_PROVENANCE
    # data_source stays "crw_observed_plus_literature" — we did NOT swap to
    # copernicus_marine because no real data was downloaded.

    data["copernicus_attempt"] = {
        "attempted_at_utc": ATTEMPT_UTC,
        "toolbox_version": "copernicusmarine 2.4.1",
        "status": "auth_required_no_credentials",
        "anonymous_access": False,
        "error_message": (
            "Downloading Copernicus Marine data requires a Copernicus Marine "
            "username and password."
        ),
        "target_datasets": {
            "phy": "GLOBAL_ANALYSISFORECAST_PHY_001_024 "
                   "(cmems_mod_glo_phy_anfc_merged-uv_PT1H-i etc.; "
                   "vars thetao/so/uo/vo)",
            "bgc": "GLOBAL_ANALYSISFORECAST_BGC_001_029 "
                   "(near-real-time) / GLOBAL_MULTIYEAR_BGC_001_029 "
                   "(reanalysis); vars ph/o2/chl/no3/po4/si/arag",
        },
        "region_bbox": {"lat": [4.0, 5.0], "lon": [118.5, 119.5]},
        "depth_range_m": [0, 50],
        "outcome": "kept_literature_values_pending_user_credentials",
        "next_step": "Provide Copernicus Marine username + password "
                     "(free signup at https://data.marine.copernicus.eu/register), "
                     "then re-run download.",
    }

    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")

    report.append((sid, n_dhw))

print(f"Updated {len(report)} files in {ENV_DIR}")
for sid, n in report:
    print(f"  {sid}: dhw_history kept = {n} entries")
