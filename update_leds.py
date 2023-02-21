# -*- coding: utf-8 -*- #

"""
# update_leds.py
# Moved all of the airport specific data / metar analysis functions to update_airport.py
# This module creates a class updateLEDs that is specifically focused around
# managing a string of LEDs.
"""

# All of the functions to initialise, manipulate, wipe, change the LEDs are
# being included here.
#
# This also includes the wipe patterns from wipes-v4.py
#
# As this transition completes, all older code will be removed from here, so that the focus is only
# on managing an LED self.strip
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

# Import needed libraries

import math
import datetime
import time
from enum import Enum, auto

# from datetime import datetime
# from datetime import time as time

# import random
import collections
import ast

from rpi_ws281x import (
    Color,
    PixelStrip,
    ws,
)  # works with python 3.7. sudo pip3 install rpi_ws281x

import debugging
import utils
import utils_colors

class LedMode(Enum):
    """Set of Operating Modes for LED Strip."""
    OFF = auto()
    SLEEP = auto()
    METAR = auto()
    HEATMAP = auto()
    TEST = auto()
    SHUFFLE = auto()
    RADARWIPE = auto()
    RABBIT = auto()
    RAINBOW = auto()
    SQUAREWIPE = auto()
    WHEELWIPE = auto()
    CIRCLEWIPE = auto()


