"""
run_connectivity.py
-------------------
Coral larval connectivity model for the Semporna reef complex (Sabah, Malaysia).

Method: Pure-Python 4th-order Runge-Kutta (RK4) particle advection on HYCOM GLBy0.08
1/12° ocean analysis u/v currents.

Biological processes included:
  * Daily background mortality (exponential, rate = 0.05 / day)
  * Diel vertical migration (DVM): larvae at 15 m during local daytime,
    at 0 m (surface) during local nighttime.
  * Settlement: a larva that enters a reef's ~1 km radius settles and stops drifting.

Outputs:
  connectivity/output/connectivity_matrix.csv       N x N settlement matrix
  connectivity/output/reef_connectivity_features.csv per-reef metrics
  connectivity/output/particle_tracks.npz           particle end-points (for plotting)
  connectivity/output/run_log.txt                   parameters and run summary

Usage:
  python run_connectivity.py
"""
import os
import sys
import time as _time
import json
import numpy as np
import xarray as xr

# local
from reef_definitions import load_reefs

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(HERE, "..", "data"))
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "output"))
os.makedirs(OUT_DIR, exist_ok=True)

HYCOM_FILE = os.path.join(DATA_DIR, "hycom_uv_30d.nc")

# Simulation parameters
N_PARTICLES_PER_REEF = 80      # larvae released per reef
SIM_DAYS = 30                  # planktonic duration window
DT_HOURS = 1.0                 # model timestep
DAILY_MORTALITY = 0.05         # 5% per day
SETTLE_RADIUS_KM = 5.0         # settlement detection radius (~grid-scale at 1/12°)
COMPETENCY_DAYS = 5.0          # larvae not competent to settle for first 5 days
KM_PER_DEG_LAT = 111.32
KM_PER_DEG_LON_AT_EQ = 111.32

# Diel vertical migration: local (Malaysia, UTC+8) day 06:00-18:00 at depth=15 m,
# night at surface (0 m).
UTC_OFFSET_HOURS = 8
DAY_START_LOCAL = 6
DAY_END_LOCAL = 18

# Depth layer indices in the HYCOM file (depths are [0., 15.])
DEPTH_SURFACE = 0.0
DEPTH_DEEP = 15.0

RNG_SEED = 42


