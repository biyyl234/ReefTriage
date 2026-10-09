"""Test whether NCSS honors vertCoord=15.0, and fall back to all-depths if needed."""
import requests
import xarray as xr
import io

NCSS = "https://ncss.hycom.org/thredds/ncss/grid/GLBy0.08/expt_93.0/uv3z"

# Try requesting ONLY depth=15
params = [
    ("var", "water_u"),
    ("var", "water_v"),
    ("north", "6.5"), ("south", "4.0"), ("west", "118.0"), ("east", "119.8"),
    ("vertCoord", "15.0"),
    ("time_start", "2024-09-04T00:00:00Z"),
    ("time_end", "2024-09-04T00:00:00Z"),
    ("accept", "netcdf"),
]
r = requests.get(NCSS, params=params, timeout=120)
print("status:", r.status_code, "bytes:", len(r.content))
ds = xr.open_dataset(io.BytesIO(r.content))
print("depsts returned:", ds["depth"].values)
print("vars:", list(ds.data_vars))
ds.close()
