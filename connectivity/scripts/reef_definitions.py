"""
reef_definitions.py
-------------------
Reef segment definitions for the Semporna (Sabah, Malaysia) larval connectivity model.

If `data/output/reef_segments.geojson` exists (produced by the data pipeline module),
it is read and used. Otherwise, the 15 placeholder reef points below are used,
each represented as a circle of ~1 km radius around its centroid.

Coordinates are (lat, lon) in decimal degrees, matching the HYCOM grid.
"""
import os
import json
import numpy as np

# Placeholder reefs: (name, lat, lon)
# Coordinates from the task brief + additional surrounding reefs to reach N=15.
PLACEHOLDER_REFS = [
    ("Sipadan",      4.12, 118.63),
    ("Mabul",        4.15, 118.63),
    ("Kapalai",      4.13, 118.62),
    ("Mataking",     4.16, 118.70),
    ("PomPom",       4.20, 118.73),
    ("Bodgaya",      4.68, 118.85),
    ("Boheydulang",  4.63, 118.83),
    ("Sibuan",       4.60, 118.85),
    ("Mantabuan",    4.58, 118.80),
    ("Tetagan",      4.55, 118.78),
    ("Maiga",        4.65, 118.82),
    ("Omada",        4.50, 118.75),
    ("Reef_12",      4.30, 118.68),
    ("Reef_14",      4.05, 118.55),
    ("Reef_15",      4.50, 118.90),
]

# Default settlement radius (~1 km at the equator ~= 0.009 deg lat)
SETTLE_RADIUS_KM = 1.0
KM_PER_DEG_LAT = 111.32


def load_reefs(geojson_path=None):
    """
    Return list of dicts: {id, name, lat, lon, radius_deg}.
    If geojson_path exists, derive centroids from polygon features.
    Otherwise use PLACEHOLDER_REFS.
    """
    if geojson_path and os.path.exists(geojson_path):
        with open(geojson_path, "r", encoding="utf-8") as f:
            gj = json.load(f)
        reefs = []
        for i, feat in enumerate(gj.get("features", [])):
            geom = feat.get("geometry", {})
            props = feat.get("properties", {})
            coords = geom.get("coordinates", [])
            # For Polygon or MultiPolygon, compute a rough centroid from all vertices
            lats, lons = [], []
            def walk(c):
                if isinstance(c[0], (int, float)):
                    lons.append(c[0]); lats.append(c[1])
                else:
                    for x in c: walk(x)
            walk(coords)
            if lats:
                reefs.append({
                    "id": i,
                    "name": props.get("name", f"reef_{i}"),
                    "lat": float(np.mean(lats)),
                    "lon": float(np.mean(lons)),
                    "radius_deg": SETTLE_RADIUS_KM / KM_PER_DEG_LAT,
                })
        if reefs:
            return reefs

    # Fallback: placeholders
    return [
        {"id": i, "name": name, "lat": lat, "lon": lon,
         "radius_deg": SETTLE_RADIUS_KM / KM_PER_DEG_LAT}
        for i, (name, lat, lon) in enumerate(PLACEHOLDER_REFS)
    ]


if __name__ == "__main__":
    g = load_reefs(os.path.join(os.path.dirname(__file__), "..", "..", "data",
                                 "output", "reef_segments.geojson"))
    print(f"Loaded {len(g)} reef segments:")
    for r in g:
        print(f"  {r['id']:2d} {r['name']:14s} lat={r['lat']:.3f} lon={r['lon']:.3f}")
