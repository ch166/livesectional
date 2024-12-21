# utils_coord

# With airports at lat/lon positions; smart wiping needs to be able to operate against the set of locations.

# Data Structure

# We need to map the airport positions into a raster array; for future operations to apply to them.

#
# Need to have an ordered array - so that we can return airports in for processing in sequence.
# In sorted order from left / top / circling etc. for wipe style changes
# This should be an Array[] that indexes the LEDs in sequence
#
# Need to have groups of airports together - so we can do "these are on, these are off" wipes
# checkerboard / radar sweep /

# For a given set of airports; it should be possible to compute these answers once - if we can then subsequently
# apply the correct colors.

# We need at least two types of wipe ;
# 1/ Fully replace color ( new color applies and we don't care about what was there )
# 2/ Temporarily swap color ( new color applies, but we want to revert to what was there previously)
#
# A radar sweep ; would want to turn a line of airports bright green, but then revert to original color.
# A matrix style rain fall would want progressive application of green from the top down, filling in over time, but then also changing previously applied colors.

import math
import airport
import debugging


def airport_list_to_raster(geoarray):
    """Return a raster array from a list of airports and geo coordinates."""
    raster_icao = []
    raster_lat = []
    raster_lon = []
    raster_led = []
    for icao, lat, lon, led in geoarray:
        raster_icao.append(icao)
        raster_lat.append(lat)
        raster_lon.append(lon)
        raster_led.append(led)
    print(raster_icao)
    print(raster_lat)
    print(raster_lon)
    print(raster_led)
    return


def reorder_latitude_s_n(geoarray):
    """Reorder a geomap to be an array sorted by latitude."""
    return sorted(geoarray, key=lambda k: k[1])


def reorder_latitude_n_s(geoarray):
    """Reorder a geomap to be an array sorted by latitude."""
    return sorted(geoarray, key=lambda k: k[1], reverse=True)


def reorder_longitude_e_w(geoarray):
    """Reorder a geomap to be an array sorted by latitude."""
    return sorted(geoarray, key=lambda k: k[2])


def reorder_longitude_w_e(geoarray):
    """Reorder a geomap to be an array sorted by latitude."""
    return sorted(geoarray, key=lambda k: k[2], reverse=True)


def triangle_area(x_1, y_1, x_2, y_2, x_3, y_3):
    """Calculate area of triangle."""
    return abs((x_1 * (y_2 - y_3) + x_2 * (y_3 - y_1) + x_3 * (y_1 - y_2)) / 2.0)


def is_inside_triangle(point, pt1, pt2, pt3):
    """Alternative Algorithm ... """
    (xp, yp) = point
    (x1, y1) = pt1
    (x2, y2) = pt2
    (x3, y3) = pt3
    # print(f"is_inside_triangle({x1, y1, x2, y2, x3, y3}, {xp, yp})")
    c1 = (x2 - x1) * (yp - y1) - (y2 - y1) * (xp - x1)
    c2 = (x3 - x2) * (yp - y2) - (y3 - y2) * (xp - x2)
    c3 = (x1 - x3) * (yp - y3) - (y1 - y3) * (xp - x3)
    if (c1 < 0 and c2 < 0 and c3 < 0) or (c1 > 0 and c2 > 0 and c3 > 0):
        return True
    return False


def point_inside_triangle(point, pt1, pt2, pt3):
    """Check if point (x,y), is inside the triangle made by
    pt1 (x1, y1), pt2 (x2, y2), pt3 (x3, y3)"""
    (x_pos, y_pos) = point
    (x_1, y_1) = pt1
    (x_2, y_2) = pt2
    (x_3, y_3) = pt3
    # Calculate area of triangle ABC
    a_0 = triangle_area(x_1, y_1, x_2, y_2, x_3, y_3)
    # Calculate area of triangle PBC
    a_1 = triangle_area(x_pos, y_pos, x_2, y_2, x_3, y_3)
    # Calculate area of triangle PAC
    a_2 = triangle_area(x_1, y_1, x_pos, y_pos, x_3, y_3)
    # Calculate area of triangle PAB
    a_3 = triangle_area(x_1, y_1, x_2, y_2, x_pos, y_pos)
    # Check if sum of A_1, A_2 and A_3 is same as A
    return ((a_1 + a_2 + a_3) - 1) >= a_0 <= ((a_1 + a_2 + a_3) + 1)


def func(radius, c):
    """Circle XYZ"""
    return math.sqrt(radius * radius - c * c)


def circle_triangles(radius, step, center_lon, center_lat):
    """Generate a set of triangles for radar sweep."""
    # For a radius of r, we want to start the sweep at the 360 position, and rotate anticlockwise 270, 180, 90 back to 0
    # Allowing for a 10 degree arc, that is 9 triangles per quadrant.
    xy_dict = {}
    triangle_list = []
    triangle_step = step
    for angle in range(0, 360, triangle_step):
        x = radius * math.cos(math.pi * 2 * angle / 360)
        y = radius * math.sin(math.pi * 2 * angle / 360)
        xy_dict[angle] = (x + center_lon, y + center_lat)

    for angle in range(0, 360, triangle_step):
        x1_ang = angle
        if x1_ang == 360:
            x1_ang = 0
        x2_ang = angle + triangle_step
        if x2_ang == 360:
            x2_ang = 0
        triangle = (
            (x1_ang, x2_ang),
            (center_lon, center_lat),
            xy_dict[x1_ang],
            xy_dict[x2_ang],
        )
        triangle_list.append(triangle)
    return triangle_list


def airport_boundary_calc(airport_database):
    """Scan airport lat/lon data and work out Airport Map boundaries."""
    max_lon = None
    min_lon = None
    max_lat = None
    min_lat = None
    airports = airport_database.get_airport_dict_led()
    for icao, airport_obj in airports.items():
        if not airport_obj.active():
            continue
        if not airport_obj.valid_coordinates():
            continue
        lon = airport_obj.longitude()
        lat = airport_obj.latitude()
        if max_lon is None: max_lon = lon
        if min_lon is None: min_lon = lon
        if max_lat is None: max_lat = lat
        if min_lat is None: min_lat = lat
        max_lon = max(max_lon, lon)
        min_lon = min(min_lon, lon)
        max_lat = max(max_lat, lat)
        min_lat = min(min_lat, lat)
    return max_lon, min_lon, max_lat, min_lat
