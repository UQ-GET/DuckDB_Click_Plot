# DuckDB Click Plot (QGIS Plugin)

**Author:** Stephen Kennedy-Clark  
**Organisation:** [Gas & Energy Transition Research Centre](https://gas-energy.centre.uq.edu.au/),  
The University of Queensland  

---

## Overview

DuckDB Click Plot is a QGIS plugin for quick exploration of gridded greenhouse-gas emissions time series from the [EDGAR](https://edgar.jrc.ec.europa.eu/) database (Emissions Database for Global Atmospheric Research). 

Click anywhere in Queensland on the map, and the plugin snaps to the nearest 0.1° grid point and plots historical emissions. Select different substances (CH₄, CO₂, CO₂bio, N₂O) and IPCC sectors. Export time series to CSV.

---

## Intended Use

- Quick inspection of emissions time series at specific locations
- Comparing different substances at the same grid point
- Exploring spatial patterns in IPCC sectors
- Exporting location-specific time series for further analysis

---

## Data Requirements

The plugin expects a DuckDB database with a table named `emissions`.

### Required columns

| Column     | Type        | Notes |
|------------|------------|------|
| `lat`      | DOUBLE     | Grid centre latitude (WGS84) |
| `lon`      | DOUBLE     | Grid centre longitude (WGS84) |
| `year`     | INTEGER    | Calendar year |
| `substance`| TEXT       | e.g. CH₄, CO₂, CO₂bio, N₂O |
| `sector`   | TEXT       | IPCC sector code (e.g. ENF, IND, TOTALS) |
| `emission` | DOUBLE     | Emissions value (see units below) |
| `location` | GEOMETRY   | Optional; needed for spatial snapping |

The Queensland database is ~12GB and not included with this plugin. Get the workflow to build it from EDGAR data here: [Build Queensland EDGAR Database](https://github.com/skennedy-clark/Build_Queensland_EDGAR_Database)

### Spatial snapping

If DuckDB's spatial extension is available, the plugin uses `ST_Distance(location, ST_Point(lon, lat))` for snapping. Otherwise it falls back to rounding to 0.1° grid cell centres (…, 0.05, 0.15, 0.25, …).

---

## Units and Conventions

Values are plotted as: tonnes of substance per (0.1° × 0.1° grid cell) per year

Display format: t <SUBSTANCE> · (0.1°)⁻² · yr⁻¹

The plugin doesn't convert units—it assumes the DuckDB table is already consistent.

---

## Sector Handling

The sector dropdown only shows sectors with non-zero emissions for the selected substance. "All sectors" uses `sector = 'TOTALS'` if present, otherwise sums the dominant sectors.

---

## User Interface

The dock widget shows:

- Clicked coordinates (WGS84)
- Selected substance and IPCC sector
- Most recent value and year
- Substance and sector selectors
- Time-series plot
- CSV export button

The map marker updates with each click to show the snapped grid point.

---

## CSV Export

The CSV button exports the displayed time series with columns: `year, emission`

Filenames include substance, sector, and grid coordinates (rounded).

---

## Reproducibility Notes

This plugin is for exploratory analysis. Generate authoritative results via scripts. The plugin doesn't modify source data—any insights should be traceable to scripted queries.

---

## Known Limitations

The EDGAR data comes from modelling assumptions based on reported industry activities, not direct observations. See [Uncertainties in the Emissions Database for Global Atmospheric Research (EDGAR) emission inventory of greenhouse gases](https://publications.jrc.ec.europa.eu/repository/handle/JRC122204) for discussion of limitations.

---

##  Installation

### QGIS plugin installation

Install as a ZIP archive:

1. Download and zip this repository
2. Open QGIS
3. Go to Plugins → Manage and Install Plugins…
4. Select Install from ZIP
5. Choose the duckdb_click_plot.zip
6. Enable when prompted

The plugin appears in the toolbar as DuckDB Click Plot.

### Python dependency: DuckDB

You need the `duckdb` Python package in the QGIS Python environment. On Windows, QGIS uses OSGeo4W Python, not system Python.

#### Install DuckDB (Windows)

1. Open OSGeo4W Shell
2. Run: `python -m pip install duckdb`

Verify in QGIS → Plugins → Python Console:
```python
import duckdb
duckdb.__version__
```

The plugin tries to load DuckDB's spatial extension for optimised grid snapping. If unavailable, it falls back to a python/sql solution. It won't attempt to install packages automatically.

---

## Example DuckDB Queries for Parquet Outputs

These queries generate analysis-ready Parquet files suitable for time-series animations in QGIS, rasterisation workflows, or independent visualisation.

All examples assume: `emissions(lat, lon, year, substance, sector, emission, location)`

### 1. Annual totals per grid cell (single substance)

CH₄ totals, all years:
```sql
COPY (
    SELECT lat, lon, year, emission
    FROM emissions
    WHERE substance = 'CH₄'
      AND sector = 'TOTALS'
) TO 'ch4_totals_all_years_grid.parquet'
  (FORMAT PARQUET);
```

### 2. Single-year grid (for raster layers)

CH₄ totals for 2024:
```sql
COPY (
    SELECT lat, lon, emission
    FROM emissions
    WHERE substance = 'CH₄'
      AND sector = 'TOTALS'
      AND year = 2024
) TO 'ch4_totals_2024_grid.parquet'
  (FORMAT PARQUET);
```

### 3. Dominant-sector time series 

Top emitting CH₄ sectors:

```sql
WITH top_sectors AS (
    SELECT sector
    FROM emissions
    WHERE substance = 'CH₄'
      AND sector != 'TOTALS'
    GROUP BY sector
    HAVING SUM(emission) > 0
    ORDER BY SUM(emission) DESC
    LIMIT 8
)
SELECT lat, lon, year, SUM(emission) AS emission
FROM emissions
WHERE substance = 'CH₄'
  AND sector IN (SELECT sector FROM top_sectors)
GROUP BY lat, lon, year;
```

### 4. Geometry-aware export (requires spatial extension)
```sql
COPY (
    SELECT lat, lon, year, emission, location
    FROM emissions
    WHERE substance = 'CH₄'
      AND sector = 'TOTALS'
) TO 'ch4_totals_all_years_grid_geom.parquet'
  (FORMAT PARQUET);
```

---

## Notes on Animation Workflows

Load these Parquet outputs directly into QGIS. Use Temporal Controller with `year` as the temporal field. For rasterisation, Parquet → GeoPackage → Raster is usually fastest.

These Parquet files are complementary products to support reproducible research—the plugin itself doesn't depend on them.

### Export DuckDB database queries as CSV

**Command-line / DuckDB shell:**
```sql
COPY (
    SELECT *
    FROM emissions
    WHERE substance = 'CH₄'
      AND sector = 'TOTALS'
) TO 'ch4_totals.csv'
  (HEADER, DELIMITER ',');
```
Note: COPY is fast and streams directly to disk. Use a subquery to avoid mutating tables.

**From Python:**
```python
import duckdb

con = duckdb.connect("emissions.duckdb", read_only=True)

con.execute("""
    COPY (
        SELECT lat, lon, year, emission
        FROM emissions
        WHERE substance = 'CH₄'
          AND sector = 'TOTALS'
    )
    TO 'ch4_totals.csv'
    (HEADER, DELIMITER ',')
""")
```
No pandas dependency. Fast for large tables. Good for scripted pipelines.

For large-scale analysis consider using Polars—Pandas isn't recommended for multi-GB results.

---

## Licensing

Released under the GNU General Public License (GPL), consistent with QGIS plugin requirements.

---

## Contact

**Stephen Kennedy-Clark**  
Gas & Energy Transition Research Centre  
The University of Queensland  
uqsken12@uq.edu.au