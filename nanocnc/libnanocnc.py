import json
import math
import svgpathtools


class Polygon():
    def __init__(self, xlist, ylist):
        assert len(xlist) == len(ylist)
        xylist = [(x, y) for i, (x, y) in enumerate(zip(xlist, ylist)) if i == 0 or (x, y) != (xlist[i - 1], ylist[i - 1])]
        self.xlist, self.ylist = [item[0] for item in xylist], [item[1] for item in xylist]

    def __str__(self):
        return ", ".join("({:f}, {:f})".format(x, y) for x, y in zip(self.xlist, self.ylist))

    def asdict(self):
        return dict(xlist=self.xlist, ylist=self.ylist)

    def _parallel(self, distance: float, x1: float, y1: float, x2: float, y2: float):
        """Compute coordinates of points on a line which is parallel to the given.

        Args:
            distance: Distance to the line
            x1, y1  : coordinates of first line point
            x2, y2  : coordinates of second line point
        Returns:
            (tuple) with coordinates of first shifted point and coordinates of second shifted point
        """
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx ** 2 + dy ** 2)
        if length == 0:
            print(x1, y1, x2, y2)
        udx = dx / length
        udy = dy / length

        x1h = x1 - udy * distance
        y1h = y1 + udx * distance
        x2h = x1h + dx
        y2h = y1h + dy

        return (x1h, y1h, x2h, y2h)

    def expand(self, distance):
        """Expond polygon by distance.

        Args:
            distance: Distance to expand.
        Returns:
            (Polygon) expanded
        """
        llist = []
        # compute m, b for all parallels of all segments and put (m, b) im llist
        for index in range(len(self.xlist) - 1):
            x1, y1, x2, y2 = self._parallel(distance, self.xlist[index], self.ylist[index], self.xlist[index + 1], self.ylist[index + 1])
            if x1 - x2 == 0:
                # line is parallel to y axis, vertical line
                m = None
                b = x1
            else:
                m = (y1 - y2) / (x1 - x2)
                b = (y2 * x1 - y1 * x2) / (x1 - x2)
            llist.append((m, b))
        # last (m, b) is equal to first (m, b)
        llist.append(llist[0])
        # compute all intersection points of parallels and put to xlist, ylist
        xlist, ylist = [], []
        for index in range(len(llist) - 1):
            if llist[index][0] is None:
                # first line is vertical line
                # x is llist[index][1]
                xlist.append(llist[index][1])
                # y is computed from (m, b) of second line
                ylist.append(llist[index + 1][0] * xlist[-1] + llist[index + 1][1])
            elif llist[index + 1][0] is None:
                # second line is vertical line
                # x is llist[index +1][1]
                xlist.append(llist[index + 1][1])
                # y is computed from (m, b) of first line
                ylist.append(llist[index][0] * xlist[-1] + llist[index][1])
            else:
                #             b               - t                    /  n                   - m
                xlist.append((llist[index][1] - llist[index + 1][1]) / (llist[index + 1][0] - llist[index][0]))
                #            m               * x         + b
                ylist.append(llist[index][0] * xlist[-1] + llist[index][1])
        # it is a closed polygon, therefore last point is equal to frist point
        xlist.append(xlist[0])
        ylist.append(ylist[0])
        return Polygon(xlist, ylist)


def svg2polygon(filename, number_of_samples=50):
    pathlist, attributelist = svgpathtools.svg2paths(filename)

    polygonlist = []
    for _, subpathlist in enumerate(pathlist):
        print(_)
        pointlist = []
        for path in subpathlist:
            if isinstance(path, svgpathtools.CubicBezier) or isinstance(path, svgpathtools.Arc):
                for index in range(number_of_samples):
                    pointlist.append(path.point(index / number_of_samples))
            elif isinstance(path, svgpathtools.Line):
                pointlist.append(path.start)
                pointlist.append(path.end)
            else:
                raise ValueError(path)
        xlist = [p.real for p in pointlist]
        ylist = [p.imag for p in pointlist]
        polygonlist.append(Polygon(xlist, ylist))
    return polygonlist