# ----------------------------------------------------------------------
# Velocity field interpolator
# ----------------------------------------------------------------------
class VelocityField:
    """
    Vectorized bilinear-in-space + linear-in-time interpolator for HYCOM u/v.
    Pre-loads the two depth layers and builds fast lookup arrays.
    """
    def __init__(self, nc_path):
        ds = xr.open_dataset(nc_path)
        self.lon = ds["lon"].values.astype(np.float64)
        self.lat = ds["lat"].values.astype(np.float64)
        self.time = ds["time"].values  # numpy datetime64
        self.depth = ds["depth"].values.astype(np.float64)

        # u/v shape: (time, depth, lat, lon)
        self.u = ds["water_u"].values.astype(np.float64)
        self.v = ds["water_v"].values.astype(np.float64)
        ds.close()

        # Time axis in hours since first timestamp
        t0 = self.time[0]
        self.t_hours = (self.time - t0) / np.timedelta64(1, "h")

        # Identify depth indices
        self.i_surf = int(np.argmin(np.abs(self.depth - DEPTH_SURFACE)))
        self.i_deep = int(np.argmin(np.abs(self.depth - DEPTH_DEEP)))

        # Grid spacing
        self.dlon = float(self.lon[1] - self.lon[0])
        self.dlat = float(self.lat[1] - self.lat[0])

        print(f"  VelocityField: {self.lon.size} lon x {self.lat.size} lat, "
              f"{self.t_hours.size} times, depths={self.depth}", flush=True)

    def _interp_uv(self, lons, lats, t_hours, depth_idx):
        """
        Vectorized bilinear spatial + linear temporal interpolation.
        lons, lats: (N,) arrays (already clipped to domain)
        t_hours: scalar or (N,) hours since start
        depth_idx: index into depth axis
        Returns u, v (N,)
        """
        n = lons.shape[0]
        # --- spatial indices (bilinear) ---
        x = (lons - self.lon[0]) / self.dlon
        y = (lats - self.lat[0]) / self.dlat
        i0 = np.floor(x).astype(int)
        j0 = np.floor(y).astype(int)
        i0 = np.clip(i0, 0, self.lon.size - 2)
        j0 = np.clip(j0, 0, self.lat.size - 2)
        i1 = i0 + 1
        j1 = j0 + 1
        wx = x - i0
        wy = y - j0

        # --- temporal indices (linear) ---
        if np.isscalar(t_hours):
            t_hours = np.full(n, t_hours)
        k0 = np.floor((t_hours - self.t_hours[0]) /
                      (self.t_hours[1] - self.t_hours[0])).astype(int)
        k0 = np.clip(k0, 0, self.t_hours.size - 2)
        k1 = k0 + 1
        wt = (t_hours - self.t_hours[k0]) / (self.t_hours[k1] - self.t_hours[k0])

        # Gather corners: shape (N,)
        def gather(field):
            f00 = field[k0, depth_idx, j0, i0]
            f01 = field[k0, depth_idx, j0, i1]
            f10 = field[k0, depth_idx, j1, i0]
            f11 = field[k0, depth_idx, j1, i1]
            # spatial bilinear
            f0 = (1 - wx) * (1 - wy) * f00 + wx * (1 - wy) * f01 + \
                 (1 - wx) * wy * f10 + wx * wy * f11
            g00 = field[k1, depth_idx, j0, i0]
            g01 = field[k1, depth_idx, j0, i1]
            g10 = field[k1, depth_idx, j1, i0]
            g11 = field[k1, depth_idx, j1, i1]
            f1 = (1 - wx) * (1 - wy) * g00 + wx * (1 - wy) * g01 + \
                 (1 - wx) * wy * g10 + wx * wy * g11
            # temporal linear
            return (1 - wt) * f0 + wt * f1

        u = gather(self.u)
        v = gather(self.v)
        return u, v

    def velocity(self, lons, lats, t_hours, use_deep):
        """
        Return (u, v) in m/s at particle positions/time.
        use_deep: if True use deep layer (15 m), else surface (0 m).
        Particles outside the domain get velocity 0 (will be removed by caller).
        """
        depth_idx = self.i_deep if use_deep else self.i_surf
        # clip to domain so interpolation stays valid; NaN positions -> 0 velocity
        lons_c = np.clip(lons, self.lon[0], self.lon[-1])
        lats_c = np.clip(lats, self.lat[0], self.lat[-1])
        lons_c = np.where(np.isfinite(lons_c), lons_c, self.lon[0])
        lats_c = np.where(np.isfinite(lats_c), lats_c, self.lat[0])
        u, v = self._interp_uv(lons_c, lats_c, t_hours, depth_idx)
        # Where input was non-finite, zero out velocity
        bad = ~np.isfinite(lons) | ~np.isfinite(lats)
        u = np.where(bad, 0.0, u)
        v = np.where(bad, 0.0, v)
        return u, v


# ----------------------------------------------------------------------
# RK4 advection
# ----------------------------------------------------------------------
def rk4_step(vf, lons, lats, t_hours, dt_hours, use_deep):
    """
    One RK4 step for a vector of particles.
    Returns updated (lons, lats) in degrees.
    Velocities converted from m/s to deg/timestep using local Earth radius.
    """
    dt_sec = dt_hours * 3600.0

    def accel(lon, lat, t):
        u, v = vf.velocity(lon, lat, t, use_deep)  # m/s
        dlat = v * dt_sec / (KM_PER_DEG_LAT * 1000.0)
        dlon = u * dt_sec / (KM_PER_DEG_LON_AT_EQ * 1000.0 * np.cos(np.deg2rad(lat)))
        return dlon, dlat

    k1_lon, k1_lat = accel(lons, lats, t_hours)
    k2_lon, k2_lat = accel(lons + 0.5 * k1_lon, lats + 0.5 * k1_lat,
                           t_hours + 0.5 * dt_hours)
    k3_lon, k3_lat = accel(lons + 0.5 * k2_lon, lats + 0.5 * k2_lat,
                           t_hours + 0.5 * dt_hours)
    k4_lon, k4_lat = accel(lons + k3_lon, lats + k3_lat,
                           t_hours + dt_hours)

    new_lon = lons + (k1_lon + 2 * k2_lon + 2 * k3_lon + k4_lon) / 6.0
    new_lat = lats + (k1_lat + 2 * k2_lat + 2 * k3_lat + k4_lat) / 6.0
    return new_lon, new_lat


