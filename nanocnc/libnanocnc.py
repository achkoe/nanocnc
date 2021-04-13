import math
import svgpathtools


class Polygon():
    def __init__(self, xlist, ylist):
        assert len(xlist) == len(ylist)
        xylist = [(x, y) for i, (x, y) in enumerate(zip(xlist, ylist)) if i == 0 or (x, y) != (xlist[i - 1], ylist[i - 1])]
        self.xlist, self.ylist = [item[0] for item in xylist], [item[1] for item in xylist]

    def __str__(self):
        return ", ".join("({:f}, {:f})".format(x, y) for x, y in zip(self.xlist, self.ylist))

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

