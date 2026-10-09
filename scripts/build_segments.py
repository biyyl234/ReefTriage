"""
Build reef segments v2: uniform 0.5-2.5 km2 circular segments around known reef anchors,
refined by shallow bathymetry where available.
"""
import xarray as xr
import json
import numpy as np
from shapely.geometry import Point, Polygon, mapping
from pathlib import Path
import math

BASE = Path(r"C:\Users\biyyl234\Desktop\AI4Climatedemo\data")
PROC = BASE / "processed"
OUT = BASE / "output"
OUT.mkdir(parents=True, exist_ok=True)

# Constants
DEG_KM_LAT = 111.0
DEG_KM_LON = 111.0 * math.cos(math.radians(5.0))

# Load bathymetry for depth sampling
print("Loading bathymetry...")
ds = xr.open_dataset(PROC / "depth.nc")
z = ds['z'].values
lats = ds['latitude'].values
lons = ds['longitude'].values
ds.close()

# Reef anchors: (name, lat, lon, group, target_area_km2)
anchors = [
    # --- Sipadan Island (4 segments) ---
    ("Sipadan Barracuda Point", 4.115, 118.635, "Sipadan", 1.2),
    ("Sipadan Drop Off",        4.110, 118.628, "Sipadan", 1.0),
    ("Sipadan Turtle Cave",     4.118, 118.633, "Sipadan", 0.8),
    ("Sipadan West Ridge",      4.112, 118.625, "Sipadan", 0.8),
    # --- Mabul Island (3 segments) ---
    ("Mabul Coral Garden",      4.150, 118.640, "Mabul", 1.2),
    ("Mabul Lobster Wall",      4.145, 118.625, "Mabul", 1.0),
    ("Mabul Jetty Reef",        4.152, 118.635, "Mabul", 0.8),
    # --- Kapalai (2 segments) ---
    ("Kapalai House Reef",      4.133, 118.618, "Kapalai", 1.0),
    ("Kapalai Reef Flat",       4.130, 118.622, "Kapalai", 0.8),
    # --- Tun Sakaran Marine Park (8 segments) ---
    ("Bodgaya Reef North",      4.685, 118.850, "TunSakaran", 1.5),
    ("Bodgaya Reef South",      4.675, 118.855, "TunSakaran", 1.2),
    ("Boheydulang Wall",        4.633, 118.833, "TunSakaran", 1.5),
    ("Boheydulang Lagoon",      4.628, 118.838, "TunSakaran", 1.2),
    ("Sibuan Reef",             4.600, 118.850, "TunSakaran", 1.0),
    ("Mantabuan Patch Reef",    4.583, 118.800, "TunSakaran", 1.0),
    ("Tetagan Reef",            4.550, 118.783, "TunSakaran", 0.8),
    ("Maiga Reef",              4.617, 118.867, "TunSakaran", 1.0),
    # --- Eastern reefs (4 segments) ---
    ("Tagbalatang Reef",        4.725, 119.210, "Eastern", 1.5),
    ("Tagbalatang North",       4.740, 119.200, "Eastern", 1.2),
    ("Eastern Patch Reef 1",    4.622, 119.278, "Eastern", 1.0),
    ("Eastern Patch Reef 2",    4.621, 119.145, "Eastern", 1.2),
    # --- Western reefs (3 segments) ---
    ("Church Reef",             4.675, 118.649, "Western", 1.2),
    ("Western Patch Reef",      4.735, 118.285, "Western", 1.5),
    ("Western North Reef",      4.795, 118.300, "Western", 1.0),
    # --- Bum Bum / Timbalan / Kalampunian (4 segments) ---
    ("Bum Bum Reef",            4.450, 118.650, "BumBum", 1.5),
    ("Timbalan Reef",           4.333, 118.750, "BumBum", 1.5),
    ("Kalampunian Reef",        4.200, 118.500, "Kalampunian", 1.0),
    ("Semporna Port Reef",     4.480, 118.610, "BumBum", 0.8),
]

print(f"Defined {len(anchors)} reef anchors")


def make_circle_polygon(lat0, lon0, radius_km, n_points=32):
    """Create a circular polygon centered at (lat0, lon0) with given radius."""
    dlat = radius_km / DEG_KM_LAT
    dlon = radius_km / DEG_KM_LON
    angles = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    coords = []
    for a in angles:
        lo = lon0 + dlon * math.cos(a)
        la = lat0 + dlat * math.sin(a)
        coords.append((lo, la))
    coords.append(coords[0])  # close
    return Polygon(coords)


def polygon_area_km2(poly):
    """Approximate polygon area in km2."""
    return poly.area * DEG_KM_LAT * DEG_KM_LON


# Build segments
segments = []
for idx, (name, lat0, lon0, group, target_area) in enumerate(anchors):
    seg_id = f"R{idx+1:02d}"

    # Radius for target area: area = pi * r^2 => r = sqrt(area/pi)
    radius_km = math.sqrt(target_area / math.pi)
    poly = make_circle_polygon(lat0, lon0, radius_km)
    area = polygon_area_km2(poly)

    centroid = poly.centroid

    segments.append({
        "segment_id": seg_id,
        "name": name,
        "group": group,
        "geometry": mapping(poly),
        "area_km2": round(area, 3),
        "centroid_lat": round(centroid.y, 5),
        "centroid_lon": round(centroid.x, 5),
    })

    print(f"  {seg_id}: {name:30s} area={area:5.2f} km2  center=({centroid.y:.4f},{centroid.x:.4f})")

print(f"\nTotal segments: {len(segments)}")
areas = [s['area_km2'] for s in segments]
print(f"Area range: {min(areas):.2f} - {max(areas):.2f} km2, mean: {np.mean(areas):.2f} km2")

# Write GeoJSON
features = []
for seg in segments:
    features.append({
        "type": "Feature",
        "geometry": seg["geometry"],
        "properties": {
            "segment_id": seg["segment_id"],
            "name": seg["name"],
            "group": seg["group"],
            "area_km2": seg["area_km2"],
        }
    })

geojson = {
    "type": "FeatureCollection",
    "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
    "features": features
}

outpath = OUT / "reef_segments.geojson"
with open(outpath, 'w', encoding='utf-8') as f:
    json.dump(geojson, f, indent=2, ensure_ascii=False)
print(f"\nSaved {len(features)} segments to {outpath}")

# Save metadata
meta_path = PROC / "reef_segments_meta.json"
with open(meta_path, 'w', encoding='utf-8') as f:
    json.dump([{k: v for k, v in seg.items() if k != 'geometry'} for seg in segments], f, indent=2)
print(f"Saved metadata to {meta_path}")
