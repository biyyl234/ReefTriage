"""Diagnose netCDF4 OPeNDAP support and test alternate access."""
import netCDF4
print("netCDF4 version:", netCDF4.__version__)
print("has getlibversion:", getattr(netCDF4, "__netcdf4libversion__", "?"))
try:
    print("netcdf lib:", netCDF4.getlibversion())
except Exception as e:
    print("getlibversion failed:", e)

# Check if OPeNDAP is compiled in
try:
    nc = netCDF4.Dataset("https://tds.hycom.org/thredds/dodsC/GLBy0.08/expt_93.0/uv3z")
    print("OPENED OK:", nc)
    nc.close()
except Exception as e:
    print("OPeNDAP open failed:", repr(e)[:300])
