# -*- coding: utf-8 -*- "

""" update_leds.py.

# Moved all of the airport specific data / metar analysis functions to update_airport.py
# This module creates a class updateLEDs that is specifically focused around
# managing a string of LEDs.
"""
#
# All of the functions to initialise, manipulate, wipe, change the LEDs are
# being included here.
#
# This also includes the wipe patterns from wipes-v4.py
#
# As this transition completes, all older code will be removed from here, so that the focus is only
# on managing an LED strip
#
# Flight Category Definitions. (https://www.aviationweather.gov/taf/help?page=plot)
# +--------------------------------------+---------------+-------------------------------+-------+----------------------------+
# |Category                              |Color          |Ceiling                        |       |Visibility                  |
# |--------------------------------------+---------------+-------------------------------+-------+----------------------------+
# |VFR   Visual Flight Rules             |Green          |greater than 3,000 feet AGL    |and    |greater than 5 miles        |
# |MVFR  Marginal Visual Flight Rules    |Blue           |1,000 to 3,000 feet AGL        |and/or |3 to 5 miles                |
# |IFR   Instrument Flight Rules         |Red            |500 to below 1,000 feet AGL    |and/or |1 mile to less than 3 miles |
# |LIFR  Low Instrument Flight Rules     |Magenta        |       below 500 feet AGL      |and-or |less than 1 mile            |
# +--------------------------------------+---------------+-------------------------------+-------+----------------------------+
# AGL = Above Ground Level

#    Includes the following patterns;
#       Rainbow
#       Square
#       Circle
#       Radar
#       Up/Down and Side to Side
#       All One Color
#       Fader
#       Shuffle
#       Morse Code
#       Rabbit Chase
#       Checkerbox
#
#    Fixed wipes that turned on NULL and LGND Leds
#    Fixed dimming feature when a wipe is executed
#    Fixed bug whereby lat/lon was miscalculated for certain wipes.


# Import needed libraries

import math
import datetime
import time
from enum import Enum, auto

# from datetime import datetime
# from datetime import time as time
# import random
# import collections
import colorsys
import ast

from rpi_ws281x import (
    Color,
    PixelStrip,
    ws,
)  # works with python 3.7. sudo pip3 install rpi_ws281x

import debugging
import utils
import utils_colors
import utils_gfx


class LedMode(Enum):
    """Set of Operating Modes for LED Strip."""

    OFF = auto()
    SLEEP = auto()
    METAR = auto()
    HEATMAP = auto()
    FADE = auto()
    TEST = auto()
    SHUFFLE = auto()
    RADARWIPE = auto()
    RABBIT = auto()
    RAINBOW = auto()
    SQUAREWIPE = auto()
    WHEELWIPE = auto()
    CIRCLEWIPE = auto()


