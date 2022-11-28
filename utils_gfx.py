#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilities for handling images / graphics .

Created on Thu Nov 24 20:40:47 2022

@author: chris
"""

import math
import debugging


def rotate_point(xy, angle):
    """Rotate X,Y around the origin to Angle (radians)."""
    origin_x, origin_y = (0, 0)
    px, py = xy
    qx = origin_x + math.cos(angle) * (px - origin_x) - math.sin(angle) * (py - origin_x)
    qy = origin_y + math.sin(angle) * (px - origin_y) + math.cos(angle) * (py - origin_y)
    return (int(qx), int(qy))


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
    mid_xy = (mid_x, mid_y)
    return mid_xy


def poly_offset(polygon, xoffset, yoffset):
    """Move each xy part of a polygon by an x and y offset."""
    result = []
    for pos in polygon:
        x, y = pos
        pos2 = (x + xoffset, y + yoffset)
        result = result + [
            pos2,
        ]
    return result


def create_wind_arrow(windangle, width, height):
    """Draw a Wind Arrow."""
    arrow = [(0, 15), (35, 8), (30, 15), (35, 22)]
    midPoly = poly_center(arrow)
    offX, offY = midPoly
    seqOffset = poly_offset(arrow, 0 - offX, 0 - offY)
    seqR = rotate_polygon(seqOffset, math.radians((windangle + 270) % 360))
    seqOffset2 = poly_offset(seqR, offX, offY)
    seqDraw = poly_offset(seqOffset2, int((width / 2) - offX), int((height / 2) - offY))
    debugging.debug(f"arrow:{windangle}\n  in:{arrow}\n out:{seqDraw}\n   w:{width} / h:{height}")
    return seqDraw


def create_runway(rx, ry, rwidth, rwangle, width, height):
    """Draw a runway on a canvas."""
    # Runway is centered on X axis, and rwidth high
    runway = [(rx, ry), (rx + (width - rx), ry), (rx + (width - rx), (ry + rwidth)), (rx, (ry + rwidth))]
    midPoly = poly_center(runway)
    offX, offY = midPoly
    seqOffset = poly_offset(runway, 0 - offX, 0 - offY)
    seqR = rotate_polygon(seqOffset, math.radians((rwangle + 270) % 360))
    seqOffset2 = poly_offset(seqR, offX, offY)
    seqDraw = poly_offset(seqOffset2, int((width / 2) - offX), int((height / 2) - offY))
    debugging.debug(f"runway:{rwangle}\n  in:{runway}\n out:{seqDraw}")
    debugging.debug(f"runway:x-{rx}:y-{ry}:rw-{rwidth}:w-{width}:h-{height}")
    return seqDraw
