from dataclasses import dataclass
import json
import math
import svgpathtools

@dataclass
class Point:
    x: float
    y: float
    tabwidth: float = 0.0


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


def _searchpoint(ps, pointlist):
    for index, p in enumerate(pointlist):
        if math.isclose(p.x, ps.x, rel_tol=1E-3) and math.isclose(p.y, ps.y, rel_tol=1E-3):
            return index
    return None


def process_tabs(dictobj):
    for tab in dictobj["tablist"]:
        # search path to which tab belongs
        found = False
        for path in dictobj["pathlist"]:
            if path["id"] == tab["refid"]:
                found = True
                break
        if not found:
            raise ValueError("tab at {pos!r}: no parent path with id {refid} not found".format(**tab))

        pt = Point(*tab["pos"])
        print(pt)
        pl1, pl2 = Point(*tab["linepoints"][:2]), Point(*tab["linepoints"][2:])
        if pl2.x <= pl1.x:
            pl1.x, pl2.x = pl2.x, pl1.x
            pl1.y, pl2.y = pl2.y, pl1.y
            print("swap")
        print(pl1.x, pl1.y, pl2.x, pl2.y)
        index1 = _searchpoint(pl1, path["polygonpoints"])
        index2 = _searchpoint(pl2, path["polygonpoints"])
        print("index:", index1, index2)
        if index1 is None or index2 is None:
            raise(ValueError("points not found"))

        # compute length of line where tab lies
        linelength = math.sqrt((pl1.x - pl2.x) ** 2 + (pl1.y - pl2.y) ** 2)
        w = tab["width"]

        if w <= linelength:
            # insert two points at tab position - width / 2 and tab position + width / 2 and mark them as tab
            wx = tab["width"] * (pl2.x - pl1.x) / linelength
            wy = tab["width"] * (pl2.y - pl1.y) / linelength
            if round(pt.x - wx / 2 - pl1.x, 3) < 0 or round(pt.y - wy / 2 - pl1.y, 3) < 0:
                print("i2")
                # tab would extend over xt1 or yt1, so set tab start point to xt1, yt2
                path["polygon"]["xlist"][index1] = [pl1.x, pl1.y, tab["width"]]
                path["polygon"]["ylist"].insert(index1, [pl1.x + wx, pl1.y + wy, tab["width"]])
            elif round(pt.x + wx / 2 - pl2.x, 3) > 0 or round(pt.y + wy / 2 - pl2.y, 3) > 0:
                # tab would extend over xt2 or yt2, so set tab end point to xt2, yt2
                print("i3")
                xte, yte = pl2.x, pl2.y
                xts, yts = pl2.x - wx, pl2.y - wy
            else:
                # tab is lying between the two points
                print("i4")

                lt = math.sqrt((pt.x - pl1.x) ** 2 + (pt.y - pl1.y) ** 2)  # length between (xt, yt) and (pl1.x, pl1.y)
                xta = ((lt - w / 2) / linelength) * (pl2.x - pl1.x) + pl1.x
                yta = ((lt - w / 2) / linelength) * (pl2.y - pl1.y) + pl1.y
                xtb = ((lt + w / 2) / linelength) * (pl2.x - pl1.x) + pl1.x
                ytb = ((lt + w / 2) / linelength) * (pl2.y - pl1.y) + pl1.y

                print(f"pl1.x={pl1.x:6.2f}, pl1.y={pl1.y:6.2f}, pl2.x={pl2.x:6.2f}, pl2.y={pl2.y:6.2f}")
                print(f"lt={lt:6.2f}, l={linelength:6.2f}")
                print(f"xta={xta:6.2f}, yta={yta:6.2f}, xtb={xtb:6.2f}, ytb={ytb:6.2f}")

                path["polygonpoints"].insert(index2, Point(xta, yta))
                path["polygonpoints"].insert(index2, Point(xtb, ytb, tab["width"]))

                # path["polygon"]["xlist"].insert(index2, xta)
                # path["polygon"]["ylist"].insert(index2, yta)
                # path["polygon"]["xlist"].insert(index2, [xtb, tab["width"]])
                # path["polygon"]["ylist"].insert(index2, [ytb, tab["width"]])
        else:
            # mark all points from tab position till tap position + tab width as tab
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
        for index, p in enumerate(path["polygonpoints"]):
            if math.isclose(p.x, overcut["pos"][0], rel_tol=1E-3) and math.isclose(p.y, overcut["pos"][1], rel_tol=1E-3):
                found = True
                break
        if not found:
            raise ValueError("overcut {id}: no position on parent path {parentid} not found".format(**overcut))
#        print(f"{path['id']}, {parentid}, {overcut['pos']}, {index}, {path['polygon']['xlist'][index]}, {path['polygon']['ylist'][index]}")

        diameter = dictobj["toollist"][path["tool"]]["Diameter"]

        # get two points of line
        if index == len(path["polygonpoints"]) - 1:
            # if it is last point in list
            p1 = path["polygonpoints"][index - 1]
        else:
            p1 = path["polygonpoints"][index + 1]
        p2 = path["polygonpoints"][index]
        if p1.x - p2.x == 0:
            # line is parallel to y axis, vertical line
            dx = 0
            dy = (diameter / 2) * [+1, -1][p1.y - p2.y > 0]
        else:
            D = math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)  # length of line
            dx = ((p1.x - p2.x) * (diameter / 2) / D) * [+1, -1][p1.x - p2.x < 0]
            dy = ((p1.y - p2.y) * (diameter / 2) / D) * [+1, -1][p1.y - p2.y < 0]
        path['polygonpoints'].insert(index, Point(p2.x + dx, p2.y + dy))
        path['polygonpoints'].insert(index, Point(p2.x, p2.y))


def make_gcode(dictobj):
    process_overcuts(dictobj)
    process_tabs(dictobj)
    for path in dictobj["pathlist"]:
        path["polygon"]["xlist"] = [p.x for p in path["polygonpoints"]]
        path["polygon"]["ylist"] = [p.y for p in path["polygonpoints"]]
        del path["polygonpoints"]
    json.dump(dictobj, open("debug.json", "w"), indent=4)

def test(dictobj):
    for path in dictobj["pathlist"]:

        if 0:
            path["polygonpoints"] = path["polygonpoints"][::-1]

        if 0:
            result = 0
            for a in range(len(path)):
                b = (a + 1) % len(path)
                result += path["polygonpoints"][a].x * path["polygonpoints"][b].y;
                result -= path["polygonpoints"][a].y * path["polygonpoints"][b].x;
            print(result)

        area = 0
        for index, b_point in enumerate(path["polygonpoints"][:-1]):
            e_point = path["polygonpoints"][index + 1]
            area += b_point.x * e_point.y - b_point.y * e_point.x
        print(area)
        if area > 0:
            print("clockwise")
        elif area < 0:
            print("counterclockwise")
        else:
            print("Oops")

if __name__ == '__main__':
    filename = "../../overcut.json"
    dictobj = json.load(open(filename))
    for path in dictobj["pathlist"]:
        print(1)
        path["polygonpoints"] = [Point(x, y) for x, y in zip(path["polygon"]["xlist"], path["polygon"]["ylist"])]
    for path in dictobj["pathlist"]:
        assert len(path["polygonpoints"]) == len(path["polygon"]["xlist"])
        assert len(path["polygonpoints"]) == len(path["polygon"]["ylist"])
    # make_gcode(dictobj)

    test(dictobj)


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
