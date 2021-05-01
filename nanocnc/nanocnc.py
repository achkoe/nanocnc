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
from PyQt5 import QtWidgets, QtCore, QtGui

import libnanocnc


PROGNAME = "nanocnc"

# TODO: fix id off TAB, has to refer to base polygon, not to INNER or OUTER polygon

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

    def drawPolygonList(self, polygonlist, clear=False, pathattr=Attribute.NONE):
        if clear is True:
            self.setScene(QtWidgets.QGraphicsScene(QtCore.QRectF()))
            self.scene().addItem(QtWidgets.QGraphicsLineItem(-2, 0, +2, 0))
            self.scene().addItem(QtWidgets.QGraphicsLineItem(0, -2, 0, +2))
        for polygon in polygonlist:
            self.drawPolygon(polygon, pathattr)
        self.fitInView(self.scene().itemsBoundingRect(), QtCore.Qt.KeepAspectRatio)
        self.update()

    def drawPolygon(self, polygon, pathattr, tool=None):
        group = QtWidgets.QGraphicsItemGroup()
        #group = self.scene().createItemGroup([])
        self.pid += 1
        for index in range(len(polygon.xlist) - 1):
            group.addToGroup(QtWidgets.QGraphicsLineItem(polygon.xlist[index], polygon.ylist[index], polygon.xlist[index + 1], polygon.ylist[index + 1]))
            if 1 and pathattr == Attribute.CUTPATH:
                marker = QtWidgets.QGraphicsEllipseItem(polygon.xlist[index] - 0.5, polygon.ylist[index] - 0.5, 1, 1)
                marker._pathattr = Attribute.CORNER
                marker._parentrefid = self.pid
                self.mid += 1
                marker._id = self.mid
                marker._pos = (polygon.xlist[index], polygon.ylist[index])
                marker.setVisible(False)
                self.scene().addItem(marker)
        group._pathattr = pathattr
        group._polygon = polygon
        group._tool = tool
        group._pid = self.pid
        # print(group, self.pid)
        if pathattr == Attribute.CUTPATH:
            effect = QtWidgets.QGraphicsColorizeEffect()
            effect.setColor(QtGui.QColor(0, 0, 255))
            group.setGraphicsEffect(effect)
        self.scene().addItem(group)
        return group

    def drawJson(self, jsonobj):
        for path in jsonobj["pathlist"]:
            polygon = libnanocnc.Polygon(path["polygon"]["xlist"], path["polygon"]["ylist"])
            self.drawPolygon(polygon, Attribute(path["pathattr"]), path["tool"])
        for corner in jsonobj["cornerlist"]:
            pass
        for tab in jsonobj["tablist"]:
            # TODO: set attributes of returned tab item, 0 is not correct
            self.drawTab(tab["refid"], tab["pos"][0], tab["pos"][1], tab["width"], tab["height"], tab["parentid"])
        for overcut in jsonobj["overcutlist"]:
            # search the marker witt same id as overcut id
            itemlist = [item for item in self.scene().items() if getattr(item, "_pathattr", None) == Attribute.CORNER and math.isclose(item._pos[0], overcut["pos"][0], rel_tol=1E-3) and math.isclose(item._pos[1], overcut["pos"][1], rel_tol=1E-3) ]
            assert len(itemlist) > 0, "no matching overcut found"
            self.addOverCut(itemlist[0])
        self.fitInView(self.scene().itemsBoundingRect(), QtCore.Qt.KeepAspectRatio)
        self.update()

    def deleteGroup(self, group):
        print("deleteGroup")
        group.prepareGeometryChange()
        self.scene().removeItem(group)

    def addTab(self, itemgroup, xpos, ypos, tabwidth, tabheight, parentrefid):
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
        item = self.drawTab(itemgroup._pid, tabxpos, tabypos, tabwidth, tabheight, parentrefid)
        return item

    def drawTab(self, pid, tabxpos, tabypos, tabwidth, tabheight, parentrefid):
        item = QtWidgets.QGraphicsEllipseItem(tabxpos - 1, tabypos - 1, 2, 2)
        item._pathattr = Attribute.TAB
        item._pos = (tabxpos, tabypos)
        item._tabwidth = tabwidth
        item._tabheight = tabheight
        item._refid = pid
        item._parentrefid = parentrefid
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(QtGui.QColor(0, 255, 255))
        item.setGraphicsEffect(effect)
        self.scene().addItem(item)
        return item

    def removeTab(self, item):
        item.prepareGeometryChange()
        self.scene().removeItem(item)

    def addOverCut(self, item):
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(QtGui.QColor(255, 0, 0))
        item.setGraphicsEffect(effect)
        item._pathattr = Attribute.OVERCUT
        item.setVisible(True)
        self.previousitemslist = [theitem for theitem in self.previousitemslist if theitem != item]

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
            effect = QtWidgets.QGraphicsColorizeEffect()
            action = getattr(item, "_pathattr", None)
            #print(action)
            if action in [Attribute.CUTPATH, Attribute.TAB]:
                effect.setColor(QtGui.QColor(0, 0, 255))
            elif action in [Attribute.ADD_OVERCUT, Attribute.REMOVE_OVERCUT]:
                # effect.setColor(QtGui.QColor(0, 255, 0))
                pass
            else:
                effect.setColor(QtGui.QColor(0, 0, 0))
            item.setGraphicsEffect(effect)
        pos = self.cursor().pos()
        scenePoint = self.mapToScene(self.mapFromGlobal(pos))
        # put all items in previousitemslist ifthey are in getSelectionRect() and right item
        self.previousitemslist = [item for item in self.scene().items(self.getSelectionRect(scenePoint)) if isinstance(item, self.selectitem) and item._pathattr in self.selectlist]
        effect = QtWidgets.QGraphicsColorizeEffect()
        effect.setColor(QtGui.QColor(255, 0, 0))
        # highlight all items in previousitemslist in color red
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
            effect.setColor(QtGui.QColor(0, 0, 0))
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
                item._group = group
                item._pathattr = Attribute.INNER
                item._tool = tool
                group._parent = item._pid
        elif self.commandwidget.action == Attribute.OUTER:
            if item._pathattr == Attribute.NONE:
                print("OUTER")
                print(item._pid)
                group = self.graphicview.drawPolygon(item._polygon.expand(-diameter / 2), pathattr=Attribute.CUTPATH)
                item._group = group
                item._pathattr = Attribute.OUTER
                item._tool = tool
                group._parent = item._pid
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
        else:
            raise AttributeError(self.commandwidget.action)

        self.graphicview.update()

    def updateAction(self):
        self.graphicview.setAction(self.commandwidget.action)

    def loadSvgFile(self, filename):
        polygonlist = libnanocnc.svg2polygon(filename)
        self.graphicview.drawPolygonList(polygonlist, clear=True)

    def loadJsonFile(self, filename):
        with open(filename) as fh:
            self.graphicview.drawJson(json.load(fh))

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
        print(filename)
        itemlist = [item for item in self.graphicview.scene().items() if isinstance(item, QtWidgets.QGraphicsItemGroup)]
        pathlist = [dict(id=item._pid, parentid=getattr(item, "_parent", None), pathattr=item._pathattr.value, polygon=item._polygon.asdict(), tool=item._tool) for item in itemlist]

        itemlist = [item for item in self.graphicview.scene().items() if isinstance(item, QtWidgets.QGraphicsEllipseItem) and getattr(item, "_pathattr", None) == Attribute.TAB]
        tablist = [dict(refid=item._refid, parentid=item._parentrefid, pos=item._pos, width=item._tabwidth, height=item._tabheight) for item in itemlist]

        itemlist = [item for item in self.graphicview.scene().items() if isinstance(item, QtWidgets.QGraphicsEllipseItem) and getattr(item, "_pathattr", None) == Attribute.OVERCUT]
        overcutlist = [dict(id=item._id, parentid=item._parentrefid, pos=item._pos) for item in itemlist]

        itemlist = [item for item in self.graphicview.scene().items() if isinstance(item, QtWidgets.QGraphicsEllipseItem) and getattr(item, "_pathattr", None) == Attribute.CORNER]
        cornerlist = [dict(id=item._id, parentid=item._parentrefid, pos=item._pos) for item in itemlist]

        settings = dict(savez=self.commandwidget.wgSaveZ.value(), materialthickness=self.commandwidget.wgMaterialThickness.value())

        json.dump(dict(settings=settings, pathlist=pathlist, tablist=tablist, overcutlist=overcutlist, cornerlist=cornerlist, toollist=self.settings["tooltable"]), open(filename, "w"), indent=4)

    def open(self, _, filename=None):
        print(filename)
        if filename is None:
            filename = QtWidgets.QFileDialog.getOpenFileName(self, "Open File", ".", "*.svg;; *.json")[0]
        if filename:
            suffix = pathlib.Path(filename).suffix
            try:
                if suffix == ".svg":
                    self.loadSvgFile(filename)
                elif suffix == ".json":
                    self.loadJsonFile(filename)
                else:
                    raise ValueError(f"Don't know how to {filename}")
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

