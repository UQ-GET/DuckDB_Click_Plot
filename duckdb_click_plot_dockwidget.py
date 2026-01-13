# -*- coding: utf-8 -*-
"""
DuckDBClickPlotDockWidget

Dock widget UI for the DuckDB Click Plot QGIS plugin.

Responsibilities:
- Display contextual information about the last map click
- Provide selectors for substance and IPCC sector
- Render a time-series plot of emissions
- Allow export of the currently plotted data to CSV

This widget deliberately contains *no database logic*.
All querying and snapping logic lives in the main plugin class.

Author:
    Stephen Kennedy-Clark
    Gas & Energy Transition Research Centre
    The University of Queensland
"""

import os
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class DuckDBClickPlotDockWidget(QtWidgets.QDockWidget):
    """
    Dock widget providing:
      - Information panel (location, substance, sector, value)
      - Substance and sector selectors
      - Time-series plot
      - CSV export

    Emits a signal when closed so the main plugin can clean up
    (e.g. remove map markers).
    """

    # Emitted when the dock widget is closed
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Click Plot")

        # -----------------------------
        # State for CSV export
        # -----------------------------
        # Store the most recently plotted DataFrame
        self._last_df = None

        # Context used to build filenames and annotations for export
        self._ctx = {
            "lat": None,
            "lon": None,
            "substance": None,
            "sector": None,
        }

        # -----------------------------
        # Root widget + main layout
        # -----------------------------
        root = QtWidgets.QWidget()
        self.setWidget(root)

        # Compact vertical layout to maximise plot area
        layout = QtWidgets.QVBoxLayout(root)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # -----------------------------
        # Information label
        # -----------------------------
        # Displays clicked location, substance, sector and
        # the most recent emission value.
        self.info_label = QtWidgets.QLabel("Click the map…")
        self.info_label.setWordWrap(True)
        self.info_label.setMinimumHeight(40)
        layout.addWidget(self.info_label)

        # -----------------------------
        # Controls row:
        #   Substance | Sector | Export
        # -----------------------------
        controls = QtWidgets.QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(6)

        # ---- Substance selector ----
        substance_col = QtWidgets.QVBoxLayout()
        substance_col.setContentsMargins(0, 0, 0, 0)
        substance_col.setSpacing(2)

        substance_col.addWidget(QtWidgets.QLabel("Substance:"))
        self.substance_combo = QtWidgets.QComboBox()
        substance_col.addWidget(self.substance_combo)

        # ---- Sector selector ----
        # Given more width because IPCC labels are longer
        sector_col = QtWidgets.QVBoxLayout()
        sector_col.setContentsMargins(0, 0, 0, 0)
        sector_col.setSpacing(2)

        sector_col.addWidget(QtWidgets.QLabel("Sector:"))
        self.sector_combo = QtWidgets.QComboBox()

        # Convention:
        #   userData = None  → "All sectors"
        self.sector_combo.addItem("All sectors", userData=None)
        sector_col.addWidget(self.sector_combo)

        # ---- CSV export button ----
        # Right-aligned but on the same row to save vertical space
        export_col = QtWidgets.QVBoxLayout()
        export_col.setContentsMargins(0, 0, 0, 0)
        export_col.setSpacing(2)

        # Empty label keeps vertical alignment consistent
        export_col.addWidget(QtWidgets.QLabel(""))
        self.export_btn = QtWidgets.QPushButton("CSV…")
        self.export_btn.setToolTip("Export current time series to CSV")
        export_col.addWidget(self.export_btn)

        controls.addLayout(substance_col, 1)
        controls.addLayout(sector_col, 2)
        controls.addLayout(export_col, 0)

        layout.addLayout(controls)

        # Connect export button
        self.export_btn.clicked.connect(self.export_csv)

        # -----------------------------
        # Matplotlib plot
        # -----------------------------
        # Kept intentionally simple: one axis, one line.
        self.fig = Figure(figsize=(5, 3), dpi=100)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvas(self.fig)

        # Stretch factor ensures plot uses remaining space
        layout.addWidget(self.canvas, 1)

    def closeEvent(self, event):
        """
        Emit a signal so the main plugin can clean up
        (e.g. remove map markers) when the dock closes.
        """
        self.closingPlugin.emit()
        event.accept()

    # ------------------------------------------------------------------
    # Dropdown helpers
    # ------------------------------------------------------------------

    def set_substances(self, substances):
        """
        Populate the substance dropdown.

        Parameters
        ----------
        substances : list[str]
            List of substance codes (e.g. ["CH4", "CO2", "N2O"]).

        The substance code is stored in itemData so the UI text
        can be changed later without affecting logic.
        """
        self.substance_combo.blockSignals(True)
        self.substance_combo.clear()
        for s in substances:
            self.substance_combo.addItem(s, userData=s)
        self.substance_combo.blockSignals(False)

    def current_substance(self):
        """Return currently selected substance code."""
        return self.substance_combo.currentData()

    def set_sectors(self, sectors, labels=None):
        """
        Populate the sector dropdown.

        Parameters
        ----------
        sectors : list[str]
            IPCC sector codes to show (ordered).
        labels : dict[str, str], optional
            Mapping from sector code to human-readable name.

        Display format:
            "CODE - Human readable name"

        Logical value:
            itemData stores only the sector code.
        """
        labels = labels or {}

        self.sector_combo.blockSignals(True)
        self.sector_combo.clear()

        # "All sectors" sentinel
        self.sector_combo.addItem("All sectors", userData=None)

        for code in sectors:
            name = labels.get(code, "")
            text = f"{code} - {name}" if name else code
            self.sector_combo.addItem(text, userData=code)

        self.sector_combo.blockSignals(False)

    def current_sector(self):
        """
        Return selected sector code.

        Returns
        -------
        str | None
            None represents "All sectors".
        """
        return self.sector_combo.currentData()

    # ------------------------------------------------------------------
    # Plot + CSV export
    # ------------------------------------------------------------------

    def set_context(self, lat, lon, substance, sector):
        """
        Store the current query context.

        This information is used for:
        - CSV filename generation
        - Reproducibility (knowing what was plotted)
        """
        self._ctx = {
            "lat": lat,
            "lon": lon,
            "substance": substance,
            "sector": sector,
        }

    def update_plot(self, df, title, ylabel=None):
        """
        Update the matplotlib plot.

        Parameters
        ----------
        df : pandas.DataFrame
            Must contain columns: 'year', 'emission'
        title : str
            Plot title
        ylabel : str, optional
            Y-axis label (typically includes units)
        """
        self._last_df = df
        self.ax.clear()

        if df is None or df.empty:
            # Explicit empty-state handling
            self.ax.set_title(title)
            self.ax.set_xlabel("Year")
            if ylabel:
                self.ax.set_ylabel(ylabel)
            self.ax.text(
                0.5, 0.5, "No data",
                transform=self.ax.transAxes,
                ha="center", va="center"
            )
            self.canvas.draw()
            return

        # Standard time-series plot
        self.ax.plot(df["year"], df["emission"])
        self.ax.set_title(title)
        self.ax.set_xlabel("Year")
        if ylabel:
            self.ax.set_ylabel(ylabel)

        self.fig.tight_layout()
        self.canvas.draw()

    def export_csv(self):
        """
        Export the currently plotted time series to CSV.

        The exported file contains exactly the data shown
        in the plot — no additional aggregation or filtering.
        """
        if self._last_df is None or self._last_df.empty:
            QtWidgets.QMessageBox.information(
                self, "Export CSV", "No data to export yet."
            )
            return

        lat = self._ctx.get("lat")
        lon = self._ctx.get("lon")
        substance = self._ctx.get("substance") or "unknown"
        sector = self._ctx.get("sector") or "TOTALS"

        def safe(x):
            """Make strings filesystem-safe."""
            return str(x).replace(" ", "_").replace("/", "_")

        if lat is None or lon is None:
            default_name = f"{safe(substance)}_{safe(sector)}.csv"
        else:
            default_name = (
                f"{safe(substance)}_{safe(sector)}_{lat:.2f}_{lon:.2f}.csv"
            )

        start_dir = os.path.expanduser("~")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export time series to CSV",
            os.path.join(start_dir, default_name),
            "CSV (*.csv)"
        )
        if not path:
            return

        try:
            self._last_df.to_csv(path, index=False)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Export CSV", f"Failed to write CSV:\n{e}"
            )
            return

        QtWidgets.QMessageBox.information(
            self, "Export CSV", f"Wrote:\n{path}"
        )