# ----------------------------------------------------------------------
# Main simulation
# ----------------------------------------------------------------------
def main():
    t_start = _time.time()
    rng = np.random.default_rng(RNG_SEED)

    print("=" * 64, flush=True)
    print("Coral Larval Connectivity Model (pure-Python RK4)", flush=True)
    print("=" * 64, flush=True)

    # 1. Load reefs
    gj_path = os.path.abspath(os.path.join(
        HERE, "..", "..", "data", "output", "reef_segments.geojson"))
    reefs = load_reefs(gj_path)
    N = len(reefs)
    print(f"\n[1] Reef segments: {N} (geojson={'yes' if os.path.exists(gj_path) else 'no, using placeholders'})", flush=True)
    for r in reefs:
        print(f"      {r['id']:2d} {r['name']:14s} ({r['lat']:.3f}, {r['lon']:.3f})", flush=True)

    # 2. Load velocity field
    print("\n[2] Loading HYCOM velocity field...", flush=True)
    vf = VelocityField(HYCOM_FILE)

    # 3. Initialize particles
    n_total = N * N_PARTICLES_PER_REEF
    release_reef = np.repeat(np.arange(N), N_PARTICLES_PER_REEF)
    # Small initial spread within reef radius (uniform in circle)
    lons = np.empty(n_total)
    lats = np.empty(n_total)
    for i, r in enumerate(reefs):
        idx = np.where(release_reef == i)[0]
        # uniform in radius ~ 0.5 km
        ang = rng.uniform(0, 2 * np.pi, size=idx.size)
        rad = rng.uniform(0, 0.5 / KM_PER_DEG_LAT, size=idx.size)
        lons[idx] = r["lon"] + rad * np.cos(ang) / np.cos(np.deg2rad(r["lat"]))
        lats[idx] = r["lat"] + rad * np.sin(ang)

    alive = np.ones(n_total, dtype=bool)
    settled_reef = np.full(n_total, -1, dtype=int)  # -1 = not settled
    final_lons = lons.copy()
    final_lats = lats.copy()

    # Reef centroid arrays for distance checks
    reef_lats = np.array([r["lat"] for r in reefs])
    reef_lons = np.array([r["lon"] for r in reefs])
    settle_rad_deg = SETTLE_RADIUS_KM / KM_PER_DEG_LAT

    # 4. Time loop
    n_steps = int(SIM_DAYS * 24 / DT_HOURS)
    dt_days = DT_HOURS / 24.0
    mortality_per_step = DAILY_MORTALITY * dt_days  # survival prob per step = 1 - this
    print(f"\n[3] Simulating {n_total} particles x {n_steps} steps "
          f"(dt={DT_HOURS}h, mortality={DAILY_MORTALITY}/day)...", flush=True)

    for step in range(n_steps):
        t_hours = step * DT_HOURS
        # Determine active depth layer from local solar time
        local_hour = (t_hours + UTC_OFFSET_HOURS) % 24
        use_deep = (DAY_START_LOCAL <= local_hour < DAY_END_LOCAL)

        # Only advect alive AND not-yet-settled particles
        active = alive & (settled_reef < 0)
        if not active.any():
            break

        a_lons = lons[active]
        a_lats = lats[active]
        new_lon, new_lat = rk4_step(vf, a_lons, a_lats, t_hours, DT_HOURS, use_deep)
        lons[active] = new_lon
        lats[active] = new_lat

        # Remove particles that drifted out of the HYCOM domain (exported offshore)
        out_mask = ((lons < vf.lon[0]) | (lons > vf.lon[-1]) |
                    (lats < vf.lat[0]) | (lats > vf.lat[-1]) |
                    ~np.isfinite(lons) | ~np.isfinite(lats))
        alive[out_mask & (settled_reef < 0)] = False

        # Settlement check: distance to each reef centroid.
        # Only count settlement after the competency period (larvae must develop
        # competence before they can settle; avoids counting release location
        # as an immediate settlement event).
        if t_hours >= COMPETENCY_DAYS * 24.0:
            for ri in range(N):
                dlat_deg = lats[active] - reef_lats[ri]
                dlon_deg = (lons[active] - reef_lons[ri]) * np.cos(np.deg2rad(reef_lats[ri]))
                dist_km = np.sqrt(dlat_deg**2 + dlon_deg**2) * KM_PER_DEG_LAT
                hit = dist_km <= SETTLE_RADIUS_KM
                if hit.any():
                    # only settle if not already settled this step
                    act_idx = np.where(active)[0]
                    newly = act_idx[hit]
                    # particle settles on reef ri (including its own home reef,
                    # after drifting away and returning = self-retention)
                    for p in newly:
                        if settled_reef[p] < 0:
                            settled_reef[p] = ri

        # Apply mortality (only to still-drifting particles; settled ones are done)
        drifting = alive & (settled_reef < 0)
        kill = rng.random(n_total) < mortality_per_step
        # do not kill settled particles
        kill &= drifting
        alive[kill] = False

        if step % 120 == 0:
            n_alive = alive.sum()
            n_settled = (settled_reef >= 0).sum()
            print(f"    step {step:4d}/{n_steps} t={t_hours:6.1f}h "
                  f"({'deep' if use_deep else 'surf'}) alive={n_alive} settled={n_settled}",
                  flush=True)

    # Record final positions
    final_lons = lons.copy()
    final_lats = lats.copy()

    # 5. Build connectivity matrix C[i][j] = fraction from i settling on j
    C = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        released_i = np.where(release_reef == i)[0]
        n_rel = released_i.size
        for j in range(N):
            C[i, j] = np.sum(settled_reef[released_i] == j) / n_rel

    # 6. Per-reef metrics
    self_retention = np.diag(C).copy()
    larval_output = C.sum(axis=1) - np.diag(C)     # exported to others
    larval_input = C.sum(axis=0) - np.diag(C)     # received from others

    # Normalized connectivity score: min-max of input and output, averaged
    def minmax(x):
        lo, hi = np.min(x), np.max(x)
        if hi - lo < 1e-12:
            return np.full_like(x, 0.5)
        return (x - lo) / (hi - lo)
    connectivity_score = 0.5 * minmax(larval_output) + 0.5 * minmax(larval_input)

    # Survival stats
    n_alive_final = int(alive.sum())
    n_settled_total = int((settled_reef >= 0).sum())
    n_died = n_total - n_alive_final - n_settled_total  # died before settlement
    # Note: settled particles are counted separately; alive includes settled.
    # Reconcile: alive means not killed by mortality; settled particles are still "alive" in our bookkeeping.
    # Let's recompute cleanly:
    n_released = n_total
    n_settled = int((settled_reef >= 0).sum())
    n_died_no_settle = int(np.sum(alive & (settled_reef < 0) == False) - 0)  # died and never settled
    # Simpler: died = not settled and not alive
    n_died = int(np.sum(~alive))
    # Alive includes both settled and still-drifting survivors
    n_drifting_alive = int(np.sum(alive & (settled_reef < 0)))

    elapsed = _time.time() - t_start

    # 7. Save outputs
    # 7a. Connectivity matrix CSV
    mat_path = os.path.join(OUT_DIR, "connectivity_matrix.csv")
    header = "from_reef," + ",".join(r["name"] for r in reefs)
    with open(mat_path, "w", encoding="utf-8") as f:
        f.write(header + "\n")
        for i, r in enumerate(reefs):
            row = ",".join(f"{C[i,j]:.4f}" for j in range(N))
            f.write(f"{r['name']},{row}\n")

    # 7b. Per-reef features CSV
    feat_path = os.path.join(OUT_DIR, "reef_connectivity_features.csv")
    with open(feat_path, "w", encoding="utf-8") as f:
        f.write("reef_id,name,lat,lon,larval_input,larval_output,self_retention,"
                "connectivity_score,total_settlements,particles_released\n")
        for i, r in enumerate(reefs):
            f.write(f"{i},{r['name']},{r['lat']:.4f},{r['lon']:.4f},"
                    f"{larval_input[i]:.4f},{larval_output[i]:.4f},"
                    f"{self_retention[i]:.4f},{connectivity_score[i]:.4f},"
                    f"{int((settled_reef==i).sum())},{N_PARTICLES_PER_REEF}\n")

    # 7c. Particle tracks npz (for plotting)
    tracks_path = os.path.join(OUT_DIR, "particle_tracks.npz")
    np.savez(tracks_path,
             final_lons=final_lons, final_lats=final_lats,
             release_reef=release_reef, settled_reef=settled_reef,
             alive=alive,
             reef_lats=reef_lats, reef_lons=reef_lons,
             reef_names=np.array([r["name"] for r in reefs]))

    # 7d. Run log
    log_path = os.path.join(OUT_DIR, "run_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("Coral Larval Connectivity Model - Run Log\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"Method: Pure-Python RK4 (OceanParcels unavailable on Python 3.14)\n")
        f.write(f"HYCOM dataset: GLBy0.08 expt_93.0 uv3z (1/12 deg analysis)\n")
        f.write(f"HYCOM time window: {str(vf.time[0])} -> {str(vf.time[-1])}\n")
        f.write(f"Region: lon {float(vf.lon[0]):.3f}-{float(vf.lon[-1]):.3f}, "
                f"lat {float(vf.lat[0]):.3f}-{float(vf.lat[-1]):.3f}\n")
        f.write(f"Depth layers used: {list(vf.depth)} m\n\n")
        f.write(f"Reefs: {N}\n")
        f.write(f"Particles per reef: {N_PARTICLES_PER_REEF} (total {n_total})\n")
        f.write(f"Simulation: {SIM_DAYS} days, dt={DT_HOURS} h ({n_steps} steps)\n")
        f.write(f"Daily mortality: {DAILY_MORTALITY}\n")
        f.write(f"Settlement radius: {SETTLE_RADIUS_KM} km\n")
        f.write(f"Competency period (no settlement): first {COMPETENCY_DAYS} days\n")
        f.write(f"Diel vertical migration: local day ({DAY_START_LOCAL}:00-{DAY_END_LOCAL}:00, UTC+{UTC_OFFSET_HOURS}) "
                f"at {DEPTH_DEEP} m, night at {DEPTH_SURFACE} m\n\n")
        f.write("--- Results ---\n")
        f.write(f"Total released: {n_released}\n")
        f.write(f"Total settled (any reef): {n_settled}\n")
        f.write(f"Died (mortality, never settled): {n_died}\n")
        f.write(f"Still drifting alive at end: {n_drifting_alive}\n")
        f.write(f"Overall settlement rate: {n_settled/n_released:.3f}\n")
        f.write(f"Overall survival rate (not killed): {(n_settled+n_drifting_alive)/n_released:.3f}\n\n")
        f.write("Connectivity matrix row sums (total settlement success per source reef):\n")
        for i, r in enumerate(reefs):
            f.write(f"  {r['name']:14s}: row_sum={C[i].sum():.3f} "
                    f"(self={self_retention[i]:.3f}, out={larval_output[i]:.3f})\n")
        f.write(f"\nElapsed: {elapsed:.1f}s\n")

    # 8. Print summary
    print("\n" + "=" * 64, flush=True)
    print("RESULTS SUMMARY", flush=True)
    print("=" * 64, flush=True)
    print(f"  Total released:        {n_released}", flush=True)
    print(f"  Settled (any reef):   {n_settled} ({n_settled/n_released*100:.1f}%)", flush=True)
    print(f"  Died (mortality):     {n_died} ({n_died/n_released*100:.1f}%)", flush=True)
    print(f"  Drifting alive at end:{n_drifting_alive} ({n_drifting_alive/n_released*100:.1f}%)", flush=True)
    print(f"  Matrix C range: [{C.min():.4f}, {C.max():.4f}], mean={C.mean():.4f}", flush=True)
    print(f"  Mean self-retention: {self_retention.mean():.4f}", flush=True)
    print(f"  Mean larval output:  {larval_output.mean():.4f}", flush=True)
    print(f"  Mean larval input:    {larval_input.mean():.4f}", flush=True)
    print(f"\nOutputs written to: {OUT_DIR}", flush=True)
    print(f"  - connectivity_matrix.csv", flush=True)
    print(f"  - reef_connectivity_features.csv", flush=True)
    print(f"  - particle_tracks.npz", flush=True)
    print(f"  - run_log.txt", flush=True)
    print(f"Elapsed: {elapsed:.1f}s", flush=True)


if __name__ == "__main__":
    main()
