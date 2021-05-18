import logging
import pytest
from nanocnc import libnanocnc
from nanocnc.libnanocnc import Point

##libnanocnc.logger.setLevel(logging.DEBUG)

class Test():
    @pytest.mark.parametrize(
        ("tab", ),
        [pytest.param(value, id=key) for key, value in {
            "in_horizontal": {
                "expected": [True, True],
                "refid": 1,
                "parentid": 0,
                "pos": [20, 20],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 100, 20]
            },
            "out_left_horizontal": {
                "expected": [False, False],
                "refid": 1,
                "parentid": 0,
                "pos": [5, 20],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 100, 20]
            },
            "out_right_horizontal": {
                "expected": [False, False],
                "refid": 1,
                "parentid": 0,
                "pos": [105, 20],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 100, 20]
            },
            "oneout_left_horizontal": {
                "expected": [False, True],
                "refid": 1,
                "parentid": 0,
                "pos": [9, 20],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 100, 20]
            },
            "oneout_right_horizontal": {
                "expected": [True, False],
                "refid": 1,
                "parentid": 0,
                "pos": [101, 20],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 100, 20]
            },
            "in_vertical": {
                "expected": [True, True],
                "refid": 1,
                "parentid": 0,
                "pos": [10, 40],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 10, 200]
            },
            "out_bottom_vertical": {
                "expected": [False, False],
                "refid": 1,
                "parentid": 0,
                "pos": [10, 5],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 10, 200]
            },
            "out_top_vertical": {
                "expected": [False, False],
                "refid": 1,
                "parentid": 0,
                "pos": [10, 205],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 10, 200]
            },
            "oneout_bottom_vertical": {
                "expected": [False, True],
                "refid": 1,
                "parentid": 0,
                "pos": [10, 19],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 10, 200]
            },
            "oneout_top_vertical": {
                "expected": [True, False],
                "refid": 1,
                "parentid": 0,
                "pos": [10, 201],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [10, 20, 10, 200]
            },
            "in_p45": {
                "expected": [True, True],
                "refid": 1,
                "parentid": 0,
                "pos": [100, 100],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [50, 50, 150, 150]
            },
            "in_m45": {
                "expected": [True, True],
                "refid": 1,
                "parentid": 0,
                "pos": [100, 100],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [150, 150, 50, 50]
            },
            "out_p45": {
                "expected": [False, False],
                "refid": 1,
                "parentid": 0,
                "pos": [40, 40],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [50, 50, 150, 150]
            },
            "out_m45": {
                "expected": [False, False],
                "refid": 1,
                "parentid": 0,
                "pos": [160, 160],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [150, 150, 50, 50]
            },
            "oneout_p45": {
                "expected": [False, True],
                "refid": 1,
                "parentid": 0,
                "pos": [49, 49],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [50, 50, 150, 150]
            },
            "oneout_m45": {
                "expected": [False, True],
                "refid": 1,
                "parentid": 0,
                "pos": [49, 49],
                "width": 4.0,
                "height": 4.0,
                "linepoints": [150, 150, 50, 50]
            }

        }.items()]
    )
    def test_tabpoint_inside_segment(self, tab):
        p1, p2 = Point(*tab["linepoints"][:2]), Point(*tab["linepoints"][2:])
        pt = Point(*tab["pos"], tab["width"])
        obtained = libnanocnc._tabpoint_inside_segment(p1, p2, pt)
        expected = tab["expected"]
        assert obtained == expected

