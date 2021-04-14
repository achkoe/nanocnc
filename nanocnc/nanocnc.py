"""
CNC programs only support linear moves and arc moves

svgpathtools supports Arc, Line CubicBezier

For offsetting path:
Arc -> offset_curve
CubicBezier -> offset_curve
Line -> Shapely
"""

import sys
import enum
from PyQt5 import QtWidgets, QtCore, QtGui

import libnanocnc


class Attribute(enum.Enum):
    NONE = enum.auto()
    INNER = enum.auto()
    OUTER = enum.auto()
    DISABLE = enum.auto()
    IGNORE = enum.auto()


class GraphicView(QtWidgets.QGraphicsView):

    signal_groupselect = QtCore.pyqtSignal(QtWidgets.QGraphicsItem)

    def __init__(self):
        super().__init__()
        self.setMouseTracking(True)
        self.color_a = QtGui.QColor(255, 0, 0)
        self.color_b = QtGui.QColor(255, 255, 0)
        self.effect_a = QtWidgets.QGraphicsColorizeEffect()
        self.effect_a.setColor(self.color_a)
        self.effect_b = QtWidgets.QGraphicsColorizeEffect()
        self.effect_b.setColor(self.color_b)

    def drawPolygonList(self, polygonlist, clear=False, pathattr=Attribute.NONE):
        if clear is True:
            self.setScene(QtWidgets.QGraphicsScene(QtCore.QRectF()))
        for polygon in polygonlist:
            self.drawPolygon(polygon, pathattr)
        self.fitInView(self.scene().itemsBoundingRect(), QtCore.Qt.KeepAspectRatio)
        self.update()

    def drawPolygon(self, polygon, pathattr):
        group = QtWidgets.QGraphicsItemGroup()
        #group = self.scene().createItemGroup([])
        for index in range(len(polygon.xlist) - 1):
            group.addToGroup(QtWidgets.QGraphicsLineItem(polygon.xlist[index], polygon.ylist[index],polygon.xlist[index + 1], polygon.ylist[index + 1]))
        group._pathattr = pathattr
        group._polygon = polygon
        if pathattr == Attribute.IGNORE:
            effect = QtWidgets.QGraphicsColorizeEffect()
            effect.setColor(QtGui.QColor(0, 0, 255))
            group.setGraphicsEffect(effect)
        self.scene().addItem(group)
        return group

    def deleteGroup(self, group):
        print("deleteGroup")
        group.prepareGeometryChange()
        self.scene().removeItem(group)

    def mousePressEvent(self, event):
        extension = 6
        pos = self.cursor().pos()
        scenePoint = self.mapToScene(self.mapFromGlobal(pos))
        rect = QtCore.QRectF(scenePoint.x() - extension, scenePoint.y() - extension, 2 * extension, 2 * extension)
        itemlist = [item for item in self.scene().items(rect) if isinstance(item, QtWidgets.QGraphicsItemGroup) and item._pathattr != Attribute.IGNORE]
        # itemlist = [item for item in self.scene().items(rect) if item in self.activegroup.childItems()]
        #print(itemlist)
        if len(itemlist) != 1:
            return
        self.signal_groupselect.emit(itemlist[0])
        return

        color = itemlist[0]._color

        effect = QtWidgets.QGraphicsColorizeEffect()
        if  color == self.color_a:
            itemlist[0]._color = self.color_b
            effect.setColor(self.color_b)
        else:
            itemlist[0]._color = self.color_a
            effect.setColor(self.color_a)
        itemlist[0].setGraphicsEffect(effect)
        self.update()


