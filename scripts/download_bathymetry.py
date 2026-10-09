"""Download ETOPO 2022 bathymetry regional subset for Semporna."""
import requests
import time
from pathlib import Path

PROC = Path(r"C:\Users\biyyl234\Desktop\AI4Climatedemo\data\processed")
PROC.mkdir(parents=True, exist_ok=True)

headers = {'User-Agent': 'ReefTriage-Research/1.0'}

LAT_MIN, LAT_MAX = 4.0, 6.5
LON_MIN, LON_MAX = 118.0, 119.8

# ETOPO_2022_v1_15s uses -180..180 lon. Variable is "z" (elevation/bathymetry in meters)
# Negative = depth below sea level.
BASE = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/ETOPO_2022_v1_15s.nc"

outpath = PROC / "depth.nc"

# Build subset URL: z[(lat_min):(lat_max)][(lon_min):(lon_max)]
# Note: latitude in ETOPO is usually north-to-south (high to low)
url = (
    f"{BASE}?"
    f"z[({LAT_MAX}):({LAT_MIN})]"
    f"[({LON_MIN}):({LON_MAX})]"
)

print(f"Downloading bathymetry from ETOPO 2022 15s...")
print(f"Region: lat {LAT_MIN}-{LAT_MAX}, lon {LON_MIN}-{LON_MAX}")

for attempt in range(4):
    try:
        print(f"Attempt {attempt+1}...")
        r = requests.get(url, headers=headers, timeout=180, stream=True)
        if r.status_code == 200:
            total = int(r.headers.get('content-length', 0))
            print(f"  Size: {total/1024:.0f} KB")
            with open(outpath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=65536):
                    f.write(chunk)
            sz = outpath.stat().st_size
            print(f"  Saved: {sz/1024:.0f} KB -> depth.nc")
            break
        elif r.status_code == 429:
            wait = 30 * (attempt + 1)
            print(f"  Rate limited (429), waiting {wait}s...")
            time.sleep(wait)
        else:
            print(f"  HTTP {r.status_code}: {r.text[:300]}")
            time.sleep(15)
    except Exception as e:
        print(f"  Error: {e}")
        time.sleep(15)
else:
    print("FAILED to download bathymetry after all retries.")
