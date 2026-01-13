# -*- coding: utf-8 -*-
"""
DuckDB query helpers for DuckDBClickPlot plugin.

This module contains **all database-side logic** used by the plugin.
It is intentionally kept separate from any QGIS or UI code so that:

- scientific assumptions are easy to audit
- queries can be tested independently in DuckDB
- future changes to aggregation logic are localised

---------------------------------------------------------------------------
Author:
    Stephen Kennedy-Clark
    Gas & Energy Transition Research Centre
    The University of Queensland

Scientific context:
    - Emissions are stored on a regular 0.1° × 0.1° grid.
    - Latitude/longitude values refer to **cell centres**, not corners.
    - Time series are yearly totals per grid cell.
    - Sector codes follow IPCC-style conventions.
---------------------------------------------------------------------------

Tables assumed:
    emissions(
        lat DOUBLE,
        lon DOUBLE,
        year INTEGER,
        substance VARCHAR,
        sector VARCHAR,
        emission DOUBLE,
        location GEOMETRY
    )
"""

def find_nearest_point(con, lon, lat):
    """
    Find the nearest grid-cell centre to an arbitrary point.

    This function requires DuckDB's spatial extension and uses
    ST_Distance on the stored GEOMETRY column.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Open DuckDB connection (spatial extension loaded).
    lon : float
        Longitude in degrees (WGS84).
    lat : float
        Latitude in degrees (WGS84).

    Returns
    -------
    (lat, lon) : tuple of float
        Latitude and longitude of the nearest grid-cell centre.

    Notes
    -----
    - This is used only for snapping the user’s click to the grid.
    - Performance is acceptable because the grid is coarse (0.1°).
    - A deterministic mathematical fallback exists in the main plugin
      if the spatial extension is unavailable.
    """
    sql = """
    SELECT lat, lon
    FROM emissions
    ORDER BY ST_Distance(location, ST_Point(?, ?))
    LIMIT 1;
    """
    return con.execute(sql, [lon, lat]).fetchone()


def top_sectors_for_substance(con, substance, limit=8):
    """
    Determine the dominant emitting sectors for a given substance.

    This helper is *not currently used dynamically* by the plugin,
    but is retained for:
      - exploratory analysis
      - validating hard-coded sector selections
      - potential future extensions

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Open DuckDB connection.
    substance : str
        Gas or species code (e.g. 'CH4', 'CO2', 'N2O').
    limit : int, optional
        Number of sectors to return (default: 8).

    Returns
    -------
    list of str
        Sector codes ordered by total emissions (descending).

    Scientific notes
    ----------------
    - The 'TOTALS' sector is explicitly excluded to avoid double counting.
    - Sectors with zero total emissions are excluded.
    - Ranking is based on *global* totals for the substance, not per-cell.
    """
    sql = """
    SELECT sector
    FROM emissions
    WHERE substance = ?
      AND sector != 'TOTALS'
    GROUP BY sector
    HAVING SUM(emission) > 0
    ORDER BY SUM(emission) DESC
    LIMIT ?;
    """
    rows = con.execute(sql, [substance, limit]).fetchall()
    return [r[0] for r in rows]


def query_timeseries(con, lat, lon, substance="CH4", sector=None, top_sectors=None):
    """
    Query a yearly emissions time series for a single grid cell.

    Parameters
    ----------
    con : duckdb.DuckDBPyConnection
        Open DuckDB connection.
    lat : float
        Grid-cell centre latitude.
    lon : float
        Grid-cell centre longitude.
    substance : str, optional
        Gas/species code (default: 'CH4').
    sector : str or None, optional
        IPCC sector code.
        - None means "All sectors".
    top_sectors : list of str or None, optional
        List of sector codes used as a fallback aggregation set
        when TOTALS is not available.

    Returns
    -------
    pandas.DataFrame
        Columns:
            - year (int)
            - emission (float)

    Aggregation semantics
    ---------------------
    This function deliberately encodes the following logic:

    1. If `sector` is None ("All sectors" mode):
        a) Prefer sector = 'TOTALS' if it exists for this
           (lat, lon, substance) combination.
        b) If TOTALS does not exist, fall back to summing
           emissions over `top_sectors`.

    2. If `sector` is specified:
        - Return emissions for that sector only.

    Rationale
    ---------
    - Many inventories provide a pre-computed TOTALS sector that
      avoids double counting across IPCC categories.
    - Where TOTALS is missing, summing a small, fixed set of dominant
      sectors captures >96–99% of emissions for most substances,
      which is acceptable for exploratory analysis.
    - This behaviour is explicit and auditable.
    """

    if sector is None:
        # ---- Case 1: "All sectors" ----
        # Prefer TOTALS when present (avoids double counting)
        sql_totals = """
        SELECT year, SUM(emission) AS emission
        FROM emissions
        WHERE lat = ? AND lon = ?
          AND substance = ?
          AND sector = 'TOTALS'
        GROUP BY year
        ORDER BY year;
        """
        df = con.execute(sql_totals, [lat, lon, substance]).fetchdf()
        if df is not None and not df.empty:
            return df

        # Fallback: sum dominant sectors only (explicit, bounded set)
        if top_sectors:
            placeholders = ",".join(["?"] * len(top_sectors))
            sql_fallback = f"""
            SELECT year, SUM(emission) AS emission
            FROM emissions
            WHERE lat = ? AND lon = ?
              AND substance = ?
              AND sector IN ({placeholders})
            GROUP BY year
            ORDER BY year;
            """
            params = [lat, lon, substance] + list(top_sectors)
            return con.execute(sql_fallback, params).fetchdf()

        # No TOTALS and no fallback sectors: return empty result
        return df

    # ---- Case 2: Specific sector ----
    sql_sector = """
    SELECT year, SUM(emission) AS emission
    FROM emissions
    WHERE lat = ? AND lon = ?
      AND substance = ?
      AND sector = ?
    GROUP BY year
    ORDER BY year;
    """
    return con.execute(sql_sector, [lat, lon, substance, sector]).fetchdf()
