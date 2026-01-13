# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DuckDBClickPlot
                                 A QGIS plugin
 Click-based exploration of gridded emissions data stored in DuckDB

 This file is the QGIS *plugin entry point*. It is discovered and invoked
 automatically by QGIS when the plugin is loaded.

 It exposes a single factory function (`classFactory`) which returns an
 instance of the main plugin class.

 ---------------------------------------------------------------------------
 Author:
     Stephen Kennedy-Clark
     Gas & Energy Transition Research Centre
     The University of Queensland

 Begin:
     2025-12-17

 Copyright:
     (C) 2025 University of Queensland

 Licence:
     GNU General Public License v2 or later
 ---------------------------------------------------------------------------

 Generated originally using QGIS Plugin Builder:
     http://g-sherman.github.io/Qgis-Plugin-Builder/

 The generated boilerplate has been retained intentionally, as QGIS expects
 this structure for plugin discovery and loading.
 ***************************************************************************/
"""

# NOTE:
# QGIS looks specifically for a function named `classFactory(iface)`
# in the top-level module of each plugin. This function must return
# an instance of the plugin's main class.


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """
    QGIS plugin factory function.

    This function is called by QGIS when the plugin is loaded.
    It must return an instance of the plugin's main class.

    Parameters
    ----------
    iface : QgsInterface
        The QGIS interface object. This provides access to the main
        application, map canvas, menus, toolbars, etc.

    Returns
    -------
    DuckDBClickPlot
        An instance of the main plugin class.
    """

    # Import is done here (rather than at top-level) to ensure that
    # QGIS has fully initialised its environment before plugin code
    # is executed.
    from .duckdb_click_plot import DuckDBClickPlot

    return DuckDBClickPlot(iface)
