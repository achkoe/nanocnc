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
import pathlib
import math
import traceback
import pprint
from PyQt5 import QtWidgets, QtCore, QtGui

import libnanocnc


PROGNAME = "nanocnc"

# TODO: fix id off TAB, has to refer to base polygon, not to INNER or OUTER polygon

COLOR_NORMAL = QtGui.QColor(QtCore.Qt.black)
COLOR_HOVER = QtGui.QColor(QtCore.Qt.green)
COLOR_CUTPATH = QtGui.QColor(QtCore.Qt.blue)
COLOR_TAB =  QtGui.QColor(QtCore.Qt.red)
COLOR_OVERCUT = QtGui.QColor(QtCore.Qt.magenta)
COLOR_DISABLE = QtGui.QColor(QtCore.Qt.gray)


class Attribute(enum.Enum):
    NONE = enum.auto()      # indicates no action on path
    INNER = enum.auto()     # indicates an inner cut for path
    OUTER = enum.auto()     # indicates an outer cut for path
    DISABLE = enum.auto()   # indicates an ignored path
    CUTPATH = enum.auto()   # indicates that path is a cut path
    ADD_TAB = enum.auto()       # action to add a tab to a cut path
    REMOVE_TAB = enum.auto()    # action to remove a tab from a cut path
    ADD_OVERCUT = enum.auto()
    REMOVE_OVERCUT = enum.auto()
    TAB = enum.auto()       # indicates a TAB
    OVERCUT = enum.auto()   # indicates an OVERCUT
    CORNER = enum.auto()
    DEBUG = enum.auto()


class Zoom(enum.Enum):
    FIT, IN, OUT = enum.auto(), enum.auto(), enum.auto()