class UpdateLEDs:
    """Class to manage LED Strips"""

    def __init__(self, conf, airport_database):
        self.conf = conf

        self.airport_database = airport_database

        # list of pins that need to reverse the rgb_grb setting. To accommodate two different models of LED's are used.
        # self.rev_rgb_grb = self.conf.rev_rgb_grb        # [] # ['1', '2', '3', '4', '5', '6', '7', '8']

        # Specific Variables to default data to display if Rotary Switch is not installed.
        # hour_to_display # Offset in HOURS to choose which TAF/MOS to display
        self.hour_to_display = self.conf.get_int("rotaryswitch", "time_sw0")
        # metar_taf_mos    # 0 = Display TAF, 1 = Display METAR, 2 = Display MOS, 3 = Heat Map (Heat map not controlled by rotary switch)
        self.metar_taf_mos = self.conf.get_int("rotaryswitch", "data_sw0")
        # Set toggle_sw to an initial value that forces rotary switch to dictate data displayed
        self.toggle_sw = -1

        self.__led_mode = LedMode.METAR
        # MOS/TAF Config settings
        # self.prob = self.conf.prob                      # probability threshhold in Percent to assume reported weather will be displayed on map or not. MOS Only.

        # Heat Map settings
        # delay in fading the home airport if used
        self.fade_delay = conf.get_float("rotaryswitch", "fade_delay")

        # MOS Config settings
        # self.prob = self.conf.prob                      # probability threshhold in Percent to assume reported weather will be displayed on map or not.

        # Specific settings for on/off timer. Used to turn off LED's at night if desired.
        # Verify Raspberry Pi is set to the correct time zone, otherwise the timer will be off.
        # self.usetimer = self.conf.usetimer              # 0 = No, 1 = Yes. Turn the timer on or off with this setting

        self.nightsleep = self.conf.get_bool("schedule", "usetimer")

        self.offtime = datetime.time(
            self.conf.get_int("schedule", "offhour"),
            self.conf.get_int("schedule", "offminutes"),
            0,
            0,
        )

        self.ontime = datetime.time(
            self.conf.get_int("schedule", "onhour"),
            self.conf.get_int("schedule", "onminutes"),
            0,
            0,
        )

        # Set number of MINUTES to turn map on temporarily during sleep mode
        self.tempsleepon = self.conf.get_int("schedule", "tempsleepon")

        # Number of LED pixels. Change this value to match the number of LED's being used on map
        self.__led_count = self.conf.get_int("default", "led_count")
        self.__active_led_dict = {}

        # Misc settings
        # 0 = No, 1 = Yes, use wipes. Defined by configurator
        self.usewipes = self.conf.get_int("rotaryswitch", "usewipes")
        # 1 = RGB color codes. 0 = GRB color codes. Populate color codes below with normal RGB codes and script will change if necessary
        self.rgb_grb = self.conf.get_int("lights", "rgb_grb")
        # Used to determine if board should reboot every day at time set in setting below.
        self.use_reboot = self.conf.get_int("modules", "use_reboot")

        self.time_reboot = self.conf.get_string("default", "nightly_reboot_hr")

        self.homeport_toggle = False
        self.homeport_colors = ast.literal_eval(
            self.conf.get_string("colors", "homeport_colors")
        )

        # Blanking during refresh of the LED string between FAA updates.
        # TODO: Move to config
        self.blank_during_refresh = False

        # List of METAR weather categories to designate weather in area. Many Metars will report multiple conditions, i.e. '-RA BR'.
        # The code pulls the first/main weather reported to compare against the lists below. In this example it uses the '-RA' and ignores the 'BR'.
        # See https://www.aviationweather.gov/metar/symbol for descriptions. Add or subtract codes as desired.
        # Thunderstorm and lightning
        self.wx_lghtn_ck = [
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
        self.wx_snow_ck = [
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
        self.wx_rain_ck = [
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
        self.wx_frrain_ck = ["-FZDZ", "FZDZ", "+FZDZ", "-FZRA", "FZRA", "+FZRA"]
        # Dust Sand and/or Ash
        self.wx_dustsandash_ck = [
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
        self.wx_fog_ck = ["BR", "MIFG", "VCFG", "BCFG", "PRFG", "FG", "FZFG"]

        # FIXME: Needs to tie to the list of disabled LEDs
        self.nullpins = []

        self.wait = 1

        # LED Cycle times - Can change if necessary.
        # Used to create weather designation effects.
        self.cycle_wait = [0.9, 0.9, 0.08, 0.1, 0.08, 0.5]

        # LED self.strip configuration:
        self.__led_pin = 18  # GPIO pin connected to the pixels (18 uses PWM!).

        # LED signal frequency in hertz (usually 800khz)
        self.__led_freq_hz = 800_000
        self.__led_dma = 5  # DMA channel to use for generating signal (try 5)

        # True to invert the signal (when using NPN transistor level shift)
        self.__led_invert = False
        self.__led_channel = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
        self.__led_strip = ws.WS2811_STRIP_GRB  # Strip type and color ordering

        # starting brightness. It will be changed below.
        self.__led_brightness = self.conf.get_int("lights", "bright_value")

        # MOS Data Settings
        # location of the downloaded local MOS file.
        # TODO: Move to config file
        self.mos_filepath = "/NeoSectional/data/GFSMAV"
        self.categories = [
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
        self.obv_wx = {
            "N": "None",
            "HZ": "HZ",
            "BR": "RA",
            "FG": "FG",
            "BL": "HZ",
        }  # Decode from MOS to TAF/METAR
        # Decode from MOS to TAF/METAR
        self.typ_wx = {"S": "SN", "Z": "FZRA", "R": "RA"}

        # Morse Code Dictionary
        self.morse_code = {
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
            ", ": "--..--",
            ".": ".-.-.-",
            "?": "..--..",
            "/": "-..-.",
            "-": "-....-",
            "(": "-.--.",
            ")": "-.--.-",
        }

        # Create an instance of NeoPixel
        # FIXME: MOVE THIS FROM HERE TO LEDSTRIP for one INIT action
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

    # Functions
    def ledmode(self):
        """Return current LED Mode."""
        return self.__led_mode

    def set_ledmode(self, new_mode):
        """Update active LED Mode."""
        self.__led_mode = new_mode

    def setLedColor(self, led_id, hexcolor):
        """Convert color from HEX to RGB or GRB and apply to LED String"""
        # TODO: Add capability here to manage 'nullpins' and remove any mention of it from the code
        # This function should do all the color conversions
        rgb_color = utils_colors.RGB(hexcolor)
        color_ord = self.rgbtogrb(led_id, rgb_color, self.rgb_grb)
        pixel_data = Color(color_ord[0], color_ord[1], color_ord[2])
        self.strip.setPixelColor(led_id, pixel_data)

    def updateActiveLedList(self, airport_database):
        """Update Active LED list."""
        active_led_dict = {}
        led_index = 0
        posn = 0
        airports = self.airport_database.get_airport_dict_led()
        for icao, airportdb_row in airports.items():
            arpt = airportdb_row["airport"]
            if not arpt.active():
                continue
            led_index = arpt.get_led_index()
            active_led_dict[posn] = led_index
            posn = posn + 1
        self.__active_led_dict = active_led_dict

    def show(self):
        """Update LED strip to display current colors."""
        self.strip.show()

    def turnoff(self):
        """Set color to 0,0,0  - turning off LED."""
        for i in range(self.numPixels()):
            self.setLedColor(i, utils_colors.black())
        self.show()

    def numPixels(self):
        """Return number of Pixels defined."""
        return self.__led_count

    def set_brightness(self, lux):
        """Update saved brightness value."""
        self.__led_brightness = round(lux)

    def dim(self, color_data, value):
        """
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

        data = utils_colors.RGB(color_data)
        red = max(data[0] - ((value * data[0]) / 100), 0)
        grn = max(data[1] - ((value * data[1]) / 100), 0)
        blu = max(data[2] - ((value * data[2]) / 100), 0)
        data = (red, grn, blu)

        return data

    def findpoint(self, x_1, y_1, x_2, y_2, x_posn, y_posn):
        """Check to see if x,y is inside rectangle x_1,y_1-x_2,y_2."""
        return ((x_1 < x_posn < x_2) and (y_1 < y_posn < y_2))

    def area(self, x_1, y_1, x_2, y_2, x_3, y_3):
        """Calculate area of triangle."""
        return abs((x_1 * (y_2 - y_3) + x_2 * (y_3 - y_1) + x_3 * (y_1 - y_2)) / 2.0)

    def isInside(self, x_1, y_1, x_2, y_2, x_3, y_3, x_posn, y_posn):
        """Check to see if x,y is inside x_1,y_1-x_2,y_2-x_3-y_3."""
        # Calculate area of triangle ABC
        a_0 = self.area(x_1, y_1, x_2, y_2, x_3, y_3)
        # Calculate area of triangle PBC
        a_1 = self.area(x_posn, y_posn, x_2, y_2, x_3, y_3)
        # Calculate area of triangle PAC
        a_2 = self.area(x_1, y_1, x_posn, y_posn, x_3, y_3)
        # Calculate area of triangle PAB
        a_3 = self.area(x_1, y_1, x_2, y_2, x_posn, y_posn)
        # Check if sum of A_1, A_2 and A_3 is same as A
        return ((a_1 + a_2 + a_3) - 1) >= a_0 <= ((a_1 + a_2 + a_3) + 1)

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

    def center(self, max_a, min_a):
        """Calculate the middle point between two values."""
        z_val = ((max_a - min_a) / 2) + min_a
        return round(z_val, 2)

    def rgbtogrb(self, pin, data, order=True):
        """Change colorcode to match self.strip RGB / GRB style"""
        # Change color code to work with various led self.strips. For instance, WS2812 model self.strip uses RGB where WS2811 model uses GRB
        # Set the "rgb_grb" user setting above. 1 for RGB LED self.strip, and 0 for GRB self.strip.
        # If necessary, populate the list rev_rgb_grb with pin numbers of LED's that use the opposite color scheme.
        # rev_rgb_grb # list of pins that need to use the reverse of the normal order setting.
        # This accommodates the use of both models of LED strings on one map.
        if str(pin) in self.conf.get_string("lights", "rev_rgb_grb"):
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
            # TODO: Move to config
            color = utils_colors.rgb2hex((20, 20, 20))
        elif visits == "100":
            if self.conf.get_bool("rotaryswitch", "fade_yesno") and self.conf.get_bool(
                "rotaryswitch", "bin_grad"
            ):
                color = utils_colors.black()
            elif not self.conf.get_bool("rotaryswitch", "use_homeap"):
                color = utils_colors.rgb2hex((255, 0, 0))
            else:
                color = self.conf.get_string("colors", "color_vfr")
        elif "1" <= visits <= "50":  # Working
            if self.conf.get_bool("rotaryswitch", "bin_grad"):
                red = 255
                grn = 0
                blu = 0
                red = int(int(visits) * 5.1)
                color = utils_colors.rgb2hex((red, grn, blu))
            else:
                color = utils_colors.rgb2hex((255, 0, 0))
        elif "51" <= visits <= "99":  # Working
            if self.conf.get_bool("rotaryswitch", "bin_grad"):
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
        BIGNUM = 10000000
        DELAYSHORT = 0.2
        DELAYMEDIUM = 0.4
        DELAYLONG = 0.6
        PAUSESHORT = 1
        sleeping = False
        original_state = LedMode.METAR
        self.updateActiveLedList(self.airport_database)
        while True:
            # Going to use an index counter as a pseudo clock tick for
            # each LED module. It's going to continually increase through
            # each pass - and it's max value is a limiter on the number of LEDs
            # If each pass through this loop touches one LED ; then we need enough
            # clock cycles to cover every LED.
            clocktick = (clocktick + 1) % BIGNUM

            # print(".", end='')
            # sys.stdout.flush()

            if (clocktick % 100) == 1:
                # print(".", end='')
                debugging.info(f"clocktick: {clocktick}")

            if (clocktick % 1000) == 1:
                # Make sure the active LED list is updated
                self.updateActiveLedList(self.airport_database)

            # Check for nighttime every 1000 times through the loop
            # Keep the CPU load down
            if ((clocktick % 500) == 1) and self.nightsleep:
                debugging.info(f"Checking if it's time for sleep mode: {clocktick}")
                datetime_now = utils.current_time(self.conf)
                time_now = datetime_now.time()
                if utils.time_in_range(self.offtime, self.ontime, time_now):
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
                time.sleep(PAUSESHORT)
                continue
            if self.__led_mode == LedMode.METAR:
                led_color_dict = self.ledmode_metar(clocktick)
                self.update_ledstring(led_color_dict)
                continue
            if self.__led_mode == LedMode.HEATMAP:
                led_color_dict = self.ledmode_heatmap(clocktick)
                self.update_ledstring(led_color_dict)
                continue
            if self.__led_mode == LedMode.TEST:
                self.ledmode_test(clocktick)
                time.sleep(DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.RADARWIPE:
                led_color_dict = self.ledmode_rabbit(clocktick)
                time.sleep(DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.RABBIT:
                led_color_dict = self.ledmode_rabbit(clocktick)
                self.update_ledstring(led_color_dict)
                time.sleep(DELAYSHORT)
                continue
            if self.__led_mode == LedMode.SHUFFLE:
                led_color_dict = self.ledmode_shuffle(clocktick)
                self.update_ledstring(led_color_dict)
                time.sleep(DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.RAINBOW:
                led_color_dict = self.ledmode_rabbit(clocktick)
                time.sleep(DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.SQUAREWIPE:
                led_color_dict = self.ledmode_rabbit(clocktick)
                time.sleep(DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.WHEELWIPE:
                led_color_dict = self.ledmode_rabbit(clocktick)
                time.sleep(DELAYMEDIUM)
                continue
            if self.__led_mode == LedMode.CIRCLEWIPE:
                led_color_dict = self.ledmode_rabbit(clocktick)
                time.sleep(DELAYMEDIUM)
                continue

    def update_ledstring(self, led_color_dict):
        """Iter across all the LEDs and set the color appropriately."""
        for ledindex, led_color in led_color_dict.items():
            self.setLedColor(ledindex, led_color)
        self.strip.setBrightness(self.__led_brightness)
        self.show()

    def ledmode_test(self, clocktick):
        """Run self test sequences."""
        self.colorwipe(clocktick)

    def ledmode_heatmap(self, clocktick):
        """Placeholder STUB."""
        # FIXME: Stub
        if clocktick:   # Local scope ; no effect
            return {}
        return {}

    def legend_color(self, airportwxsrc, cycle_num):
        """Work out the color for the legend LEDs."""
        ledcolor = utils_colors.off()
        if airportwxsrc == "vfr":
            ledcolor = utils_colors.VFR(self.conf)
        if airportwxsrc == "mvfr":
            ledcolor = utils_colors.MVFR(self.conf)
        if airportwxsrc == "ifr":
            ledcolor = utils_colors.IFR(self.conf)
        if airportwxsrc == "lfr":
            ledcolor = utils_colors.LIFR(self.conf)
        if airportwxsrc == "nowx":
            ledcolor = utils_colors.NOWEATHER(self.conf)
        if airportwxsrc == "hiwind":
            if cycle_num in (3, 4, 5):
                ledcolor = utils_colors.off()
            else:
                ledcolor = utils_colors.IFR(self.conf)
        if airportwxsrc == "lghtn":
            if cycle_num in (2, 4):
                ledcolor = utils_colors.LIGHTNING(self.conf)
            else:
                ledcolor = utils_colors.MVFR(self.conf)
        if airportwxsrc == "snow":
            if cycle_num in (3, 5):  # Check for Snow
                ledcolor = utils_colors.SNOW(self.conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.SNOW(self.conf, 2)
            else:
                ledcolor = utils_colors.LIFR(self.conf)
        if airportwxsrc == "rain":
            if cycle_num in (3, 5):  # Check for Rain
                ledcolor = utils_colors.RAIN(self.conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.RAIN(self.conf, 2)
            else:
                ledcolor = utils_colors.VFR(self.conf)
        if airportwxsrc == "frrain":
            if cycle_num in (3, 5):  # Check for Freezing Rain
                ledcolor = utils_colors.FRZRAIN(self.conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.FRZRAIN(self.conf, 2)
            else:
                ledcolor = utils_colors.MVFR(self.conf)
        if airportwxsrc == "dust":
            if cycle_num in (3, 5):  # Check for Dust, Sand or Ash
                ledcolor = utils_colors.DUST_SAND_ASH(self.conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.DUST_SAND_ASH(self.conf, 2)
            else:
                ledcolor = utils_colors.VFR(self.conf)
        if airportwxsrc == "fog":
            if cycle_num in (3, 5):  # Check for Fog
                ledcolor = utils_colors.FOG(self.conf, 1)
            if cycle_num == 4:
                ledcolor = utils_colors.FOG(self.conf, 2)
            elif cycle_num in (0, 1, 2):
                ledcolor = utils_colors.IFR(self.conf)
        return ledcolor

    def ledmode_metar(self, clocktick):
        """Generate LED Color set for Airports..."""
        airport_list = self.airport_database.get_airport_dict_led()
        led_updated_dict = {}
        for led_index in range(self.numPixels()):
            led_updated_dict[led_index] = utils_colors.off()

        cycle_num = clocktick % len(self.cycle_wait)

        for airport_key in airport_list:
            airport_record = airport_list[airport_key]["airport"]
            airportcode = airport_record.icaocode()
            airportled = airport_record.get_led_index()
            airportwxsrc = airport_record.wxsrc()
            if not airportcode:
                continue
            if airportcode == "null":
                continue
            if airportcode == "lgnd":
                ledcolor = self.legend_color(airportwxsrc, cycle_num)

            # Initialize color
            ledcolor = utils_colors.off()
            # Pull the next flight category from dictionary.
            flightcategory = airport_record.get_wx_category_str()
            if not flightcategory:
                flightcategory = "UNKN"
            # Pull the winds from the dictionary.
            airportwinds = airport_record.get_wx_windspeed()
            if not airportwinds:
                airportwinds = -1
            airport_conditions = airport_record.wxconditions()
            debugging.debug(
                f"{airportcode}:{flightcategory}:{airportwinds}:cycle=={cycle_num}"
            )

            # Start of weather display code for each airport in the "airports" file
            # Check flight category and set the appropriate color to display
            if flightcategory == "VFR":  # Visual Flight Rules
                ledcolor = utils_colors.VFR(self.conf)
            elif flightcategory == "MVFR":  # Marginal Visual Flight Rules
                ledcolor = utils_colors.MVFR(self.conf)
            elif flightcategory == "IFR":  # Instrument Flight Rules
                ledcolor = utils_colors.IFR(self.conf)
            elif flightcategory == "LIFR":  # Low Instrument Flight Rules
                ledcolor = utils_colors.LIFR(self.conf)
            elif flightcategory == "UNKN":
                ledcolor = utils_colors.NOWEATHER(self.conf)

            # Check winds and set the 2nd half of cycles to black to create blink effect
            if self.conf.get_bool("lights", "hiwindblink"):
                # bypass if "hiwindblink" is set to 0
                if int(airportwinds) >= self.conf.get_int(
                    "metar", "max_wind_speed"
                ) and (cycle_num in (3, 4, 5)):
                    ledcolor = utils_colors.off()
                    debugging.debug(f"HIGH WINDS {airportcode} : {airportwinds} kts")

            if self.conf.get_bool("lights", "lghtnflash"):
                # Check for Thunderstorms
                if airport_conditions in self.wx_lghtn_ck and (cycle_num in (2, 4)):
                    ledcolor = utils_colors.LIGHTNING(self.conf)

            if self.conf.get_bool("lights", "snowshow"):
                # Check for Snow
                if airport_conditions in self.wx_snow_ck and (cycle_num in (3, 5)):
                    ledcolor = utils_colors.SNOW(self.conf, 1)
                if airport_conditions in self.wx_snow_ck and cycle_num == 4:
                    ledcolor = utils_colors.SNOW(self.conf, 2)

            if self.conf.get_bool("lights", "rainshow"):
                # Check for Rain
                if airport_conditions in self.wx_rain_ck and (cycle_num in (3, 4)):
                    ledcolor = utils_colors.RAIN(self.conf, 1)
                if airport_conditions in self.wx_rain_ck and cycle_num == 5:
                    ledcolor = utils_colors.RAIN(self.conf, 2)

            if self.conf.get_bool("lights", "frrainshow"):
                # Check for Freezing Rain
                if airport_conditions in self.wx_frrain_ck and (cycle_num in (3, 5)):
                    ledcolor = utils_colors.FRZRAIN(self.conf, 1)
                if airport_conditions in self.wx_frrain_ck and cycle_num == 4:
                    ledcolor = utils_colors.FRZRAIN(self.conf, 2)

            if self.conf.get_bool("lights", "dustsandashshow"):
                # Check for Dust, Sand or Ash
                if airport_conditions in self.wx_dustsandash_ck and (
                    cycle_num in (3, 5)
                ):
                    ledcolor = utils_colors.DUST_SAND_ASH(self.conf, 1)
                if airport_conditions in self.wx_dustsandash_ck and cycle_num == 4:
                    ledcolor = utils_colors.DUST_SAND_ASH(self.conf, 2)

            if self.conf.get_bool("lights", "fogshow"):
                # Check for Fog
                if airport_conditions in self.wx_fog_ck and (cycle_num in (3, 5)):
                    ledcolor = utils_colors.FOG(self.conf, 1)
                if airport_conditions in self.wx_fog_ck and cycle_num == 4:
                    ledcolor = utils_colors.FOG(self.conf, 2)

            # If homeport is set to 1 then turn on the appropriate LED using a specific color, This will toggle
            # so that every other time through, the color will display the proper weather, then homeport color(s).
            self.homeport_toggle = not self.homeport_toggle
            if (
                airportled == self.conf.get_int("lights", "homeport_pin")
                and self.conf.get_bool("lights", "homeport")
                and self.homeport_toggle
            ):
                if self.conf.get_int("lights", "homeport_display") == 1:
                    # FIXME: ast.literal_eval converts a string to a list of tuples..
                    # Should move these colors to be managed with other colors.
                    homeport_colors = ast.literal_eval(
                        self.conf.get_string("colors", "homeport_colors")
                    )
                    # The length of this array needs to metch the cycle_num length or we'll get errors.
                    # FIXME: Fragile
                    ledcolor = homeport_colors[cycle_num]
                elif self.conf.get_int("lights", "homeport_display") == 2:
                    # Homeport set based on METAR data
                    pass
                else:
                    # Homeport set to fixed color
                    ledcolor = self.conf.get_color("colors", "color_homeport")

            # FIXME: Need to fix the way this next section picks colors
            if airportled == self.conf.get_int(
                "lights", "homeport_pin"
            ) and self.conf.get_bool("lights", "homeport"):
                # TODO: Skips for now .. need a better plan
                pass
            elif self.conf.get_bool("lights", "homeport"):
                # FIXME: This doesn't work
                # if this is not the home airport, dim out the brightness
                dim_color = self.dim(ledcolor, self.conf.get_int("lights", "dim_value"))
                # ledcolor = utils_colors.HEX(int(dim_color[0]), int(dim_color[1]), int(dim_color[2]))
            else:  # if home airport feature is disabled, then don't dim out any airports brightness
                norm_color = ledcolor
                # ledcolor = utils_colors.HEX(norm_color[0], norm_color[1], norm_color[2])

            led_updated_dict[airportled] = ledcolor
        # Add cycle delay to this loop
        time.sleep(self.cycle_wait[cycle_num])
        return led_updated_dict

    def colorwipe(self, clocktick):
        """Run a color wipe test"""
        wipe_steps = clocktick % 5
        if wipe_steps == 0:
            self.strip.fill(utils_colors.colordict["RED"])
            self.strip.setBrightness(self.__led_brightness)
            self.show()
            return
        if wipe_steps == 1:
            self.strip.fill(utils_colors.colordict["GREEN"])
            self.strip.setBrightness(self.__led_brightness)
            self.show()
            return
        if wipe_steps == 2:
            self.strip.fill(utils_colors.colordict["BLUE"])
            self.strip.setBrightness(self.__led_brightness)
            self.show()
            return
        if wipe_steps == 3:
            self.strip.fill(utils_colors.colordict["MAGENTA"])
            self.strip.setBrightness(self.__led_brightness)
            self.show()
            return
        if wipe_steps == 4:
            self.strip.fill(utils_colors.colordict["YELLOW"])
            self.strip.setBrightness(self.__led_brightness)
            self.show()
            return

    # Rainbow Animation functions - taken from https://github.com/JJSilva/NeoSectional/blob/master/metar.py
    def wheel(self, pos):
        """Generate rainbow colors across 0-255 positions."""
        if pos < 85:
            return Color(pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return Color(255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return Color(0, pos * 3, 255 - pos * 3)

    def rainbow_cycle(self, led_indexations, wait=0.1):
        """Draw rainbow that uniformly distributes itself across all pixels."""
        for j in range(256 * led_indexations):
            for led_index in range(self.numPixels()):
                if (
                    str(led_index) in self.nullpins
                ):  # exclude NULL and LGND pins from wipe
                    self.setLedColor(led_index, Color(0, 0, 0))
                else:
                    self.setLedColor(
                        led_index,
                        self.wheel((int(led_index * 256 / self.numPixels()) + j) & 255),
                    )
            self.show()
            time.sleep(wait / 100)

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

    # Change color code to work with various led strips. For instance, WS2812 model strip uses RGB where WS2811 model uses GRB
    # Set the "rgb_grb" user setting above. 1 for RGB LED strip, and 0 for GRB self._leds.
    # If necessary, populate the list rev_rgb_grb with pin numbers of LED's that use the opposite color scheme.
    def rgbtogrb_wipes(self, led_index, data, order=0):
        """Match RGB color to LED type."""
        # TODO: Move to utils_ function
        if str(led_index) in self.rev_rgb_grb:
            # This accommodates the use of both models of LED strings on one map.
            order = not order
            debugging.debug(f"Reversing rgb2grb Routine Output for LED PIN {led_index}")
        red = data[0]
        grn = data[1]
        blu = data[2]
        if order:
            data = [red, grn, blu]
        else:
            data = [grn, red, blu]
        xcolor = Color(data[0], data[1], data[2])
        return xcolor

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

                    color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    self.setLedColor(led_index, color)
                    self.show()
                    time.sleep(self.wait * wait_mult)

                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                    self.setLedColor(led_index, color)
                    self.show()
                    time.sleep(self.wait * wait_mult)

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

        for j in range(led_index):
            airports = self.airport_database.get_airport_dict_led()
            for key, airport_record in airports.items():
                arpt = airport_record["airport"]
                if not arpt.active():
                    continue
                x_posn = float(arpt.longitude())
                y_posn = float(arpt.latitude())
                led_index = int(arpt.get_led_index())

                if (x_posn - circle_x) * (x_posn - circle_x) + (y_posn - circle_y) * (
                    y_posn - circle_y
                ) <= rad * rad:
                    #               print("Inside")
                    color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                else:
                    #               print("Outside")
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                self.setLedColor(led_index, color)
                self.show()
                time.sleep(self.wait)
            rad = rad + rad_inc

        for j in range(led_index):
            rad = rad - rad_inc
            airports = self.airport_database.get_airport_dict_led()
            for key, airport_record in airports.items():
                arpt = airport_record["airport"]
                x_posn = float(arpt.longitude())
                y_posn = float(arpt.latitude())
                led_index = int(arpt.get_led_index())

                if (x_posn - circle_x) * (x_posn - circle_x) + (y_posn - circle_y) * (
                    y_posn - circle_y
                ) <= rad * rad:
                    #               print("Inside")
                    color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                else:
                    #               print("Outside")
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)

                self.setLedColor(led_index, color)
                self.show()
                time.sleep(self.wait)

        self.allonoff_wipes((0, 0, 0), 0.1)

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
        PI = 3.141592653
        angle = 0

        for k in range(led_index):
            # Calculate the x_1,y_1 for the end point of our 'sweep' based on
            # the current angle. Then do the same for x_2,y_2
            x_1 = round(radius * math.sin(angle) + centerlon, 2)
            y_1 = round(radius * math.cos(angle) + centerlat, 2)
            x_2 = round(radius * math.sin(angle + sweepwidth) + centerlon, 2)
            y_2 = round(radius * math.cos(angle + sweepwidth) + centerlat, 2)

            airports = self.airport_database.get_airport_dict_led()
            for key, airport_record in airports.items():
                arpt = airport_record["airport"]
                px_1 = float(arpt.longitude())  # Lon
                py_1 = float(arpt.latitude())  # Lat
                led_index = int(arpt.get_led_index())  # LED Pin Num
                #           print (centerlon, centerlat, x_1, y_1, x_2, y_2, px_1, py_1, pin) #debug

                if self.isInside(centerlon, centerlat, x_1, y_1, x_2, y_2, px_1, py_1):
                    #               print('Inside')
                    color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    self.setLedColor(led_index, color)
                else:
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                    self.setLedColor(led_index, color)
            #               print('Not Inside')
            self.show()
            time.sleep(self.wait)

            # Increase the angle by angleinc radians
            angle = angle + angleinc

            # If we have done a full sweep, reset the angle to 0
            if angle > 2 * PI:
                angle = angle - (2 * PI)

    # Square wipe
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
        centlon = self.center(maxlon, minlon)
        centlat = self.center(maxlat, minlat)

        for j in range(led_index):
            for inclon in self.frange(maxlon, centlon, step):
                # declon, declat = Upper Left of box.
                # inclon, inclat = Lower Right of box
                for key, airport_record in self.airport_database.get_airport_dict_led():
                    arpt = airport_record["airport"]
                    px_1 = float(arpt.longitude())  # Lon
                    py_1 = float(arpt.latitude())  # Lat
                    led_index = int(arpt.get_led_index())  # LED Pin Num

                    #                print((declon, declat, inclon, inclat, px_1, py_1)) #debug
                    if self.findpoint(declon, declat, inclon, inclat, px_1, py_1):
                        #                    print('Inside') #debug
                        color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    else:
                        #                    print('Not Inside') #debug
                        color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)

                    self.setLedColor(led_index, color)

                inclat = round(inclat - step, 2)
                declon = round(declon + step, 2)
                declat = round(declat + step, 2)

                self.show()
                time.sleep(self.wait * wait_mult)

            for inclon in self.frange(centlon, maxlon, step):
                # declon, declat = Upper Left of box.
                # inclon, inclat = Lower Right of box
                for key, airport_record in self.airport_database.get_airport_dict_led():
                    arpt = airport_record["airport"]
                    px_1 = float(arpt.longitude())  # Lon
                    py_1 = float(arpt.latitude())  # Lat
                    led_index = int(arpt.get_led_index())  # LED Pin Num

                    #                print((declon, declat, inclon, inclat, px_1, py_1)) #debug
                    if self.findpoint(declon, declat, inclon, inclat, px_1, py_1):
                        #                    print('Inside') #debug
                        color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    else:
                        #                   print('Not Inside') #debug
                        color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)

                    self.setLedColor(led_index, color)

                inclat = round(inclat + step, 2)
                declon = round(declon - step, 2)
                declat = round(declat - step, 2)

                self.show()
                time.sleep(self.wait * wait_mult)

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
        centlon = self.center(maxlon, minlon)
        centlat = self.center(maxlat, minlat)

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

        for j in range(led_index):
            for box in squarelist:
                for key, airport_record in self.airport_database.get_airport_dict_led():
                    arpt = airport_record["airport"]
                    px_1 = float(arpt.longitude())  # Lon
                    py_1 = float(arpt.latitude())  # Lat
                    led_index = int(arpt.get_led_index())  # LED Pin Num

                    if self.findpoint(
                        *box, px_1, py_1
                    ):  # Asterick allows unpacking of list in function call.
                        color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                    else:
                        color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)

                    self.setLedColor(led_index, color)
                self.show()
                time.sleep(self.wait * wait_mult)
        self.allonoff_wipes((0, 0, 0), 0.1)

    # Turn on or off all the lights using the same color.
    def allonoff_wipes(self, color1, delay):
        """Single Color wipe."""
        for led_index in range(self.numPixels()):
            if str(led_index) in self.nullpins:  # exclude NULL and LGND pins from wipe
                self.setLedColor(led_index, Color(0, 0, 0))
            else:
                color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                self.setLedColor(led_index, color)
        self.show()
        time.sleep(delay)

    # Fade LED's in and out using the same color.
    def fade(self, color1, delay):
        """Fade in/out."""
        for val in range(0, self.__led_brightness, 1):  # self.numPixels()):
            for led_index in range(self.numPixels()):  # LED_BRIGHTNESS,0,-1):
                if (
                    str(led_index) in self.nullpins
                ):  # exclude NULL and LGND pins from wipe
                    self.setLedColor(led_index, Color(0, 0, 0))
                else:
                    color2 = self.dimwipe(color1, val)
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                    self.setLedColor(led_index, color)
            self.show()
            time.sleep(self.wait * 0.5)

        for val in range(self.__led_brightness, 0, -1):  # self.numPixels()):
            for led_index in range(self.numPixels()):  # 0,LED_BRIGHTNESS,1):
                if (
                    str(led_index) in self.nullpins
                ):  # exclude NULL and LGND pins from wipe
                    self.setLedColor(led_index, Color(0, 0, 0))
                else:
                    color2 = self.dimwipe(color1, val)
                    color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                    self.setLedColor(led_index, color)
            self.show()
            time.sleep(self.wait * 0.5)
        time.sleep(delay * 1)

    # Dim LED's
    def dimwipe(self, data, value):
        """Reduce light colors."""
        # FIXME: Seems like this code just jumps straight to zero
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
        dot_leng = self.wait * 1
        dash_leng = self.wait * 3
        bet_symb_leng = self.wait * 1
        bet_let_leng = self.wait * 3
        bet_word_leng = self.wait * 4  # logic will add bet_let_leng + bet_word_leng = 7

        for char in self.conf("rotaryswitch", "morse_msg"):
            letter = []
            if char.upper() in self.morse_code:
                letter = list(self.morse_code[char.upper()])
                debugging.debug(letter)  # debug

                for val in letter:  # display individual dot/dash with proper timing
                    if val == ".":
                        morse_signal = dot_leng
                    else:
                        morse_signal = dash_leng

                    for led_index in range(self.numPixels()):  # turn LED's on
                        if (
                            str(led_index) in self.nullpins
                        ):  # exclude NULL and LGND pins from wipe
                            self.setLedColor(led_index, Color(0, 0, 0))
                        else:
                            color = self.rgbtogrb_wipes(led_index, color1, self.rgb_grb)
                            self.setLedColor(led_index, color)
                    self.show()
                    time.sleep(morse_signal)  # time on depending on dot or dash

                    for led_index in range(self.numPixels()):  # turn LED's off
                        if (
                            str(led_index) in self.nullpins
                        ):  # exclude NULL and LGND pins from wipe
                            self.setLedColor(led_index, Color(0, 0, 0))
                        else:
                            color = self.rgbtogrb_wipes(led_index, color2, self.rgb_grb)
                            self.setLedColor(led_index, color)
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

                        for led_index in range(self.numPixels()):  # turn LED's on
                            if (
                                str(led_index) in self.nullpins
                            ):  # exclude NULL and LGND pins from wipe
                                self.setLedColor(led_index, Color(0, 0, 0))
                            else:
                                color = self.rgbtogrb_wipes(
                                    led_index, color1, self.rgb_grb
                                )
                                self.setLedColor(led_index, color)
                        self.show()
                        time.sleep(morse_signal)  # time on depending on dot or dash

                        for led_index in range(self.numPixels()):  # turn LED's off
                            if (
                                str(led_index) in self.nullpins
                            ):  # exclude NULL and LGND pins from wipe
                                self.setLedColor(led_index, Color(0, 0, 0))
                            else:
                                color = self.rgbtogrb_wipes(
                                    led_index, color2, self.rgb_grb
                                )
                                self.setLedColor(led_index, color)
                        self.show()
                        time.sleep(bet_symb_leng)  # timing between symbols

                    time.sleep(bet_let_leng)  # timing between letters

        time.sleep(delay)

    def ledmode_rabbit(self, clocktick):
        """Rabbit running through the map"""
        led_updated_dict = {}
        rabbit_posn = clocktick % len(self.__active_led_dict)
        rabbit_color_1 = utils_colors.colordict["RED"]
        rabbit_color_2 = utils_colors.colordict["BLUE"]
        rabbit_color_3 = utils_colors.colordict["ORANGE"]

        debugging.info("Rabbit: In the rabbit loop")

        for led_index in enumerate(self.__active_led_dict):

            # debugging.info(f"posn:{rabbit_posn}/index:{led_index}")
            led_updated_dict[self.__active_led_dict[led_index]] = utils_colors.off()
            if led_index == rabbit_posn - 2:
                led_updated_dict[self.__active_led_dict[led_index]] = rabbit_color_1
            if led_index == rabbit_posn - 1:
                led_updated_dict[self.__active_led_dict[led_index]] = rabbit_color_2
            if led_index == rabbit_posn:
                led_updated_dict[self.__active_led_dict[led_index]] = rabbit_color_3
        return led_updated_dict

    def ledmode_shuffle(self, clocktick):
        """Random LED colors"""
        led_updated_dict = {}
        for led_index in range(len(self.__active_led_dict)):
            led_updated_dict[led_index] = utils_colors.randomcolor()
        return led_updated_dict
