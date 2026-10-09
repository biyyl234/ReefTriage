"""
plot_connectivity.py
--------------------
Generate two figures from the connectivity run:
  1. particle_tracks.png  - particle end-points overlaid on reef positions
  2. connectivity_heatmap.png - N x N connectivity matrix heatmap
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.abspath(os.path.join(HERE, "..", "output"))

# Load saved data
d = np.load(os.path.join(OUT_DIR, "particle_tracks.npz"), allow_pickle=True)
final_lons = d["final_lons"]
final_lats = d["final_lats"]
release_reef = d["release_reef"]
settled_reef = d["settled_reef"]
alive = d["alive"]
reef_lats = d["reef_lats"]
reef_lons = d["reef_lons"]
reef_names = d["reef_names"]

N = len(reef_lats)

# ---------------------------------------------------------------
# Figure 1: particle end-points + reef positions
# ---------------------------------------------------------------
fig, ax = plt.subplots(figsize=(10, 8))

# Color by status: settled on a reef (green), drifted alive (blue), died/exported (red)
settled = settled_reef >= 0
drifting = alive & ~settled
dead = ~alive

ax.scatter(final_lons[dead], final_lats[dead], s=8, c="lightgray", alpha=0.5,
           label=f"Died/exported ({dead.sum()})")
ax.scatter(final_lons[drifting], final_lats[drifting], s=12, c="steelblue", alpha=0.7,
           label=f"Still drifting ({drifting.sum()})")
ax.scatter(final_lons[settled], final_lats[settled], s=18, c="seagreen", alpha=0.8,
           edgecolors="darkgreen", linewidths=0.3,
           label=f"Settled on reef ({settled.sum()})")

# Reef positions
ax.scatter(reef_lons, reef_lats, s=80, c="red", marker="*", zorder=5,
           edgecolors="black", linewidths=0.5, label="Reef segments")
for i in range(N):
    ax.annotate(str(i), (reef_lons[i], reef_lats[i]),
                textcoords="offset points", xytext=(5, 5), fontsize=7)

ax.set_xlabel("Longitude (°E)")
ax.set_ylabel("Latitude (°N)")
ax.set_title("Coral Larval Particle End-Points (30-day HYCOM RK4 simulation)\n"
             "Semporna reef complex, Malaysia")
ax.legend(loc="lower left", fontsize=8)
ax.grid(alpha=0.3)
ax.set_xlim(118.0, 119.8)
ax.set_ylim(4.0, 5.0)
plt.tight_layout()
fig1 = os.path.join(OUT_DIR, "particle_tracks.png")
plt.savefig(fig1, dpi=150)
plt.close()
print(f"Saved: {fig1}")

# ---------------------------------------------------------------
# Figure 2: connectivity matrix heatmap
# ---------------------------------------------------------------
# Rebuild C from saved data
C = np.zeros((N, N))
for i in range(N):
    rel = np.where(release_reef == i)[0]
    for j in range(N):
        C[i, j] = np.sum(settled_reef[rel] == j) / rel.size

fig, ax = plt.subplots(figsize=(12, 10))
im = ax.imshow(C, cmap="YlOrRd", aspect="auto", vmin=0, vmax=max(0.1, C.max()))
ax.set_xticks(range(N))
ax.set_yticks(range(N))
ax.set_xticklabels([str(i) for i in range(N)], rotation=90, fontsize=7)
ax.set_yticklabels([str(i) for i in range(N)], fontsize=7)
ax.set_xlabel("Settlement reef (destination)")
ax.set_ylabel("Source reef (release)")
ax.set_title("Coral Larval Connectivity Matrix C[i][j]\n"
             "Fraction of larvae released from reef i that settle on reef j")
plt.colorbar(im, ax=ax, label="Settlement fraction")

# Annotate non-trivial cells
for i in range(N):
    for j in range(N):
        if C[i, j] > 0.05:
            ax.text(j, i, f"{C[i,j]:.2f}", ha="center", va="center",
                    fontsize=6, color="black")

plt.tight_layout()
fig2 = os.path.join(OUT_DIR, "connectivity_heatmap.png")
plt.savefig(fig2, dpi=150)
plt.close()
print(f"Saved: {fig2}")

# Print reef index legend
print("\nReef index legend:")
for i in range(N):
    print(f"  {i:2d} = {reef_names[i]}")
