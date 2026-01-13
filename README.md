# DuckDB Click Plot (QGIS Plugin)

**Author:** Stephen Kennedy-Clark  
**Organisation:** [Gas & Energy Transition Research Centre](https://gas-energy.centre.uq.edu.au/),  
The University of Queensland  

---

## Overview

**DuckDB Click Plot** is a lightweight QGIS plugin for exploratory analysis of gridded greenhouse-gas emissions time series. The data is sourced from [EDGAR](https://edgar.jrc.ec.europa.eu/)- Emissions Database for Global Atmospheric Research. 


1. Open the plugin and then click anywhere in Queansland (Australia) on the map.  
2. The click snaps to the nearest 0.1° emissions grid point and creats a historic emissions time series graph.  
3. Emission substance and industery are selectable, defaulting to CH₄, Totals 
4. A DuckDB query retrieves the historical emissions time series  
5. The result is plotted immediately and can be exported to CSV  


---

## Intended Use

This tool is intended for:

- Rapid inspection of emissions time series at specific locations
- Comparing substances (CH₄, CO₂, CO₂bio, N₂O) at the same grid point
- Exploring dominant IPCC sectors spatially
- Exporting location-specific time series for downstream analysis

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

The database for Qld is ~12GB and is not distrubuted with this plugin. A workflow to download the origional data from [EDGAR](https://edgar.jrc.ec.europa.eu/) and create the database is avalabel seperatly: [Build Queensland EDGAR Database](https://github.com/skennedy-clark/Build_Queensland_EDGAR_Database)

### Spatial snapping

- If DuckDB’s **spatial extension** is available, this plugin uses: ST_Distance(location, ST_Point(lon, lat))
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
- The plugin intentionally avoids modifying the source data
- Any insight gained here should be traceable back to scripted queries

---

## Known Limitations

- The underlying EDGAR data is based on modeling assumptions from reported current and historical industery acttivities. This data is not based on current observations. nThe limitations of the EDGAR modeling process are discussed in [Uncertainties in the Emissions Database for Global Atmospheric Research (EDGAR) emission inventory of greenhouse gases](https://publications.jrc.ec.europa.eu/repository/handle/JRC122204)
  

---

##  Installation
### QGIS plugin installation

- This plugin is most easily installed as a ZIP archive.
1. Download and Zip this repository
2. Open QGIS
3. Go to Plugins → Manage and Install Plugins…
4. Select Install from ZIP
5. Choose the duckdb_click_plot.zip
6. Enable the plugin when prompted

Once installed, the plugin is available via the toolbar as DuckDB Click Plot.

### Python dependency: DuckDB

This plugin requires the Python package duckdb to be available in the QGIS Python environment.

- On Windows, QGIS uses the OSGeo4W Python, not system Python.

#### Install DuckDB (Windows)

1. Open OSGeo4W Shell
2. Run:
  ```bash
  python -m pip install duckdb
  ```
- Verify inside QGIS
After restarting QGIS open QGIS → Plugins → Python Console and run:
```python
import duckdb
duckdb.__version__
```
If this succeeds, the dependency is installed correctly.

The plugin does not attempt to install Python packages automatically. It does try to load and use DuckDB’s spatial extension to optomise nearest-grid snapping.
If the extension is not available or cannot be installed, the plugin falls back to a python/sql solution. 

## Example DuckDB Queries for Parquet Outputs

The following queries illustrate how to generate analysis-ready Parquet files for each substance. These products are suitable for:

- Time-series animations in QGIS
- Rasterisation workflows
- Aggregated visualisation independent of the plugin
All examples assume a base table:
```sql
emissions(lat, lon, year, substance, sector, emission, location)
```
### 1. Annual totals per grid cell (single substance)
Example: **CH₄ totals, all years**
```sql
COPY (
    SELECT
        lat,
        lon,
        year,
        emission
    FROM emissions
    WHERE substance = 'CH4'
      AND sector = 'TOTALS'
) TO 'ch4_totals_all_years_grid.parquet'
  (FORMAT PARQUET);
```

### 2. Single-year grid (for raster layers)

Example: **CH₄ totals for 2024**
```sql
COPY (
    SELECT
        lat,
        lon,
        emission
    FROM emissions
    WHERE substance = 'CH4'
      AND sector = 'TOTALS'
      AND year = 2024
) TO 'ch4_totals_2024_grid.parquet'
  (FORMAT PARQUET);
```

### 3. Dominant-sector time series 

Example: **Top emitting CH₄ sectors only**

```sql
WITH top_sectors AS (
    SELECT sector
    FROM emissions
    WHERE substance = 'CH4'
      AND sector != 'TOTALS'
    GROUP BY sector
    HAVING SUM(emission) > 0
    ORDER BY SUM(emission) DESC
    LIMIT 8
)
SELECT
    lat,
    lon,
    year,
    SUM(emission) AS emission
FROM emissions
WHERE substance = 'CH4'
  AND sector IN (SELECT sector FROM top_sectors)
GROUP BY lat, lon, year;
```

### 4. Geometry-aware export (requires spatial extension)
```sql
COPY (
    SELECT
        lat,
        lon,
        year,
        emission,
        location
    FROM emissions
    WHERE substance = 'CH4'
      AND sector = 'TOTALS'
) TO 'ch4_totals_all_years_grid_geom.parquet'
  (FORMAT PARQUET);
```

## Notes on Animation Workflows

These Parquet outputs can be loaded directly into QGIS

Use Temporal Controller with year as the temporal field

For rasterisation, Parquet → GeoPackage → Raster is typically fastest

The plugin itself does not depend on these Parquet files; they are complementary products to support reproduciable rescearch. 

### Export DuckDB database queries as CSV
1. Comandline / DuckDB shell
```sql
COPY (
    SELECT *
    FROM emissions
    WHERE substance = 'CH4'
      AND sector = 'TOTALS'
) TO 'ch4_totals.csv'
  (HEADER, DELIMITER ',');
```
note: COPY is fast and streams directly to disk. Use a subquery so you don’t mutate tables.

2. From Python
```python
import duckdb

con = duckdb.connect("emissions.duckdb", read_only=True)

con.execute("""
    COPY (
        SELECT
            lat, lon, year, emission
        FROM emissions
        WHERE substance = 'CH4'
          AND sector = 'TOTALS'
    )
    TO 'ch4_totals.csv'
    (HEADER, DELIMITER ',')
""")

```
Advantages: No pandas dependency. Very fast for large tables. Suitable for scripted pipelines.

Further analytics in Python should consider using **Polars**,  due to the multi-GB results **Pandas** is not recomended. 


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