class CommandWidget(QtWidgets.QWidget):

    signal_actionclicked = QtCore.pyqtSignal()

    def __init__(self, graphicview):
        super().__init__()
        self.graphicview = graphicview
        layout = QtWidgets.QVBoxLayout()
        button = QtWidgets.QPushButton("Zoom In")
        layout.addWidget(button)
        button.clicked.connect(self.buttonZoomInClick)
        button = QtWidgets.QPushButton("Zoom Out")
        button.clicked.connect(self.buttonZoomOutClick)
        layout.addWidget(button)

        self.buttongroup = QtWidgets.QButtonGroup()
        self.buttongroup.setExclusive(True)

        button = QtWidgets.QPushButton("Cut Outer")
        button._data = Attribute.OUTER
        button.setCheckable(True)
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        layout.addWidget(button)

        button = QtWidgets.QPushButton("Cut Inner")
        button._data = Attribute.INNER
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        button.setCheckable(True)
        layout.addWidget(button)

        button = QtWidgets.QPushButton("No Cut")
        button._data = Attribute.NONE
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        button.setCheckable(True)
        layout.addWidget(button)

        button = QtWidgets.QPushButton("Disable",)
        button._data = Attribute.DISABLE
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        button.setCheckable(True)
        layout.addWidget(button)

        cbToolDiameter = QtWidgets.QComboBox()
        cbToolDiameter.addItems(["1mm", "2mm", "3mm", "4mm"])
        layout.addWidget(cbToolDiameter)
        layout.addStretch(1)
        self.setLayout(layout)

        self.cutmode = Attribute.NONE

    def buttonZoomOutClick(self):
        self.graphicview.scale(1 / 1.2, 1 / 1.2)

    def buttonZoomInClick(self):
        self.graphicview.scale(1.2, 1.2)

    def buttonActionClicked(self):
        button = self.sender()
        [other.setChecked(False) for other in self.buttongroup.buttons() if other != button]
        print(button, button.isChecked())
        self.cutmode = button._data
        self.signal_actionclicked.emit()


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, filename=None):
        super().__init__()
        self.filename = filename
        self.cutmode = Attribute.NONE
        self.graphicview = GraphicView()
        self.graphicview.signal_groupselect.connect(self.groupSelect)

        self.commandwidget = CommandWidget(self.graphicview)

        dockWidget = QtWidgets.QDockWidget("Commands")
        dockWidget.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable)
        dockWidget.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        dockWidget.setWidget(self.commandwidget)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dockWidget)

        mainlayout = QtWidgets.QHBoxLayout()
        mainlayout.addWidget(self.graphicview)
        self.setCentralWidget(self.graphicview)
        if filename is not None:
            self.loadSvgFile(filename)

    def groupSelect(self, item):
        if self.commandwidget.cutmode == Attribute.NONE:
            item._pathattr = Attribute.NONE
            effect = QtWidgets.QGraphicsColorizeEffect()
            effect.setColor(QtGui.QColor(0, 0, 0))
            item.setGraphicsEffect(effect)
            group = getattr(item, "_group", None)
            if group is not None:
                self.graphicview.deleteGroup(group)
                item._group = None
            print("44")
        elif self.commandwidget.cutmode == Attribute.INNER:
            if item._pathattr == Attribute.NONE:
                print("INNER")
                group = self.graphicview.drawPolygon(item._polygon.expand(2), pathattr=Attribute.IGNORE)
                item._group = group
                item._pathattr = Attribute.INNER
        elif self.commandwidget.cutmode == Attribute.OUTER:
            if item._pathattr == Attribute.NONE:
                print("OUTER")
                group = self.graphicview.drawPolygon(item._polygon.expand(-2), pathattr=Attribute.IGNORE)
                item._group = group
                item._pathattr = Attribute.OUTER
        elif self.commandwidget.cutmode == Attribute.DISABLE:
            if item._pathattr == Attribute.NONE:
                print("DISABLE")
                effect = QtWidgets.QGraphicsColorizeEffect()
                effect.setColor(QtGui.QColor(128, 128, 128))
                item.setGraphicsEffect(effect)
                item._pathattr = Attribute.DISABLE
        elif self.commandwidget.cutmode == Attribute.IGNORE:
            pass
        else:
            raise AttributeError(self.commandwidget.cutmode)

        self.graphicview.update()
        self.cutmode = Attribute.NONE

    def loadSvgFile(self, filename):
        polygonlist = libnanocnc.svg2polygon(filename)
        self.graphicview.drawPolygonList(polygonlist, clear=True)


if __name__ == '__main__':
    filename = "/home/achim/Dokumente/cnc/kreispoly.svg"
    app = QtWidgets.QApplication([sys.argv[0]] + ["-style", "Fusion"] + sys.argv[1:])
    o = MainWindow(filename)
    o.show()
    sys.exit(app.exec_())

