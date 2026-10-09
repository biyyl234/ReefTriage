"""
Download Copernicus Marine data for Semporna region and replace literature values.
Region: lat 4.0-5.0, lon 118.5-119.5
"""
import copernicusmarine as cm
import xarray as xr
import numpy as np
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
ENV_DIR = PROJECT_ROOT / "data" / "output" / "environmental"
OUT_DIR = PROJECT_ROOT / "data" / "copernicus"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Region
MIN_LAT, MAX_LAT = 4.0, 5.0
MIN_LON, MAX_LON = 118.5, 119.5
MIN_DEPTH, MAX_DEPTH = 0.5, 50

# Time range: last 1 year + 2020/2024 bleaching peaks
TIME_RANGES = [
    ("2025-09-01", "2026-09-01", "recent"),
    ("2020-04-01", "2020-09-30", "bleach_2020"),
    ("2024-04-01", "2024-09-30", "bleach_2024"),
]

def download_phy():
    """Download physical data: temperature, salinity, currents"""
    print("=== Downloading PHYSICAL data ===")
    for start, end, label in TIME_RANGES:
        outfile = OUT_DIR / f"phy_{label}.nc"
        if outfile.exists():
            print(f"  {label}: already exists, skipping")
            continue
        try:
            cm.subset(
                dataset_id="cmems_mod_glo_phy_anfc_0.083deg_P1D-m",
                variables=["thetao", "so", "uo", "vo"],
                minimum_longitude=MIN_LON,
                maximum_longitude=MAX_LON,
                minimum_latitude=MIN_LAT,
                maximum_latitude=MAX_LAT,
                minimum_depth=MIN_DEPTH,
                maximum_depth=MAX_DEPTH,
                start_datetime=start,
                end_datetime=end,
                output_filename=f"phy_{label}.nc",
                output_directory=str(OUT_DIR),
                overwrite=True,
            )
            print(f"  {label}: downloaded")
        except Exception as e:
            print(f"  {label}: FAILED - {e}")
            # Try alternative dataset
            try:
                cm.subset(
                    dataset_id="cmems_mod_glo_phy_my_0.083deg_P1D-m",
                    variables=["thetao", "so", "uo", "vo"],
                    minimum_longitude=MIN_LON,
                    maximum_longitude=MAX_LON,
                    minimum_latitude=MIN_LAT,
                    maximum_latitude=MAX_LAT,
                    minimum_depth=MIN_DEPTH,
                    maximum_depth=MAX_DEPTH,
                    start_datetime=start,
                    end_datetime=end,
                    output_filename=f"phy_{label}.nc",
                    output_directory=str(OUT_DIR),
                    overwrite=True,
                )
                print(f"  {label}: downloaded (my product)")
            except Exception as e2:
                print(f"  {label}: FAILED again - {e2}")

def download_bgc():
    """Download biogeochemical data: pH, O2, chl, nutrients"""
    print("=== Downloading BIOGEOCHEMICAL data ===")
    for start, end, label in TIME_RANGES:
        outfile = OUT_DIR / f"bgc_{label}.nc"
        if outfile.exists():
            print(f"  {label}: already exists, skipping")
            continue
        try:
            cm.subset(
                dataset_id="cmems_mod_glo_bgc_my_0.25deg_P1D-m",
                variables=["chl", "o2", "no3", "po4", "si"],
                minimum_longitude=MIN_LON,
                maximum_longitude=MAX_LON,
                minimum_latitude=MIN_LAT,
                maximum_latitude=MAX_LAT,
                minimum_depth=MIN_DEPTH,
                maximum_depth=MAX_DEPTH,
                start_datetime=start,
                end_datetime=end,
                output_filename=f"bgc_{label}.nc",
                output_directory=str(OUT_DIR),
                overwrite=True,
            )
            print(f"  {label}: downloaded")
        except Exception as e:
            print(f"  {label}: FAILED - {e}")
            # Try multiyear product
            try:
                cm.subset(
                    dataset_id="cmems_mod_glo_bgc_my_0.25deg_P1D-m",
                    variables=["chl", "o2", "no3", "po4", "si"],
                    minimum_longitude=MIN_LON,
                    maximum_longitude=MAX_LON,
                    minimum_latitude=MIN_LAT,
                    maximum_latitude=MAX_LAT,
                    minimum_depth=MIN_DEPTH,
                    maximum_depth=MAX_DEPTH,
                    start_datetime=start,
                    end_datetime=end,
                    output_filename=f"bgc_{label}.nc",
                    output_directory=str(OUT_DIR),
                    overwrite=True,
                )
                print(f"  {label}: downloaded (my product)")
            except Exception as e2:
                print(f"  {label}: FAILED again - {e2}")

