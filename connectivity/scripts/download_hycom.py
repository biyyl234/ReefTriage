"""
Download HYCOM u/v for two depth layers (0 m and 15 m) separately, then merge.
NCSS grid service only honored the first vertCoord when both were passed,
so we fetch depth=0 and depth=15 as two requests and concatenate.
"""
import requests
import xarray as xr
import io
import os
import time as _time

NCSS = "https://ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z"
OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "hycom_uv_30d.nc"))

TIME_START = "2024-08-06T00:00:00Z"
TIME_END   = "2024-09-05T09:00:00Z"
DEPTHS = [0.0, 15.0]

def fetch_depth(depth):
    params = [
        ("var", "water_u"),
        ("var", "water_v"),
        ("north", "6.5"), ("south", "4.0"),
        ("west", "118.0"), ("east", "119.8"),
        ("vertCoord", str(depth)),
        ("time_start", TIME_START),
        ("time_end", TIME_END),
        ("accept", "netcdf"),
    ]
    print(f"  fetching depth={depth} m ...", flush=True)
    t0 = _time.time()
    r = requests.get(NCSS, params=params, timeout=600)
    dt = _time.time() - t0
    print(f"    HTTP {r.status_code}, {len(r.content)/1e6:.1f} MB in {dt:.0f}s", flush=True)
    if r.status_code != 200:
        print(r.text[:800]); raise SystemExit(1)
    return xr.open_dataset(io.BytesIO(r.content))

parts = [fetch_depth(d) for d in DEPTHS]
ds = xr.concat(parts, dim="depth").sortby("depth")

print("\n=== Merged dataset ===", flush=True)
print("  vars:", list(ds.data_vars), flush=True)
print("  time steps:", ds.sizes["time"], flush=True)
print("  first:", ds["time"].values[0], flush=True)
print("  last :", ds["time"].values[-1], flush=True)
print("  depths:", ds["depth"].values, flush=True)
print("  lon:", float(ds["lon"].min()), "->", float(ds["lon"].max()), flush=True)
print("  lat:", float(ds["lat"].min()), "->", float(ds["lat"].max()), flush=True)
print("  u range: %.3f to %.3f m/s" % (float(ds["water_u"].min()), float(ds["water_u"].max())), flush=True)
print("  v range: %.3f to %.3f m/s" % (float(ds["water_v"].min()), float(ds["water_v"].max())), flush=True)

os.makedirs(os.path.dirname(OUT), exist_ok=True)
ds.to_netcdf(OUT)
for p in parts: p.close()
print(f"\nSaved: {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB)", flush=True)
print("DONE", flush=True)
