"""
Download NOAA CRW 5km DHW/SST regional subset for Semporna from ERDDAP.
- Current: last 30 days (CRW_DHW + CRW_SST)
- History: 2020-2025 (CRW_DHW only, for 5-year max)
"""
import requests
import time
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Paths
BASE = Path(r"C:\Users\biyyl234\Desktop\AI4Climatedemo\data")
RAW = BASE / "raw"
PROC = BASE / "processed"
RAW.mkdir(parents=True, exist_ok=True)
PROC.mkdir(parents=True, exist_ok=True)

# Region: Semporna
LAT_MIN, LAT_MAX = 4.0, 6.5
LON_MIN, LON_MAX = 118.0, 119.8

headers = {'User-Agent': 'ReefTriage-Research/1.0'}

# ERDDAP base
ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/NOAA_DHW.nc"

# Time ranges
# Current: 最近30天, 动态计算 (随"更新数据"拉到最新窗口)
_now = datetime.now(timezone.utc)
CURRENT_END   = _now.strftime("%Y-%m-%dT12:00:00Z")
CURRENT_START = (_now - timedelta(days=30)).strftime("%Y-%m-%dT12:00:00Z")
# History: 2020-2025 (用于5年最大DHW, 固定窗口)
HIST_START    = "2020-01-01T12:00:00Z"
HIST_END      = "2025-12-31T12:00:00Z"


def download_nc(url, outpath, label):
    """Download a netCDF file with retries."""
    outpath = Path(outpath)
    if outpath.exists() and outpath.stat().st_size > 1000:
        print(f"  [{label}] Already exists ({outpath.stat().st_size/1024:.0f} KB), skipping.")
        return True
    for attempt in range(4):
        try:
            print(f"  [{label}] Attempt {attempt+1}: downloading...")
            print(f"    URL: {url[:120]}...")
            r = requests.get(url, headers=headers, timeout=120, stream=True)
            if r.status_code == 200:
                total = int(r.headers.get('content-length', 0))
                print(f"    Size: {total/1024/1024:.1f} MB")
                with open(outpath, 'wb') as f:
                    downloaded = 0
                    for chunk in r.iter_content(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                sz = outpath.stat().st_size
                print(f"    Saved: {sz/1024/1024:.1f} MB -> {outpath.name}")
                return True
            elif r.status_code == 429:
                wait = 20 * (attempt + 1)
                print(f"    Rate limited (429), waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    HTTP {r.status_code}: {r.text[:300]}")
                time.sleep(10)
        except Exception as e:
            print(f"    Error: {e}, retrying...")
            time.sleep(10)
    return False


# ============================================================
# 1. Current DHW + SST (last 30 days)
# ============================================================
print("=" * 60)
print("1. Downloading CURRENT CRW data (last 30 days)...")
print("=" * 60)

current_url = (
    f"{ERDDAP}?"
    f"CRW_DHW[({CURRENT_START}):({CURRENT_END})]"
    f"[({LAT_MIN}):({LAT_MAX})]"
    f"[({LON_MIN}):({LON_MAX})],"
    f"CRW_SST[({CURRENT_START}):({CURRENT_END})]"
    f"[({LAT_MIN}):({LAT_MAX})]"
    f"[({LON_MIN}):({LON_MAX})]"
)

ok_current = download_nc(current_url, PROC / "crw_current.nc", "current")
print(f"  Result: {'OK' if ok_current else 'FAILED'}")

time.sleep(5)  # Be polite to ERDDAP

# ============================================================
# 2. Historical DHW (2020-2025, for 5-year max)
# ============================================================
print("\n" + "=" * 60)
print("2. Downloading HISTORICAL CRW DHW (2020-2025)...")
print("=" * 60)

hist_url = (
    f"{ERDDAP}?"
    f"CRW_DHW[({HIST_START}):({HIST_END})]"
    f"[({LAT_MIN}):({LAT_MAX})]"
    f"[({LON_MIN}):({LON_MAX})]"
)

ok_hist = download_nc(hist_url, PROC / "crw_history.nc", "history")
print(f"  Result: {'OK' if ok_hist else 'FAILED'}")

print("\n" + "=" * 60)
print(f"Summary: current={'OK' if ok_current else 'FAIL'}, history={'OK' if ok_hist else 'FAIL'}")
