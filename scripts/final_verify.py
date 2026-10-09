"""Final verification of all deliverables."""
import json
import pandas as pd
from pathlib import Path
import geopandas as gpd

OUT = Path(r"C:\Users\biyyl234\Desktop\AI4Climatedemo\data\output")
PROC = Path(r"C:\Users\biyyl234\Desktop\AI4Climatedemo\data\processed")

print("=" * 60)
print("FINAL VERIFICATION")
print("=" * 60)

# 1. reef_segments.geojson
print("\n1. reef_segments.geojson")
gdf = gpd.read_file(OUT / "reef_segments.geojson")
print(f"   Features: {len(gdf)}")
print(f"   CRS: {gdf.crs}")
print(f"   Area range: {gdf.area.min()*111*111:.1f} - {gdf.area.max()*111*111:.1f} km2 (approx)")
print(f"   Columns: {list(gdf.columns)}")
print(f"   IDs: {list(gdf['segment_id'])}")

# 2. reef_features.csv
print("\n2. reef_features.csv")
df = pd.read_csv(OUT / "reef_features.csv")
print(f"   Rows: {len(df)}")
print(f"   Columns: {list(df.columns)}")
print(f"   NaN count: {df.isna().sum().sum()}")
print(f"   Segment IDs match: {set(df['segment_id']) == set(gdf['segment_id'])}")

# 3. Check processed files exist
print("\n3. Processed files:")
for f in ["crw_current.nc", "crw_history.nc", "depth.nc", "dive_sites.geojson"]:
    p = PROC / f
    sz = p.stat().st_size / 1024 / 1024 if p.exists() else 0
    print(f"   {f:30s}: {sz:.1f} MB {'OK' if p.exists() else 'MISSING'}")

# 4. Output files
print("\n4. Output files:")
for f in ["reef_segments.geojson", "reef_features.csv", "DATA_SOURCES.md"]:
    p = OUT / f
    print(f"   {f:30s}: {'OK' if p.exists() else 'MISSING'}")

# 5. Quick data sanity
print("\n5. Data sanity:")
print(f"   current_dhw range: {df['current_dhw'].min():.1f} - {df['current_dhw'].max():.1f}")
print(f"   current_sst range: {df['current_sst'].min():.1f} - {df['current_sst'].max():.1f}")
print(f"   max_dhw_5yr range: {df['max_dhw_5yr'].min():.1f} - {df['max_dhw_5yr'].max():.1f}")
print(f"   mean_depth range: {df['mean_depth'].min():.1f} - {df['mean_depth'].max():.1f} m")
print(f"   dive sites within 5km: mean={df['dive_sites_within_5km'].mean():.1f}")
print(f"   nearest dive dist: {df['distance_to_nearest_dive_site_km'].min():.1f} - {df['distance_to_nearest_dive_site_km'].max():.1f} km")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
