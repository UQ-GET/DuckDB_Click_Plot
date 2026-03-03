# DuckDB Click Plot (QGIS Plugin) — Tool Summary

## What the tool does

DuckDB Click Plot is a **QGIS dock-widget plugin** for fast, interactive exploration of **gridded greenhouse-gas emissions time series** stored in a **DuckDB** database (commonly EDGAR-derived products).

In plain terms: you **click on the map**, the tool **snaps the click to the nearest EDGAR-style grid point**, **queries the DuckDB table for that grid cell**, then **plots the historical series**. You can change **substance** and **sector**, and **export the current time series to CSV**.

---

## High-level data flow

```
User click in QGIS map canvas
        |
        v
Snap-to-grid (nearest 0.1° cell centre)
  - Prefer: spatial snapping using DuckDB spatial geometry (ST_Distance)
  - Fallback: round-to-grid-cell-centre (…0.05, 0.15, 0.25…)
        |
        v
Query DuckDB for (lat, lon, substance, sector) across years
        |
        v
Render results in dock widget
  - time-series plot
  - latest value/year summary
  - map marker at snapped grid point
        |
        v
Optional: Export displayed series to CSV
```

---

## Inputs

### 1) User / QGIS inputs
- **Map click location** (lon/lat inferred from the clicked point in QGIS).
- UI selections:
  - **Substance** (e.g. CH₄, CO₂, CO₂bio, N₂O; exact set depends on what exists in your DB).
  - **Sector** (IPCC/EDGAR sector codes; tool typically hides sectors with all-zero series for the chosen substance).

### 2) Data inputs (required)
A **DuckDB database** containing an `emissions` table with (at minimum) these fields:

- `lat` (DOUBLE) — grid centre latitude (WGS84)
- `lon` (DOUBLE) — grid centre longitude (WGS84)
- `year` (INTEGER)
- `substance` (TEXT)
- `sector` (TEXT)
- `emission` (DOUBLE)

### 3) Data inputs (optional but improves snapping)
- `location` (GEOMETRY) column in `emissions`, so snapping can use DuckDB Spatial operations.

---

## Outputs

### 1) Interactive outputs (in QGIS)
- A **time-series plot** of emissions vs year for the snapped grid point.
- Displayed **coordinates** of the snapped grid cell centre.
- A **map marker** showing the snapped grid point.
- A **summary readout** (typically most recent year/value for the current selection).

### 2) File output (optional)
- **CSV export** of the currently displayed time series:
  - Columns: `year, emission`
  - Filename typically includes: substance, sector, and grid coordinates (rounded).

---

## Assumptions and conventions (tool-level)

- The tool **does not do unit conversion**. It assumes your DuckDB `emissions.emission` values are already consistent and meaningful for plotting.
- Common convention (as described in the project docs): *tonnes of substance per 0.1° × 0.1° grid cell per year*.
- “All sectors” behaviour depends on the DB contents:
  - If `sector='TOTALS'` exists it may use that,
  - otherwise it may sum or approximate from available sectors (implementation-dependent).

---

## What the tool is not

- Not a data processing pipeline or authoritative reporting system.
- Not intended to modify source data.
- Best used as a **rapid inspection and hypothesis generator**, with final numbers reproduced via scripted queries/workflows.
