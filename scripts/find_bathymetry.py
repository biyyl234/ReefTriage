"""Search ERDDAP for bathymetry/bathymetric data and download regional subset."""
import requests
import json
import time

headers = {'User-Agent': 'ReefTriage-Research/1.0'}

# Search NOAA ERDDAP for bathymetry
search_url = 'https://coastwatch.pfeg.noaa.gov/erddap/search/index.json'
for query in ['GEBCO bathymetry', 'ETOPO elevation', 'bathymetry global']:
    params = {'searchFor': query, 'itemsPerPage': 10}
    print(f'\n=== Search: "{query}" ===')
    try:
        r = requests.get(search_url, params=params, headers=headers, timeout=30)
        if r.status_code == 200:
            d = r.json()
            rows = d.get('table', {}).get('rows', [])
            for row in rows:
                print(f'  {row[0]}')
        else:
            print(f'  HTTP {r.status_code}')
    except Exception as e:
        print(f'  Error: {e}')
    time.sleep(2)

# Also try PMEL ERDDAP
print('\n=== Trying PMEL ERDDAP search ===')
try:
    pmel_search = 'https://data.pmel.noaa.gov/erddap/search/index.json'
    r = requests.get(pmel_search, params={'searchFor': 'GEBCO', 'itemsPerPage': 10},
                     headers=headers, timeout=30)
    if r.status_code == 200:
        d = r.json()
        for row in d.get('table', {}).get('rows', []):
            print(f'  {row[0]}')
except Exception as e:
    print(f'  Error: {e}')
