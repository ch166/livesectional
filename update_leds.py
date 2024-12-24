# -*- coding: utf-8 -*- "

""" update_leds.py.

# Moved all the airport specific data / metar analysis functions to update_airport.py
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

# import collections
import colorsys
import ast

from rpi_ws281x import Color, PixelStrip, ws

import debugging
import utils
import utils_colors
import utils_gfx
import utils_mos
import utils_coord


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
    MORSE = auto()

    # TODO: how should this work ?
    # Should we have a different mode for each possible hour offset ?
    # or should we have 4 programmable modes ; that get their hour offset from config info ?
    TAF_1 = auto()
    TAF_2 = auto()
    TAF_3 = auto()
    TAF_4 = auto()
    TAF_5 = auto()
    TAF_6 = auto()
    MOS_1 = auto()
    MOS_2 = auto()
    MOS_3 = auto()
    MOS_4 = auto()


class UpdateLEDs:
    """Class to manage LED Strips."""

    PI = 3.141592653
    BIGNUM = 10000000
    DELAYZERO = 0
    DELAYSHORT = 0.1
    DELAYMEDIUM = 0.4
    DELAYLONG = 0.6
    PAUSESHORT = 1

    _app_conf = {}
    _airport_database = {}
    _app_conf_cache = {}

    # Set toggle_sw to an initial value that forces rotary switch to dictate data displayed
    _toggle_sw = -1
    _led_mode = LedMode.METAR

    _active_led_dict = {}

    # List of METAR weather categories to designate weather in area.
    # Many Metars will report multiple conditions, i.e. '-RA BR'.
    # The code pulls the first/main weather reported to compare against the lists below.
    # In this example it uses the '-RA' and ignores the 'BR'.
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

    radar_beam_color = "#00FF00"
    radar_beam_width = 10
    radar_beam_radius = 50
    _radar_map = {}

    # FIXME: Needs to tie to the list of disabled LEDs
    _nullpins = []
    _wait = 1

    # Colors
    _rgb_rainbow = None

    # LED Cycle times - Can change if necessary.
    # Used to create weather designation effects.
    _cycle_wait = [0.9, 0.9, 0.08, 0.1, 0.08, 0.5]

    # LED self.strip configuration:
    _led_pin = 18  # GPIO pin connected to the pixels (18 uses PWM!).

    # LED signal frequency in hertz (usually 800khz)
    _led_freq_hz = 800_000
    _led_dma = 5  # DMA channel to use for generating signal (try 5)

    # True to invert the signal (when using NPN transistor level shift)
    _led_invert = False
    _led_channel = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
    _led_strip = ws.WS2811_STRIP_GRB  # Strip type and color ordering

    # Time Delay
    time_base_delay = 0.2

    # Morse Code Timing
    # Dit: 1 unit
    # Dah: 3 units
    # Intra-character space (the gap between dits and dahs within a character): 1 unit
    # Inter-character space (the gap between the characters of a word): 3 units
    # Word space (the gap between two words): 7 units

    # Two clock_ticks = 1 Morse Code Unit

    morse_dot_symbol = "."
    morse_dot_encoded = ".."  # 1 unit / 2 clock_ticks
    morse_dash_symbol = "-"
    morse_dash_encoded = "------"  # 3 units / 6 clock_ticks
    morse_interval = "*"
    morse_interval_encoded = "**"  # 1 Unit / 2 clock_ticks
    # Letter interval is 3 units ; but will come after a symbol interval ; so adding two more units
    morse_letter_interval_encoded = "****"  # +2 incremental units / 4 clock_ticks
    # Word interval is 7 units; but will come after a symbol and word interval ; adding 4 more units
    morse_word_interval_encoded = "********"  # +4 units / 8 clock_ticks

    morse_signal_encoded = "...... ------------------ ......"

    morse_color_dot = "#007000"
    morse_color_dash = "#000070"

    def __init__(self, conf, airport_database):
        """Initialize LED Strip."""
        self._app_conf = conf
        self._airport_database = airport_database

        # Populate the config cache data
        self.update_confcache()

        # Specific Variables to default data to display if Rotary Switch is not installed.
        # hour_to_display # Offset in HOURS to choose which TAF/MOS to display
        self.hour_to_display = self._app_conf.get_int("rotaryswitch", "time_sw0")
        # metar_taf_mos
        # 0 = Display TAF, 1 = Display METAR, 2 = Display MOS, 3 = Heat Map (Heat map not controlled by rotary switch)
        self._metar_taf_mos = self._app_conf.get_int("rotaryswitch", "data_sw0")

        self.nightsleep = self._app_conf.get_bool("schedule", "usetimer")

        self._offtime = datetime.time(
            self._app_conf.get_int("schedule", "offhour"),
            self._app_conf.get_int("schedule", "offminutes"),
            0,
            0,
        )

        self._ontime = datetime.time(
            self._app_conf.get_int("schedule", "onhour"),
            self._app_conf.get_int("schedule", "onminutes"),
            0,
            0,
        )

        # Set number of MINUTES to turn map on temporarily during sleep mode
        self._tempsleepon = self._app_conf.get_int("schedule", "tempsleepon")

        # Number of LED pixels. Change this value to match the number of LED's being used on map
        self._led_count = self._app_conf.get_int("default", "led_count")

        # 1 = RGB color codes. 0 = GRB color codes.
        # Populate color codes below with normal RGB codes and script will change if necessary
        self._rgb_grb = self._app_conf.get_int("lights", "rgb_grb")

        self.homeport_toggle = False
        self.homeport_colors = ast.literal_eval(
            self._app_conf.get_string("colors", "homeport_colors")
        )

        # Blanking during refresh of the LED string between FAA updates.
        # Removing because it's not currently used
        # Future code could have the wx_update loop send a signal here to update_leds to trigger a refresh.
        # self.blank_during_refresh = False

        # starting brightness. It will be changed below.
        self._led_brightness = self._app_conf.get_int("lights", "bright_value")

        # MOS Data Settings
        self._mos_filepath = self._app_conf.get_string("filenames", "mos_filepath")

        # Create an instance of NeoPixel
        self.strip = PixelStrip(
            self._led_count,
            self._led_pin,
            self._led_freq_hz,
            self._led_dma,
            self._led_invert,
            self._led_brightness,
            self._led_channel,
            self._led_strip,
        )
        self.strip.begin()
        self.turnoff()
        self.init_rainbow()

        self.morse_color_dot = self._app_conf.get_string("morse", "color_dot")
        self.morse_color_dash = self._app_conf.get_string("morse", "color_dash")

        self.encode_morse_string()
        debugging.info("LED Strip INIT complete")

    # Functions
    def init_rainbow(self):
        """Define set of colors to create the Rainbow effect."""
        rainbow_index = 30
        hsv_tuples = [
            (x * 1.0 / rainbow_index, 0.85, 0.5) for x in range(rainbow_index)
        ]
        rgb_tuples = map(lambda x: colorsys.hsv_to_rgb(*x), hsv_tuples)
        rgb_list = list(rgb_tuples)
        for i, rgb_col in enumerate(rgb_list):
            (col_r, col_g, col_b) = rgb_col
            rgb_list[i] = (col_r * 255, col_g * 255, col_b * 255)
        self._rgb_rainbow = rgb_list
        debugging.info(f"Rainbow List - {self._rgb_rainbow}")

    def update_confcache(self):
        """Update class local variables to cache conf data."""
        # This is a performance improvement cache of conf data
        # TODO: Need to make sure we update this when the config changes
        self._app_conf_cache["vfr_color"] = utils_colors.cat_vfr(self._app_conf)
        self._app_conf_cache["mvfr_color"] = utils_colors.cat_mvfr(self._app_conf)
        self._app_conf_cache["ifr_color"] = utils_colors.cat_ifr(self._app_conf)
        self._app_conf_cache["lifr_color"] = utils_colors.cat_lifr(self._app_conf)
        self._app_conf_cache["unkn_color"] = utils_colors.wx_noweather(self._app_conf)
        self._app_conf_cache["lights_highwindblink"] = self._app_conf.get_bool(
            "activelights", "high_wind_blink"
        )
        self._app_conf_cache["metar_maxwindspeed"] = self._app_conf.get_int(
            "activelights", "high_wind_limit"
        )
        self._app_conf_cache["lights_lghtnflash"] = self._app_conf.get_bool(
            "lights", "lghtnflash"
        )
        self._app_conf_cache["lights_snowshow"] = self._app_conf.get_bool(
            "lights", "snowshow"
        )
        self._app_conf_cache["lights_rainshow"] = self._app_conf.get_bool(
            "lights", "rainshow"
        )
        self._app_conf_cache["lights_frrainshow"] = self._app_conf.get_bool(
            "lights", "frrainshow"
        )
        self._app_conf_cache["lights_dustsandashshow"] = self._app_conf.get_bool(
            "lights", "dustsandashshow"
        )
        self._app_conf_cache["lights_fogshow"] = self._app_conf.get_bool(
            "lights", "fogshow"
        )
        self._app_conf_cache["lights_homeportpin"] = self._app_conf.get_int(
            "lights", "homeport_pin"
        )
        self._app_conf_cache["lights_homeport"] = self._app_conf.get_int(
            "lights", "homeport"
        )
        self._app_conf_cache["lights_homeport_display"] = self._app_conf.get_int(
            "lights", "homeport_display"
        )
        self._app_conf_cache["rev_rgb_grb"] = self._app_conf.get_string(
            "lights", "rev_rgb_grb"
        )

    def ledmode(self):
        """Return current LED Mode."""
        return self._led_mode

    def set_ledmode(self, new_mode):
        """Update active LED Mode."""
        self._led_mode = new_mode

    def set_led_color(self, led_id, hexcolor):
        """Convert color from HEX to RGB or GRB and apply to LED String."""
        if isinstance(led_id, str):
            debugging.info(f"led_id : Unexpected {led_id} as str")
            return
        # Input should be a HEX color; and then we should convert to the appropriate signaling
        # for the individual LED - this should allow us to support LEDs that use RGB as well as GRB color signaling
        if str(led_id) in self._nullpins:
            rgb_color = utils_colors.off()
        else:
            rgb_color = utils_colors.rgb_color(hexcolor)

        color_ord = self.rgb_to_pixel(led_id, rgb_color, self._rgb_grb)
        pixel_data = Color(color_ord[0], color_ord[1], color_ord[2])

        self.strip.setPixelColor(led_id, pixel_data)

    def update_active_led_list(self):
        """Update Active LED list."""
        active_led_dict = {}
        for index in range(self._led_count):
            active_led_dict[index] = None
        pos = 0
        airports = self._airport_database.get_airport_dict_led()
        if airports is None:
            return
        for icao, airport_obj in airports.items():
            if not airport_obj.active():
                debugging.debug(f"Airport Not Active {icao} : Not updating LED list")
                continue
            led_index = airport_obj.get_led_index()
            active_led_dict[pos] = led_index
            pos = pos + 1
        self._active_led_dict = active_led_dict

    def show(self):
        """Update LED strip to display current colors."""
        self.strip.show()

    def turnoff(self):
        """Set color to 0,0,0  - turning off LED."""
        for i in range(self.num_pixels()):
            self.set_led_color(i, utils_colors.off())
        self.show()

    def fill(self, color):
        """Return led_updated_dict containing single color only"""
        debugging.info(f"Fill: In the fill loop for {color}")
        led_updated_dict = {}
        for led_key in self._active_led_dict.keys():
            if self._active_led_dict[led_key] is not None:
                led_index = self._active_led_dict[led_key]
                led_updated_dict[led_index] = color
        return led_updated_dict

    def num_pixels(self) -> int:
        """Return number of Pixels defined."""
        return self._led_count

    def get_brightness_level(self) -> int:
        """Get Light Percentage Level."""
        return round(self._led_brightness / 255 * 100)

    def set_brightness(self, lux):
        """Update saved brightness value."""
        self._led_brightness = round(lux)

    def dim(self, color_data, value):
        """DIM LED.

        # TODO: Move this to utils_color.py
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
        # If necessary, populate the list rev_rgb_grb with pins of LED's that use the opposite color scheme.
        # list of pins that need to use the reverse of the normal order setting.
        # This accommodates the use of both models of LED strings on one map.
        if str(pin) in self._app_conf_cache["rev_rgb_grb"]:
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

    # For Heat Map. Based on visits, assign color.
    # Using a 0 to 100 scale where 0 is never visted and 100 is home airport.
    # Can choose to display binary colors with homeap.
    def heatmap_color(self, visits):
        """Color codes assigned with heatmap."""
        if visits == "0":
            color = utils_colors.colordict["GOLD"]
        elif visits == "100":
            if self._app_conf.get_bool(
                "rotaryswitch", "fade_yesno"
            ) and self._app_conf.get_bool("rotaryswitch", "bin_grad"):
                color = utils_colors.black()
            elif not self._app_conf.get_bool("rotaryswitch", "use_homeap"):
                color = utils_colors.colordict["RED"]
            else:
                color = self._app_conf.get_string("colors", "color_vfr")
        elif "1" <= visits <= "50":  # Working
            if self._app_conf.get_bool("rotaryswitch", "bin_grad"):
                grn = 0
                blu = 0
                red = int(int(visits) * 5.1)
                color = utils_colors.rgb2hex((red, grn, blu))
            else:
                color = utils_colors.colordict["RED"]
        elif "51" <= visits <= "99":  # Working
            if self._app_conf.get_bool("rotaryswitch", "bin_grad"):
                red = 255
                grn = 0
                blu = 255 - int((int(visits) - 50) * 5.1)
                color = utils_colors.rgb2hex((red, grn, blu))
            else:
                color = utils_colors.rgb2hex((255, 0, 0))
        else:
            color = utils_colors.black()
        return color

    def check_for_sleep_time(self, clock_tick, sleeping, default_led_mode):
        debugging.info(f"Checking if it's time for sleep mode: {clock_tick}")
        datetime_now = utils.current_time(self._app_conf)
        time_now = datetime_now.time()
        if utils.time_in_range(self._offtime, self._ontime, time_now):
            if not sleeping:
                debugging.info("Enabling sleeping mode...")
                self._led_mode = LedMode.SLEEP
                sleeping = True
            else:
                # It's night time; we're already sleeping. Take a break.
                debugging.info(f"Sleeping .. {clock_tick}")
        elif sleeping:
            debugging.info(f"Disabling sleeping mode... {clock_tick} ")
            self._led_mode = default_led_mode
            sleeping = False
        return sleeping

    def update_loop(self):
        """LED Display Loop - supporting multiple functions."""
        sleeping = False
        default_led_mode = LedMode.METAR
        self.update_active_led_list()
        self.turnoff()
        # Tick values are used to provide a ticking clock interval that can be used by functions that want to have
        # time or interval based sequences without blocking to complete the entire sequence in one go
        rainbowtick = 0
        clock_tick = 0

        self.ledmode_radar_setup()

        while True:
            # Going to use an index counter as a pseudo clock tick for
            # each LED module. It's going to continually increase through
            # each pass - and it's max value is a limiter on the number of LEDs
            # If each pass through this loop touches one LED ; then we need enough
            # clock cycles to cover every LED.
            clock_tick = (clock_tick + 1) % self.BIGNUM

            if (clock_tick % 1000) == 0:
                # Execute things that need to be done occasionally
                # Make sure the active LED list is updated
                self.update_active_led_list()
                if self.nightsleep:
                    sleeping = self.check_for_sleep_time(
                        clock_tick, sleeping, default_led_mode
                    )

            if self._led_mode in (LedMode.OFF, LedMode.SLEEP):
                self.turnoff()
                time.sleep(self.PAUSESHORT)
                continue
            if self._led_mode == LedMode.METAR:
                led_color_dict = self.ledmode_metar(clock_tick)
                if (clock_tick % 100) == 0:
                    debugging.info(f"ledmode_metar: {led_color_dict}")
                self.update_ledstring(led_color_dict)
                continue
            if self._led_mode == LedMode.TEST:
                # self.ledmode_test(clock_tick)
                led_color_dict = self.colorwipe(clock_tick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.RAINBOW:
                led_color_dict = self.ledmode_rainbow(rainbowtick)
                self.update_ledstring(led_color_dict)
                rainbowtick += 5
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.FADE:
                led_color_dict = self.ledmode_fade(clock_tick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYSHORT)
                continue
            if self._led_mode == LedMode.RABBIT:
                led_color_dict = self.ledmode_rabbit(clock_tick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYSHORT)
                continue
            if self._led_mode == LedMode.SHUFFLE:
                led_color_dict = self.ledmode_shuffle(clock_tick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.MORSE:
                led_color_dict = self.ledmode_morse(clock_tick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYSHORT)
                continue
            if self._led_mode == LedMode.TAF_1:
                led_color_dict = self.ledmode_taf(clock_tick, 1)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.TAF_2:
                led_color_dict = self.ledmode_taf(clock_tick, 2)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.TAF_3:
                led_color_dict = self.ledmode_taf(clock_tick, 3)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.TAF_4:
                led_color_dict = self.ledmode_taf(clock_tick, 4)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.MOS_1:
                led_color_dict = self.ledmode_mos(clock_tick, 1)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.MOS_2:
                led_color_dict = self.ledmode_mos(clock_tick, 2)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.MOS_3:
                led_color_dict = self.ledmode_mos(clock_tick, 3)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.MOS_4:
                led_color_dict = self.ledmode_mos(clock_tick, 4)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            #
            # Rewrite complete as far as here
            #
            if self._led_mode == LedMode.RADARWIPE:
                led_color_dict = self.ledmode_radar(clock_tick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYSHORT)
                continue
            if self._led_mode == LedMode.SQUAREWIPE:
                led_color_dict = self.ledmode_rabbit(clock_tick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.WHEELWIPE:
                led_color_dict = self.ledmode_rabbit(clock_tick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.CIRCLEWIPE:
                led_color_dict = self.ledmode_rabbit(clock_tick)
                self.update_ledstring(led_color_dict)
                time.sleep(self.DELAYMEDIUM)
                continue
            if self._led_mode == LedMode.HEATMAP:
                led_color_dict = self.ledmode_heatmap(clock_tick)
                self.update_ledstring(led_color_dict)
                continue

    def update_ledstring(self, led_color_dict):
        """Iterate across all the LEDs and set the color appropriately."""
        for ledindex, led_color in led_color_dict.items():
            self.set_led_color(ledindex, led_color)
        self.strip.setBrightness(self._led_brightness)
        self.show()

    def airport_taf_flightcategory(self, airport, hr_offset):
        """Get Flight Category for TAF data"""
        airport_taf_dict = self._airport_database.get_airport_taf(airport)
        if airport_taf_dict is None:
            return None
        debugging.info(f"{airport}:taf:{airport_taf_dict}")
        airport_taf_future = self._airport_database.airport_taf_future(
            airport, hr_offset
        )
        if airport_taf_future is None:
            return None
        debugging.info(f"{airport}:forecast:{airport_taf_future}")
        return airport_taf_future["flightcategory"]

    def airport_mos_flightcategory(self, airport, hr_offset):
        """Get Flight Category for MOS data"""
        airport_mos_dict = self._airport_database.get_airport_mos(airport)
        if airport_mos_dict is None:
            debugging.debug(f"airport_mos_flightcategory: airport_mos_dict is NONE")
            return None
        airport_mos_future = utils_mos.get_mos_weather(
            self._airport_database.get_airport_mos(airport.upper()),
            self._app_conf,
            hr_offset,
        )
        if airport_mos_future is None:
            debugging.info(f"airport_mos_future: airport_mos_future is NONE")
            return None
        # debugging.info(f"{airport}:forecast:{airport_mos_future}")
        return airport_mos_future

    def ledmode_test(self, clock_tick):
        """Run self test sequences."""
        return self.colorwipe(clock_tick)

    def ledmode_circlewipe(self, clock_tick):
        """Wipe circle around the geographically center most airport"""

    def legend_color(self, airport_wxsrc, cycle_num):
        """Work out the color for the legend LEDs."""
        ledcolor = utils_colors.off()
        if airport_wxsrc == "vfr":
            ledcolor = self._app_conf_cache["vfr_color"]
        if airport_wxsrc == "mvfr":
            ledcolor = self._app_conf_cache["mvfr_color"]
        if airport_wxsrc == "ifr":
            ledcolor = self._app_conf_cache["ifr_color"]
        if airport_wxsrc == "lifr":
            ledcolor = self._app_conf_cache["lifr_color"]
        if airport_wxsrc == "unkn":
            ledcolor = self._app_conf_cache["unkn_color"]
        if airport_wxsrc == "hiwind":
            if cycle_num in [3, 4, 5]:
                ledcolor = utils_colors.off()
            else:
                ledcolor = self._app_conf_cache["ifr_color"]
        if airport_wxsrc == "lghtn":
            if cycle_num in [2, 4]:
                ledcolor = utils_colors.wx_lightning(self._app_conf)
            else:
                ledcolor = self._app_conf_cache["mvfr_color"]
        if airport_wxsrc == "snow":
            if cycle_num in [3, 5]:  # Check for Snow
                ledcolor = utils_colors.wx_snow(self._app_conf, 1)
            elif cycle_num == 4:
                ledcolor = utils_colors.wx_snow(self._app_conf, 2)
            else:
                ledcolor = self._app_conf_cache["lifr_color"]
        if airport_wxsrc == "rain":
            if cycle_num in [3, 5]:  # Check for Rain
                ledcolor = utils_colors.wx_rain(self._app_conf, 1)
            elif cycle_num == 4:
                ledcolor = utils_colors.wx_rain(self._app_conf, 2)
            else:
                ledcolor = self._app_conf_cache["vfr_color"]
        if airport_wxsrc == "frrain":
            if cycle_num in [3, 5]:  # Check for Freezing Rain
                ledcolor = utils_colors.wx_frzrain(self._app_conf, 1)
            elif cycle_num == 4:
                ledcolor = utils_colors.wx_frzrain(self._app_conf, 2)
            else:
                ledcolor = self._app_conf_cache["mvfr_color"]
        if airport_wxsrc == "dust":
            if cycle_num in [3, 5]:  # Check for Dust, Sand or Ash
                ledcolor = utils_colors.wx_dust_sand_ash(self._app_conf, 1)
            elif cycle_num == 4:
                ledcolor = utils_colors.wx_dust_sand_ash(self._app_conf, 2)
            else:
                ledcolor = self._app_conf_cache["vfr_color"]
        if airport_wxsrc == "fog":
            if cycle_num in [3, 5]:  # Check for Fog
                ledcolor = utils_colors.wx_fog(self._app_conf, 1)
            elif cycle_num == 4:
                ledcolor = utils_colors.wx_fog(self._app_conf, 2)
            elif cycle_num in [0, 1, 2]:
                ledcolor = self._app_conf_cache["ifr_color"]
        return ledcolor

    def ledmode_metar(self, clock_tick):
        """Generate LED Color set for Airports."""
        airport_list = self._airport_database.get_airport_dict_led()
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()

        cycle_num = clock_tick % len(self._cycle_wait)

        for airport_key, airport_obj in airport_list.items():
            airportcode = airport_obj.icao_code()
            airport_led = airport_obj.get_led_index()
            airport_wxsrc = airport_obj.wxsrc()
            if not airportcode:
                continue
            if airportcode.startswith("null"):
                led_updated_dict[airport_led] = utils_colors.off()
                continue
            if airportcode.startswith("lgnd"):
                ledcolor = self.legend_color(airport_wxsrc, cycle_num)
                led_updated_dict[airport_led] = ledcolor
                continue

            # Initialize color
            ledcolor = utils_colors.off()
            # Pull the next flight category from dictionary.
            flightcategory = airport_obj.flightcategory()
            if not flightcategory:
                flightcategory = "UNKN"
            # Pull the winds from the dictionary.
            airportwinds = airport_obj.wx_windspeed()
            if not airportwinds:
                airportwinds = -1
            airport_conditions = airport_obj.wxconditions()
            debugging.debug(
                f"{airportcode}:{flightcategory}:{airportwinds}:cycle=={cycle_num}"
            )

            # Start of weather display code for each airport in the "airports" file
            # Check flight category and set the appropriate color to display
            if flightcategory == "VFR":  # Visual Flight Rules
                ledcolor = self._app_conf_cache["vfr_color"]
            elif flightcategory == "MVFR":  # Marginal Visual Flight Rules
                ledcolor = self._app_conf_cache["mvfr_color"]
            elif flightcategory == "IFR":  # Instrument Flight Rules
                ledcolor = self._app_conf_cache["ifr_color"]
            elif flightcategory == "LIFR":  # Low Instrument Flight Rules
                ledcolor = self._app_conf_cache["lifr_color"]
            elif flightcategory == "UNKN":
                ledcolor = self._app_conf_cache["unkn_color"]

            # Check winds and set the 2nd half of cycles to black to create blink effect
            if self._app_conf_cache["lights_highwindblink"]:
                # bypass if "hiwindblink" is set to 0
                if int(airportwinds) >= self._app_conf_cache["metar_maxwindspeed"] and (
                    cycle_num in [3, 4, 5]
                ):
                    ledcolor = utils_colors.off()
                    debugging.debug(f"HIGH WINDS {airportcode} : {airportwinds} kts")

            if self._app_conf_cache["lights_lghtnflash"]:
                # Check for Thunderstorms
                if airport_conditions in self.wx_lghtn_ck and (cycle_num in [2, 4]):
                    ledcolor = utils_colors.wx_lightning(self._app_conf)

            if self._app_conf_cache["lights_snowshow"]:
                # Check for Snow
                if airport_conditions in self.wx_snow_ck and (cycle_num in [3, 5]):
                    ledcolor = utils_colors.wx_snow(self._app_conf, 1)
                if airport_conditions in self.wx_snow_ck and cycle_num == 4:
                    ledcolor = utils_colors.wx_snow(self._app_conf, 2)

            if self._app_conf_cache["lights_rainshow"]:
                # Check for Rain
                if airport_conditions in self.wx_rain_ck and (cycle_num in [3, 4]):
                    ledcolor = utils_colors.wx_rain(self._app_conf, 1)
                if airport_conditions in self.wx_rain_ck and cycle_num == 5:
                    ledcolor = utils_colors.wx_rain(self._app_conf, 2)

            if self._app_conf_cache["lights_frrainshow"]:
                # Check for Freezing Rain
                if airport_conditions in self.wx_frrain_ck and (cycle_num in [3, 5]):
                    ledcolor = utils_colors.wx_frzrain(self._app_conf, 1)
                if airport_conditions in self.wx_frrain_ck and cycle_num == 4:
                    ledcolor = utils_colors.wx_frzrain(self._app_conf, 2)

            if self._app_conf_cache["lights_dustsandashshow"]:
                # Check for Dust, Sand or Ash
                if airport_conditions in self.wx_dustsandash_ck and (
                    cycle_num in [3, 5]
                ):
                    ledcolor = utils_colors.wx_dust_sand_ash(self._app_conf, 1)
                if airport_conditions in self.wx_dustsandash_ck and cycle_num == 4:
                    ledcolor = utils_colors.wx_dust_sand_ash(self._app_conf, 2)

            if self._app_conf_cache["lights_fogshow"]:
                # Check for Fog
                if airport_conditions in self.wx_fog_ck and (cycle_num in [3, 5]):
                    ledcolor = utils_colors.wx_fog(self._app_conf, 1)
                if airport_conditions in self.wx_fog_ck and cycle_num == 4:
                    ledcolor = utils_colors.wx_fog(self._app_conf, 2)

            # If homeport is set to 1 then turn on the appropriate LED using a specific color, This will toggle
            # so that every other time through, the color will display the proper weather, then homeport color(s).
            self.homeport_toggle = not self.homeport_toggle
            if (
                airport_led == self._app_conf_cache["lights_homeportpin"]
                and self._app_conf_cache["lights_homeport"]
                and self.homeport_toggle
            ):
                if self._app_conf_cache["lights_homeport_display"] == 1:
                    # FIXME: ast.literal_eval converts a string to a list of tuples..
                    # Should move these colors to be managed with other colors.
                    homeport_colors = ast.literal_eval(
                        self._app_conf.get_string("colors", "homeport_colors")
                    )
                    # The length of this array needs to metch the cycle_num length or we'll get errors.
                    # FIXME: Fragile
                    ledcolor = homeport_colors[cycle_num]
                elif self._app_conf_cache["lights_homeport_display"] == 2:
                    # Homeport set based on METAR data
                    pass
                else:
                    # Homeport set to fixed color
                    ledcolor = self._app_conf.get_color("colors", "color_homeport")

            # FIXME: Need to fix the way this next section picks colors
            # if airportled == self._app_conf_cache["lights_homeportpin"] and self._app_conf.get_bool("lights", "homeport"):
            #    pass
            # elif self._app_conf.get_bool("lights", "homeport"):
            #     # FIXME: This doesn't work
            #    # if this is not the home airport, dim out the brightness
            #    dim_color = self.dim(ledcolor, self._app_conf.get_int("lights", "dim_value"))
            #    # ledcolor = utils_colors.hexcode(int(dim_color[0]), int(dim_color[1]), int(dim_color[2]))
            # else:  # if home airport feature is disabled, then don't dim out any airports brightness
            #    norm_color = ledcolor
            #    # ledcolor = utils_colors.hexcode(norm_color[0], norm_color[1], norm_color[2])

            if (clock_tick % 150) == 0:
                debugging.info(
                    f"ledmode_metar: {airportcode}:{flightcategory}:{airportwinds}:{airport_led}:{ledcolor}"
                )
            led_updated_dict[airport_led] = ledcolor
        # Add cycle delay to this loop
        time.sleep(self._cycle_wait[cycle_num])
        return led_updated_dict

    def colorwipe(self, clock_tick):
        """Run a color wipe test."""
        new_color = utils_colors.colordict["BLACK"]
        wipe_steps = clock_tick % 5
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

    def ledmode_rainbow(self, clock_tick):
        """Update LEDs with rainbow pattern."""
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()
        for led_key in self._active_led_dict.keys():
            if self._active_led_dict[led_key] is not None:
                led_index = self._active_led_dict[led_key]
                rainbow_index = (clock_tick + led_index) % len(self._rgb_rainbow)
                rainbow_color = utils_colors.hex_tuple(self._rgb_rainbow[rainbow_index])
                # print(f"Rainbow loop {_led_index} / {rainbow_index} / {rainbow_color} ")
                led_updated_dict[led_index] = rainbow_color
        return led_updated_dict

    def ledmode_morse(self, clock_tick):
        """Update LEDs with morse pattern."""
        led_updated_dict = {}
        morse_pos = clock_tick % len(self.morse_signal_encoded)
        led_color = utils_colors.black()
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()
        if self.morse_signal_encoded[morse_pos] == self.morse_dot_symbol:
            led_color = self.morse_color_dot
        elif self.morse_signal_encoded[morse_pos] == self.morse_dash_symbol:
            led_color = self.morse_color_dash
        elif self.morse_signal_encoded[morse_pos] == self.morse_interval:
            led_color = utils_colors.black()

        debugging.info(f"morse:{led_color}")

        for led_key in self._active_led_dict.keys():
            if self._active_led_dict[led_key] is not None:
                led_index = self._active_led_dict[led_key]
                led_updated_dict[led_index] = led_color
        return led_updated_dict

    def ledmode_taf(self, clock_tick, hr_offset):
        """Update LEDs based on TAF data."""
        airport_list = self._airport_database.get_airport_dict_led()
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()

        cycle_num = clock_tick % len(self._cycle_wait)

        for airport_key, airport_obj in airport_list.items():
            airportcode = airport_obj.icao_code()
            airportled = airport_obj.get_led_index()
            airportwxsrc = airport_obj.wxsrc()
            if not airportcode:
                continue
            if airportcode.startswith("null"):
                led_updated_dict[airportled] = utils_colors.off()
                continue
            if airportcode.startswith("lgnd"):
                ledcolor = self.legend_color(airportwxsrc, cycle_num)
                led_updated_dict[airportled] = ledcolor
                continue

            # Initialize color
            ledcolor = utils_colors.off()
            # Pull the next flight category from dictionary.
            flightcategory = self.airport_taf_flightcategory(airportcode, hr_offset)
            if not flightcategory:
                flightcategory = "UNKN"

            # Start of weather display code for each airport in the "airports" file
            # Check flight category and set the appropriate color to display
            if flightcategory == "VFR":  # Visual Flight Rules
                ledcolor = self._app_conf_cache["vfr_color"]
            elif flightcategory == "MVFR":  # Marginal Visual Flight Rules
                ledcolor = self._app_conf_cache["mvfr_color"]
            elif flightcategory == "IFR":  # Instrument Flight Rules
                ledcolor = self._app_conf_cache["ifr_color"]
            elif flightcategory == "LIFR":  # Low Instrument Flight Rules
                ledcolor = self._app_conf_cache["lifr_color"]
            elif flightcategory == "UNKN":
                ledcolor = self._app_conf_cache["unkn_color"]

            if (clock_tick % 150) == 0:
                debugging.debug(
                    f"ledmode_taf: {airportcode}:{flightcategory}:{airportled}:{ledcolor}"
                )
            led_updated_dict[airportled] = ledcolor
        return led_updated_dict

    def ledmode_mos(self, clock_tick, hr_offset):
        """Update LEDs based on MOS data."""
        airport_list = self._airport_database.get_airport_dict_led()
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()

        cycle_num = clock_tick % len(self._cycle_wait)

        for airport_key, airport_obj in airport_list.items():
            airportcode = airport_obj.icao_code()
            airportled = airport_obj.get_led_index()
            airportwxsrc = airport_obj.wxsrc()
            if not airportcode:
                continue
            if airportcode.startswith("null"):
                led_updated_dict[airportled] = utils_colors.off()
                continue
            if airportcode.startswith("lgnd"):
                ledcolor = self.legend_color(airportwxsrc, cycle_num)
                led_updated_dict[airportled] = ledcolor
                continue

            # Initialize color
            ledcolor = utils_colors.off()
            # Pull the next flight category from dictionary.
            flightcategory = self.airport_mos_flightcategory(airportcode, hr_offset)
            if not flightcategory:
                flightcategory = "UNKN"

            # Start of weather display code for each airport in the "airports" file
            # Check flight category and set the appropriate color to display
            if flightcategory == "VFR":  # Visual Flight Rules
                ledcolor = self._app_conf_cache["vfr_color"]
            elif flightcategory == "MVFR":  # Marginal Visual Flight Rules
                ledcolor = self._app_conf_cache["mvfr_color"]
            elif flightcategory == "IFR":  # Instrument Flight Rules
                ledcolor = self._app_conf_cache["ifr_color"]
            elif flightcategory == "LIFR":  # Low Instrument Flight Rules
                ledcolor = self._app_conf_cache["lifr_color"]
            elif flightcategory == "UNKN":
                ledcolor = self._app_conf_cache["unkn_color"]

            if (clock_tick % 150) == 0:
                debugging.info(
                    f"ledmode_mos: {airportcode}:{flightcategory}:{airportled}:{ledcolor}"
                )
            led_updated_dict[airportled] = ledcolor
        return led_updated_dict

    # Wipe routines based on Lat/Lons of airports on map.
    # Need to pass name of dictionary with coordinates, either latdict or londict
    # Also need to pass starting value and ending values to led_indexate through. These are floats for Lat/Lon. i.e. 36.23

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
                    )  # Assign the pin to the led to turn on/off

                    self.set_led_color(led_index, color1)
                    self.show()
                    time.sleep(self.time_base_delay * wait_mult)

                    self.set_led_color(led_index, color2)
                    self.show()
                    time.sleep(self.time_base_delay * wait_mult)

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
            airports = self._airport_database.get_airport_dict_led()
            for dummy_key, airport_obj in airports.items():
                if not airport_obj.active():
                    continue
                x_pos = float(airport_obj.longitude())
                y_pos = float(airport_obj.latitude())
                led_index = int(airport_obj.get_led_index())

                if (x_pos - circle_x) * (x_pos - circle_x) + (y_pos - circle_y) * (
                    y_pos - circle_y
                ) <= rad * rad:
                    #               print("Inside")
                    color = color1
                else:
                    #               print("Outside")
                    color = color2
                self.set_led_color(led_index, color)
                self.show()
                time.sleep(self.time_base_delay)
            rad = rad + rad_inc

        for dummy_j in range(led_index):
            rad = rad - rad_inc
            airports = self._airport_database.get_airport_dict_led()
            for dummy_key, airport_obj in airports.items():
                x_pos = float(airport_obj.longitude())
                y_pos = float(airport_obj.latitude())
                led_index = int(airport_obj.get_led_index())

                if (x_pos - circle_x) * (x_pos - circle_x) + (y_pos - circle_y) * (
                    y_pos - circle_y
                ) <= rad * rad:
                    #               print("Inside")
                    color = color1
                else:
                    #               print("Outside")
                    color = color2

                self.set_led_color(led_index, color)
                self.show()
                time.sleep(self.time_base_delay)

    def ledmode_radar_setup(self):
        """Set up data structures for ledmode_radar"""
        # For all these calculations ; longitude is X ; latitude is Y
        self.radar_beam_color = "#00FF00"
        self.radar_beam_width = 5

        radar_map = {}
        max_lon, min_lon, max_lat, min_lat = utils_coord.airport_boundary_calc(
            self._airport_database
        )

        debugging.info(
            f"RADAR: max_lon: {max_lon}, min_lon: {min_lon}, max_lat: {max_lat}, min_lat: {min_lat}, "
        )
        if (
            (max_lat is None)
            or (min_lat is None)
            or (max_lon is None)
            or (min_lon is None)
        ):
            debugging.info("RADAR: Setup incomplete ; no lon/lat data")
            return
        width = abs(max_lon - min_lon)
        height = abs(max_lat - min_lat)
        center_lon = (max_lon + min_lon) / 2
        center_lat = (max_lat + min_lat) / 2
        self.radar_beam_radius = (
            max(height, width) * 1.1
        )  # Radius of 110% of the biggest boundary size surrounding the airports
        debugging.info(
            f"RADAR: center_lon: {center_lon}, center_lat: {center_lat}, self.radar_beam_radius: {self.radar_beam_radius}"
        )
        area_triangles = utils_coord.circle_triangles(
            self.radar_beam_radius, self.radar_beam_width, center_lon, center_lat
        )
        debugging.info(f"RADAR: {area_triangles}")
        for triangle in area_triangles:
            for (
                airport_key,
                airport_obj,
            ) in self._airport_database.get_airport_dict_led().items():
                if airport_obj.valid_coordinates():
                    airport_led = airport_obj.get_led_index()
                    airport_lat = airport_obj.latitude()
                    airport_lon = airport_obj.longitude()
                    if utils_coord.is_inside_triangle(
                        (airport_lon, airport_lat),
                        triangle[1],
                        triangle[2],
                        triangle[3],
                    ):
                        deg_pos_start = triangle[0][0]
                        deg_pos_end = triangle[0][1]
                        debugging.info(
                            f"RADAR: Match airport {airport_key}:  inside {deg_pos_start}/{deg_pos_end}: led {airport_led}"
                        )
                        for deg_pos in range(deg_pos_start, deg_pos_end):
                            if deg_pos in radar_map:
                                radar_map[deg_pos] = radar_map[deg_pos] + (airport_led,)
                            else:
                                radar_map[deg_pos] = (airport_led,)

        debugging.info(f"RADAR: radar_map: {radar_map}")
        self._radar_map = radar_map

    def ledmode_radar(self, clock_tick):
        """Provide anticlockwise radar sweep style LED updates."""
        # There are 360 degrees in the sweep; going to use clock_tick as the seed for the active angle

        if len(self._radar_map) == 0:
            self.ledmode_radar_setup()

        led_updated_dict = {}
        led_color = utils_colors.black()

        angle_seed = 360 - (clock_tick % 360)

        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()

        if angle_seed in self._radar_map:
            radar_leds = self._radar_map[angle_seed]
            for led_index in radar_leds:
                led_updated_dict[led_index] = self.radar_beam_color

        return led_updated_dict

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

            airports = self._airport_database.get_airport_dict_led()
            for dummy_key, airport_obj in airports.items():
                px_1 = float(airport_obj.longitude())  # Lon
                py_1 = float(airport_obj.latitude())  # Lat
                led_index = int(airport_obj.get_led_index())  # LED Pin Num

                if utils_coord.point_inside_triangle(
                    (px_1, py_1), (centerlon, centerlat), (x_1, y_1), (x_2, y_2)
                ):
                    #               print('Inside')
                    self.set_led_color(led_index, color1)
                else:
                    self.set_led_color(led_index, color2)
            self.show()
            time.sleep(self.time_base_delay)

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
                ) in self._airport_database.get_airport_dict_led():
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
                time.sleep(self.time_base_delay * wait_mult)

            for inclon in self.frange(centlon, maxlon, step):
                # declon, declat = Upper Left of box.
                # inclon, inclat = Lower Right of box
                for (
                    dummy_key,
                    airport_obj,
                ) in self._airport_database.get_airport_dict_led():
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
                time.sleep(self.time_base_delay * wait_mult)

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
                ) in self._airport_database.get_airport_dict_led():
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
                time.sleep(self.time_base_delay * wait_mult)

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
    # Each character gets encoded into multiple clock_tick entries
    def encode_morse_string(self):
        """Display Morse message."""
        # define timing of morse display
        morse_signal = []
        morse_raw_message = self._app_conf.get_string("morse", "message")
        debugging.debug(f"morse_raw_message :{morse_raw_message }")

        for morse_char in morse_raw_message:
            debugging.debug(f"morse: {morse_char}")
            morse_letter = []
            if morse_char.upper() in self.morse_code:
                morse_letter = list(self.morse_code[morse_char.upper()])
                for morse_symbol in morse_letter:
                    if morse_symbol == ".":
                        debugging.debug(f"morse: dot_encoded")
                        morse_signal.append(self.morse_dot_encoded)
                    else:
                        debugging.debug(f"morse: dash_encoded")
                        morse_signal.append(self.morse_dash_encoded)
                debugging.debug(f"morse: morse_interval_encoded")
                morse_signal.append(self.morse_interval_encoded)
            elif morse_char == " ":
                debugging.debug(f"morse: morse_word_interval_encoded")
                morse_signal.append(self.morse_word_interval_encoded)
            else:
                debugging.debug(f"morse encode huh?? :{morse_char}:")
            morse_signal.append(self.morse_letter_interval_encoded)

        morse_string_encoded = "".join(morse_signal)
        self.morse_signal_encoded = list(morse_string_encoded)
        debugging.info(f"morse_message :{self.morse_signal_encoded}")
        return

    def ledmode_rabbit(self, clock_tick):
        """Rabbit running through the map."""
        led_updated_dict = {}
        rabbit_pos = clock_tick % (len(self._active_led_dict) + 1)
        rabbit_color_1 = utils_colors.colordict["RED"]
        rabbit_color_2 = utils_colors.colordict["BLUE"]
        rabbit_color_3 = utils_colors.colordict["ORANGE"]

        debugging.info("Rabbit: In the rabbit loop")

        for led_key in self._active_led_dict.keys():
            if self._active_led_dict[led_key] is not None:
                led_index = self._active_led_dict[led_key]
                # debugging.info(f"posn:{rabbit_pos}/index:{_led_index}")
                led_updated_dict[led_index] = utils_colors.off()
                if led_index == rabbit_pos - 2:
                    led_updated_dict[led_index] = rabbit_color_1
                if led_index == rabbit_pos - 1:
                    led_updated_dict[led_index] = rabbit_color_2
                if led_index == rabbit_pos:
                    led_updated_dict[led_index] = rabbit_color_3
        return led_updated_dict

    def ledmode_shuffle(self, clock_tick):
        """Random LED colors."""
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = utils_colors.off()
        for led_key in self._active_led_dict.keys():
            if self._active_led_dict[led_key] is not None:
                led_index = self._active_led_dict[led_key]
                led_updated_dict[led_index] = utils_colors.randomcolor()
        return led_updated_dict

    def ledmode_fade(self, clock_tick):
        """Fade out and in colors."""
        led_updated_dict = {}
        fade_val = clock_tick % 255
        fade_col = utils_colors.hexcode(fade_val, 255 - fade_val, fade_val)
        for led_index in range(self.num_pixels()):
            if self._active_led_dict[led_index] is not None:
                led_updated_dict[led_index] = fade_col
        return led_updated_dict

    def ledmode_heatmap(self, clock_tick):
        """Set airport color based on number of visits."""
        airport_list = self._airport_database.get_airport_dict_led()
        led_updated_dict = {}
        for led_index in range(self.num_pixels()):
            led_updated_dict[led_index] = self.heatmap_color(0)
        for airport_key in airport_list:
            airport_obj = airport_list[airport_key]
            airportled = airport_obj.get_led_index()
            airportheat = airport_obj.heatmap_index()
            led_updated_dict[airportled] = self.heatmap_color(airportheat)
        return led_updated_dict
