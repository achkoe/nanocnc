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
import json
from PyQt5 import QtWidgets, QtCore, QtGui

import libnanocnc


PROGNAME = "nanocnc"


class Attribute(enum.Enum):
    NONE = enum.auto()
    INNER = enum.auto()
    OUTER = enum.auto()
    DISABLE = enum.auto()
    IGNORE = enum.auto()
    ADD_TAB = enum.auto()
    REMOVE_TAB = enum.auto()


class Zoom(enum.Enum):
    FIT, IN, OUT = enum.auto(), enum.auto(), enum.auto()


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

class CommandWidget(QtWidgets.QWidget):

    signal_actionclicked = QtCore.pyqtSignal()

    def __init__(self, graphicview):
        super().__init__()
        self.graphicview = graphicview
        layout = QtWidgets.QVBoxLayout()
        button = QtWidgets.QPushButton("Zoom In")
        button._data = Zoom.IN
        layout.addWidget(button)
        button.clicked.connect(self.buttonZoomClick)
        button = QtWidgets.QPushButton("Zoom Out")
        button._data = Zoom.OUT
        button.clicked.connect(self.buttonZoomClick)
        layout.addWidget(button)
        button = QtWidgets.QPushButton("Fit in View")
        button.clicked.connect(self.buttonZoomClick)
        button._data = Zoom.FIT
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

        button = QtWidgets.QPushButton("Add tab",)
        button._data = Attribute.ADD_TAB
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        button.setCheckable(True)
        layout.addWidget(button)

        button = QtWidgets.QPushButton("Remove tab",)
        button._data = Attribute.REMOVE_TAB
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        button.setCheckable(True)
        layout.addWidget(button)

        layout.addWidget(QtWidgets.QLabel("Tab width"))
        cbTabWidth = QtWidgets.QComboBox()
        cbTabWidth.addItems(["1mm", "2mm", "3mm", "4mm"])
        layout.addWidget(cbTabWidth)
        layout.addStretch(1)

        layout.addWidget(QtWidgets.QLabel("Tab height"))
        cbTabHeight = QtWidgets.QComboBox()
        cbTabHeight.addItems(["100%", "80%", "60%", "40%", "20%"])
        layout.addWidget(cbTabHeight)
        layout.addStretch(1)
        self.setLayout(layout)

        self.cutmode = Attribute.NONE

    def buttonZoomClick(self):
        button = self.sender()
        if button._data == Zoom.OUT:
            self.graphicview.scale(1 / 1.2, 1 / 1.2)
        elif button._data == Zoom.IN:
            self.graphicview.scale(1.2, 1.2)
        elif button._data == Zoom.FIT:
            self.graphicview.fitInView(self.graphicview.scene().itemsBoundingRect(), QtCore.Qt.KeepAspectRatio)

    def buttonActionClicked(self):
        button = self.sender()
        [other.setChecked(False) for other in self.buttongroup.buttons() if other != button]
        print(button, button.isChecked())
        self.cutmode = button._data
        self.signal_actionclicked.emit()


class ToolWidget(QtWidgets.QTableWidget):
    def __init__(self, toollist):
        super().__init__()
        self.setColumnCount(len(toollist[0].keys()))
        self.setRowCount(len(toollist))
        self.setHorizontalHeaderLabels(toollist[0].keys())
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.itemSelectionChanged.connect(self.toolChanged)

        for row, tool in enumerate(toollist):
            for column, key in enumerate(tool.keys()):
                item = QtWidgets.QTableWidgetItem(str(tool[key]))
                self.setItem(row, column, item)
        self.currenttool = 0
        self.selectRow(self.currenttool)

    def toolChanged(self):
        self.currenttool = self.selectionModel().selectedRows()[0].row()


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, settings, filename=None):
        super().__init__()
        print(filename)
        self.setWindowTitle(PROGNAME)
        self.setGeometry(0, 0, 600, 600)
        self.settings = settings
        self.filename = filename
        self.graphicview = GraphicView()
        self.graphicview.signal_groupselect.connect(self.groupSelect)

        self.commandwidget = CommandWidget(self.graphicview)
        self.toolWidget = ToolWidget(settings["tooltable"])

        self.openAct = QtWidgets.QAction("&Open...", self, shortcut="Ctrl+O", triggered=self.open)
        self.saveAct = QtWidgets.QAction("&Save...", self, shortcut="Ctrl+S", triggered=self.save, enabled=False)
        self.exitAct = QtWidgets.QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)

        self.fileMenu = QtWidgets.QMenu("&File", self)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addAction(self.saveAct)
        self.fileMenu.addAction(self.exitAct)
        self.menuBar().addMenu(self.fileMenu)

        dockWidget = QtWidgets.QDockWidget("Commands")
        dockWidget.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable)
        dockWidget.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)
        dockWidget.setWidget(self.commandwidget)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, dockWidget)

        dockWidget = QtWidgets.QDockWidget("Tools")
        dockWidget.setFeatures(QtWidgets.QDockWidget.DockWidgetMovable)
        dockWidget.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea | QtCore.Qt.TopDockWidgetArea)
        dockWidget.setWidget(self.toolWidget)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dockWidget)

        mainlayout = QtWidgets.QHBoxLayout()
        mainlayout.addWidget(self.graphicview)
        self.setCentralWidget(self.graphicview)
        if filename:
            self.open(filename=filename)

    def groupSelect(self, item):
        tool = self.settings["tooltable"][self.toolWidget.currenttool]
        diameter = tool["Diameter"]
        if self.commandwidget.cutmode == Attribute.NONE:
            item._pathattr = Attribute.NONE
            effect = QtWidgets.QGraphicsColorizeEffect()
            effect.setColor(QtGui.QColor(0, 0, 0))
            item.setGraphicsEffect(effect)
            group = getattr(item, "_group", None)
            if group is not None:
                self.graphicview.deleteGroup(group)
                item._group = None
        elif self.commandwidget.cutmode == Attribute.INNER:
            if item._pathattr == Attribute.NONE:
                print("INNER")
                group = self.graphicview.drawPolygon(item._polygon.expand(diameter / 2), pathattr=Attribute.IGNORE)
                item._group = group
                item._pathattr = Attribute.INNER
                item._tool = tool
        elif self.commandwidget.cutmode == Attribute.OUTER:
            if item._pathattr == Attribute.NONE:
                print("OUTER")
                group = self.graphicview.drawPolygon(item._polygon.expand(-diameter / 2), pathattr=Attribute.IGNORE)
                item._group = group
                item._pathattr = Attribute.OUTER
                item._tool = tool
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

    def loadSvgFile(self, filename):
        polygonlist = libnanocnc.svg2polygon(filename)
        self.graphicview.drawPolygonList(polygonlist, clear=True)

    def save(self, filename=None):
        print("save need to be implemented")

    def open(self, _, filename=None):
        print(filename)
        if filename is None:
            filename = QtWidgets.QFileDialog.getOpenFileName(self, "Open File", ".", "*.svg")[0]
        if filename:
            try:
                self.loadSvgFile(filename)
            except Exception:
                QtWidgets.QMessageBox.critical(self, "Error opening file", traceback.format_exc())
                return

if __name__ == '__main__':
    settings = json.load(open("settings.json"))
    filename = None if len(sys.argv) < 2 else sys.argv[1]
    print(filename)
    #filename = "/home/achim/Dokumente/cnc/kreispoly.svg"
    app = QtWidgets.QApplication([sys.argv[0]] + ["-style", "Fusion"] + sys.argv[1:])
    o = MainWindow(settings, filename)
    o.show()
    sys.exit(app.exec_())

