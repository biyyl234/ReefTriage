"""Verify depth.nc and inspect OSM reef data, then build reef segments."""
import xarray as xr
import json
import numpy as np
from pathlib import Path

PROC = Path(r"C:\Users\biyyl234\Desktop\AI4Climatedemo\data\processed")

# 1. Verify depth data
print("=== Depth Data ===")
ds = xr.open_dataset(PROC / "depth.nc")
print(ds)
z = ds['z']
print(f"\nDepth stats (z, negative=depth):")
print(f"  shape: {z.shape}")
print(f"  min: {float(z.min()):.1f} m, max: {float(z.max()):.1f} m")
print(f"  mean: {float(z.mean()):.1f} m")
# Find shallow areas (likely reefs)
shallow = z.where(z > -30)  # shallower than 30m
print(f"  Pixels shallower than 30m: {int(shallow.notnull().sum())}")
ds.close()

# 2. Read OSM reef points
print("\n=== OSM Reef Points ===")
with open(PROC / "dive_sites.geojson", 'r', encoding='utf-8') as f:
    gdata = json.load(f)

reef_points = []
for feat in gdata['features']:
    props = feat['properties']
    if props['type'] in ['reef', 'dive_site']:
        lon, lat = feat['geometry']['coordinates']
        reef_points.append((lat, lon, props.get('name', 'unnamed'), props['type']))

print(f"Reef/dive points: {len(reef_points)}")
for p in reef_points[:15]:
    print(f"  {p[2]}: ({p[0]:.4f}, {p[1]:.4f}) [{p[3]}]")
