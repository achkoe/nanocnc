"""
CNC programs only support linear moves and arc moves

svgpathtools supports Arc, Line CubicBezier

For offsetting path:
Arc -> offset_curve
CubicBezier -> offset_curve
Line -> Shapely
"""

import sys
from enum import Enum
from PyQt5 import QtWidgets, QtCore, QtGui

import libnanocnc


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

    def drawPolygonList(self, polygonlist, clear=False):
        if clear is True:
            self.setScene(QtWidgets.QGraphicsScene(QtCore.QRectF()))
        for polygon in polygonlist:
            group = QtWidgets.QGraphicsItemGroup()
            for index in range(len(polygon.xlist) - 1):
                group.addToGroup(QtWidgets.QGraphicsLineItem(polygon.xlist[index], polygon.ylist[index],polygon.xlist[index + 1], polygon.ylist[index + 1]))
            group._color = self.color_a
            self.scene().addItem(group)
        self.fitInView(self.scene().itemsBoundingRect(), QtCore.Qt.KeepAspectRatio)
        self.update()

    def mousePressEvent(self, event):
        extension = 6
        pos = self.cursor().pos()
        scenePoint = self.mapToScene(self.mapFromGlobal(pos))
        rect = QtCore.QRectF(scenePoint.x() - extension, scenePoint.y() - extension, 2 * extension, 2 * extension)
        itemlist = [item for item in self.scene().items(rect) if isinstance(item, QtWidgets.QGraphicsItemGroup)]
        # itemlist = [item for item in self.scene().items(rect) if item in self.activegroup.childItems()]
        print(itemlist)
        if len(itemlist) != 1:
            return
        self.signal_groupselect.emit(itemlist[0])

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


class MainWindow(QtWidgets.QMainWindow):

    cutmode_enum = Enum("cutmode_enum", ["NONE", "INNER", "OUTER"])

    def __init__(self, filename=None):
        super().__init__()
        self.filename = filename
        self.cutmode = self.cutmode_enum.NONE
        self.graphicview = GraphicView()
        mainwidget = QtWidgets.QWidget()
        mainlayout = QtWidgets.QHBoxLayout()
        mainlayout.addWidget(self.graphicview)
        controllayout = QtWidgets.QVBoxLayout()
        buttonlist = (
            ("Zoom In", self.buttonZoomInClick), ("Zoom Out", self.buttonZoomOutClick),
            ("Cut Outer", self.buttonCutOuterClick), ("Cut Inner", self.buttonCutInnerClick))
        for (caption, method) in buttonlist:
            button = QtWidgets.QPushButton(caption)
            button.clicked.connect(method)
            controllayout.addWidget(button)
        mainlayout.addLayout(controllayout)
        mainwidget.setLayout(mainlayout)
        self.setCentralWidget(mainwidget)
        if filename is not None:
            self.loadSvgFile(filename)
        self.graphicview.signal_groupselect.connect(self.groupSelect)

    def groupSelect(self, item):
        print(self.cutmode)
        effect = QtWidgets.QGraphicsColorizeEffect()
        if self.cutmode == self.cutmode_enum.INNER:
            effect.setColor(QtGui.QColor(255, 0, 0))
        elif self.cutmode == self.cutmode_enum.OUTER:
            effect.setColor(QtGui.QColor(255, 255, 0))
        else:
            effect = None
        item.setGraphicsEffect(effect)
        self.graphicview.update()
        self.cutmode = self.cutmode_enum.NONE

    def buttonZoomOutClick(self):
        self.graphicview.scale(1 / 1.2, 1 / 1.2)

    def buttonZoomInClick(self):
        self.graphicview.scale(1.2, 1.2)

    def buttonCutInnerClick(self):
        self.cutmode = self.cutmode_enum.INNER

    def buttonCutOuterClick(self):
        self.cutmode = self.cutmode_enum.OUTER

    def loadSvgFile(self, filename):
        polygonlist = libnanocnc.svg2polygon(filename)
        self.graphicview.drawPolygonList(polygonlist, clear=True)


if __name__ == '__main__':
    filename = "/home/achim/Dokumente/cnc/kreispoly.svg"
    app = QtWidgets.QApplication([sys.argv[0]] + ["-style", "Fusion"] + sys.argv[1:])
    o = MainWindow(filename)
    o.show()
    sys.exit(app.exec_())

