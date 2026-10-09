# Coral Reference Images — Attribution & Provenance

These four images are **reference illustrations** for the ReefTriage Reef Lab micro-page
(`micro.html`). They are used to demonstrate the four bleaching severity classes
(healthy / mild / moderate / severe) alongside the on-device color analyzer.

> **Licensing note for production deployment.** The images below were retrieved from public
> web sources during a hackathon/demo build. Before any public release, replace them with
> explicitly licensed imagery (CC-BY / CC0) from:
> - **CoralNet** (https://coralnet.ucsd.edu) — research-grade annotated coral images
> - **Allen Coral Atlas** (https://allencoralatlas.org)
> - **NOAA Coral Reef Conservation Program** image library
> - **Wikimedia Commons** (search "coral bleaching", filter by license)
> - **XL Catlin / Global Reef Record**

## Files

| File | Class | Visual content | Retrieved from |
|---|---|---|---|
| `healthy.jpg` | Healthy | Vibrant red/orange soft coral reef with glassfish, Raja Ampat-style | Tuchong Creative stock (Raja Ampat coral reef photo) |
| `mild.jpg` | Mild bleaching | Central staghorn colony fully white, surrounded by yellow/orange healthy coral | Dreamstime "Coral reef, bleached white, with a few colorful corals" |
| `moderate.jpg` | Moderate bleaching | Extensive pale/beige Acropora field, partial pigment loss | Scripps Institution of Oceanography (bleached reef photo) |
| `severe.jpg` | Severe bleaching | Fully white staghorn skeleton in foreground, more bleached reef in background | Wild Hope / "Coral Comeback" episode still |

## Recommended replacement sources (search queries)

- Wikimedia Commons: `coral bleaching`, `Acropora bleached`, `healthy coral reef`
- CoralNet: public label sets include `bleached`, `healthy`, `dead coral`
- Unsplash / Pexels: `coral reef underwater` (royalty-free)

## Fallback if images unavailable

If the `img/coral/` directory is empty or images fail to load, `micro.html` should render
CSS gradient placeholders:
- healthy: radial-gradient(#2e8b57, #cd5c5c, #ff8c00)
- mild:    radial-gradient(#c8e6c9, #fff8e1, #ffffff)
- moderate:radial-gradient(#e0e0e0, #f5f5f5, #ffffff)
- severe:  radial-gradient(#ffffff, #f0f0f0, #d0d0d0)
