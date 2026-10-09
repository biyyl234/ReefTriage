"""Probe whether Copernicus Marine subset works anonymously.
Run with a short wall-clock expectation: if it prompts for creds, it will
raise rather than hang because stdin is not a TTY.
"""
import sys, traceback
from copernicusmarine import subset

try:
    res = subset(
        dataset_id="cmems_mod_glo_phy_anfc_merged-uv_PT1H-i",
        variables=["utotal"],
        minimum_longitude=118.6,
        maximum_longitude=118.7,
        minimum_latitude=4.1,
        maximum_latitude=4.2,
        start_datetime="2026-09-20",
        end_datetime="2026-09-21",
        output_directory="data/raw/copernicus",
        disable_progress_bar=True,
        overwrite=True,
    )
    print("OK anonymous subset:")
    print(res)
except SystemExit as e:
    print("SystemExit:", e.code)
except Exception as e:
    print("EXC TYPE:", type(e).__name__)
    print("EXC MSG:", str(e)[:2000])
    traceback.print_exc()
    sys.exit(2)
