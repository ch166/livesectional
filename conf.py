# -*- coding: utf-8 -*- #
"""
Created on Oct 28 - 2021.

@author: chris.higgins@alternoc.net
"""
import logging
import re
import configparser

from logzero import loglevel

import debugging
import utils
import utils_colors
from enum import Enum, auto

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
#   - a config file format that allows importing other config files, as this would allow separation of
#       the configuration data into system / hardware config and separate user / color config

# There are snippets of the configuration that are site hardware implementation specific, and
# snippets of the configuration that are 'end user' airport / settings specific. It would be useful
# to be able to swap out / reset the 'end user' pieces of the configuration without losing the
# configuration state for the hardware (LED , OLED , Switch setup )


class Features(Enum):
    ENABLE_MOS = auto()
    ENABLE_ZEROCONF = auto()
    ENABLE_LED = auto()
    ENABLE_OLED = auto()
    ENABLE_WEB = auto()
    ENABLE_LIGHTSENSOR = auto()
    ENABLE_GPIO_MOD = auto()


class Conf:
    """Configuration Class."""

    cache = {}
    config_filename = None
    configfile = None
    _features = ()

    def __init__(self):
        """Initialize and load configuration."""
        self.config_filename = "config.ini"
        self.configfile = configparser.ConfigParser()
        self.configfile._interpolation = configparser.ExtendedInterpolation()
        self.configfile.read(self.config_filename)
        self.load_features()
        self.update_confcache()

    def get(self, section, key) -> str:
        """Read Setting."""
        return self.configfile.get(section, key, fallback=None)

    def color(self, key) -> str:
        """Pull out color value in hex."""
        return self.configfile.get("colors", key, fallback=None)

    def get_color_decimal(self, section, key) -> tuple:
        """Read three tuple string, Return as tuple of integers."""
        color_list = []
        tmp_string = self.configfile.get(section, key, fallback=None)
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

    def get_web_string(self, section, key, var_type) -> str:
        var_value = self.configfile.get(section, key, fallback=None)
        if var_type == "int":
            return int(var_value)
        if var_type == "bool":
            if utils.str2bool(var_value):
                return "true"
            else:
                return "false"
        if var_type == "string":
            return var_value

    def get_string(self, section, key) -> str:
        """Read Setting."""
        return self.configfile.get(section, key, fallback=None)

    def set_string(self, section, key, value):
        """Set String Value."""
        str_value = f"{value}"
        self.configfile.set(section, key, str_value)

    def set_bool(self, section, key, value):
        """Set Bool Value."""
        bool_value = utils.str2bool(value)
        if bool_value:
            self.configfile.set(section, key, "true")
        else:
            self.configfile.set(section, key, "false")

    def get_bool(self, section, key) -> bool:
        """Read Setting."""
        bool_val = self.configfile.getboolean(section, key, fallback=None)
        if bool_val is None:
            return False
        return bool_val

    def get_float(self, section, key) -> float:
        """Read Setting."""
        return self.configfile.getfloat(section, key, fallback=None)

    def get_int(self, section, key) -> int:
        """Read Setting."""
        return self.configfile.getint(section, key, fallback=None)

    def save_config(self):
        """Save configuration file."""
        self.update_confcache()
        cfgfile = open(self.config_filename, "w", encoding="utf-8")
        self.configfile.write(cfgfile)
        cfgfile.close()

    def enable_proxies(self):
        # Enable use of web proxies for Internet access
        self.set_bool("urls", "use_proxies", True)

    def set_proxy(self, proxy_url, proxy_https=False):
        proxy_type = "http_proxy"
        if proxy_https:
            proxy_type = "https_proxy"
        self.set_string("urls", proxy_type, proxy_url)

    def use_proxies(self):
        """Check for use of http / https proxies."""
        return self.get_bool("urls", "use_proxies")

    def http_proxies(self):
        """Return HTTP(S) proxies from configuration."""
        proxies_conf_http = self.get_string("urls", "http_proxy")
        proxies_conf_https = self.get_string("urls", "https_proxy")
        proxies = {"http": proxies_conf_http, "https": proxies_conf_https}
        if self.use_proxies():
            return proxies
        else:
            return {}

    def load_features(self):
        module_section = "modules"
        for key, value in self.configfile.items(module_section):
            if key == "use_mos" and self.configfile.getboolean(module_section, key):
                self._features += (Features.ENABLE_MOS,)

            if key == "use_zeroconf" and self.configfile.getboolean(
                module_section, key
            ):
                self._features += (Features.ENABLE_ZEROCONF,)

            if key == "use_led_string" and self.configfile.getboolean(
                module_section, key
            ):
                self._features += (Features.ENABLE_LED,)

            if key == "use_oled_panels" and self.configfile.getboolean(
                module_section, key
            ):
                self._features += (Features.ENABLE_OLED,)

            if key == "use_web_interface" and self.configfile.getboolean(
                module_section, key
            ):
                self._features += (Features.ENABLE_WEB,)

            if key == "use_lightsensor" and self.configfile.getboolean(
                module_section, key
            ):
                self._features += (Features.ENABLE_LIGHTSENSOR,)

            if key == "use_gpio" and self.configfile.getboolean(module_section, key):
                self._features += (Features.ENABLE_GPIO_MOD,)

    def active_features(self):
        return self._features

    def update_confcache(self):
        """Update class local variables to cache conf data."""
        # This is a performance improvement cache of conf data
        # TODO: Move in the rest of the data that gets accessed regularly
        # Would be useful to have usage stats for the conf data to prioritize new additions
        self.cache["first_setup_complete"] = self.get_bool(
            "default", "first_setup_complete"
        )
        self.cache["adminuser"] = self.get_string("default", "adminuser")
        self.cache["adminpass"] = self.get_string("default", "adminpass")
        self.cache["use_proxies"] = self.get_bool("urls", "use_proxies")
        self.cache["http_proxy"] = self.get_string("urls", "http_proxy")
        self.cache["https_proxy"] = self.get_string("urls", "https_proxy")

        self.cache["color_vfr"] = utils_colors.cat_vfr(self)
        self.cache["color_mvfr"] = utils_colors.cat_mvfr(self)
        self.cache["color_ifr"] = utils_colors.cat_ifr(self)
        self.cache["color_lifr"] = utils_colors.cat_lifr(self)
        self.cache["color_nowx"] = utils_colors.wx_noweather(self)
        self.cache["lights_highwindblink"] = self.get_bool(
            "activelights", "high_wind_blink"
        )
        self.cache["metar_maxwindspeed"] = self.get_int(
            "activelights", "high_wind_limit"
        )
        self.cache["lights_lghtnflash"] = self.get_bool("lights", "lghtnflash")
        self.cache["lights_snowshow"] = self.get_bool("lights", "snowshow")
        self.cache["lights_rainshow"] = self.get_bool("lights", "rainshow")
        self.cache["lights_frrainshow"] = self.get_bool("lights", "frrainshow")
        self.cache["lights_dustsandashshow"] = self.get_bool(
            "lights", "dustsandashshow"
        )
        self.cache["lights_fogshow"] = self.get_bool("lights", "fogshow")
        self.cache["lights_homeportpin"] = self.get_int("lights", "homeport_pin")
        self.cache["lights_homeport"] = self.get_int("lights", "homeport")
        self.cache["lights_homeport_display"] = self.get_int(
            "lights", "homeport_display"
        )
        self.cache["rgb_grb"] = self.get_bool("lights", "rgb_grb")
        self.cache["rev_rgb_grb"] = self.get_string("lights", "rev_rgb_grb")
        self.cache["usetimer"] = self.get_bool("schedule", "usetimer")

    def gen_settings_dict(self) -> dict:
        """Generate settings template to pass to flask."""
        # Use get_web_string here rather than get_bool ; to generate a string in a format that is consistent for the HTML templates & jinja2 logic
        settings = {
            "LED_COUNT": self.get_string("default", "led_count"),
            "legend": self.get_web_string("default", "legend", "bool"),
            "first_setup_complete": self.get_web_string(
                "default", "first_setup_complete", "bool"
            ),
            "max_wind_speed": self.get_string("activelights", "high_wind_limit"),
            "wx_update_interval": self.get_string("metar", "wx_update_interval"),
            "metar_age": self.get_string("metar", "metar_age"),
            "usetimer": self.get_web_string("schedule", "usetimer", "bool"),
            "offtime": self.get_string("schedule", "offtime"),
            "ontime": self.get_string("schedule", "ontime"),
            "loglevel": self.get_string("logging", "loglevel"),
            "tempsleepon": self.get_string("schedule", "tempsleepon"),
            "sleepmsg": self.get_string("schedule", "sleepmsg"),
            "displayused": self.get_web_string("oled", "displayused", "bool"),
            "oledused": self.get_web_string("oled", "oledused", "bool"),
            "lcddisplay": self.get_web_string("oled", "lcddisplay", "bool"),
            "numofdisplays": self.get_string("oled", "numofdisplays"),
            "bright_value": self.get_string("lights", "bright_value"),
            "highwindblink": self.get_web_string(
                "activelights", "high_wind_blink", "bool"
            ),
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
        self.set_string("default", "led_count", form_data["LED_COUNT"])
        #

        # Handle checkboxes - Only if the checkbox is set in the browser, it will appear in the form.
        if "first_setup_complete" in form_data:
            self.set_bool("default", "first_setup_complete", True)
        else:
            self.set_bool("default", "first_setup_complete", False)

        if "legend" in form_data:
            self.set_bool("default", "legend", True)
        else:
            self.set_bool("default", "legend", False)

        if "usetimer" in form_data:
            self.set_bool("schedule", "usetimer", True)
        else:
            self.set_bool("schedule", "usetimer", False)

        if "sleepmsg" in form_data:
            self.set_bool("schedule", "sleepmsg", True)
        else:
            self.set_bool("schedule", "sleepmsg", False)

        if "displayused" in form_data:
            self.set_bool("oled", "displayused", True)
        else:
            self.set_bool("oled", "displayused", False)

        if "oledused" in form_data:
            self.set_bool("oled", "oledused", True)
        else:
            self.set_bool("oled", "oledused", False)

        if "lcddisplay" in form_data:
            self.set_bool("oled", "lcddisplay", True)
        else:
            self.set_bool("oled", "lcddisplay", False)

        if "highwindblink" in form_data:
            self.set_bool("activelights", "highwindblink", True)
        else:
            self.set_bool("activelights", "highwindblink", False)

        if "lghtnflash" in form_data:
            self.set_bool("lights", "lghtnflash", True)
        else:
            self.set_bool("lights", "lghtnflash", False)

        if "rainshow" in form_data:
            self.set_bool("lights", "rainshow", True)
        else:
            self.set_bool("lights", "rainshow", False)

        if "frrainshow" in form_data:
            self.set_bool("lights", "frrainshow", True)
        else:
            self.set_bool("lights", "frrainshow", False)

        if "snowshow" in form_data:
            self.set_bool("lights", "snowshow", True)
        else:
            self.set_bool("lights", "snowshow", False)

        if "dustsandashshow" in form_data:
            self.set_bool("lights", "dustsandashshow", True)
        else:
            self.set_bool("lights", "dustsandashshow", False)

        if "fogshow" in form_data:
            self.set_bool("lights", "fogshow", True)
        else:
            self.set_bool("lights", "fogshow", False)

        if "legend_hiwinds" in form_data:
            self.set_bool("lights", "legend_hiwinds", True)
        else:
            self.set_bool("lights", "legend_hiwinds", False)

        if "legend_lghtn" in form_data:
            self.set_bool("lights", "legend_lghtn", True)
        else:
            self.set_bool("lights", "legend_lghtn", False)

        if "legend_snow" in form_data:
            self.set_bool("lights", "legend_snow", True)
        else:
            self.set_bool("lights", "legend_snow", False)

        if "legend_rain" in form_data:
            self.set_bool("lights", "legend_rain", True)
        else:
            self.set_bool("lights", "legend_rain", False)

        if "legend_frrain" in form_data:
            self.set_bool("lights", "legend_frrain", True)
        else:
            self.set_bool("lights", "legend_frrain", False)

        if "legend_dustsandash" in form_data:
            self.set_bool("lights", "legend_dustsandash", True)
        else:
            self.set_bool("lights", "legend_dustsandash", False)

        if "legend_fog" in form_data:
            self.set_bool("lights", "legend_fog", True)
        else:
            self.set_bool("lights", "legend_fog", False)

        if "exclusive_flag" in form_data:
            self.set_bool("lights", "exclusive_flag", True)
        else:
            self.set_bool("lights", "exclusive_flag", False)

        if "abovekts" in form_data:
            self.set_bool("lights", "abovekts", True)
        else:
            self.set_bool("lights", "abovekts", False)

        if "rotyesno" in form_data:
            self.set_bool("lights", "rotyesno", True)
        else:
            self.set_bool("lights", "rotyesno", False)

        if "oledposorder" in form_data:
            self.set_bool("oled", "oledposorder", True)
        else:
            self.set_bool("oled", "oledposorder", False)

        if "wind_numorarrow" in form_data:
            self.set_bool("oled", "wind_numorarrow", True)
        else:
            self.set_bool("oled", "wind_numorarrow", False)

        if "boldhiap" in form_data:
            self.set_bool("oled", "boldhiap", True)
        else:
            self.set_bool("oled", "boldhiap", False)

        if "blankscr" in form_data:
            self.set_bool("oled", "blankscr", True)
        else:
            self.set_bool("oled", "blankscr", False)

        if "border" in form_data:
            self.set_bool("oled", "border", True)
        else:
            self.set_bool("oled", "border", False)

        if "invert" in form_data:
            self.set_bool("oled", "invert", True)
        else:
            self.set_bool("oled", "invert", False)

        if "toginv" in form_data:
            self.set_bool("oled", "toginv", True)
        else:
            self.set_bool("oled", "toginv", False)

        if "scrolldis" in form_data:
            self.set_bool("oled", "scrolldis", True)
        else:
            self.set_bool("oled", "scrolldis", False)

        if "usewelcome" in form_data:
            self.set_bool("oled", "usewelcome", True)
        else:
            self.set_bool("oled", "usewelcome", False)

        if "displaytime" in form_data:
            self.set_bool("oled", "displaytime", True)
        else:
            self.set_bool("oled", "displaytime", False)

        if "displayip" in form_data:
            self.set_bool("oled", "displayip", True)
        else:
            self.set_bool("oled", "displayip", False)

        if "rgb_grb" in form_data:
            self.set_bool("lights", "rgb_grb", True)
        else:
            self.set_bool("lights", "rgb_grb", False)

        debugging.info("processing input form data ; getting to loglevel")

        if "loglevel" in form_data:
            self.set_string("logging", "loglevel", form_data["loglevel"])
            new_loglevel = form_data["loglevel"]
            new_loglevel = new_loglevel.lower()
            if new_loglevel == "debug":
                debugging.setLogLevel(logging.DEBUG)
            elif new_loglevel == "info":
                debugging.setLogLevel(logging.INFO)
            elif new_loglevel == "warning":
                debugging.setLogLevel(logging.WARNING)
            elif new_loglevel == "error":
                debugging.setLogLevel(logging.ERROR)
            elif new_loglevel == "critical":
                debugging.setLogLevel(logging.CRITICAL)
            else:
                debugging.setLogLevel(logging.ERROR)
                debugging.info(
                    f"Parsing web input - Trying to set loglevel, defaulting to ERROR couldn't handle {form_data['loglevel']}"
                )

        debugging.info("processing input form data ; past loglevel")

        self.set_string("activelights", "high_wind_limit", form_data["max_wind_speed"])
        self.set_string("metar", "wx_update_interval", form_data["wx_update_interval"])
        self.set_string("metar", "metar_age", form_data["metar_age"])

        self.set_string("schedule", "offtime", form_data["offtime"])
        self.set_string("schedule", "ontime", form_data["ontime"])
        self.set_string("schedule", "tempsleepon", form_data["tempsleepon"])
        #

        self.set_string("oled", "numofdisplays", form_data["numofdisplays"])
        #
        self.set_string("lights", "bright_value", form_data["bright_value"])
        self.set_string("lights", "homeport_pin", form_data["homeport_pin"])
        self.set_string("lights", "homeport_display", form_data["homeport_display"])
        self.set_string("lights", "dim_value", form_data["dim_value"])

        self.set_string("lights", "rev_rgb_grb", form_data["rev_rgb_grb"])
        self.set_string("lights", "dimmed_value", form_data["dimmed_value"])
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
        self.set_string("lights", "exclusive_list", form_data["exclusive_list"])
        self.set_string("lights", "lcdpause", form_data["lcdpause"])
        self.set_string("oled", "oledpause", form_data["oledpause"])
        self.set_string("oled", "fontsize", form_data["fontsize"])
        self.set_string("oled", "offset", form_data["offset"])
        self.set_string("oled", "dimswitch", form_data["dimswitch"])
        self.set_string("oled", "dimmin", form_data["dimmin"])
        self.set_string("oled", "dimmax", form_data["dimmax"])
        self.set_string("default", "welcome", form_data["welcome"])
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
