"""Probe HYCOM GLBy0.08 expt_93.0 OPeNDAP dataset structure."""
import xarray as xr
import sys

URL = "https://tds.hycom.org/thredds/dodsC/GLBy0.08/expt_93.0"

print("Opening:", URL, flush=True)
try:
    ds = xr.open_dataset(URL, decode_times=True, chunks={})
except Exception as e:
    print("OPEN FAILED:", repr(e))
    sys.exit(1)

print("\n=== Variables ===", flush=True)
for v in ds.data_vars:
    print(f"  {v}: dims={ds[v].dims}, shape={ds[v].shape}", flush=True)

print("\n=== Coords ===", flush=True)
for c in ds.coords:
    print(f"  {c}: dims={ds[c].dims}, shape={ds[c].shape}", flush=True)

print("\n=== Time range ===", flush=True)
t = ds["time"]
print("  first:", t.values[0], flush=True)
print("  last :", t.values[-1], flush=True)
print("  n times:", t.size, flush=True)

print("\n=== Depth levels ===", flush=True)
d = ds["depth"]
print("  values:", d.values[:15], flush=True)

print("\n=== Lon/Lat bounds ===", flush=True)
print("  lon:", float(ds["lon"].min()), "->", float(ds["lon"].max()), flush=True)
print("  lat:", float(ds["lat"].min()), "->", float(ds["lat"].max()), flush=True)

ds.close()
print("\nDONE", flush=True)
