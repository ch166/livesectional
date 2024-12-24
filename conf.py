# -*- coding: utf-8 -*- #
"""
Created on Oct 28 - 2021.

@author: chris.higgins@alternoc.net
"""

import re
import configparser
import utils

# This configuration parser provides access to the key/value data stored in
# the config.ini file. It currently uses configparser as the backend for managing ini files.
# .ini files are useful for swapping data with humans
# Future work in this space should look at storing the config as either
# - json - structured, able to store more data cleanly
#        - harder to handle random external generated configs through the export/import process
# - toml - more rigid .ini file equivalent
#
# What would be really useful ;
#   - a config file format that supports persistance of comments across load - parse - save cycles.
#   - a config file format that allows file imports
#
# There are snippets of the configuration that are site hardware implementation specific, and
# snippets of the configuration that are 'end user' airport / settings specific. It would be useful
# to be able to swap out / reset the 'end user' pieces of the configuration without losing the
# configuration state for the hardware (LED , OLED , Switch setup )


class Conf:
    """Configuration Class."""

    def __init__(self):
        """Initialize and load configuration."""
        self.config_filename = "config.ini"
        self.configfile = configparser.ConfigParser()
        self.configfile._interpolation = configparser.ExtendedInterpolation()
        self.configfile.read(self.config_filename)

    def get(self, section, key) -> str:
        """Read Setting."""
        return self.configfile.get(section, key)

    def color(self, section, key) -> str:
        """Pull out color value in hex."""
        return self.configfile.get(section, key)

    def get_color_decimal(self, section, key) -> tuple:
        """Read three tuple string, Return as tuple of integers."""
        color_list = []
        tmp_string = self.configfile.get(section, key)
        # print("tmp_string:" + tmp_string + ":--")
        # color_list = tmp_string.split(',')
        color_list = re.split(r"[(),\s]\s*", tmp_string)
        # print(type(color_list))
        # print(len(color_list))
        # print("-=-=-=-=-=-=-")
        # print(color_list)
        # print("-=-=-=-=-=-=-")
        rgb_r = int(color_list[0])
        rgb_g = int(color_list[1])
        rgb_b = int(color_list[2])
        # print(rgb_r, rgb_g, rgb_b)
        # print("-=-=-=-=-=-=-")

        return tuple([rgb_r, rgb_g, rgb_b])

    def get_string(self, section, key) -> str:
        """Read Setting."""
        return self.configfile.get(section, key)

    def set_string(self, section, key, value):
        """Set String Value."""
        # FIXME: Convert value to a string
        str_value = f"{value}"
        self.configfile.set(section, key, str_value)

    def get_bool(self, section, key) -> bool:
        """Read Setting."""
        return self.configfile.getboolean(section, key)

    def get_float(self, section, key) -> float:
        """Read Setting."""
        return self.configfile.getfloat(section, key)

    def get_int(self, section, key) -> int:
        """Read Setting."""
        return self.configfile.getint(section, key)

    def save_config(self):
        """Save configuration file."""
        cfgfile = open(self.config_filename, "w", encoding="utf8")
        self.configfile.write(cfgfile)
        cfgfile.close()

    def gen_settings_dict(self) -> dict:
        """Generate settings template to pass to flask."""
        settings = {
            "autorun": self.get_string("default", "autorun"),
            "LED_COUNT": self.get_string("default", "led_count"),
            "legend": self.get_string("default", "legend"),
            "max_wind_speed": self.get_string("activelights", "high_wind_limit"),
            "wx_update_interval": self.get_string("metar", "wx_update_interval"),
            "metar_age": self.get_string("metar", "metar_age"),
            "usetimer": self.get_bool("schedule", "usetimer"),
            "offhour": self.get_string("schedule", "offhour"),
            "offminutes": self.get_string("schedule", "offminutes"),
            "onhour": self.get_string("schedule", "onhour"),
            "onminutes": self.get_string("schedule", "onminutes"),
            "tempsleepon": self.get_string("schedule", "tempsleepon"),
            "sleepmsg": self.get_string("schedule", "sleepmsg"),
            "displayused": self.get_string("oled", "displayused"),
            "oledused": self.get_string("oled", "oledused"),
            "lcddisplay": self.get_string("oled", "lcddisplay"),
            "numofdisplays": self.get_string("oled", "numofdisplays"),
            "bright_value": self.get_string("lights", "bright_value"),
            "hiwindblink": self.get_string("activelights", "high_wind_blink"),
            "lghtnflash": self.get_string("lights", "lghtnflash"),
            "rainshow": self.get_string("lights", "rainshow"),
            "frrainshow": self.get_string("lights", "frrainshow"),
            "snowshow": self.get_string("lights", "snowshow"),
            "dustsandashshow": self.get_string("lights", "dustsandashshow"),
            "fogshow": self.get_string("lights", "fogshow"),
            "homeport": self.get_string("lights", "homeport"),
            "homeport_pin": self.get_string("lights", "homeport_pin"),
            "homeport_display": self.get_string("lights", "homeport_display"),
            "dim_value": self.get_string("lights", "dim_value"),
            "rgb_grb": self.get_string("lights", "rgb_grb"),
            "rev_rgb_grb": self.get_string("lights", "rev_rgb_grb"),
            "dimmed_value": self.get_string("lights", "dimmed_value"),
            "legend_hiwinds": self.get_string("lights", "legend_hiwinds"),
            "legend_lghtn": self.get_string("lights", "legend_lghtn"),
            "legend_snow": self.get_string("lights", "legend_snow"),
            "legend_rain": self.get_string("lights", "legend_rain"),
            "legend_frrain": self.get_string("lights", "legend_frrain"),
            "legend_dustsandash": self.get_string("lights", "legend_dustsandash"),
            "legend_fog": self.get_string("lights", "legend_fog"),
            "leg_pin_vfr": self.get_string("lights", "leg_pin_vfr"),
            "leg_pin_mvfr": self.get_string("lights", "leg_pin_mvfr"),
            "leg_pin_ifr": self.get_string("lights", "leg_pin_ifr"),
            "leg_pin_lifr": self.get_string("lights", "leg_pin_lifr"),
            "leg_pin_nowx": self.get_string("lights", "leg_pin_nowx"),
            "leg_pin_hiwinds": self.get_string("lights", "leg_pin_hiwinds"),
            "leg_pin_lghtn": self.get_string("lights", "leg_pin_lghtn"),
            "leg_pin_snow": self.get_string("lights", "leg_pin_snow"),
            "leg_pin_rain": self.get_string("lights", "leg_pin_rain"),
            "leg_pin_frrain": self.get_string("lights", "leg_pin_frrain"),
            "leg_pin_dustsandash": self.get_string("lights", "leg_pin_dustsandash"),
            "leg_pin_fog": self.get_string("lights", "leg_pin_fog"),
            "num2display": self.get_string("lights", "num2display"),
            "exclusive_flag": self.get_string("lights", "exclusive_flag"),
            "exclusive_list": self.get_string("lights", "exclusive_list"),
            "abovekts": self.get_string("lights", "abovekts"),
            "lcdpause": self.get_string("lights", "lcdpause"),
            "rotyesno": self.get_string("oled", "rotyesno"),
            "oledposorder": self.get_string("oled", "oledposorder"),
            "oledpause": self.get_string("oled", "oledpause"),
            "fontsize": self.get_string("oled", "fontsize"),
            "offset": self.get_string("oled", "offset"),
            "wind_numorarrow": self.get_string("oled", "wind_numorarrow"),
            "boldhiap": self.get_string("oled", "boldhiap"),
            "blankscr": self.get_string("oled", "blankscr"),
            "border": self.get_string("oled", "border"),
            "dimswitch": self.get_string("oled", "dimswitch"),
            "dimmin": self.get_string("oled", "dimmin"),
            "dimmax": self.get_string("oled", "dimmax"),
            "invert": self.get_string("oled", "invert"),
            "toginv": self.get_string("oled", "toginv"),
            "scrolldis": self.get_string("oled", "scrolldis"),
            "usewelcome": self.get_string("default", "usewelcome"),
            "welcome": self.get_string("default", "welcome"),
            "displaytime": self.get_string("oled", "displaytime"),
            "displayip": self.get_string("oled", "displayip"),
            "data_sw0": self.get_string("rotaryswitch", "data_sw0"),
            "time_sw0": self.get_string("rotaryswitch", "time_sw0"),
            "data_sw1": self.get_string("rotaryswitch", "data_sw1"),
            "time_sw1": self.get_string("rotaryswitch", "time_sw1"),
            "data_sw2": self.get_string("rotaryswitch", "data_sw2"),
            "time_sw2": self.get_string("rotaryswitch", "time_sw2"),
            "data_sw3": self.get_string("rotaryswitch", "data_sw3"),
            "time_sw3": self.get_string("rotaryswitch", "time_sw3"),
            "data_sw4": self.get_string("rotaryswitch", "data_sw4"),
            "time_sw4": self.get_string("rotaryswitch", "time_sw4"),
            "data_sw5": self.get_string("rotaryswitch", "data_sw5"),
            "time_sw5": self.get_string("rotaryswitch", "time_sw5"),
            "data_sw6": self.get_string("rotaryswitch", "data_sw6"),
            "time_sw6": self.get_string("rotaryswitch", "time_sw6"),
            "data_sw7": self.get_string("rotaryswitch", "data_sw7"),
            "time_sw7": self.get_string("rotaryswitch", "time_sw7"),
            "color_vfr": self.get_string("colors", "color_vfr"),
            "color_mvfr": self.get_string("colors", "color_mvfr"),
            "color_ifr": self.get_string("colors", "color_ifr"),
            "color_lifr": self.get_string("colors", "color_lifr"),
            "color_nowx": self.get_string("colors", "color_nowx"),
            "color_black": self.get_string("colors", "color_black"),
            "color_lghtn": self.get_string("colors", "color_lghtn"),
            "color_snow1": self.get_string("colors", "color_snow1"),
            "color_snow2": self.get_string("colors", "color_snow2"),
            "color_rain1": self.get_string("colors", "color_rain1"),
            "color_rain2": self.get_string("colors", "color_rain2"),
            "color_frrain1": self.get_string("colors", "color_frrain1"),
            "color_frrain2": self.get_string("colors", "color_frrain2"),
            "color_dustsandash1": self.get_string("colors", "color_dustsandash1"),
            "color_dustsandash2": self.get_string("colors", "color_dustsandash2"),
            "color_fog1": self.get_string("colors", "color_fog1"),
            "color_fog2": self.get_string("colors", "color_fog2"),
            "color_homeport": self.get_string("colors", "color_homeport"),
            "homeport_colors": self.get_string("colors", "homeport_colors"),
            "fade_color1": self.get_string("colors", "fade_color1"),
            "allsame_color1": self.get_string("colors", "allsame_color1"),
            "allsame_color2": self.get_string("colors", "allsame_color2"),
            "shuffle_color1": self.get_string("colors", "shuffle_color1"),
            "shuffle_color2": self.get_string("colors", "shuffle_color2"),
            "radar_color1": self.get_string("colors", "radar_color1"),
            "radar_color2": self.get_string("colors", "radar_color2"),
            "circle_color1": self.get_string("colors", "circle_color1"),
            "circle_color2": self.get_string("colors", "circle_color2"),
            "square_color1": self.get_string("colors", "square_color1"),
            "square_color2": self.get_string("colors", "square_color2"),
            "updn_color1": self.get_string("colors", "updn_color1"),
            "updn_color2": self.get_string("colors", "updn_color2"),
            "rabbit_color1": self.get_string("colors", "rabbit_color1"),
            "rabbit_color2": self.get_string("colors", "rabbit_color2"),
            "checker_color1": self.get_string("colors", "checker_color1"),
            "checker_color2": self.get_string("colors", "checker_color2"),
        }
        return settings

    def parse_config_input(self, form_data):
        """Parse settings data input."""
        #
        autorun_flag = utils.str2bool(form_data["autorun"])
        self.set_string("default", "autorun", autorun_flag)
        self.set_string("default", "led_count", form_data["LED_COUNT"])
        #
        legend_flag = utils.str2bool(form_data["legend"])
        self.set_string("default", "legend", legend_flag)
        self.set_string("activelights", "high_wind_limit", form_data["max_wind_speed"])
        self.set_string("metar", "wx_update_interval", form_data["wx_update_interval"])
        self.set_string("metar", "metar_age", form_data["metar_age"])
        #
        timer_flag = utils.str2bool(form_data["usetimer"])
        self.set_string("schedule", "usetimer", timer_flag)
        self.set_string("schedule", "offhour", form_data["offhour"])
        self.set_string("schedule", "offminutes", form_data["offminutes"])
        self.set_string("schedule", "onhour", form_data["onhour"])
        self.set_string("schedule", "onminutes", form_data["onminutes"])
        self.set_string("schedule", "tempsleepon", form_data["tempsleepon"])
        self.set_string("schedule", "sleepmsg", form_data["sleepmsg"])
        #
        self.set_string("oled", "displayused", form_data["displayused"])
        self.set_string("oled", "oledused", form_data["oledused"])
        self.set_string("oled", "lcddisplay", form_data["lcddisplay"])
        self.set_string("oled", "numofdisplays", form_data["numofdisplays"])
        #
        self.set_string("lights", "bright_value", form_data["bright_value"])
        self.set_string("activelights", "high_wind_blink", form_data["hiwindblink"])
        self.set_string("lights", "lghtnflash", form_data["lghtnflash"])
        self.set_string("lights", "rainshow", form_data["rainshow"])
        self.set_string("lights", "frrainshow", form_data["frrainshow"])
        self.set_string("lights", "snowshow", form_data["snowshow"])
        self.set_string("lights", "dustsandashshow", form_data["dustsandashshow"])
        self.set_string("lights", "fogshow", form_data["fogshow"])
        self.set_string("lights", "homeport", form_data["homeport"])
        self.set_string("lights", "homeport_pin", form_data["homeport_pin"])
        self.set_string("lights", "homeport_display", form_data["homeport_display"])
        self.set_string("lights", "dim_value", form_data["dim_value"])
        self.set_string("lights", "rgb_grb", form_data["rgb_grb"])
        self.set_string("lights", "rev_rgb_grb", form_data["rev_rgb_grb"])
        self.set_string("lights", "dimmed_value", form_data["dimmed_value"])
        self.set_string("lights", "legend_hiwinds", form_data["legend_hiwinds"])
        self.set_string("lights", "legend_lghtn", form_data["legend_lghtn"])
        self.set_string("lights", "legend_snow", form_data["legend_snow"])
        self.set_string("lights", "legend_rain", form_data["legend_rain"])
        self.set_string("lights", "legend_frrain", form_data["legend_frrain"])
        self.set_string("lights", "legend_dustsandash", form_data["legend_dustsandash"])
        self.set_string("lights", "legend_fog", form_data["legend_fog"])
        self.set_string("lights", "leg_pin_vfr", form_data["leg_pin_vfr"])
        self.set_string("lights", "leg_pin_mvfr", form_data["leg_pin_mvfr"])
        self.set_string("lights", "leg_pin_ifr", form_data["leg_pin_ifr"])
        self.set_string("lights", "leg_pin_lifr", form_data["leg_pin_lifr"])
        self.set_string("lights", "leg_pin_nowx", form_data["leg_pin_nowx"])
        self.set_string("lights", "leg_pin_hiwinds", form_data["leg_pin_hiwinds"])
        self.set_string("lights", "leg_pin_lghtn", form_data["leg_pin_lghtn"])
        self.set_string("lights", "leg_pin_snow", form_data["leg_pin_snow"])
        self.set_string("lights", "leg_pin_rain", form_data["leg_pin_rain"])
        self.set_string("lights", "leg_pin_frrain", form_data["leg_pin_frrain"])
        self.set_string(
            "lights", "leg_pin_dustsandash", form_data["leg_pin_dustsandash"]
        )
        self.set_string("lights", "leg_pin_fog", form_data["leg_pin_fog"])
        self.set_string("lights", "num2display", form_data["num2display"])
        self.set_string("lights", "exclusive_flag", form_data["exclusive_flag"])
        self.set_string("lights", "exclusive_list", form_data["exclusive_list"])
        self.set_string("lights", "abovekts", form_data["abovekts"])
        self.set_string("lights", "lcdpause", form_data["lcdpause"])
        self.set_string("oled", "rotyesno", form_data["rotyesno"])
        self.set_string("oled", "oledposorder", form_data["oledposorder"])
        self.set_string("oled", "oledpause", form_data["oledpause"])
        self.set_string("oled", "fontsize", form_data["fontsize"])
        self.set_string("oled", "offset", form_data["offset"])
        self.set_string("oled", "wind_numorarrow", form_data["wind_numorarrow"])
        self.set_string("oled", "boldhiap", form_data["boldhiap"])
        self.set_string("oled", "blankscr", form_data["blankscr"])
        self.set_string("oled", "border", form_data["border"])
        self.set_string("oled", "dimswitch", form_data["dimswitch"])
        self.set_string("oled", "dimmin", form_data["dimmin"])
        self.set_string("oled", "dimmax", form_data["dimmax"])
        self.set_string("oled", "invert", form_data["invert"])
        self.set_string("oled", "toginv", form_data["toginv"])
        self.set_string("oled", "scrolldis", form_data["scrolldis"])
        self.set_string("default", "usewelcome", form_data["usewelcome"])
        self.set_string("default", "welcome", form_data["welcome"])
        self.set_string("oled", "displaytime", form_data["displaytime"])
        self.set_string("oled", "displayip", form_data["displayip"])
        self.set_string("rotaryswitch", "data_sw0", form_data["data_sw0"])
        self.set_string("rotaryswitch", "time_sw0", form_data["time_sw0"])
        self.set_string("rotaryswitch", "data_sw1", form_data["data_sw1"])
        self.set_string("rotaryswitch", "time_sw1", form_data["time_sw1"])
        self.set_string("rotaryswitch", "data_sw2", form_data["data_sw2"])
        self.set_string("rotaryswitch", "time_sw2", form_data["time_sw2"])
        self.set_string("rotaryswitch", "data_sw3", form_data["data_sw3"])
        self.set_string("rotaryswitch", "time_sw3", form_data["time_sw3"])
        self.set_string("rotaryswitch", "data_sw4", form_data["data_sw4"])
        self.set_string("rotaryswitch", "time_sw4", form_data["time_sw4"])
        self.set_string("rotaryswitch", "data_sw5", form_data["data_sw5"])
        self.set_string("rotaryswitch", "time_sw5", form_data["time_sw5"])
        self.set_string("rotaryswitch", "data_sw6", form_data["data_sw6"])
        self.set_string("rotaryswitch", "time_sw6", form_data["time_sw6"])
        self.set_string("rotaryswitch", "data_sw7", form_data["data_sw7"])
        self.set_string("rotaryswitch", "time_sw7", form_data["time_sw7"])

        self.set_string("colors", "color_vfr", form_data["color_vfr"])
        self.set_string("colors", "color_mvfr", form_data["color_mvfr"])
        self.set_string("colors", "color_ifr", form_data["color_ifr"])
        self.set_string("colors", "color_lifr", form_data["color_lifr"])
        self.set_string("colors", "color_nowx", form_data["color_nowx"])
        self.set_string("colors", "color_black", form_data["color_black"])
        self.set_string("colors", "color_lghtn", form_data["color_lghtn"])
        self.set_string("colors", "color_snow1", form_data["color_snow1"])
        self.set_string("colors", "color_snow2", form_data["color_snow2"])
        self.set_string("colors", "color_rain1", form_data["color_rain1"])
        self.set_string("colors", "color_rain2", form_data["color_rain2"])
        self.set_string("colors", "color_frrain1", form_data["color_frrain1"])
        self.set_string("colors", "color_frrain2", form_data["color_frrain2"])
        self.set_string("colors", "color_dustsandash1", form_data["color_dustsandash1"])
        self.set_string("colors", "color_dustsandash2", form_data["color_dustsandash2"])
        self.set_string("colors", "color_fog1", form_data["color_fog1"])
        self.set_string("colors", "color_fog2", form_data["color_fog2"])
        self.set_string("colors", "color_homeport", form_data["color_homeport"])
        self.set_string("colors", "homeport_colors", form_data["homeport_colors"])
        self.set_string("colors", "fade_color1", form_data["fade_color1"])
        self.set_string("colors", "allsame_color1", form_data["allsame_color1"])
        self.set_string("colors", "allsame_color2", form_data["allsame_color2"])
        self.set_string("colors", "shuffle_color1", form_data["shuffle_color1"])
        self.set_string("colors", "shuffle_color2", form_data["shuffle_color2"])
        self.set_string("colors", "radar_color1", form_data["radar_color1"])
        self.set_string("colors", "radar_color2", form_data["radar_color2"])
        self.set_string("colors", "circle_color1", form_data["circle_color1"])
        self.set_string("colors", "circle_color2", form_data["circle_color2"])
        self.set_string("colors", "square_color1", form_data["square_color1"])
        self.set_string("colors", "square_color2", form_data["square_color2"])
        self.set_string("colors", "updn_color1", form_data["updn_color1"])
        self.set_string("colors", "updn_color2", form_data["updn_color2"])
        self.set_string("colors", "rabbit_color1", form_data["rabbit_color1"])
        self.set_string("colors", "rabbit_color2", form_data["rabbit_color2"])
        self.set_string("colors", "checker_color1", form_data["checker_color1"])
        self.set_string("colors", "checker_color2", form_data["checker_color2"])
