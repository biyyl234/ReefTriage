"""
Query OpenStreetMap Overpass API for dive sites, reefs, and tourism POIs
in the Semporna region.
"""
import requests
import json
import time
from pathlib import Path

BASE = Path(r"C:\Users\biyyl234\Desktop\AI4Climatedemo\data")
PROC = BASE / "processed"
PROC.mkdir(parents=True, exist_ok=True)

# Semporna bounding box: (south, west, north, east)
BBOX = "(4.0,118.0,6.5,119.8)"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

# Query: dive sites, reefs, marinas, tourism-related nodes and ways
QUERY = f"""
[out:json][timeout:60];
(
  node["natural"="reef"]{BBOX};
  way["natural"="reef"]{BBOX};
  node["tourism"="information"]["information"="dive"]{BBOX};
  node["leisure"="marina"]{BBOX};
  way["leisure"="marina"]{BBOX};
  node["amenity"="diving_center"]{BBOX};
  way["amenity"="diving_center"]{BBOX};
  node["tourism"="hotel"]["name"~"div|dive|resort|sipadan|mabul|kapalai",i]{BBOX};
  node["place"="islet"]{BBOX};
  way["place"="islet"]{BBOX};
  node["place"="island"]{BBOX};
  way["place"="island"]{BBOX};
);
out center tags;
"""


def query_overpass():
    for url in OVERPASS_URLS:
        for attempt in range(2):
            try:
                print(f"Trying {url} (attempt {attempt+1})...")
                r = requests.post(url, data=QUERY, timeout=90,
                                 headers={'User-Agent': 'ReefTriage-Research/1.0'})
                if r.status_code == 200:
                    return r.json()
                else:
                    print(f"  HTTP {r.status_code}: {r.text[:200]}")
                    time.sleep(5)
            except Exception as e:
                print(f"  Error: {e}")
                time.sleep(5)
    return None


print("Querying Overpass API for dive sites and reef features...")
data = query_overpass()

if data is None:
    print("FAILED to query Overpass API after all retries.")
    # Fallback: create minimal GeoJSON with known dive sites
    print("Using fallback: hardcoded known dive site coordinates...")
    features = []
    known_sites = [
        ("Sipadan Island", 4.113, 118.630, "island"),
        ("Mabul Island", 4.148, 118.632, "island"),
        ("Kapalai", 4.133, 118.618, "reef"),
        ("Bodgaya Island", 4.683, 118.850, "island"),
        ("Boheydulang Island", 4.633, 118.833, "island"),
        ("Sibuan Island", 4.600, 118.850, "island"),
        ("Mantabuan Island", 4.583, 118.800, "island"),
        ("Tetagan Island", 4.550, 118.783, "island"),
        ("Maiga Island", 4.617, 118.867, "island"),
        ("Seavent Reef", 4.120, 118.640, "dive_site"),
        ("Barracuda Point (Sipadan)", 4.115, 118.635, "dive_site"),
        ("Coral Garden (Mabul)", 4.150, 118.640, "dive_site"),
        ("Lobster Wall (Mabul)", 4.145, 118.625, "dive_site"),
        ("Drop Off (Sipadan)", 4.110, 118.628, "dive_site"),
        ("Turtle Cave (Sipadan)", 4.118, 118.633, "dive_site"),
        ("White Sandy Beach (Mabul)", 4.152, 118.635, "dive_site"),
        ("Bum Bum Island", 4.450, 118.650, "island"),
        ("Timbalan Island", 4.333, 118.750, "island"),
        ("Bukat Island", 4.400, 118.700, "island"),
        ("Kalampunian Island", 4.200, 118.500, "island"),
    ]
    for name, lat, lon, ftype in known_sites:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": name, "type": ftype, "source": "fallback_known"}
        })
    geojson = {"type": "FeatureCollection", "features": features}
else:
    elements = data.get('elements', [])
    print(f"Received {len(elements)} elements from Overpass.")
    features = []
    for el in elements:
        etype = el.get('type', '')
        tags = el.get('tags', {})
        name = tags.get('name', '')
        feature_type = tags.get('natural', tags.get('leisure', tags.get('amenity', tags.get('place', 'unknown'))))

        if etype == 'node':
            lon = el.get('lon')
            lat = el.get('lat')
        elif 'center' in el:
            lon = el['center'].get('lon')
            lat = el['center'].get('lat')
        else:
            continue

        if lon is None or lat is None:
            continue

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            "properties": {
                "name": name,
                "type": feature_type,
                "osm_id": el.get('id'),
                "source": "overpass_osm"
            }
        })

    # Also add known dive sites not likely in OSM
    known_dive_sites = [
        ("Sipadan Barracuda Point", 4.115, 118.635, "dive_site"),
        ("Sipadan Drop Off", 4.110, 118.628, "dive_site"),
        ("Sipadan Turtle Cave", 4.118, 118.633, "dive_site"),
        ("Mabul Coral Garden", 4.150, 118.640, "dive_site"),
        ("Mabul Lobster Wall", 4.145, 118.625, "dive_site"),
        ("Kapalai House Reef", 4.133, 118.618, "dive_site"),
        ("Bodgaya Reef", 4.683, 118.850, "dive_site"),
        ("Boheydulang Wall", 4.633, 118.833, "dive_site"),
        ("Sibuan Reef", 4.600, 118.850, "dive_site"),
        ("Mantabuan Patch Reef", 4.583, 118.800, "dive_site"),
    ]
    for name, lat, lon, ftype in known_dive_sites:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": name, "type": ftype, "source": "known_dive_site"}
        })

    geojson = {"type": "FeatureCollection", "features": features}

outpath = PROC / "dive_sites.geojson"
with open(outpath, 'w', encoding='utf-8') as f:
    json.dump(geojson, f, indent=2, ensure_ascii=False)

print(f"\nSaved {len(features)} features to {outpath}")
# Count by type
from collections import Counter
type_counts = Counter(feat['properties']['type'] for feat in features)
print("Type distribution:")
for t, c in type_counts.most_common():
    print(f"  {t}: {c}")
