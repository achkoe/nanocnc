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
    NONE = enum.auto()      # indicates no action on path
    INNER = enum.auto()     # indicates an inner cut for path
    OUTER = enum.auto()     # indicates an outer cut for path
    DISABLE = enum.auto()   # indicates an ignored path
    CUTPATH = enum.auto()   # indicates that path is a cut path
    ADD_TAB = enum.auto()       # action to add a tab to a cut path
    REMOVE_TAB = enum.auto()    # action to remove a tab from a cut path


class Zoom(enum.Enum):
    FIT, IN, OUT = enum.auto(), enum.auto(), enum.auto()


class GraphicView(QtWidgets.QGraphicsView):

    signal_itemselect = QtCore.pyqtSignal(QtWidgets.QGraphicsItem, float, float)
    signal_mousepos_changed = QtCore.pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self.selectlist = [Attribute.NONE, Attribute.INNER, Attribute.OUTER, Attribute.DISABLE]
        self.setMouseTracking(True)
        self.pid = 0
        self.previousitemslist = []
        self.color_a = QtGui.QColor(255, 0, 0)
        self.color_b = QtGui.QColor(255, 255, 0)
        self.effect_a = QtWidgets.QGraphicsColorizeEffect()
        self.effect_a.setColor(self.color_a)
        self.effect_b = QtWidgets.QGraphicsColorizeEffect()
        self.effect_b.setColor(self.color_b)

    def setAction(self, action):
        if action in [Attribute.ADD_TAB, Attribute.REMOVE_TAB]:
            self.selectlist = [Attribute.CUTPATH]
        else:
            self.selectlist = [Attribute.NONE, Attribute.INNER, Attribute.OUTER, Attribute.DISABLE]

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
            group.addToGroup(QtWidgets.QGraphicsLineItem(polygon.xlist[index], polygon.ylist[index], polygon.xlist[index + 1], polygon.ylist[index + 1]))
        group._pathattr = pathattr
        group._polygon = polygon
        group._tool = None
        self.pid += 1
        group._pid = self.pid
        print(group, self.pid)
        if pathattr == Attribute.CUTPATH:
            effect = QtWidgets.QGraphicsColorizeEffect()
            effect.setColor(QtGui.QColor(0, 0, 255))
            group.setGraphicsEffect(effect)
        self.scene().addItem(group)
        return group

    def deleteGroup(self, group):
        print("deleteGroup")
        group.prepareGeometryChange()
        self.scene().removeItem(group)

    def addTab(self, itemgroup, xpos, ypos, tabwidth, tabheight):
        print("ADD_TAB", itemgroup._pid)
        nearest_item = None
        nearest_distance = 2 ** 30
        N = 10
        # get the item with nearest distance to (xpos, ypos)
        for item in itemgroup.childItems():
            for t in range(N):
                pt = item.line().pointAt(t / N)
                distance = (xpos - pt.x()) ** 2 + (ypos - pt.y()) ** 2
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_item = item
        if nearest_item is None:
            print("No nearest item found")
            return
        # get position atline where to put tab on
        if nearest_item.line().length() <= tabwidth:
            center = nearest_item.line().center()
            tabxpos, tabypos = center.x(), center.y()
        else:
            nearest_distance = 2 ** 30
            nearest_point = nearest_item.line().p1()
            N = 100
            for t in range(N):
                pt = nearest_item.line().pointAt(t / N)
                distance = (xpos - pt.x()) ** 2 + (ypos - pt.y()) ** 2
                if distance < nearest_distance:
                    nearest_distance = distance
                    nearest_point = pt
            tabxpos, tabypos = nearest_point.x(), nearest_point.y()

        item = QtWidgets.QGraphicsEllipseItem(tabxpos - 1, tabypos - 1, 2, 2)
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(QtGui.QColor(0, 255, 255))
        item.setGraphicsEffect(effect)
        self.scene().addItem(item)

    def mousePressEvent(self, event):
        extension = 3
        pos = self.cursor().pos()
        scenePoint = self.mapToScene(self.mapFromGlobal(pos))
        rect = QtCore.QRectF(scenePoint.x() - extension, scenePoint.y() - extension, 2 * extension, 2 * extension)
        #self.scene().addItem(QtWidgets.QGraphicsRectItem(rect))
        itemlist = [item for item in self.scene().items(rect) if isinstance(item, QtWidgets.QGraphicsItemGroup) and item._pathattr in self.selectlist]
        # itemlist = [item for item in self.scene().items(rect) if item in self.activegroup.childItems()]
        # print(itemlist)
        if len(itemlist) != 1:
            return
        self.signal_itemselect.emit(itemlist[0], scenePoint.x(), scenePoint.y())

    def mouseMoveEvent(self, event):
        for item in self.previousitemslist:
            effect = QtWidgets.QGraphicsColorizeEffect()
            if getattr(item, "_pathattr", None) == Attribute.CUTPATH:
                effect.setColor(QtGui.QColor(0, 0, 255))
            else:
                effect.setColor(QtGui.QColor(0, 0, 0))
            item.setGraphicsEffect(effect)
        extension = 3
        pos = self.cursor().pos()
        scenePoint = self.mapToScene(self.mapFromGlobal(pos))
        rect = QtCore.QRectF(scenePoint.x() - extension, scenePoint.y() - extension, 2 * extension, 2 * extension)
        self.previousitemslist = [item for item in self.scene().items(rect) if isinstance(item, QtWidgets.QGraphicsItemGroup) and item._pathattr in self.selectlist]
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(QtGui.QColor(255, 0, 0))
        [item.setGraphicsEffect(effect) for item in self.previousitemslist]
        self.signal_mousepos_changed.emit(scenePoint.x(), scenePoint.y())

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
        self.cbTabWidth = QtWidgets.QComboBox()
        self.cbTabWidth.addItems(["1", "2", "3", "4"])
        layout.addWidget(self.cbTabWidth)
        layout.addStretch(1)

        layout.addWidget(QtWidgets.QLabel("Tab height"))
        self.cbTabHeight = QtWidgets.QComboBox()
        self.cbTabHeight.addItems(["100%", "80%", "60%", "40%", "20%"])
        layout.addWidget(self.cbTabHeight)
        layout.addStretch(1)
        self.setLayout(layout)

        self.action = Attribute.NONE

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
        self.action = button._data
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
        self.graphicview.signal_itemselect.connect(self.itemSelect)
        self.graphicview.signal_mousepos_changed.connect(self.viewMousePosition)

        self.commandwidget = CommandWidget(self.graphicview)
        self.commandwidget.signal_actionclicked.connect(self.updateAction)
        self.updateAction()

        self.toolWidget = ToolWidget(settings["tooltable"])

        self.openAct = QtWidgets.QAction("&Open...", self, shortcut="Ctrl+O", triggered=self.open)
        self.saveAct = QtWidgets.QAction("&Save...", self, shortcut="Ctrl+S", triggered=self.save)#, enabled=False)
        self.exitAct = QtWidgets.QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)

        self.fileMenu = QtWidgets.QMenu("&File", self)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addAction(self.saveAct)
        self.fileMenu.addAction(self.exitAct)
        self.menuBar().addMenu(self.fileMenu)

        self.mouseposLabel = QtWidgets.QLabel("----.-, ----.-")
        statusBar = self.statusBar()
        statusBar.addWidget(self.mouseposLabel)

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
            self.open(None, filename=filename)
            self.save()

    def viewMousePosition(self, xpos, ypos):
        self.mouseposLabel.setText("{:4.1f}, {:4.1f}".format(xpos, ypos))

    def itemSelect(self, item, xpos, ypos):
        tool = self.settings["tooltable"][self.toolWidget.currenttool]
        diameter = tool["Diameter"]
        if self.commandwidget.action == Attribute.NONE:
            item._pathattr = Attribute.NONE
            effect = QtWidgets.QGraphicsColorizeEffect()
            effect.setColor(QtGui.QColor(0, 0, 0))
            item.setGraphicsEffect(effect)
            group = getattr(item, "_group", None)
            if group is not None:
                self.graphicview.deleteGroup(group)
                item._group = None
        elif self.commandwidget.action == Attribute.INNER:
            if item._pathattr == Attribute.NONE:
                print("INNER")
                group = self.graphicview.drawPolygon(item._polygon.expand(diameter / 2), pathattr=Attribute.CUTPATH)
                item._group = group
                item._pathattr = Attribute.INNER
                item._tool = tool
        elif self.commandwidget.action == Attribute.OUTER:
            if item._pathattr == Attribute.NONE:
                print("OUTER")
                group = self.graphicview.drawPolygon(item._polygon.expand(-diameter / 2), pathattr=Attribute.CUTPATH)
                item._group = group
                item._pathattr = Attribute.OUTER
                item._tool = tool
        elif self.commandwidget.action == Attribute.DISABLE:
            if item._pathattr == Attribute.NONE:
                print("DISABLE")
                effect = QtWidgets.QGraphicsColorizeEffect()
                effect.setColor(QtGui.QColor(128, 128, 128))
                item.setGraphicsEffect(effect)
                item._pathattr = Attribute.DISABLE
        elif self.commandwidget.action == Attribute.CUTPATH:
            pass
        elif self.commandwidget.action == Attribute.ADD_TAB:
            width = float(self.commandwidget.cbTabWidth.currentText())
            height = self.commandwidget.cbTabHeight.currentText()
            self.graphicview.addTab(item, xpos, ypos, width, height)
        elif self.commandwidget.action == Attribute.REMOVE_TAB:
            pass
        else:
            raise AttributeError(self.commandwidget.action)

        self.graphicview.update()

    def updateAction(self):
        self.graphicview.setAction(self.commandwidget.action)

    def loadSvgFile(self, filename):
        polygonlist = libnanocnc.svg2polygon(filename)
        self.graphicview.drawPolygonList(polygonlist, clear=True)

    def save(self, filename=None):
        print("save need to be implemented")
        itemlist = [item for item in self.graphicview.scene().items() if isinstance(item, QtWidgets.QGraphicsItemGroup)]
        olist = []
        for item in itemlist:
            olist.append(dict(pathattr=item._pathattr.value, polygon=item._polygon.asdict(), tool=item._tool))
        import json
        json.dump(olist, open("n.nanocnc", "w"), indent=4)

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

