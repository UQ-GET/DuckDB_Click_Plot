from qgis.gui import QgsMapToolEmitPoint
from qgis.PyQt.QtCore import pyqtSignal


class ClickTool(QgsMapToolEmitPoint):
    clicked = pyqtSignal(object)  # QgsPointXY

    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas

    def canvasReleaseEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        self.clicked.emit(point)
