#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilities for handling images / graphics .

Created on Thu Nov 24 20:40:47 2022

@author: chris
"""

import math
import debugging


def rotate_point(x_y, angle):
    """Rotate X,Y around the origin to Angle (radians)."""
    origin_x, origin_y = (0, 0)
    p_x, p_y = x_y
    q_x = (
        origin_x
        + math.cos(angle) * (p_x - origin_x)
        - math.sin(angle) * (p_y - origin_x)
    )
    q_y = (
        origin_y
        + math.sin(angle) * (p_x - origin_y)
        + math.cos(angle) * (p_y - origin_y)
    )
    return (int(q_x), int(q_y))


def rotate_polygon(seq, angle):
    """Rotate a polygon around 0,0."""
    result = []
    for point in seq:
        point2 = rotate_point(point, angle)
        result = result + [
            point2,
        ]
    return result


def poly_center(polygon):
    """Calculate the x,y midpoint of the bounding box around a polygon."""
    min_x = polygon[0][0]
    max_x = polygon[0][0]
    min_y = polygon[0][1]
    max_y = polygon[0][1]
    for pos in polygon:
        min_x = min(pos[0], min_x)
        min_y = min(pos[1], min_y)
        max_x = max(pos[0], max_x)
        max_y = max(pos[1], max_y)
    mid_x = (max_x - min_x) / 2 + min_x
    mid_y = (max_y - min_y) / 2 + min_y
    mid_x_y = (mid_x, mid_y)
    return mid_x_y


def poly_offset(polygon, xoffset, yoffset):
    """Move each x_y part of a polygon by an x and y offset."""
    result = []
    for pos in polygon:
        x_pos, y_pos = pos
        pos2 = (x_pos + xoffset, y_pos + yoffset)
        result = result + [
            pos2,
        ]
    return result


def create_wind_arrow(windangle, width, height):
    """Draw a Wind Arrow."""
    arrow = [(0, 15), (35, 8), (30, 15), (35, 22)]
    mid_poly = poly_center(arrow)
    off_x, off_y = mid_poly
    seq_offset = poly_offset(arrow, 0 - off_x, 0 - off_y)
    seq_r = rotate_polygon(seq_offset, math.radians((windangle + 270) % 360))
    seq_offset2 = poly_offset(seq_r, off_x, off_y)
    seq_draw = poly_offset(
        seq_offset2, int((width / 2) - off_x), int((height / 2) - off_y)
    )
    debugging.debug(
        f"arrow:{windangle}\n  in:{arrow}\n out:{seq_draw}\n   w:{width} / h:{height}"
    )
    return seq_draw


def create_runway(r_x, r_y, rwidth, rwangle, width, height):
    """Draw a runway on a canvas."""
    # Runway is centered on X axis, and rwidth high
    runway = [
        (r_x, r_y),
        (r_x + (width - r_x), r_y),
        (r_x + (width - r_x), (r_y + rwidth)),
        (r_x, (r_y + rwidth)),
    ]
    mid_poly = poly_center(runway)
    off_x, off_y = mid_poly
    seq_offset = poly_offset(runway, 0 - off_x, 0 - off_y)
    seq_r = rotate_polygon(seq_offset, math.radians((rwangle + 270) % 360))
    seq_offset2 = poly_offset(seq_r, off_x, off_y)
    seq_draw = poly_offset(
        seq_offset2, int((width / 2) - off_x), int((height / 2) - off_y)
    )
    debugging.debug(f"runway:{rwangle}\n  in:{runway}\n out:{seq_draw}")
    debugging.debug(f"runway:x-{r_x}:y-{r_y}:rw-{rwidth}:w-{width}:h-{height}")
    return seq_draw


def center(max_a, min_a):
    """Calculate the middle point between two values."""
    z_val = ((max_a - min_a) / 2) + min_a
    return round(z_val, 2)


def findpoint(x_1, y_1, x_2, y_2, x_posn, y_posn):
    """Check to see if x,y is inside rectangle x_1,y_1-x_2,y_2."""
    return (x_1 < x_posn < x_2) and (y_1 < y_posn < y_2)


def area(x_1, y_1, x_2, y_2, x_3, y_3):
    """Calculate area of triangle."""
    return abs((x_1 * (y_2 - y_3) + x_2 * (y_3 - y_1) + x_3 * (y_1 - y_2)) / 2.0)


def is_inside(x_1, y_1, x_2, y_2, x_3, y_3, x_posn, y_posn):
    """Check to see if x,y is inside x_1,y_1-x_2,y_2-x_3-y_3."""
    # Calculate area of triangle ABC
    a_0 = area(x_1, y_1, x_2, y_2, x_3, y_3)
    # Calculate area of triangle PBC
    a_1 = area(x_posn, y_posn, x_2, y_2, x_3, y_3)
    # Calculate area of triangle PAC
    a_2 = area(x_1, y_1, x_posn, y_posn, x_3, y_3)
    # Calculate area of triangle PAB
    a_3 = area(x_1, y_1, x_2, y_2, x_posn, y_posn)
    # Check if sum of A_1, A_2 and A_3 is same as A
    return ((a_1 + a_2 + a_3) - 1) >= a_0 <= ((a_1 + a_2 + a_3) + 1)