class GraphicView(QtWidgets.QGraphicsView):

    signal_itemselect = QtCore.pyqtSignal(QtWidgets.QGraphicsItem, float, float)
    signal_mousepos_changed = QtCore.pyqtSignal(float, float)

    def __init__(self):
        super().__init__()
        self.setScene(QtWidgets.QGraphicsScene(QtCore.QRectF()))
        self.selectlist = [Attribute.NONE, Attribute.INNER, Attribute.OUTER, Attribute.DISABLE]
        self.setMouseTracking(True)
        self.pid = 0
        self.mid = 0
        self.previousitemslist = []

    def setAction(self, action):
        if self.scene() is not None:
            [item.setVisible(False) for item in self.scene().items() if getattr(item, "_pathattr", None) == Attribute.CORNER]
        if action in [Attribute.ADD_TAB]:
            self.selectlist = [Attribute.CUTPATH]
            self.selectitem = QtWidgets.QGraphicsItemGroup
            self.selectlist = [Attribute.CUTPATH]
            self.selectitem = QtWidgets.QGraphicsItemGroup
        elif action in [Attribute.REMOVE_TAB]:
            self.selectlist = [Attribute.TAB]
            self.selectitem = QtWidgets.QGraphicsEllipseItem
        elif action in [Attribute.ADD_OVERCUT]:
            [item.setVisible(True) for item in self.scene().items() if getattr(item, "_pathattr", None) == Attribute.CORNER]
            self.selectlist = [Attribute.CORNER]
            self.selectitem = QtWidgets.QGraphicsEllipseItem
        elif action in [Attribute.REMOVE_OVERCUT]:
            self.selectlist = [Attribute.OVERCUT]
            self.selectitem = QtWidgets.QGraphicsEllipseItem
        else:
            self.selectlist = [Attribute.NONE, Attribute.INNER, Attribute.OUTER, Attribute.DISABLE]
            self.selectitem = QtWidgets.QGraphicsItemGroup

    def drawMarkerList(self, polygon, parentid):
        for index in range(len(polygon.xlist) - 1):
            self.drawMarker(polygon.xlist[index], polygon.ylist[index], parentid)

    def drawMarker(self, xpos, ypos, parentid, id=None):
        marker = QtWidgets.QGraphicsEllipseItem(xpos - 1, ypos - 1, 2, 2)
        marker._pathattr = Attribute.CORNER
        marker._parentrefid = parentid
        if id is None:
            self.mid += 1
            id = self.mid
        marker._id = id
        marker._pos = (xpos, ypos)
        marker.setVisible(False)
        self.scene().addItem(marker)
        return marker

    def drawPolygon(self, polygon, pathattr, tool=None):
        group = QtWidgets.QGraphicsItemGroup()
        self.pid += 1

        # determine if polygon is clockwise or counterclockwise
        # from https://gamedev.stackexchange.com/questions/43356/how-can-i-tell-whether-an-object-is-moving-cw-or-ccw-around-a-connected-path
        area = 0
        for index in range(len(polygon.xlist) - 1):
            bx = polygon.xlist[index]
            by = polygon.ylist[index]
            ex = polygon.xlist[index + 1]
            ey = polygon.ylist[index + 1]
            area += bx * ey - by * ex
        clockwise = area > 0
        if not clockwise:
            polygon.xlist = polygon.xlist[::-1]
            polygon.ylist = polygon.ylist[::-1]

        for index in range(len(polygon.xlist) - 1):
            x1, y1 = polygon.xlist[index], polygon.ylist[index]
            x2, y2 = polygon.xlist[index + 1], polygon.ylist[index + 1]
            group.addToGroup(QtWidgets.QGraphicsLineItem(x1, y1, x2, y2))

            DRAW_LABEL = False
            if DRAW_LABEL:
                label = QtWidgets.QGraphicsSimpleTextItem(str(index))
                label.setPos(x1, y1)
                self.scene().addItem(label)

        group._pathattr = pathattr
        group._polygon = polygon
        group._tool = tool
        group._pid = self.pid
        # print(group, self.pid)
        if pathattr == Attribute.CUTPATH:
            effect = QtWidgets.QGraphicsColorizeEffect()
            effect.setColor(COLOR_CUTPATH)
            group.setGraphicsEffect(effect)
        self.scene().addItem(group)
        return group

    def drawJson(self, jsonobj, clear=False):
        self.pid = 0
        self.mid = 0
        if clear is True:
            self.setScene(QtWidgets.QGraphicsScene(QtCore.QRectF()))
            self.scene().addItem(QtWidgets.QGraphicsLineItem(-2, 0, +2, 0))
            self.scene().addItem(QtWidgets.QGraphicsLineItem(0, -2, 0, +2))
        for path in jsonobj["pathlist"]:
            polygon = libnanocnc.Polygon(path["polygon"]["xlist"], path["polygon"]["ylist"])
            item = self.drawPolygon(polygon, Attribute(path["pathattr"]), path["tool"])
            item._parent = path["parentid"]
            item._pid = path["id"]
        for corner in jsonobj["cornerlist"]:
            self.drawMarker(*corner["pos"], parentid=corner["parentid"], id=corner["id"])
        for tab in jsonobj["tablist"]:
            # TODO: set attributes of returned tab item, 0 is not correct
            self.drawTab(tab["refid"], tab["pos"][0], tab["pos"][1], tab["width"], tab["height"], tab["parentid"], tab["linepoints"])
        for overcut in jsonobj["overcutlist"]:
            item = self.drawMarker(*overcut["pos"], parentid=overcut["parentid"], id=overcut["id"])
            self.addOverCut(item)
        self.fitInView(self.scene().itemsBoundingRect(), QtCore.Qt.KeepAspectRatio)
        self.update()

    def deleteGroup(self, group):
        print("deleteGroup")
        group.prepareGeometryChange()
        self.scene().removeItem(group)

    def addTab(self, itemgroup, xpos, ypos, tabwidth, tabheight, parentrefid):
        print("addTab", itemgroup._pid)
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
        # get position at line where to put tab on
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
        item = self.drawTab(itemgroup._pid, tabxpos, tabypos, tabwidth, tabheight, parentrefid, [nearest_item.line().x1(), nearest_item.line().y1(), nearest_item.line().x2(), nearest_item.line().y2()])
        return item

    def drawTab(self, pid, tabxpos, tabypos, tabwidth, tabheight, parentrefid, linepoints):
        item = QtWidgets.QGraphicsEllipseItem(tabxpos - 1, tabypos - 1, 2, 2)
        item._pathattr = Attribute.TAB
        item._pos = (tabxpos, tabypos)
        item._tabwidth = tabwidth
        item._tabheight = tabheight
        item._refid = pid
        item._parentrefid = parentrefid
        item._linepoints = linepoints
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(COLOR_TAB)
        item.setGraphicsEffect(effect)
        self.scene().addItem(item)
        return item

    def removeTab(self, item):
        item.prepareGeometryChange()
        self.scene().removeItem(item)

    def addOverCut(self, item):
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(COLOR_OVERCUT)
        item.setGraphicsEffect(effect)
        item._pathattr = Attribute.OVERCUT
        item.setVisible(True)
        self.previousitemslist = [theitem for theitem in self.previousitemslist if theitem != item]

    def removeOverCut(self, item):
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(COLOR_NORMAL)
        item.setGraphicsEffect(effect)
        item._pathattr = Attribute.CORNER
        item.setVisible(False)
        self.update()
        #self.previousitemslist = [theitem for theitem in self.previousitemslist if theitem != item]

    def getSelectionRect(self, scenePoint):
        extension = 3
        return QtCore.QRectF(scenePoint.x() - extension, scenePoint.y() - extension, 2 * extension, 2 * extension)

    def mousePressEvent(self, event):
        #self.scene().addItem(QtWidgets.QGraphicsRectItem(rect))
        pos = self.cursor().pos()
        scenePoint = self.mapToScene(self.mapFromGlobal(pos))
        itemlist = [item for item in self.scene().items(self.getSelectionRect(scenePoint)) if isinstance(item, self.selectitem) and item._pathattr in self.selectlist]
        # itemlist = [item for item in self.scene().items(rect) if item in self.activegroup.childItems()]
        # print(itemlist)
        if len(itemlist) != 1:
            return
        self.signal_itemselect.emit(itemlist[0], scenePoint.x(), scenePoint.y())

    def mouseMoveEvent(self, event):
        for item in self.previousitemslist:
            if 1:
                effect = QtWidgets.QGraphicsColorizeEffect()
                effect.setColor(getattr(item, "_last_effect", COLOR_NORMAL))
                item.setGraphicsEffect(effect)
            else:
                effect = QtWidgets.QGraphicsColorizeEffect()
                action = getattr(item, "_pathattr", None)
                #print(action)
                if action in [Attribute.CUTPATH, Attribute.TAB]:
                    effect.setColor(COLOR_CUTPATH)
                elif action in [Attribute.ADD_OVERCUT, Attribute.REMOVE_OVERCUT]:
                    effect.setColor(COLOR_HOVER)
                else:
                    effect.setColor(COLOR_NORMAL)
                item.setGraphicsEffect(effect)

        pos = self.cursor().pos()
        scenePoint = self.mapToScene(self.mapFromGlobal(pos))
        # put all items in previousitemslist ifthey are in getSelectionRect() and right item
        self.previousitemslist = [item for item in self.scene().items(self.getSelectionRect(scenePoint)) if isinstance(item, self.selectitem) and item._pathattr in self.selectlist]
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(COLOR_HOVER)
        # highlight all items in previousitemslist in color red
        for item in self.previousitemslist:
            try:
                item._last_effect = item.graphicsEffect().color()
            except Exception:
                pass
            item.setGraphicsEffect(effect)
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

        layout.addStretch(1)

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

        button = QtWidgets.QPushButton("Delete Cut")
        button._data = Attribute.NONE
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        button.setCheckable(True)
        layout.addWidget(button)

        button = QtWidgets.QPushButton("Disable Contour",)
        button._data = Attribute.DISABLE
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        button.setCheckable(True)
        layout.addWidget(button)

        layout.addStretch(1)

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
        self.wgTabWidth = QtWidgets.QDoubleSpinBox()
        self.wgTabWidth.setSuffix("mm")
        self.wgTabWidth.setRange(1, 10)
        self.wgTabWidth.setSingleStep(1)
        self.wgTabWidth.setValue(4)
        self.wgTabWidth.setDecimals(1)
        layout.addWidget(self.wgTabWidth)

        layout.addWidget(QtWidgets.QLabel("Tab height"))
        self.wgTabHeight = QtWidgets.QDoubleSpinBox()
        self.wgTabHeight.setSuffix("mm")
        self.wgTabHeight.setRange(1, 30)
        self.wgTabHeight.setSingleStep(1)
        self.wgTabHeight.setValue(4)
        self.wgTabHeight.setDecimals(1)
        layout.addWidget(self.wgTabHeight)
        layout.addStretch(1)

        button = QtWidgets.QPushButton("Add overcut")
        button._data = Attribute.ADD_OVERCUT
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        button.setCheckable(True)
        layout.addWidget(button)

        button = QtWidgets.QPushButton("Remove overcut")
        button._data = Attribute.REMOVE_OVERCUT
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        button.setCheckable(True)
        layout.addWidget(button)
        layout.addStretch(1)

        layout.addWidget(QtWidgets.QLabel("Material Thickness"))
        self.wgMaterialThickness = QtWidgets.QDoubleSpinBox()
        self.wgMaterialThickness.setSuffix("mm")
        self.wgMaterialThickness.setRange(1, 30)
        self.wgMaterialThickness.setSingleStep(1)
        self.wgMaterialThickness.setValue(10)
        self.wgMaterialThickness.setDecimals(1)
        self.wgMaterialThickness.valueChanged.connect(self.thicknessChanged)
        self.thicknessChanged(10)
        layout.addWidget(self.wgMaterialThickness)

        layout.addStretch(1)

        layout.addWidget(QtWidgets.QLabel("Safe Z"))
        self.wgSaveZ = QtWidgets.QDoubleSpinBox()
        self.wgSaveZ.setSuffix("mm")
        self.wgSaveZ.setRange(5, 50)
        self.wgSaveZ.setSingleStep(1)
        self.wgSaveZ.setValue(10)
        self.wgSaveZ.setDecimals(1)
        layout.addWidget(self.wgSaveZ)

        layout.addStretch(1)

        button = QtWidgets.QPushButton("DEBUG")
        button._data = Attribute.DEBUG
        button.clicked.connect(self.buttonActionClicked)
        self.buttongroup.addButton(button)
        layout.addWidget(button)
        layout.addStretch(1)

        self.setLayout(layout)

        self.action = Attribute.NONE

    def thicknessChanged(self, newvalue):
        self.wgTabHeight.setMaximum(newvalue)
        if self.wgTabHeight.value() > newvalue:
            self.wgTabHeight.setValue(newvalue)

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
        # print(button, button.isChecked())
        self.action = button._data
        self.signal_actionclicked.emit()


