# -*- coding: utf-8 -*- #
""" Collection of shared color handling functions and constants """

import debugging


def rgb2hex(rgb):
    """Convert RGB to HEX"""
    debugging.dprint(rgb)
    (red_value, green_value, blue_value) = rgb
    hexval = "#%02x%02x%02x" % (red_value, green_value, blue_value)
    return hexval


def hex2rgb(value):
    """Hex to RGB"""
    # TODO: Add checks here to error if we get a non HEX value
    value = value.lstrip("#")
    length_v = len(value)
    return tuple(
        int(value[i : i + length_v // 3], 16) for i in range(0, length_v, length_v // 3)
    )


def off():
    """Return HEX Color code for Black"""
    return "#000000"


def black():
    """Return HEX Color code for Black"""
    return "#000000"


def HEX_tuple(col_tuple):
    """Return HEX values as tuple"""
    return HEX(col_tuple[0], col_tuple[1], col_tuple[2])


def HEX(red_value, green_value, blue_value):
    """Return HEX values from RGB string"""
    hexval = "#%02x%02x%02x" % (red_value, green_value, blue_value)
    return hexval


def RGB(value):
    """Return RGB values from HEX string"""
    return hex2rgb(value)


def VFR(confdata):
    """Get VFR Color code from config"""
    return confdata.color("colors", "color_vfr")


def MVFR(confdata):
    """Get MVFR Color code from config"""
    return confdata.color("colors", "color_mvfr")


def IFR(confdata):
    """Get IFR Color code from config"""
    return confdata.color("colors", "color_ifr")


def LIFR(confdata):
    """Get LIFR Color code from config"""
    return confdata.color("colors", "color_lifr")


def LIGHTNING(confdata):
    """Get Lightning Color code from config"""
    return confdata.color("colors", "color_lghtn")


def SNOW(confdata, value):
    """Get SNOW Color code from config"""
    if value == 1:
        return confdata.color("colors", "color_snow1")
    else:
        return confdata.color("colors", "color_snow2")


def FRZRAIN(confdata, value):
    """Get Freezing Rain Color code from config"""
    if value == 1:
        return confdata.color("colors", "color_frrain1")
    else:
        return confdata.color("colors", "color_frrain2")


def DUST_SAND_ASH(confdata, value):
    """Get Dust Sand Ash Color (1) code from config"""
    if value == 1:
        return confdata.color("colors", "color_dustsandash1")
    else:
        return confdata.color("colors", "color_dustsandash2")


def FOG(confdata, value):
    """Get FOG Color code from config"""
    if value == 1:
        return confdata.color("colors", "color_fog1")
    else:
        return confdata.color("colors", "color_fog2")


def RAIN(confdata, value):
    """Get RAIN Color code from config"""
    if value == 1:
        return confdata.color("colors", "color_rain1")
    else:
        return confdata.color("colors", "color_rain2")


def NOWEATHER(confdata):
    """Get NOWX Color code from config"""
    return confdata.color("colors", "color_nowx")