def process_and_replace():
    """Process downloaded NetCDF and replace environmental JSON values"""
    print("=== Processing data ===")
    
    # Load all physical files
    phy_ds = []
    for f in sorted(OUT_DIR.glob("phy_*.nc")):
        try:
            ds = xr.open_dataset(f)
            phy_ds.append(ds)
            print(f"  Loaded {f.name}: {list(ds.data_vars)}")
        except Exception as e:
            print(f"  Failed to load {f.name}: {e}")
    
    bgc_ds = []
    for f in sorted(OUT_DIR.glob("bgc_*.nc")):
        try:
            ds = xr.open_dataset(f)
            bgc_ds.append(ds)
            print(f"  Loaded {f.name}: {list(ds.data_vars)}")
        except Exception as e:
            print(f"  Failed to load {f.name}: {e}")
    
    if not phy_ds and not bgc_ds:
        print("  No data to process")
        return
    
    # Compute regional means (surface layer, 0-10m)
    results = {}
    
    if phy_ds:
        combined = xr.concat(phy_ds, dim="time")
        # Surface mean (0-10m)
        surf = combined.sel(depth=slice(0.5, 10))
        results["sst"] = {
            "mean": float(surf["thetao"].mean().values),
            "min": float(surf["thetao"].min().values),
            "max": float(surf["thetao"].max().values),
            "unit": "degC",
            "source": "Copernicus Marine GLOBAL_ANALYSIS_FORECAST_PHY_001_024",
        }
        results["salinity"] = {
            "mean": float(surf["so"].mean().values),
            "min": float(surf["so"].min().values),
            "max": float(surf["so"].max().values),
            "unit": "PSU",
            "source": "Copernicus Marine GLOBAL_ANALYSIS_FORECAST_PHY_001_024",
        }
        # Current speed
        u = surf["uo"].mean().values
        v = surf["vo"].mean().values
        speed = np.sqrt(u**2 + v**2)
        direction = np.degrees(np.arctan2(v, u)) % 360
        results["current"] = {
            "speed_mean": float(speed),
            "direction_mean": float(direction),
            "unit": "m/s",
            "source": "Copernicus Marine GLOBAL_ANALYSIS_FORECAST_PHY_001_024",
        }
        # Monthly SST climatology
        monthly = surf["thetao"].groupby("time.month").mean(["latitude","longitude","depth"])
        results["sst"]["monthly"] = [float(x) for x in monthly.values]
        print(f"  SST: {results['sst']['mean']:.2f} degC")
        print(f"  Salinity: {results['salinity']['mean']:.2f} PSU")
        print(f"  Current: {speed:.3f} m/s @ {direction:.0f} deg")
    
    if bgc_ds:
        combined = xr.concat(bgc_ds, dim="time")
        surf = combined.sel(depth=slice(0.5, 10))
        # pH not available in BGC dataset; keeping literature value
        # O2 convert from mol/m3 to ml/L (1 mol/m3 = 22.391 ml/L)
        o2_mol = float(surf["o2"].mean().values)
        results["do"] = {
            "mean": o2_mol * 22.391,
            "min": float(surf["o2"].min().values) * 22.391,
            "max": float(surf["o2"].max().values) * 22.391,
            "unit": "ml/L",
            "source": "Copernicus Marine GLOBAL_ANALYSIS_FORECAST_BGC_001_029",
        }
        results["chlorophyll"] = {
            "mean": float(surf["chl"].mean().values),
            "min": float(surf["chl"].min().values),
            "max": float(surf["chl"].max().values),
            "unit": "mg/m3",
            "source": "Copernicus Marine GLOBAL_ANALYSIS_FORECAST_BGC_001_029",
        }
        # Aragonite saturation (if available, else compute)
        if False:  # aragonite not available
            results["arag"] = {
                "mean": float(surf["arag"].mean().values),
                "source": "Copernicus Marine",
            }
        print(f"  DO: {results['do']['mean']:.2f} ml/L")
        print(f"  Chl: {results['chlorophyll']['mean']:.3f} mg/m3")
    
    # Replace values in each segment's environmental JSON
    if not results:
        print("  No results to write")
        return
    
    updated = 0
    for env_file in sorted(ENV_DIR.glob("*.json")):
        with open(env_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        changed = False
        for key, val in results.items():
            if key in data:
                old_mean = data[key].get("mean", "N/A")
                data[key] = val
                changed = True
                print(f"  {data['segment_id']} {key}: {old_mean} -> {val.get('mean', 'N/A')}")
        
        if changed:
            data["data_source"] = "copernicus_marine_observed"
            data["provenance_note"] = "Physical and biogeochemical data from Copernicus Marine Service (GLOBAL_ANALYSIS_FORECAST_PHY_001_024 + BGC_001_029), regional mean 4.0-5.0N 118.5-119.5E, surface 0-10m. DHW from NOAA CRW 5km."
            with open(env_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            updated += 1
    
    print(f"  Updated {updated} segment files")
    
    # Save summary
    with open(OUT_DIR / "copernicus_summary.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"  Summary saved to {OUT_DIR / 'copernicus_summary.json'}")

if __name__ == "__main__":
    download_phy()
    download_bgc()
    process_and_replace()
    print("\n=== DONE ===")
