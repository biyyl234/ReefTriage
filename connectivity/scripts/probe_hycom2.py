"""Probe candidate HYCOM OPeNDAP URLs for uv3z velocity data."""
import xarray as xr

CANDIDATES = [
    "https://tds.hycom.org/thredds/dodsC/GLBy0.08/expt_93.0/uv3z",
    "https://tds.hycom.org/thredds/dodsC/GLBy0.08/expt_93.0/uv3z/2024",
    "https://tds.hycom.org/thredds/dodsC/GLBy0.08/expt_93.0_uv3z",
]

for url in CANDIDATES:
    print("=" * 60, flush=True)
    print("TRY:", url, flush=True)
    try:
        ds = xr.open_dataset(url, decode_times=True, chunks={})
    except Exception as e:
        print("  FAILED:", repr(e)[:200], flush=True)
        continue
    print("  OK vars:", list(ds.data_vars)[:10], flush=True)
    if "time" in ds:
        t = ds["time"]
        print("  time:", t.values[0], "->", t.values[-1], "n=", t.size, flush=True)
    if "depth" in ds:
        print("  depth[:8]:", ds["depth"].values[:8], flush=True)
    if "lon" in ds:
        print("  lon:", float(ds["lon"].min()), float(ds["lon"].max()), flush=True)
        print("  lat:", float(ds["lat"].min()), float(ds["lat"].max()), flush=True)
    ds.close()
print("DONE", flush=True)