def process_tabs(dictobj):
    pass


def process_overcuts(dictobj):
    for overcut in dictobj["overcutlist"]:
        # search path to which the overcut belongs to
        found = False
        parentid = overcut["parentid"]
        for path in dictobj["pathlist"]:
            if parentid == path['id']:
                found = True
                break
        if not found:
            raise ValueError("overcut {id}: no parent path {parentid} not found".format(**overcut))
        # search index of point in path where overcut is
        found = False
        for index, (xpos, ypos) in enumerate(zip(path["polygon"]["xlist"], path["polygon"]["ylist"])):
            if math.isclose(xpos, overcut["pos"][0], rel_tol=1E-3) and math.isclose(ypos, overcut["pos"][1], rel_tol=1E-3):
                found = True
                break
        if not found:
            raise ValueError("overcut {id}: no position on parent path {parentid} not found".format(**overcut))
#        print(f"{path['id']}, {parentid}, {overcut['pos']}, {index}, {path['polygon']['xlist'][index]}, {path['polygon']['ylist'][index]}")
        diameter = dictobj["toollist"][path["tool"]]["Diameter"]
        if index == len(path["polygon"]["xlist"]) - 1:
            y1, x1 = path["polygon"]["ylist"][index - 1], path["polygon"]["xlist"][index - 1]
        else:
            y1, x1 = path["polygon"]["ylist"][index + 1], path["polygon"]["xlist"][index + 1]
        y2, x2 = path["polygon"]["ylist"][index], path["polygon"]["xlist"][index]
        if x1 - x2 == 0:
            # line is parallel to y axis, vertical line
            dx = 0
            dy = (diameter / 2) * [-1, +1][y1 - y2 > 0]
        else:
            D = math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)
            dx = (x1 - x2) * (diameter / 2) / D
            dy = (y1 - y2) * (diameter / 2) / D
        path['polygon']['xlist'].insert(index + 1, x1 + dx)
        path['polygon']['ylist'].insert(index + 1, y1 + dy)


def make_gcode(dictobj):
    process_overcuts(dictobj)
    json.dump(dictobj, open("debug.json", "w"))
    process_tabs(dictobj)


if __name__ == '__main__':
    filename = "../../overcut.json"
    dictobj = json.load(open(filename))
    make_gcode(dictobj)


"""
G0 : Rapid Move
G1 : Linear Move
G0 Xnnn Ynnn Znnn Ennn Fnnn Snnn
G1 Xnnn Ynnn Znnn Ennn Fnnn Snnn
Parameters
Not all parameters need to be used, but at least one has to be used
Xnnn The position to move to on the X axis
Ynnn The position to move to on the Y axis
Znnn The position to move to on the Z axis
Ennn The amount to extrude between the starting point and ending point
Fnnn The feedrate per minute of the move between the starting point and ending point (if supplied)


G4: Dwell
Pause the machine for a period of time.
Parameters
Pnnn Time to wait, in milliseconds (In Teacup, P0, wait until all previous moves are finished)
Snnn Time to wait, in seconds (Only on Repetier, Marlin, Prusa, Smoothieware, and RepRapFirmware 1.16 and later)


M3: Spindle On, Clockwise (CNC specific)
Parameters
Snnn Spindle RPM

M5: Spindle Off (CNC specific)


(Block-name: Header), (Block-name: path821), (Block-name: Footer)
(Block-expand: 0)
(Block-enable: 1)

M3 S12000
G4 P3

G0 Z10

G02 X107.345 Y-125.643 R28.7262
G0 X0.0932 Y42.3303
G1 Z-5 f500
G1 X2.0661 Y42.2246 Z-5 f1200

G0 Z10
M5

"""