class ToolWidget(QtWidgets.QTableWidget):
    def __init__(self, toollist):
        super().__init__()
        self._initialized = False
        self.init(toollist)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.itemSelectionChanged.connect(self.toolChanged)
        self._initialized = True

    def init(self, toollist):
        if self._initialized is True:
            self.itemSelectionChanged.disconnect(self.toolChanged)
        self.clear()
        self.setColumnCount(len(toollist[0].keys()))
        self.setRowCount(len(toollist))
        self.setHorizontalHeaderLabels(toollist[0].keys())
        for row, tool in enumerate(toollist):
            for column, key in enumerate(tool.keys()):
                item = QtWidgets.QTableWidgetItem(str(tool[key]))
                self.setItem(row, column, item)
        self.currenttool = 0
        self.selectRow(self.currenttool)
        if self._initialized is True:
            self.itemSelectionChanged.connect(self.toolChanged)

    def toolChanged(self):
        self.currenttool = self.selectionModel().selectedRows()[0].row()


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, settings, filename=None):
        super().__init__()
        self.setWindowTitle(PROGNAME)
        self.setGeometry(0, 0, 1024, 1024)
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
        self.gcodeAct = QtWidgets.QAction("Save &GCode...", self, shortcut="Ctrl+G", triggered=self.save_gcode)#, enabled=False)
        self.exitAct = QtWidgets.QAction("E&xit", self, shortcut="Ctrl+Q", triggered=self.close)

        self.fileMenu = QtWidgets.QMenu("&File", self)
        self.fileMenu.addAction(self.openAct)
        self.fileMenu.addAction(self.saveAct)
        self.fileMenu.addAction(self.gcodeAct)
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

        #---------------------------------------------------
        if 0:
            tb = QtWidgets.QToolBar()
            tb.setIconSize(QtCore.QSize(32, 32))
            tb.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
            #tb.setAllowedAreas()
            #toolAction = QtWidgets.QAction()
            tb.addAction(QtGui.QIcon("icons/cutinner.png"), "Cut Inside")
            tb.addAction(QtGui.QIcon("icons/cutouter.png"), "Cut Outside")
            tb.addWidget(QtWidgets.QComboBox())
            self.addToolBar(QtCore.Qt.RightToolBarArea, tb)
            #toolButton = QtWidgets.QToolButton()
            #toolButton.setDefaultAction(toolAction)
            #layout.addWidget(toolButton)
            #---------------------------------------------------

        mainlayout = QtWidgets.QHBoxLayout()
        mainlayout.addWidget(self.graphicview)
        self.setCentralWidget(self.graphicview)
        self._last_folder = "."
        if filename:
            self.open(None, filename=filename)

    def viewMousePosition(self, xpos, ypos):
        self.mouseposLabel.setText("{:4.1f}, {:4.1f}".format(xpos, ypos))

    def itemSelect(self, item, xpos, ypos):
        tool = self.toolWidget.currenttool
        diameter = self.settings["tooltable"][tool]["Diameter"]
        if self.commandwidget.action == Attribute.NONE:
            item._pathattr = Attribute.NONE
            effect = QtWidgets.QGraphicsColorizeEffect()
            effect.setColor(COLOR_NORMAL)
            item.setGraphicsEffect(effect)
            group = getattr(item, "_group", None)
            if group is not None:
                self.graphicview.deleteGroup(group)
                item._group = None
        elif self.commandwidget.action == Attribute.INNER:
            if item._pathattr == Attribute.NONE:
                print("INNER")
                print(item._pid)
                group = self.graphicview.drawPolygon(item._polygon.expand(diameter / 2), pathattr=Attribute.CUTPATH)
                self.graphicview.drawMarkerList(group._polygon, group._pid)
                item._group = group
                item._pathattr = Attribute.INNER
                item._tool = tool
                group._parent = item._pid
                group._tool = tool
        elif self.commandwidget.action == Attribute.OUTER:
            if item._pathattr == Attribute.NONE:
                print("OUTER")
                print(item._pid)
                group = self.graphicview.drawPolygon(item._polygon.expand(-diameter / 2), pathattr=Attribute.CUTPATH)
                self.graphicview.drawMarkerList(group._polygon, group._pid)
                item._group = group
                item._pathattr = Attribute.OUTER
                item._tool = tool
                group._parent = item._pid
                group._tool = tool
        elif self.commandwidget.action == Attribute.DISABLE:
            if item._pathattr == Attribute.NONE:
                print("DISABLE")
                effect = QtWidgets.QGraphicsColorizeEffect()
                effect.setColor(COLOR_DISABLE)
                item.setGraphicsEffect(effect)
                item._pathattr = Attribute.DISABLE
        elif self.commandwidget.action == Attribute.CUTPATH:
            pass
        elif self.commandwidget.action == Attribute.ADD_TAB:
            print("ADD_TAB")
            width = self.commandwidget.wgTabWidth.value()
            height = self.commandwidget.wgTabHeight.value()
            tabitem = self.graphicview.addTab(item, xpos, ypos, width, height, parentrefid=getattr(item, "_parent", None))
        elif self.commandwidget.action == Attribute.REMOVE_TAB:
            print("REMOVE_TAB")
            self.graphicview.removeTab(item)
        elif self.commandwidget.action == Attribute.ADD_OVERCUT:
            print("ADD_OVERCUT")
            self.graphicview.addOverCut(item)
        elif self.commandwidget.action == Attribute.REMOVE_OVERCUT:
            print("REMOVE_OVERCUT")
            self.graphicview.removeOverCut(item)
        else:
            raise AttributeError(self.commandwidget.action)

        self.graphicview.update()

    def updateAction(self):
        if self.commandwidget.action == Attribute.DEBUG:
            jsonobj = self.get_as_dict()
            for path in jsonobj["pathlist"]:
                path.pop("polygon")
            pprint.pprint(jsonobj)
        else:
            self.graphicview.setAction(self.commandwidget.action)

    def loadSvgFile(self, filename):
        polygonlist = libnanocnc.svg2polygon(filename)
        jsonobj = dict(settings={}, tablist=[], overcutlist=[], cornerlist=[], toollist=[])
        jsonobj["pathlist"] = [dict(id=index, parentid=None, pathattr=Attribute.NONE, tool=None, polygon=polygon.asdict()) for index, polygon in enumerate(polygonlist)]
        self.graphicview.drawJson(jsonobj, clear=True)

    def loadJsonFile(self, filename):
        with open(filename) as fh:
            jsonobj = json.load(fh)
        self.graphicview.drawJson(jsonobj, clear=True)
        self.toolWidget.init(jsonobj["toollist"])

    def save(self, _, filename=None):
        """
        pathlist is a list of objects describing a path
        path object attributes are
            "id":
                number as identifier for the object
            "parentid":
                null or number of the id of object where this object is derived from
                Cut path must always have a parentid
                parentid is used for identifying the tool for the cut path
            "pathattr":
                type of cut, see Attribute
            "polygon":
                a dist with xlist, ylist as lists of polygon coordinates
            "tool":
                null or dict with tool, normally only object with no parentid have a tool

        tablist is a list of tabs with object describing a tab
        tab object are
            "refid":
                the id of path where ths tb lies on
            "parentid":
                the parentid of path where object lies on
            "pos":
                list (x position, y position)
            "width":
                the width of the tab
            "height":
                the height of the tab
            "linepoints": list [x1, y1, x2, y2] of start andend points of the line where tab is

        overcutlist is a list of all overcuts with object describing the overcut
        overctu object is
            "parentid": the id of path to which the overcut belongs to
            "pos": list (x position, y position)
            "id": number identifying the overcut

        cornerlist is same as overcutlist but for corners which are not already overcuts
        """
        if filename is None:
            proposedname = str(pathlib.Path(self.filename).with_suffix(".json"))
            print(proposedname)
            filename = QtWidgets.QFileDialog.getSaveFileName(self, "Save to", proposedname, "JSON (*.json);; All files (*.*")[0]
        if filename == "":
            return
        self._last_folder = str(pathlib.Path(filename).parent)
        json.dump(self.get_as_dict(), open(filename, "w"), indent=4)

    def get_as_dict(self):
        itemlist = [item for item in self.graphicview.scene().items() if isinstance(item, QtWidgets.QGraphicsItemGroup)]
        pathlist = [dict(id=item._pid, parentid=getattr(item, "_parent", None), pathattr=item._pathattr.value, polygon=item._polygon.asdict(), tool=item._tool) for item in itemlist]

        itemlist = [item for item in self.graphicview.scene().items() if isinstance(item, QtWidgets.QGraphicsEllipseItem) and getattr(item, "_pathattr", None) == Attribute.TAB]
        tablist = [dict(refid=item._refid, parentid=item._parentrefid, pos=item._pos, width=item._tabwidth, height=item._tabheight, linepoints=item._linepoints) for item in itemlist]

        itemlist = [item for item in self.graphicview.scene().items() if isinstance(item, QtWidgets.QGraphicsEllipseItem) and getattr(item, "_pathattr", None) == Attribute.OVERCUT]
        overcutlist = [dict(id=item._id, parentid=item._parentrefid, pos=item._pos) for item in itemlist]

        itemlist = [item for item in self.graphicview.scene().items() if isinstance(item, QtWidgets.QGraphicsEllipseItem) and getattr(item, "_pathattr", None) == Attribute.CORNER]
        cornerlist = [dict(id=item._id, parentid=item._parentrefid, pos=item._pos) for item in itemlist]

        settings = dict(savez=self.commandwidget.wgSaveZ.value(), materialthickness=self.commandwidget.wgMaterialThickness.value())

        return dict(settings=settings, pathlist=pathlist, tablist=tablist, overcutlist=overcutlist, cornerlist=cornerlist, toollist=self.settings["tooltable"])

    def save_gcode(self):
        dictobj = self.get_as_dict()
        try:
            libnanocnc.make_gcode(dictobj)
        except Exception as e:
            print(traceback.format_exc())
            QtWidgets.QMessageBox.critical(self, "Error processing file", traceback.format_exc())
            return

    def open(self, _, filename=None):
        print(filename)
        if filename is None:
            filename = QtWidgets.QFileDialog.getOpenFileName(self, "Open File", self._last_folder, "*.svg;; *.json")[0]
        if filename:
            suffix = pathlib.Path(filename).suffix
            try:
                if suffix == ".svg":
                    self.loadSvgFile(filename)
                elif suffix == ".json":
                    self.loadJsonFile(filename)
                else:
                    raise ValueError(f"Don't know how to {filename}")
                self._last_folder = str(pathlib.Path(filename).parent)
                self.setWindowTitle(f"{PROGNAME} {filename}")
            except Exception:
                print(traceback.format_exc())
                QtWidgets.QMessageBox.critical(self, "Error opening file", traceback.format_exc())
                return


def debug(itemlist):
    for item in itemlist:
        print("{0}: _pathattr={1}, _refid={2}, _parentrefid={3}".format(item, getattr(item, "_pathattr", None), getattr(item, "_refid", None), getattr(item, "_parentrefid", None)))


if __name__ == '__main__':
    settings = json.load(open("settings.json"))
    filename = None if len(sys.argv) < 2 else sys.argv[1]
    print(filename)
    #filename = "/home/achim/Dokumente/cnc/kreispoly.svg"
    app = QtWidgets.QApplication([sys.argv[0]] + ["-style", "Fusion"] + sys.argv[1:])
    o = MainWindow(settings, filename)
    o.show()
    sys.exit(app.exec_())

