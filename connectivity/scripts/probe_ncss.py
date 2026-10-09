"""Probe NCSS with a tiny request to confirm variable names and depth levels."""
import requests
import xarray as xr
import io

NCSS = "https://ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z"

params = {
    "var": "water_u",
    "var": "water_v",
    "north": "6.5", "south": "4.0", "west": "118.0", "east": "119.8",
    "time_start": "2024-09-04T00:00:00Z",
    "time_end": "2024-09-04T00:00:00Z",
    "accept": "netcdf",
}
print("Requesting tiny subset...", flush=True)
r = requests.get(NCSS, params=params, timeout=120)
print("status:", r.status_code, "bytes:", len(r.content), flush=True)
if r.status_code != 200:
    print(r.text[:1000])
    raise SystemExit(1)

ds = xr.open_dataset(io.BytesIO(r.content))
print("vars:", list(ds.data_vars), flush=True)
print("coords:", list(ds.coords), flush=True)
print("time:", ds["time"].values, flush=True)
print("depth levels:", ds["depth"].values, flush=True)
print("lon range:", float(ds["lon"].min()), float(ds["lon"].max()), flush=True)
print("lat range:", float(ds["lat"].min()), float(ds["lat"].max()), flush=True)
print("water_u shape:", ds["water_u"].shape, flush=True)
ds.close()
print("PROBE OK", flush=True)
