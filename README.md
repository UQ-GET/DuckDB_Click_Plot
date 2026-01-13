# DuckDB Click Plot (QGIS Plugin)

**Author:** Stephen Kennedy-Clark  
**Organisation:** Gas & Energy Transition Research Centre (GETRC),  
The University of Queensland  

---

## Overview

**DuckDB Click Plot** is a lightweight QGIS plugin for **exploratory analysis of gridded greenhouse-gas emissions time series**.

The workflow is deliberately simple:

1. Click anywhere on the map  
2. The click snaps to the nearest emissions grid point  
3. A DuckDB query retrieves the historical emissions time series  
4. The result is plotted immediately and can be exported to CSV  

The plugin is designed for **interactive exploration**, sanity checking, and hypothesis development, not for formal reporting or model validation.

---

## Intended Use

This tool is intended for:

- Rapid inspection of emissions time series at specific locations
- Comparing substances (CH₄, CO₂, CO₂bio, N₂O) at the same grid point
- Exploring dominant IPCC sectors spatially
- Exporting location-specific time series for downstream analysis

It is explicitly **not** intended to:

- Perform uncertainty analysis
- Validate TOTALS vs sectoral sums
- Act as a production-grade data access layer
- Replace scripted, reproducible analysis pipelines

Those tasks should remain in code.

---

## Data Requirements

The plugin expects a **DuckDB database** with a table named: emissions


### Required columns

| Column     | Type        | Notes |
|------------|------------|------|
| `lat`      | DOUBLE     | Grid centre latitude (WGS84) |
| `lon`      | DOUBLE     | Grid centre longitude (WGS84) |
| `year`     | INTEGER    | Calendar year |
| `substance`| TEXT       | e.g. CH4, CO2, CO2bio, N2O |
| `sector`   | TEXT       | IPCC sector code (e.g. ENF, IND, TOTALS) |
| `emission` | DOUBLE     | Emissions value (see units below) |
| `location`| GEOMETRY   | Optional; required for spatial snapping |

### Spatial snapping

- If DuckDB’s **spatial extension** is available, the plugin uses: ST_Distance(location, ST_Point(lon, lat))
- If not, it falls back to snapping to **0.1° grid cell centres**  
(…, 0.05, 0.15, 0.25, …)

---

## Units and Conventions

All plotted values are assumed to be: tonnes of substance per (0.1° × 0.1° grid cell) per year

Displayed as: t <SUBSTANCE> · (0.1°)⁻² · yr⁻¹


The plugin does **not** convert units. It assumes the DuckDB table is already consistent.

---

## Sector Handling

- The sector dropdown shows **only sectors with non-zero emissions** for the selected substance.
- “All sectors” behaves as:
  1. Use `sector = 'TOTALS'` if present
  2. Otherwise sum the dominant sectors for that substance

This is a pragmatic choice for exploration, not a validation mechanism.

---

## User Interface

The dock widget contains:

- An information header showing:
  - Clicked WGS84 coordinates
  - Substance
  - IPCC sector (or TOTALS)
  - Most recent available value and year
- Substance and sector selectors
- A time-series plot
- A CSV export button

The map marker indicates the snapped grid point and updates on each click.

---

## CSV Export

The **CSV…** button exports the currently displayed time series with columns:
year, emission


The filename includes:
- Substance
- Sector (or TOTALS)
- Grid latitude and longitude (rounded)

---

## Reproducibility Notes

This plugin is part of an **exploratory analysis stage**.

- All authoritative results should still be generated via scripts
- The plugin intentionally avoids caching or modifying the source data
- Any insight gained here should be traceable back to scripted queries

---

## Known Limitations

- No uncertainty flags or propagation
- No validation overlays
- No multi-point comparison
- Assumes consistent grid resolution across the dataset
- Assumes WGS84 coordinates

These are deliberate design choices.

---

## Licensing

This plugin is released under the GNU General Public License (GPL),  
consistent with QGIS plugin requirements.

---

## Contact

For questions, extensions, or internal use discussions:

**Stephen Kennedy-Clark**  
Gas & Energy Transition Research Centre  
The University of Queensland  
uqsken12@uq.edu.au