class UpdateLEDs:
    """Class to manage LED Strips."""

    PI = 3.141592653
    BIGNUM = 10000000
    DELAYSHORT = 0.1
    DELAYMEDIUM = 0.4
    DELAYLONG = 0.6
    PAUSESHORT = 1

    __conf = {}
    __airport_database = {}
    __confcache = {}

    # Set toggle_sw to an initial value that forces rotary switch to dictate data displayed
    __toggle_sw = -1
    __led_mode = LedMode.METAR

    __active_led_dict = {}

    # List of METAR weather categories to designate weather in area. Many Metars will report multiple conditions, i.e. '-RA BR'.
    # The code pulls the first/main weather reported to compare against the lists below. In this example it uses the '-RA' and ignores the 'BR'.
    # See https://www.aviationweather.gov/metar/symbol for descriptions. Add or subtract codes as desired.
    # Thunderstorm and lightning
    wx_lghtn_ck = [
        "TS",
        "TSRA",
        "TSGR",
        "+TSRA",
        "TSRG",
        "FC",
        "SQ",
        "VCTS",
        "VCTSRA",
        "VCTSDZ",
        "LTG",
    ]

    # Snow in various forms
    wx_snow_ck = [
        "BLSN",
        "DRSN",
        "-RASN",
        "RASN",
        "+RASN",
        "-SN",
        "SN",
        "+SN",
        "SG",
        "IC",
        "PE",
        "PL",
        "-SHRASN",
        "SHRASN",
        "+SHRASN",
        "-SHSN",
        "SHSN",
        "+SHSN",
    ]

    # Rain in various forms
    wx_rain_ck = [
        "-DZ",
        "DZ",
        "+DZ",
        "-DZRA",
        "DZRA",
        "-RA",
        "RA",
        "+RA",
        "-SHRA",
        "SHRA",
        "+SHRA",
        "VIRGA",
        "VCSH",
    ]

    # Freezing Rain
    wx_frrain_ck = ["-FZDZ", "FZDZ", "+FZDZ", "-FZRA", "FZRA", "+FZRA"]

    # Dust Sand and/or Ash
    wx_dustsandash_ck = [
        "DU",
        "SA",
        "HZ",
        "FU",
        "VA",
        "BLDU",
        "BLSA",
        "PO",
        "VCSS",
        "SS",
        "+SS",
    ]

    # Fog
    wx_fog_ck = ["BR", "MIFG", "VCFG", "BCFG", "PRFG", "FG", "FZFG"]

    # Flight Categories
    categories = [
        "HR",
        "CLD",
        "WDR",
        "WSP",
        "P06",
        "T06",
        "POZ",
        "POS",
        "TYP",
        "CIG",
        "VIS",
        "OBV",
    ]

    obv_wx = {
        "N": "None",
        "HZ": "HZ",
        "BR": "RA",
        "FG": "FG",
        "BL": "HZ",
    }

    # Decode from MOS to TAF/METAR
    typ_wx = {"S": "SN", "Z": "FZRA", "R": "RA"}

    # Morse Code Dictionary
    morse_code = {
        "A": ".-",
        "B": "-...",
        "C": "-.-.",
        "D": "-..",
        "E": ".",
        "F": "..-.",
        "G": "--.",
        "H": "....",
        "I": "..",
        "J": ".---",
        "K": "-.-",
        "L": ".-..",
        "M": "--",
        "N": "-.",
        "O": "---",
        "P": ".--.",
        "Q": "--.-",
        "R": ".-.",
        "S": "...",
        "T": "-",
        "U": "..-",
        "V": "...-",
        "W": ".--",
        "X": "-..-",
        "Y": "-.--",
        "Z": "--..",
        "1": ".----",
        "2": "..---",
        "3": "...--",
        "4": "....-",
        "5": ".....",
        "6": "-....",
        "7": "--...",
        "8": "---..",
        "9": "----.",
        "0": "-----",
        ",": "--..--",
        ".": ".-.-.-",
        "?": "..--..",
        "/": "-..-.",
        "-": "-....-",
        "(": "-.--.",
        ")": "-.--.-",
    }

    # FIXME: Needs to tie to the list of disabled LEDs
    __nullpins = []
    __wait = 1

    # Colors
    __rgb_rainbow = None

    # LED Cycle times - Can change if necessary.
    # Used to create weather designation effects.
    __cycle_wait = [0.9, 0.9, 0.08, 0.1, 0.08, 0.5]

    # LED self.strip configuration:
    __led_pin = 18  # GPIO pin connected to the pixels (18 uses PWM!).

    # LED signal frequency in hertz (usually 800khz)
    __led_freq_hz = 800_000
    __led_dma = 5  # DMA channel to use for generating signal (try 5)

    # True to invert the signal (when using NPN transistor level shift)
    __led_invert = False
    __led_channel = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
    __led_strip = ws.WS2811_STRIP_GRB  # Strip type and color ordering

    def __init__(self, conf, airport_database):
        """Initialize LED Strip."""
        self.__conf = conf
        self.__airport_database = airport_database

        # Populate the config cache data
        self.update_confcache()

        # Specific Variables to default data to display if Rotary Switch is not installed.
        # hour_to_display # Offset in HOURS to choose which TAF/MOS to display
        self.hour_to_display = self.__conf.get_int("rotaryswitch", "time_sw0")
        # metar_taf_mos    # 0 = Display TAF, 1 = Display METAR, 2 = Display MOS, 3 = Heat Map (Heat map not controlled by rotary switch)
        self.__metar_taf_mos = self.__conf.get_int("rotaryswitch", "data_sw0")

        self.nightsleep = self.__conf.get_bool("schedule", "usetimer")

        self.__offtime = datetime.time(
            self.__conf.get_int("schedule", "offhour"),
            self.__conf.get_int("schedule", "offminutes"),
            0,
            0,
        )

        self.__ontime = datetime.time(
            self.__conf.get_int("schedule", "onhour"),
            self.__conf.get_int("schedule", "onminutes"),
            0,
            0,
        )

        # Set number of MINUTES to turn map on temporarily during sleep mode
        self.__tempsleepon = self.__conf.get_int("schedule", "tempsleepon")

        # Number of LED pixels. Change this value to match the number of LED's being used on map
        self.__led_count = self.__conf.get_int("default", "led_count")

        # 1 = RGB color codes. 0 = GRB color codes. Populate color codes below with normal RGB codes and script will change if necessary
        self.__rgb_grb = self.__conf.get_int("lights", "rgb_grb")

        self.homeport_toggle = False
        self.homeport_colors = ast.literal_eval(
            self.__conf.get_string("colors", "homeport_colors")
        )

        # Blanking during refresh of the LED string between FAA updates.
        # Removing because it's not currently used
        # Future code could have the wx_update loop send a signal here to update_leds to trigger a refresh.
        # self.blank_during_refresh = False

        # starting brightness. It will be changed below.
        self.__led_brightness = self.__conf.get_int("lights", "bright_value")

        # MOS Data Settings
        self.__mos_filepath = self.__conf.get_string("filenames", "mos_filepath")

        # Create an instance of NeoPixel
        self.strip = PixelStrip(
            self.__led_count,
            self.__led_pin,
            self.__led_freq_hz,
            self.__led_dma,
            self.__led_invert,
            self.__led_brightness,
            self.__led_channel,
            self.__led_strip,
        )
        self.strip.begin()
        # self.init_rainbow()
        debugging.info("LED Strip INIT complete")

    # Functions
    def init_rainbow(self):
        """Define Rainbow Color List."""
        rainbow_index = 30
        hsv_tuples = [
            (x * 1.0 / rainbow_index, 0.85, 0.5) for x in range(rainbow_index)
        ]
        rgb_tuples = map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples)
        rgb_list = list(rgb_tuples)
        for i, rgb_col in enumerate(rgb_list):
            (col_r, col_g, col_b) = rgb_col
            rgb_list[i] = (col_r * 255, col_g * 255, col_b * 255)
        self.__rgb_rainbow = rgb_list
        debugging.info(f"Rainbow List - {self.__rgb_rainbow}")

    def update_confcache(self):
        """Update class local variables to cache conf data."""
        # This is a performance improvement cache of conf data
        # TODO: Need to make sure we update this when the config changes
        self.__confcache["vfr_color"] = utils_colors.cat_vfr(self.__conf)
        self.__confcache["mvfr_color"] = utils_colors.cat_mvfr(self.__conf)
        self.__confcache["ifr_color"] = utils_colors.cat_ifr(self.__conf)
        self.__confcache["lifr_color"] = utils_colors.cat_lifr(self.__conf)
        self.__confcache["unkn_color"] = utils_colors.wx_noweather(self.__conf)
        self.__confcache["lights_highwindblink"] = self.__conf.get_bool(
            "lights", "hiwindblink"
        )
        self.__confcache["metar_maxwindspeed"] = self.__conf.get_int(
            "metar", "max_wind_speed"
        )
        self.__confcache["lights_lghtnflash"] = self.__conf.get_bool(
            "lights", "lghtnflash"
        )
        self.__confcache["lights_snowshow"] = self.__conf.get_bool("lights", "snowshow")
        self.__confcache["lights_rainshow"] = self.__conf.get_bool("lights", "rainshow")
        self.__confcache["lights_frrainshow"] = self.__conf.get_bool(
            "lights", "frrainshow"
        )
        self.__confcache["lights_dustsandashshow"] = self.__conf.get_bool(
            "lights", "dustsandashshow"
        )
        self.__confcache["lights_fogshow"] = self.__conf.get_bool("lights", "fogshow")
        self.__confcache["lights_homeportpin"] = self.__conf.get_int(
            "lights", "homeport_pin"
        )
        self.__confcache["lights_homeport"] = self.__conf.get_int("lights", "homeport")
        self.__confcache["lights_homeport_display"] = self.__conf.get_int(
            "lights", "homeport_display"
        )
        self.__confcache["rev_rgb_grb"] = self.__conf.get_string(
            "lights", "rev_rgb_grb"
        )

    def ledmode(self):
        """Return current LED Mode."""
        return self.__led_mode

    def set_ledmode(self, new_mode):
        """Update active LED Mode."""
        self.__led_mode = new_mode

    def set_led_color(self, led_id, hexcolor):
        """Convert color from HEX to RGB or GRB and apply to LED String."""
        # TODO: Add capability here to manage 'nullpins' and remove any mention of nullpins from
        # the rest of the code
        #
        # This function should do all the color conversions
        rgb_color = utils_colors.rgb_color(hexcolor)
        color_ord = self.rgb_to_pixel(led_id, rgb_color, self.__rgb_grb)
        pixel_data = Color(color_ord[0], color_ord[1], color_ord[2])
        if isinstance(led_id, str):
            debugging.info(f"led_id : {led_id} str")
            return
        self.strip.setPixelColor(led_id, pixel_data)

    def update_active_led_list(self):
        """Update Active LED list."""
        active_led_dict = {}
        led_index = 0
        posn = 0
        airports = self.__airport_database.get_airport_dict_led()
        if airports is None:
            return
        for icao, airport_obj in airports.items():
            if not airport_obj.active():
                debugging.debug(f"Airport Not Active {icao} : Not updating LED list")
                continue
            led_index = airport_obj.get_led_index()
            active_led_dict[posn] = led_index
            posn = posn + 1
        self.__active_led_dict = active_led_dict

    def show(self):
        """Update LED strip to display current colors."""
        self.strip.show()

    def turnoff(self):
        """Set color to 0,0,0  - turning off LED."""
        for i in range(self.num_pixels()):
            self.set_led_color(i, utils_colors.black())
        self.show()

    def fill(self, color):
        """Return led_updated_dict containing single color only"""
        debugging.info("Fill: In the fill loop")
        led_updated_dict = {}
        for led_posn, active_led in enumerate(self.__active_led_dict):
            led_updated_dict[self.__active_led_dict[led_posn]] = color
        return led_updated_dict

    def num_pixels(self):
        """Return number of Pixels defined."""
        return self.__led_count

    def set_brightness(self, lux):
        """Update saved brightness value."""
        self.__led_brightness = round(lux)

    def dim(self, color_data, value):
        """DIM LED.

        # Reduces the brightness of the colors for every airport except for
        # the "homeport_pin" designated airport, which remains at the brightness set by
        # "bright_value" above in user setting. "data" is the airport color to display
        # and "value" is the percentage of the brightness to be dimmed.
        # For instance if full bright white (255,255,255) is provided and the desired
        # dimming is 50%, then the color returned will be (128,128,128),
        # or half as bright. The dim_value is set in the user defined area.
        """
        if isinstance(value, str):
            value = int(value)
        data = utils_colors.rgb_color(color_data)
        red = max(data[0] - ((value * data[0]) / 100), 0)
        grn = max(data[1] - ((value * data[1]) / 100), 0)
        blu = max(data[2] - ((value * data[2]) / 100), 0)
        return utils_colors.hexcode(red, grn, blu)

    def frange(self, start, stop, step):
        """Range to loop through floats, rather than integers. Used to loop through lat/lons."""
        if start != stop:
            i = start
            if i < stop:
                while i < stop:
                    yield round(i, 2)
                    i += step
            else:
                while i > stop:
                    yield round(i, 2)
                    i -= step

    def rgb_to_pixel(self, pin, data, order=True):
        """Change colorcode to match self.strip RGB / GRB style."""
        # Change color code to work with various led self.strips. For instance, WS2812 model
        # self.strip uses RGB where WS2811 model uses GRB
        # Set the "rgb_grb" user setting above. 1 for RGB LED self.strip, and 0 for GRB self.strip.
        # If necessary, populate the list rev_rgb_grb with pin numbers of LED's that use the opposite color scheme.
        # list of pins that need to use the reverse of the normal order setting.
        # This accommodates the use of both models of LED strings on one map.
        if str(pin) in self.__confcache["rev_rgb_grb"]:
            order = not order
            debugging.info(f"Reversing rgb2grb Routine Output for PIN {pin}")
        red = data[0]
        grn = data[1]
        blu = data[2]
        if order:
            data = [red, grn, blu]
        else:
            data = [grn, red, blu]
        return data

    # For Heat Map. Based on visits, assign color. Using a 0 to 100 scale where 0 is never visted and 100 is home airport.
    # Can choose to display binary colors with homeap.
    def heatmap_color(self, visits):
        """Color codes assigned with heatmap."""
        if visits == "0":
            color = utils_colors.colordict["GOLD"]
        elif visits == "100":
            if self.__conf.get_bool(
                "rotaryswitch", "fade_yesno"
            ) and self.__conf.get_bool("rotaryswitch", "bin_grad"):
                color = utils_colors.black()
            elif not self.__conf.get_bool("rotaryswitch", "use_homeap"):
                color = utils_colors.colordict["RED"]
            else:
                color = self.__conf.get_string("colors", "color_vfr")
        elif "1" <= visits <= "50":  # Working
            if self.__conf.get_bool("rotaryswitch", "bin_grad"):
                red = 255
                grn = 0
                blu = 0
                red = int(int(visits) * 5.1)
                color = utils_colors.rgb2hex((red, grn, blu))
            else:
                color = utils_colors.colordict["RED"]
        elif "51" <= visits <= "99":  # Working
            if self.__conf.get_bool("rotaryswitch", "bin_grad"):
                red = 255
                grn = 0
                blu = 0
                blu = 255 - int((int(visits) - 50) * 5.1)
                color = utils_colors.rgb2hex((red, grn, blu))
            else:
                color = utils_colors.rgb2hex((255, 0, 0))
        else:
            color = utils_colors.black()
        return color

    def update_loop(self):
        """LED Display Loop - supporting multiple functions."""
        clocktick = 0
        sleeping = False
        original_state = LedMode.METAR
        self.update_active_led_list()
        rainbowtick = 0
        while True:
            # Going to use an index counter as a pseudo clock tick for
            # each LED module. It's going to continually increase through
            # each pass - and it's max value is a limiter on the number of LEDs
            # If each pass through this loop touches one LED ; then we need enough
            # clock cycles to cover every LED.
            clocktick = (clocktick + 1) % self.BIGNUM

            if (clocktick % 1000) == 1:
                # Make sure the active LED list is updated
                self.update_active_led_list()

            # Check for nighttime every 1000 times through the loop
            # Keep the CPU load down
            if ((clocktick % 200) == 1) and self.nightsleep:
                debugging.info(f"Checking if it's time for sleep mode: {clocktick}")
                datetime_now = utils.current_time(self.__conf)
                time_now = datetime_now.time()
                if utils.time_in_range(self.__offtime, self.__ontime, time_now):
                    if not sleeping:
                        debugging.info("Enabling sleeping mode...")
                        original_state = self.__led_mode
                        self.__led_mode = LedMode.SLEEP
                        sleeping = True
                    else:
                        # It's night time; we're already sleeping. Take a break.
                        debugging.info(f"Sleeping .. {clocktick}")
                elif sleeping:
                    debugging.info(f"Disabling sleeping mode... {clocktick} ")
                    self.__led_mode = original_state
                    sleeping = False

            if self.__led_mode in (LedMode.OFF, LedMode.SLEEP):
                self.turnoff()
                time.sleep(self.PAUSESHORT)
                continue
            if self.__led_mode == LedMode.METAR:
                led_color_dict = self.ledmode_metar(clocktick)
                self.update_ledstring(led_color_dict)
                continue
            if self.__led_mode == LedMode.TEST:
                self.ledmode_test(clocktick)
                led_color_dict = self.colorwipe(clocktick)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.RAINBOW:
                led_color_dict = self.ledmode_rainbow(rainbowtick)
                self.update_ledstring(led_color_dict)
                rainbowtick += 5
                time.sleep(self.DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.FADE:
                led_color_dict = self.ledmode_fade(clocktick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYSHORT)
                continue
            if self.__led_mode == LedMode.RABBIT:
                led_color_dict = self.ledmode_rabbit(clocktick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYSHORT)
                continue
            if self.__led_mode == LedMode.SHUFFLE:
                led_color_dict = self.ledmode_shuffle(clocktick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            #
            # Rewrite complete as far as here
            #
            if self.__led_mode == LedMode.RADARWIPE:
                led_color_dict = self.ledmode_rabbit(clocktick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.SQUAREWIPE:
                led_color_dict = self.ledmode_rabbit(clocktick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.WHEELWIPE:
                led_color_dict = self.ledmode_rabbit(clocktick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.CIRCLEWIPE:
                led_color_dict = self.ledmode_rabbit(clocktick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.HEATMAP:
                led_color_dict = self.ledmode_heatmap(clocktick)
                self.update_ledstring(led_color_dict)
                continue

    def update_ledstring(self, led_color_dict):
        """Iterate across all the LEDs and set the color appropriately."""
        for ledindex, led_color in led_color_dict.items():
            self.set_led_color(ledindex, led_color)
        self.strip.setBrightness(self.__led_brightness)
        self.show()

    def ledmode_test(self, clocktick):
        """Run self test sequences."""
        return self.colorwipe(clocktick)

    def legend_color(self, airportwxsrc, cycle_num):
        """Work out the color for the legend LEDs."""
        ledcolor = utils_colors.off()
        if airportwxsrc == "vfr":
            ledcolor = self.__confcache["vfr_color"]
        if airportwxsrc == "mvfr":
            ledcolor = self.__confcache["mvfr_color"]
        if airportwxsrc == "ifr":
            ledcolor = self.__confcache["ifr_color"]
        if airportwxsrc == "lifr":
            ledcolor = self.__confcache["lifr_color"]
        if airportwxsrc == "nowx":
            ledcolor = self.__confcache["unkn_color"]
        if airportwxsrc == "hiwind":
            if cycle_num in (3, 4, 5):
                ledcolor = utils_colors.off()
            else:
                ledcolor = self.__confcache["ifr_color"]
        if airportwxsrc == "lghtn":
            if cycle_num in (2, 4):
                ledcolor = utils_colors.wx_lightning(self.__conf)
            else:
                ledcolor = self.__confcache["mvfr_color"]
        if airportwxsrc == "snow":
            if cycle_num in (3, 5):  # Check for Snow
                ledcolor = utils_colors.wx_snow(self.__conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.wx_snow(self.__conf, 2)
            else:
                ledcolor = self.__confcache["lifr_color"]
        if airportwxsrc == "rain":
            if cycle_num in (3, 5):  # Check for Rain
                ledcolor = utils_colors.wx_rain(self.__conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.wx_rain(self.__conf, 2)
            else:
                ledcolor = self.__confcache["vfr_color"]
        if airportwxsrc == "frrain":
            if cycle_num in (3, 5):  # Check for Freezing Rain
                ledcolor = utils_colors.wx_frzrain(self.__conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.wx_frzrain(self.__conf, 2)
            else:
                ledcolor = self.__confcache["mvfr_color"]
        if airportwxsrc == "dust":
            if cycle_num in (3, 5):  # Check for Dust, Sand or Ash
                ledcolor = utils_colors.wx_dust_sand_ash(self.__conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.wx_dust_sand_ash(self.__conf, 2)
            else:
                ledcolor = self.__confcache["vfr_color"]
        if airportwxsrc == "fog":
            if cycle_num in (3, 5):  # Check for Fog
                ledcolor = utils_colors.wx_fog(self.__conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.wx_fog(self.__conf, 2)
            elif cycle_num in (0, 1, 2):
                ledcolor = self.__confcache["ifr_color"]
        return ledcolor

    def ledmode_metar(self, clocktick):
        """Generate LED Color set for Airports."""
        airport_list = self.__airport_database.get_airport_dict_led()
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()

        cycle_num = clocktick % len(self.__cycle_wait)

        for airport_key, airport_obj in airport_list.items():
            airportcode = airport_obj.icaocode()
            airportled = airport_obj.get_led_index()
            airportwxsrc = airport_obj.wxsrc()
            if not airportcode:
                continue
            if airportcode == "null":
                continue
            if airportcode == "lgnd":
                ledcolor = self.legend_color(airportwxsrc, cycle_num)

            # Initialize color
            ledcolor = utils_colors.off()
            # Pull the next flight category from dictionary.
            flightcategory = airport_obj.flightcategory()
            if not flightcategory:
                flightcategory = "UNKN"
            # Pull the winds from the dictionary.
            airportwinds = airport_obj.get_wx_windspeed()
            if not airportwinds:
                airportwinds = -1
            airport_conditions = airport_obj.wxconditions()
            debugging.debug(
                f"{airportcode}:{flightcategory}:{airportwinds}:cycle=={cycle_num}"
            )

            # Start of weather display code for each airport in the "airports" file
            # Check flight category and set the appropriate color to display
            if flightcategory == "VFR":  # Visual Flight Rules
                ledcolor = self.__confcache["vfr_color"]
            elif flightcategory == "MVFR":  # Marginal Visual Flight Rules
                ledcolor = self.__confcache["mvfr_color"]
            elif flightcategory == "IFR":  # Instrument Flight Rules
                ledcolor = self.__confcache["ifr_color"]
            elif flightcategory == "LIFR":  # Low Instrument Flight Rules
                ledcolor = self.__confcache["lifr_color"]
            elif flightcategory == "UNKN":
                ledcolor = self.__confcache["unkn_color"]

            # Check winds and set the 2nd half of cycles to black to create blink effect
            if self.__confcache["lights_highwindblink"]:
                # bypass if "hiwindblink" is set to 0
                if int(airportwinds) >= self.__confcache["metar_maxwindspeed"] and (
                    cycle_num in (3, 4, 5)
                ):
                    ledcolor = utils_colors.off()
                    debugging.debug(f"HIGH WINDS {airportcode} : {airportwinds} kts")

            if self.__confcache["lights_lghtnflash"]:
                # Check for Thunderstorms
                if airport_conditions in self.wx_lghtn_ck and (cycle_num in (2, 4)):
                    ledcolor = utils_colors.wx_lightning(self.__conf)

            if self.__confcache["lights_snowshow"]:
                # Check for Snow
                if airport_conditions in self.wx_snow_ck and (cycle_num in (3, 5)):
                    ledcolor = utils_colors.wx_snow(self.__conf, 1)
                if airport_conditions in self.wx_snow_ck and cycle_num == 4:
                    ledcolor = utils_colors.wx_snow(self.__conf, 2)

            if self.__confcache["lights_rainshow"]:
                # Check for Rain
                if airport_conditions in self.wx_rain_ck and (cycle_num in (3, 4)):
                    ledcolor = utils_colors.wx_rain(self.__conf, 1)
                if airport_conditions in self.wx_rain_ck and cycle_num == 5:
                    ledcolor = utils_colors.wx_rain(self.__conf, 2)

            if self.__confcache["lights_frrainshow"]:
                # Check for Freezing Rain
                if airport_conditions in self.wx_frrain_ck and (cycle_num in (3, 5)):
                    ledcolor = utils_colors.wx_frzrain(self.__conf, 1)
                if airport_conditions in self.wx_frrain_ck and cycle_num == 4:
                    ledcolor = utils_colors.wx_frzrain(self.__conf, 2)

            if self.__confcache["lights_dustsandashshow"]:
                # Check for Dust, Sand or Ash
                if airport_conditions in self.wx_dustsandash_ck and (
                    cycle_num in (3, 5)
                ):
                    ledcolor = utils_colors.wx_dust_sand_ash(self.__conf, 1)
                if airport_conditions in self.wx_dustsandash_ck and cycle_num == 4:
                    ledcolor = utils_colors.wx_dust_sand_ash(self.__conf, 2)

            if self.__confcache["lights_fogshow"]:
                # Check for Fog
                if airport_conditions in self.wx_fog_ck and (cycle_num in (3, 5)):
                    ledcolor = utils_colors.wx_fog(self.__conf, 1)
                if airport_conditions in self.wx_fog_ck and cycle_num == 4:
                    ledcolor = utils_colors.wx_fog(self.__conf, 2)

            # If homeport is set to 1 then turn on the appropriate LED using a specific color, This will toggle
            # so that every other time through, the color will display the proper weather, then homeport color(s).
            self.homeport_toggle = not self.homeport_toggle
            if (
                airportled == self.__confcache["lights_homeportpin"]
                and self.__confcache["lights_homeport"]
                and self.homeport_toggle
            ):
                if self.__confcache["lights_homeport_display"] == 1:
                    # FIXME: ast.literal_eval converts a string to a list of tuples..
                    # Should move these colors to be managed with other colors.
                    homeport_colors = ast.literal_eval(
                        self.__conf.get_string("colors", "homeport_colors")
                    )
                    # The length of this array needs to metch the cycle_num length or we'll get errors.
                    # FIXME: Fragile
                    ledcolor = homeport_colors[cycle_num]
                elif self.__confcache["lights_homeport_display"] == 2:
                    # Homeport set based on METAR data
                    pass
                else:
                    # Homeport set to fixed color
                    ledcolor = self.__conf.get_color("colors", "color_homeport")

            # FIXME: Need to fix the way this next section picks colors
            # if airportled == self.__confcache["lights_homeportpin"] and self.__conf.get_bool("lights", "homeport"):
            #    pass
            # elif self.__conf.get_bool("lights", "homeport"):
            #     # FIXME: This doesn't work
            #    # if this is not the home airport, dim out the brightness
            #    dim_color = self.dim(ledcolor, self.__conf.get_int("lights", "dim_value"))
            #    # ledcolor = utils_colors.hexcode(int(dim_color[0]), int(dim_color[1]), int(dim_color[2]))
            # else:  # if home airport feature is disabled, then don't dim out any airports brightness
            #    norm_color = ledcolor
            #    # ledcolor = utils_colors.hexcode(norm_color[0], norm_color[1], norm_color[2])

            led_updated_dict[airportled] = ledcolor
        # Add cycle delay to this loop
        time.sleep(self.__cycle_wait[cycle_num])
        return led_updated_dict

    def colorwipe(self, clocktick):
        """Run a color wipe test."""
        wipe_steps = clocktick % 5
        if wipe_steps == 0:
            new_color = utils_colors.colordict["RED"]
        if wipe_steps == 1:
            new_color = utils_colors.colordict["GREEN"]
        if wipe_steps == 2:
            new_color = utils_colors.colordict["BLUE"]
        if wipe_steps == 3:
            new_color = utils_colors.colordict["MAGENTA"]
        if wipe_steps == 4:
            new_color = utils_colors.colordict["YELLOW"]
        return self.fill(new_color)

    def ledmode_rainbow(self, clocktick):
        """Update LEDs with rainbow pattern."""
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()
        for led_index in self.__active_led_dict.values():
            rainbow_index = (clocktick + led_index) % len(self.__rgb_rainbow)
            rainbow_color = utils_colors.hex_tuple(self.__rgb_rainbow[rainbow_index])
            # print(f"Rainbow loop {led_index} / {rainbow_index} / {rainbow_color} ")
            led_updated_dict[led_index] = rainbow_color
        return led_updated_dict

    # Wipe routines based on Lat/Lons of airports on map.
    # Need to pass name of dictionary with coordinates, either latdict or londict
    # Also need to pass starting value and ending values to led_indexate through. These are floats for Lat/Lon. ie. 36.23
    # Pass Step value to led_indexate through the values provided in start and end. Typically needs to be .01
    # pass the start color and ending color. Pass a wait time or delay, ie. .01
    def wipe(self, dict_name, start, end, step, color1, color2, wait_mult):
        """Wipe based on location."""
        # Need to find duplicate values (lat/lons) from dictionary using flip technique
        flipped = {}
        for key, value in list(
            dict_name.items()
        ):  # create a dict where keys and values are swapped
            if value not in flipped:
                flipped[value] = [key]
            else:
                flipped[value].append(key)

        for i in self.frange(start, end, step):
            key = str(i)

            if key in flipped:  # Grab latitude from dict
                num_elem = len(flipped[key])  # Determine the number of duplicates

                for j in range(
                    num_elem
                ):  # loop through each duplicate to get led number
                    key_id = flipped[key][j]
                    led_index = self.ap_id.index(
                        key_id
                    )  # Assign the pin number to the led to turn on/off

                    self.set_led_color(led_index, color1)
                    self.show()
                    time.sleep(self.__wait * wait_mult)

                    self.set_led_color(led_index, color2)
                    self.show()
                    time.sleep(self.__wait * wait_mult)

    # Circle wipe
    def circlewipe(self, minlon, minlat, maxlon, maxlat, color1, color2):
        """Wipe in a circle."""
        rad_inc = 4
        rad = rad_inc

        sizelat = round(abs(maxlat - minlat), 2)  # height of box
        sizelon = round(abs(maxlon - minlon), 2)  # width of box

        centerlat = round(sizelat / 2 + minlat, 2)  # center y coord of box
        centerlon = round(sizelon / 2 + minlon, 2)  # center x coord of box

        circle_x = centerlon
        circle_y = centerlat

        led_index = int(
            sizelat / rad_inc
        )  # attempt to figure number of led_indexations necessary to cover whole map

        for dummy_j in range(led_index):
            airports = self.__airport_database.get_airport_dict_led()
            for dummy_key, airport_obj in airports.items():
                if not airport_obj.active():
                    continue
                x_posn = float(airport_obj.longitude())
                y_posn = float(airport_obj.latitude())
                led_index = int(airport_obj.get_led_index())

                if (x_posn - circle_x) * (x_posn - circle_x) + (y_posn - circle_y) * (
                    y_posn - circle_y
                ) <= rad * rad:
                    #               print("Inside")
                    color = color1
                else:
                    #               print("Outside")
                    color = color2
                self.set_led_color(led_index, color)
                self.show()
                time.sleep(self.__wait)
            rad = rad + rad_inc

        for dummy_j in range(led_index):
            rad = rad - rad_inc
            airports = self.__airport_database.get_airport_dict_led()
            for dummy_key, airport_obj in airports.items():
                x_posn = float(airport_obj.longitude())
                y_posn = float(airport_obj.latitude())
                led_index = int(airport_obj.get_led_index())

                if (x_posn - circle_x) * (x_posn - circle_x) + (y_posn - circle_y) * (
                    y_posn - circle_y
                ) <= rad * rad:
                    #               print("Inside")
                    color = color1
                else:
                    #               print("Outside")
                    color = color2

                self.set_led_color(led_index, color)
                self.show()
                time.sleep(self.__wait)

    def radarwipe(
        self,
        centerlat,
        centerlon,
        led_index,
        color1,
        color2,
        sweepwidth=175,
        radius=50,
        angleinc=0.05,
    ):
        """Radar sweep."""
        angle = 0

        for dummy_k in range(led_index):
            # Calculate the x_1,y_1 for the end point of our 'sweep' based on
            # the current angle. Then do the same for x_2,y_2
            x_1 = round(radius * math.sin(angle) + centerlon, 2)
            y_1 = round(radius * math.cos(angle) + centerlat, 2)
            x_2 = round(radius * math.sin(angle + sweepwidth) + centerlon, 2)
            y_2 = round(radius * math.cos(angle + sweepwidth) + centerlat, 2)

            airports = self.__airport_database.get_airport_dict_led()
            for dummy_key, airport_obj in airports.items():
                px_1 = float(airport_obj.longitude())  # Lon
                py_1 = float(airport_obj.latitude())  # Lat
                led_index = int(airport_obj.get_led_index())  # LED Pin Num
                #           print (centerlon, centerlat, x_1, y_1, x_2, y_2, px_1, py_1, pin) #debug

                if utils_gfx.is_inside(
                    centerlon, centerlat, x_1, y_1, x_2, y_2, px_1, py_1
                ):
                    #               print('Inside')
                    self.set_led_color(led_index, color1)
                else:
                    self.set_led_color(led_index, color2)
            self.show()
            time.sleep(self.__wait)

            # Increase the angle by angleinc radians
            angle = angle + angleinc

            # If we have done a full sweep, reset the angle to 0
            if angle > 2 * self.PI:
                angle = angle - (2 * self.PI)

    def squarewipe(
        self,
        minlon,
        minlat,
        maxlon,
        maxlat,
        led_index,
        color1,
        color2,
        step=0.5,
        wait_mult=10,
    ):
        """Wipe in a square."""
        declon = minlon
        declat = minlat
        inclon = maxlon
        inclat = maxlat
        centlon = utils_gfx.center(maxlon, minlon)
        centlat = utils_gfx.center(maxlat, minlat)

        for dummy_j in range(led_index):
            for inclon in self.frange(maxlon, centlon, step):
                # declon, declat = Upper Left of box.
                # inclon, inclat = Lower Right of box
                for (
                    dummy_key,
                    airport_obj,
                ) in self.__airport_database.get_airport_dict_led():
                    px_1 = float(airport_obj.longitude())  # Lon
                    py_1 = float(airport_obj.latitude())  # Lat
                    led_index = int(airport_obj.get_led_index())  # LED Pin Num

                    #                print((declon, declat, inclon, inclat, px_1, py_1)) #debug
                    if utils_gfx.findpoint(declon, declat, inclon, inclat, px_1, py_1):
                        #                    print('Inside') #debug
                        color = color1
                    else:
                        #                    print('Not Inside') #debug
                        color = color2

                    self.set_led_color(led_index, color)

                inclat = round(inclat - step, 2)
                declon = round(declon + step, 2)
                declat = round(declat + step, 2)

                self.show()
                time.sleep(self.__wait * wait_mult)

            for inclon in self.frange(centlon, maxlon, step):
                # declon, declat = Upper Left of box.
                # inclon, inclat = Lower Right of box
                for (
                    dummy_key,
                    airport_obj,
                ) in self.__airport_database.get_airport_dict_led():
                    px_1 = float(airport_obj.longitude())  # Lon
                    py_1 = float(airport_obj.latitude())  # Lat
                    led_index = int(airport_obj.get_led_index())  # LED Pin Num

                    #                print((declon, declat, inclon, inclat, px_1, py_1)) #debug
                    if utils_gfx.findpoint(declon, declat, inclon, inclat, px_1, py_1):
                        #                    print('Inside') #debug
                        color = color1
                    else:
                        #                   print('Not Inside') #debug
                        color = color2

                    self.set_led_color(led_index, color)

                inclat = round(inclat + step, 2)
                declon = round(declon - step, 2)
                declat = round(declat - step, 2)

                self.show()
                time.sleep(self.__wait * wait_mult)

    def checkerwipe(
        self,
        minlon,
        minlat,
        maxlon,
        maxlat,
        led_index,
        color1,
        color2,
        cwccw=0,
        wait_mult=100,
    ):
        """Checkerboard wipe."""
        centlon = utils_gfx.center(maxlon, minlon)
        centlat = utils_gfx.center(maxlat, minlat)

        # Example square: lon1, lat1, lon2, lat2  [x_1, y_1, x_2, y_2]  -114.87, 37.07, -109.07, 31.42
        # +-----+-----+
        # |  1  |  2  |
        # |-----+-----|
        # |  3  |  4  |
        # +-----+-----+
        square1 = [minlon, centlat, centlon, maxlat]
        square2 = [centlon, centlat, maxlon, maxlat]
        square3 = [minlon, minlat, centlon, centlat]
        square4 = [centlon, minlat, maxlon, centlat]
        squarelist = [square1, square2, square4, square3]

        if cwccw == 1:  # clockwise = 0, counter-clockwise = 1
            squarelist.reverse()

        for dummy_j in range(led_index):
            for box in squarelist:
                for (
                    dummy_key,
                    airport_obj,
                ) in self.__airport_database.get_airport_dict_led():
                    px_1 = float(airport_obj.longitude())  # Lon
                    py_1 = float(airport_obj.latitude())  # Lat
                    led_index = int(airport_obj.get_led_index())  # LED Pin Num

                    if utils_gfx.findpoint(
                        *box, px_1, py_1
                    ):  # Asterick allows unpacking of list in function call.
                        color = color1
                    else:
                        color = color2

                    self.set_led_color(led_index, color)
                self.show()
                time.sleep(self.__wait * wait_mult)

    # Dim LED's
    def old_dimwipe(self, data, value):
        """Reduce light colors."""
        # Seems like this code just jumps straight to zero
        red = int(data[0] - value)
        red = max(red, 0)
        grn = int(data[1] - value)
        grn = max(grn, 0)
        blu = int(data[2] - value)
        blu = max(blu, 0)
        data = [red, grn, blu]
        return data

    # Morse Code Wipe
    # There are rules to help people distinguish dots from dashes in Morse code.
    #   The length of a dot is 1 time unit.
    #   A dash is 3 time units.
    #   The space between symbols (dots and dashes) of the same letter is 1 time unit.
    #   The space between letters is 3 time units.
    #   The space between words is 7 time units.
    def morse(self, color1, color2, msg, delay):
        """Display Morse message."""
        # define timing of morse display
        dot_leng = self.__wait * 1
        dash_leng = self.__wait * 3
        bet_symb_leng = self.__wait * 1
        bet_let_leng = self.__wait * 3
        bet_word_leng = (
            self.__wait * 4
        )  # logic will add bet_let_leng + bet_word_leng = 7

        for char in self.__conf("rotaryswitch", "morse_msg"):
            letter = []
            if char.upper() in self.morse_code:
                letter = list(self.morse_code[char.upper()])
                debugging.debug(letter)  # debug

                for val in letter:  # display individual dot/dash with proper timing
                    if val == ".":
                        morse_signal = dot_leng
                    else:
                        morse_signal = dash_leng

                    for led_index in range(self.num_pixels()):  # turn LED's on
                        if (
                            str(led_index) in self.__nullpins
                        ):  # exclude NULL and LGND pins from wipe
                            self.set_led_color(led_index, utils_colors.off())
                        else:
                            self.set_led_color(led_index, color1)
                    self.show()
                    time.sleep(morse_signal)  # time on depending on dot or dash

                    for led_index in range(self.num_pixels()):  # turn LED's off
                        if (
                            str(led_index) in self.__nullpins
                        ):  # exclude NULL and LGND pins from wipe
                            self.set_led_color(led_index, utils_colors.off())
                        else:
                            self.set_led_color(led_index, color2)
                    self.show()
                    time.sleep(bet_symb_leng)  # timing between symbols
                time.sleep(bet_let_leng)  # timing between letters

            else:  # if character in morse_msg is not part of the Morse Code Alphabet, substitute a '/'
                if char == " ":
                    time.sleep(bet_word_leng)

                else:
                    char = "/"
                    letter = list(self.morse_code[char.upper()])

                    for val in letter:  # display individual dot/dash with proper timing
                        if val == ".":
                            morse_signal = dot_leng
                        else:
                            morse_signal = dash_leng

                        for led_index in range(self.num_pixels()):  # turn LED's on
                            if (
                                str(led_index) in self.__nullpins
                            ):  # exclude NULL and LGND pins from wipe
                                self.set_led_color(led_index, utils_colors.off())
                            else:
                                self.set_led_color(led_index, color1)
                        self.show()
                        time.sleep(morse_signal)  # time on depending on dot or dash

                        for led_index in range(self.num_pixels()):  # turn LED's off
                            if (
                                str(led_index) in self.__nullpins
                            ):  # exclude NULL and LGND pins from wipe
                                self.set_led_color(led_index, utils_colors.off())
                            else:
                                self.set_led_color(led_index, color2)
                        self.show()
                        time.sleep(bet_symb_leng)  # timing between symbols

                    time.sleep(bet_let_leng)  # timing between letters

        time.sleep(delay)

    def ledmode_rabbit(self, clocktick):
        """Rabbit running through the map."""
        led_updated_dict = {}
        rabbit_posn = clocktick % (len(self.__active_led_dict) + 1)
        rabbit_color_1 = utils_colors.colordict["RED"]
        rabbit_color_2 = utils_colors.colordict["BLUE"]
        rabbit_color_3 = utils_colors.colordict["ORANGE"]

        debugging.info("Rabbit: In the rabbit loop")

        for led_posn, active_led in enumerate(self.__active_led_dict):
            # debugging.info(f"posn:{rabbit_posn}/index:{led_index}")
            led_updated_dict[self.__active_led_dict[led_posn]] = utils_colors.off()
            if led_posn == rabbit_posn - 2:
                led_updated_dict[self.__active_led_dict[led_posn]] = rabbit_color_1
            if led_posn == rabbit_posn - 1:
                led_updated_dict[self.__active_led_dict[led_posn]] = rabbit_color_2
            if led_posn == rabbit_posn:
                led_updated_dict[self.__active_led_dict[led_posn]] = rabbit_color_3
        return led_updated_dict

    def ledmode_shuffle(self, clocktick):
        """Random LED colors."""
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()
        for led_index in self.__active_led_dict.values():
            led_updated_dict[led_index] = utils_colors.randomcolor()
        return led_updated_dict

    def ledmode_fade(self, clocktick):
        """Fade out and in colors."""
        led_updated_dict = {}
        fade_val = clocktick % 255
        fade_col = utils_colors.hexcode(fade_val, 255 - fade_val, fade_val)
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = fade_col
        return led_updated_dict

    def ledmode_heatmap(self, clocktick):
        """Set airport color based on number of visits."""
        airport_list = self.__airport_database.get_airport_dict_led()
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = self.heatmap_color(0)
        for airport_key in airport_list:
            airport_obj = airport_list[airport_key]
            airportled = airport_obj.get_led_index()
            airportheat = airport_obj.heatmap_index()
            led_updated_dict[airportled] = self.heatmap_color(airportheat)
        return led_updated_dict
