"""Verify downloaded CRW netCDF files and inspect their structure."""
import xarray as xr
from pathlib import Path

PROC = Path(r"C:\Users\biyyl234\Desktop\AI4Climatedemo\data\processed")

for fname in ["crw_current.nc", "crw_history.nc"]:
    fpath = PROC / fname
    print(f"\n{'='*60}")
    print(f"File: {fname} ({fpath.stat().st_size/1024/1024:.1f} MB)")
    print('='*60)
    ds = xr.open_dataset(fpath)
    print(ds)
    print(f"\nTime range: {ds.time.values[0]} to {ds.time.values[-1]}")
    print(f"Lat range: {ds.latitude.values.min():.3f} to {ds.latitude.values.max():.3f}")
    print(f"Lon range: {ds.longitude.values.min():.3f} to {ds.longitude.values.max():.3f}")
    # Quick stats on DHW
    if 'CRW_DHW' in ds:
        dhw = ds['CRW_DHW']
        print(f"\nCRW_DHW stats:")
        print(f"  shape: {dhw.shape}")
        print(f"  min: {float(dhw.min()):.2f}, max: {float(dhw.max()):.2f}, mean: {float(dhw.mean()):.2f}")
    if 'CRW_SST' in ds:
        sst = ds['CRW_SST']
        print(f"\nCRW_SST stats:")
        print(f"  shape: {sst.shape}")
        print(f"  min: {float(sst.min()):.2f}, max: {float(sst.max()):.2f}, mean: {float(sst.mean()):.2f}")
    ds.close()
