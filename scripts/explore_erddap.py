"""Find variable names in NOAA_DHW dataset."""
import requests
import json

headers = {'User-Agent': 'ReefTriage-Research/1.0'}
url = 'https://coastwatch.pfeg.noaa.gov/erddap/info/NOAA_DHW/index.json'
r = requests.get(url, headers=headers, timeout=30)
d = r.json()

rows = d['table']['rows']

# Print all unique row types
row_types = set()
for row in rows:
    row_types.add(row[0])
print('Row types:', row_types)

# Print rows that mention variable names (not attributes)
print('\n=== Non-attribute rows (variables/dimensions) ===')
for row in rows:
    if row[0] != 'attribute':
        print(f'  [{row[0]}] {row[1]} | {row[2]} | {row[3]} | {row[4][:100] if row[4] else ""}')
