# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DuckDBClickPlot
                                 A QGIS plugin
 Click on map -> snap to emissions grid -> query DuckDB -> plot time series

 Author: Stephen Kennedy-Clark
 Organisation: Gas & Energy Transition Research Centre (GETRC),
               The University of Queensland

 Notes:
  - Grid assumed 0.1° × 0.1° with centres at ... 0.05, 0.15, 0.25, ...
  - "All sectors" prefers TOTALS when present, else sums top sectors list
  - Marker is rendered from icon_marker.svg and drawn as a QgsMapCanvasItem
***************************************************************************/
"""
import os
import duckdb

from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, Qt
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter
from qgis.PyQt.QtWidgets import QAction, QFileDialog
from qgis.PyQt.QtSvg import QSvgRenderer

from qgis.core import (
    QgsProject,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem,
    QgsPointXY,
)

from qgis.gui import QgsMapCanvasItem

# Initialize Qt resources (generated resources.py)
from .resources import *  # noqa: F401,F403

from .duckdb_click_plot_dockwidget import DuckDBClickPlotDockWidget
from .click_tool import ClickTool
from .duckdb_queries import find_nearest_point, query_timeseries


# ---------------------------------------------------------------------
# Hard-coded top sectors per substance (KISS / reproducible)
# ---------------------------------------------------------------------

TOP_SECTORS_BY_SUBSTANCE = {
    "CH4": ["ENF", "PRO_FFF", "PRO_COAL", "MNM", "SWD_LDF", "PRO_GAS", "WWT", "PRO_OIL"],
    "CO2": ["ENE", "TRO", "IND", "REF_TRF", "RCO", "NMM", "TNR_Aviation_CRS", "TNR_Other"],
    "CO2bio": ["IND", "AWB", "ENE", "PRO_FFF", "TRO", "SWD_INC", "TNR_Aviation_CRS", "TNR_Aviation_CDS"],
    "N2O": ["AGS", "IDE", "N2O", "CHE", "ENE", "RCO", "REF_TRF", "IND"],
}

# Labels for dropdown display ("CODE - Name")
SECTOR_LABELS = {
    # CH4
    "ENF": "Enteric Fermentation",
    "PRO_FFF": "Fossil Fuel Fires",
    "PRO_COAL": "Coal Production",
    "MNM": "Manure Management",
    "SWD_LDF": "Solid Waste Disposal (Landfills)",
    "PRO_GAS": "Gas Production",
    "WWT": "Wastewater Treatment",
    "PRO_OIL": "Oil Production",
    # CO2
    "ENE": "Power generation / Energy industry",
    "TRO": "Road transport",
    "IND": "Combustion for manufacturing industry",
    "REF_TRF": "Refineries & fuel transformation",
    "RCO": "Residential, commercial and other",
    "NMM": "Non-metallic minerals (e.g. cement)",
    "TNR_Aviation_CRS": "Aviation (cruise)",
    "TNR_Other": "Other transport",
    # CO2bio / shared
    "AWB": "Agricultural waste burning",
    "SWD_INC": "Solid waste incineration",
    "TNR_Aviation_CDS": "Aviation (climb & descent)",
    # N2O / shared
    "AGS": "Agricultural soils",
    "IDE": "Industrial processes (other)",
    "N2O": "Other N₂O sources",
    "CHE": "Chemical industry",
}


# ---------------------------------------------------------------------
# Canvas marker (SVG rendered to pixmap)
# ---------------------------------------------------------------------

class CanvasIconMarker(QgsMapCanvasItem):
    """Draw a pixmap anchored to a point (in map coordinates)."""

    def __init__(self, canvas, pixmap: QPixmap):
        super().__init__(canvas)
        self._pixmap = pixmap
        self._point = None  # QgsPointXY in map CRS of the canvas item
        self.setZValue(1000)

    def setPoint(self, point: QgsPointXY):
        self._point = point
        self.update()  # schedules repaint of this canvas item

    def paint(self, painter: QPainter, option, widget):
        if self._point is None or self._pixmap is None or self._pixmap.isNull():
            return

        # Convert map coords to canvas pixel coords
        p = self.toCanvasCoordinates(self._point)

        # Place marker with tip at location: centre-x, bottom-y
        x = int(p.x() - self._pixmap.width() / 2)
        y = int(p.y() - self._pixmap.height())
        painter.drawPixmap(x, y, self._pixmap)


def render_svg_to_pixmap(svg_path: str, size_px: int) -> QPixmap:
    """Render an SVG to a transparent QPixmap."""
    pm = QPixmap(size_px, size_px)
    pm.fill(Qt.transparent)
    renderer = QSvgRenderer(svg_path)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()
    return pm


# ---------------------------------------------------------------------
# Main plugin implementation
# ---------------------------------------------------------------------

class DuckDBClickPlot:
    """QGIS plugin implementation class (instantiated by __init__.py classFactory)."""

    SETTINGS_KEY_DB_PATH = "duckdb_click_plot/db_path"

    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)

        # i18n (Plugin Builder standard pattern)
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(self.plugin_dir, "i18n", f"DuckDBClickPlot_{locale}.qm")
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # UI plumbing
        self.actions = []
        self.menu = self.tr("&DuckDB Click Plot")
        self.toolbar = self.iface.addToolBar("DuckDBClickPlot")
        self.toolbar.setObjectName("DuckDBClickPlot")

        # Plugin state
        self.pluginIsActive = False
        self.dockwidget = None
        self.click_tool = None

        # DuckDB
        self.con = None
        self.DB_PATH = None

        # Query state
        self.substance = "CH4"
        self.sector = None  # None => All sectors mode (TOTALS preferred)
        self.last_grid_point = None  # (grid_lat, grid_lon)
        self._last_click_latlon = None  # (clicked_lat, clicked_lon) for info label

        # Marker state
        self.marker_item = None
        self.marker_pixmap = None

        # One-time warning flag (only relevant when spatial unavailable)
        self._warned_math_snap_miss = False

        # One-time init guards
        self._dropdowns_initialized = False
        self._signals_connected = False

    # -------------------------
    # Boilerplate / UI helpers
    # -------------------------

    def tr(self, message):
        return QCoreApplication.translate("DuckDBClickPlot", message)

    def add_action(self, icon_path, text, callback, parent=None):
        action = QAction(QIcon(icon_path), text, parent)
        action.triggered.connect(callback)
        self.toolbar.addAction(action)
        self.iface.addPluginToMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        # Toolbar/menu entry icon (your large icon.png, compiled in resources but also fine as a file)
        icon_path = os.path.join(self.plugin_dir, "icon.png")
        self.add_action(icon_path, self.tr("DuckDB Click Plot"), self.run, self.iface.mainWindow())

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)

        self.clear_marker()

        if self.con is not None:
            try:
                self.con.close()
            except Exception:
                pass
            self.con = None

        self.dockwidget = None
        self.pluginIsActive = False
        
    def onClosePlugin(self):
        # Dockwidget closed by user
        try:
            if self.dockwidget is not None:
                self.dockwidget.closingPlugin.disconnect(self.onClosePlugin)
        except Exception:
            pass

        self.clear_marker()
        self.pluginIsActive = False

    # -------------------------
    # DuckDB helpers
    # -------------------------

    def pick_db_path_if_needed(self) -> bool:
        """Load DB path from QSettings or prompt user. Returns True if set."""
        settings = QSettings()
        db_path = settings.value(self.SETTINGS_KEY_DB_PATH, "", type=str)

        if (not db_path) or (not os.path.exists(db_path)):
            db_path, _ = QFileDialog.getOpenFileName(
                self.iface.mainWindow(),
                "Select DuckDB database",
                "",
                "DuckDB (*.duckdb *.db);;All files (*.*)",
            )
            if not db_path:
                return False
            settings.setValue(self.SETTINGS_KEY_DB_PATH, db_path)

        self.DB_PATH = db_path
        return True

    def ensure_spatial_loaded(self) -> bool:
        """Attempt to load (and if needed install) DuckDB spatial extension."""
        if self.con is None:
            return False

        try:
            self.con.execute("LOAD spatial;")
            return True
        except Exception:
            pass

        try:
            self.con.execute("INSTALL spatial;")
            self.con.execute("LOAD spatial;")
            return True
        except Exception:
            return False

    @staticmethod
    def snap_center_0p1(x: float) -> float:
        """Snap to 0.1° grid centres with 0.05° offset."""
        return round((x - 0.05) * 10.0) / 10.0 + 0.05

    def point_exists(self, lat: float, lon: float) -> bool:
        """Cheap existence test for snapped point when spatial not available."""
        try:
            row = self.con.execute(
                "SELECT 1 FROM emissions WHERE lat = ? AND lon = ? LIMIT 1;",
                [lat, lon],
            ).fetchone()
            return row is not None
        except Exception:
            return False

    # -------------------------
    # Marker handling
    # -------------------------

    def ensure_marker_loaded(self):
        """Create marker canvas item once (lives until unload/close)."""
        if self.marker_item is not None:
            return

        svg_path = os.path.join(self.plugin_dir, "icon_marker.svg")
        if not os.path.exists(svg_path):
            return

        pm = render_svg_to_pixmap(svg_path, 48)
        if pm.isNull():
            return

        self.marker_pixmap = pm
        self.marker_item = CanvasIconMarker(self.iface.mapCanvas(), self.marker_pixmap)

    def update_marker(self, lon: float, lat: float):
        """Move marker to given lon/lat (WGS84)."""
        self.ensure_marker_loaded()
        if self.marker_item is None:
            return
        self.marker_item.setPoint(QgsPointXY(lon, lat))
        self.iface.mapCanvas().refresh()

    def clear_marker(self):
        """Remove marker so it doesn't persist across reloads."""
        try:
            if self.marker_item is not None:
                self.marker_item.hide()
                self.marker_item.deleteLater()
        except Exception:
            pass
        finally:
            self.marker_item = None
            self.marker_pixmap = None
            try:
                self.iface.mapCanvas().refresh()
            except Exception:
                pass

    # -------------------------
    # Main run + handlers
    # -------------------------

    def run(self):
        """Activate plugin: show dock, enable click tool, connect DB, wire signals."""
        if not self.pluginIsActive:
            self.pluginIsActive = True

            if self.dockwidget is None:
                self.dockwidget = DuckDBClickPlotDockWidget()

            self.dockwidget.closingPlugin.connect(self.onClosePlugin)
            self.iface.addDockWidget(Qt.LeftDockWidgetArea, self.dockwidget)
            self.dockwidget.show()

        # Map click tool
        if self.click_tool is None:
            self.click_tool = ClickTool(self.iface.mapCanvas())
            self.click_tool.clicked.connect(self.handle_click)

        self.iface.mapCanvas().setMapTool(self.click_tool)

        # DB connect (once)
        if self.con is None:
            if not self.pick_db_path_if_needed():
                self.dockwidget.info_label.setText("No database selected.")
                return

            self.con = duckdb.connect(self.DB_PATH, read_only=True)
            self.ensure_spatial_loaded()
            self.dockwidget.info_label.setText(f"DB: {self.DB_PATH}\nClick the map…")

        # Dropdown init (once)
        if not self._dropdowns_initialized:
            substances = list(TOP_SECTORS_BY_SUBSTANCE.keys())
            self.dockwidget.set_substances(substances)

            # Set default (if present in combo)
            # Dock stores code in itemData; current_substance reads itemData
            self.substance = self.dockwidget.current_substance() or self.substance
            self.refresh_dropdowns_for_substance()

            self._dropdowns_initialized = True

        # Connect signals (once)
        if not self._signals_connected:
            self.dockwidget.sector_combo.currentIndexChanged.connect(self.replot_last)
            self.dockwidget.substance_combo.currentIndexChanged.connect(self.handle_substance_change)
            self._signals_connected = True

    def refresh_dropdowns_for_substance(self):
        """Update sector list for current substance."""
        self.substance = self.dockwidget.current_substance() or self.substance
        top = TOP_SECTORS_BY_SUBSTANCE.get(self.substance, [])
        self.dockwidget.set_sectors(top, labels=SECTOR_LABELS)

    def handle_substance_change(self):
        """Substance changed -> update sectors -> replot last click if available."""
        self.refresh_dropdowns_for_substance()
        self.replot_last()

    def replot_last(self):
        """Re-run query and redraw plot using last snapped grid point."""
        if self.con is None or self.dockwidget is None or self.last_grid_point is None:
            return

        grid_lat, grid_lon = self.last_grid_point
        self.substance = self.dockwidget.current_substance() or self.substance
        self.sector = self.dockwidget.current_sector()

        df = query_timeseries(
            self.con,
            lat=grid_lat,
            lon=grid_lon,
            substance=self.substance,
            sector=self.sector,
            top_sectors=TOP_SECTORS_BY_SUBSTANCE.get(self.substance, []),
        )

        self._update_plot_and_info(df)

    def handle_click(self, point):
        """Map click -> WGS84 transform -> snap -> query -> plot + marker + info."""
        if self.con is None or self.dockwidget is None:
            return

        # Transform clicked point to WGS84
        canvas = self.iface.mapCanvas()
        map_crs = canvas.mapSettings().destinationCrs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        xform = QgsCoordinateTransform(map_crs, wgs84, QgsProject.instance())
        pt = xform.transform(point)
        lon, lat = pt.x(), pt.y()

        self._last_click_latlon = (lat, lon)

        # Snap to nearest point (spatial) else grid-centre rounding
        nearest = None
        if self.ensure_spatial_loaded():
            try:
                nearest = find_nearest_point(self.con, lon, lat)
            except Exception:
                nearest = None

        if nearest is not None:
            grid_lat, grid_lon = nearest
        else:
            grid_lat = self.snap_center_0p1(lat)
            grid_lon = self.snap_center_0p1(lon)

            # Warn once if the rounded node doesn't exist (edge cases)
            if (not self._warned_math_snap_miss) and (not self.point_exists(grid_lat, grid_lon)):
                self._warned_math_snap_miss = True
                self.dockwidget.info_label.setText(
                    "Warning: rounded centre point not found in DB for at least one click.\n"
                    "Consider enabling spatial extension or adding a bbox+distance fallback."
                )

        self.last_grid_point = (grid_lat, grid_lon)

        # Move marker immediately (WGS84 coords for our canvas item)
        self.update_marker(grid_lon, grid_lat)

        # Current dropdown selections
        self.substance = self.dockwidget.current_substance() or self.substance
        self.sector = self.dockwidget.current_sector()

        df = query_timeseries(
            self.con,
            lat=grid_lat,
            lon=grid_lon,
            substance=self.substance,
            sector=self.sector,
            top_sectors=TOP_SECTORS_BY_SUBSTANCE.get(self.substance, []),
        )

        self._update_plot_and_info(df)

    # -------------------------
    # Plot + info formatting
    # -------------------------

    def _unit_str(self) -> str:
        """Canonical unit string used for plot ylabel and info label."""
        # tonnes of substance per (0.1°)^2 per year
        return f"t {self.substance} · (0.1°)⁻² · yr⁻¹"

    def _update_plot_and_info(self, df):
        """Update plot, CSV export context, and info label text."""
        if self.dockwidget is None:
            return

        # Plot
        grid_lat, grid_lon = self.last_grid_point
        title = f"{self.substance} at grid {grid_lat:.2f}, {grid_lon:.2f}"
        if self.sector:
            title += f" ({self.sector})"

        ylabel = self._unit_str()

        self.dockwidget.set_context(grid_lat, grid_lon, self.substance, self.sector)
        self.dockwidget.update_plot(df, title, ylabel=ylabel)

        # Info label: clicked WGS84 + substance/sector + last value
        if self._last_click_latlon is None:
            return

        click_lat, click_lon = self._last_click_latlon
        code = self.sector if self.sector else "TOTALS"

        value_txt = "n/a"
        if df is not None and (not df.empty):
            try:
                last = df.iloc[-1]
                year = int(last["year"])
                val = float(last["emission"])
                value_txt = f"{val:.6g} {ylabel} (in {year})"
            except Exception:
                value_txt = "n/a"

        self.dockwidget.info_label.setText(
            f"Clicked (WGS84): {click_lat:.5f}, {click_lon:.5f}\n"
            f"Substance: {self.substance}, {code}, {value_txt}"
        )
