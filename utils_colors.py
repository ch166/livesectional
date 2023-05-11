# -*- coding: utf-8 -*- #

""" Collection of shared color handling functions and constants."""
#
# from enum import Enum, auto
import random
import debugging

colordict = {
    "OFF": "#000000",  # OLED Off
    "BLACK": "#000000",  # Black
    "GRAY": "#808080",  # Gray
    "BROWN": "#2AA52A",  # Brown
    "RED": "#FF0000",  # Red
    "ROSE": "#FF8000",  # Rose (Red)
    "MAGENTA": "#FF00FF",  # Magenta
    "PURPLE": "#800080",  # Purple
    "VIOLET": "#8000FF",  # Violet
    "PINK": "#FFC0CB",  # Pink
    "HOTPINK": "#FF69B4",  # Hotpink
    "BLUE": "#0000FF",  # Blue
    "NAVY": "#000080",  # Navy
    "AZURE": "#0080FF",  # Azure
    "CYAN": "#00FFFF",  # Cyan
    "DKCYAN": "#008B8B",  # Dark Cyan
    "SPGREEN": "#00FF80",  # Spring Green
    "DKGREEN": "#006400",  # Dark Green
    "GREEN": "#00FF00",  # Green
    "CHUSE": "#80FF00",  # Chartreuse
    "YELLOW": "#FFFF00",  # Yellow
    "ORANGE": "#FFA500",  # Orange
    "GOLD": "#FFD700",  # Gold
    "WHITE": "#FFFFFF",  # White
}


def hex2rgb(value):
    """Hex to RGB."""
    value = value.lstrip("#")
    length_v = len(value)
    return tuple(
        int(value[i : i + length_v // 3], 16) for i in range(0, length_v, length_v // 3)
    )


def off():
    """Return HEX Color code for OFF - signal LED should be off."""
    return colordict["OFF"]


def black():
    """Return HEX Color code for Black."""
    return colordict["BLACK"]


def hex_tuple(col_tuple):
    """Return HEX values as tuple."""
    return hexcode(col_tuple[0], col_tuple[1], col_tuple[2])


def hexcode(red_value, green_value, blue_value):
    """Return HEX values from RGB string."""
    red = int(red_value) % 255
    grn = int(green_value) % 255
    blu = int(blue_value) % 255
    # hexval = "#%02x%02x%02x" % (red_value, green_value, blue_value)
    hexval = f"#{red:02x}{grn:02x}{blu:02x}"
    return hexval


def rgb2hex(rgb):
    """Convert RGB to HEX."""
    debugging.dprint(rgb)
    (red, grn, blu) = rgb
    # hexval = "#%02x%02x%02x" % (red_value, green_value, blue_value)
    hexval = f"#{red:02x}{grn:02x}{blu:02x}"
    return hexval


def rgb_color(value):
    """Return RGB values from HEX string."""
    return hex2rgb(value)


def cat_vfr(confdata):
    """Get VFR Color code from config."""
    return confdata.color("colors", "color_vfr")


def cat_mvfr(confdata):
    """Get MVFR Color code from config."""
    return confdata.color("colors", "color_mvfr")


def cat_ifr(confdata):
    """Get IFR Color code from config."""
    return confdata.color("colors", "color_ifr")


def cat_lifr(confdata):
    """Get LIFR Color code from config."""
    return confdata.color("colors", "color_lifr")


def wx_lightning(confdata):
    """Get Lightning Color code from config."""
    return confdata.color("colors", "color_lghtn")


def wx_snow(confdata, value):
    """Get SNOW Color code from config."""
    if value == 1:
        return confdata.color("colors", "color_snow1")
    return confdata.color("colors", "color_snow2")


def wx_frzrain(confdata, value):
    """Get Freezing Rain Color code from config."""
    if value == 1:
        return confdata.color("colors", "color_frrain1")
    return confdata.color("colors", "color_frrain2")


def wx_dust_sand_ash(confdata, value):
    """Get Dust Sand Ash Color (1) code from config."""
    if value == 1:
        return confdata.color("colors", "color_dustsandash1")
    return confdata.color("colors", "color_dustsandash2")


def wx_fog(confdata, value):
    """Get FOG Color code from config."""
    if value == 1:
        return confdata.color("colors", "color_fog1")
    return confdata.color("colors", "color_fog2")


def wx_rain(confdata, value):
    """Get RAIN Color code from config."""
    if value == 1:
        return confdata.color("colors", "color_rain1")
    return confdata.color("colors", "color_rain2")


def wx_noweather(confdata):
    """Get NOWX Color code from config."""
    return confdata.color("colors", "color_nowx")


# Generate random RGB color
def randomcolor():
    """Generate random color."""
    red = int(random.randint(0, 255))
    grn = int(random.randint(0, 255))
    blu = int(random.randint(0, 255))
    return hexcode(red, grn, blu)
