# -*- coding: utf-8 -*- #

"""
# update_leds.py
# Moved all of the airport specific data / metar analysis functions to update_airport.py
# This module creates a class updateLEDs that is specifically focused around
# managing a string of LEDs.
#
# All of the functions to initialise, manipulate, wipe, change the LEDs are
# being included here.
#
# This also includes the wipe patterns from wipes-v4.py
#
# As this transition completes, all older code will be removed from here, so that the focus is only
# on managing an LED self.strip
#
# metar-v4.py - by Mark Harris. Capable of displaying METAR data, TAF or MOS data. Using a rotary switch to select 1 of 12 positions
# Updated to run under Python 3.7
# Added Sleep Timer routine to turn-off map at night if desired.
# Added the ability to display TAF or MOS data along with METAR's
# Note: MOS data is only available for United States, Puerto Rico, and the U.S. Virgin Islands.
# The timeframe of the TAF, MOS data to display can be selected via the rotary switch. A switch with up to 12 positions can be used.
# If no Rotary Switch is used, this script's config will set default data to display.
# Added routine by by Nick Cirincione to decode flight category if flight category is not provided by the FAA.
# Fixed bug that wouldn't allow the last airport to be 'NULL' without causing all LED's to show white.
# Added auto restart when config.py is changed, so settings will be automatically re-loaded.
# Added internet availability check and retry if necessary. This should help when power is disrupted and board reboots before router does.
# Added Logging capabilities which is stored in /NeoSectional/logs/logfile.log with 3 backup files for older logfile data.
# Added ability to specify specific LED pins to reverse the normal rgb_grb setting. For mixing models of LED strings.
# Added a Heat Map of what airports the user has landed at. Not available through Rotary switch. Only Web interface.
# Added new wipes, some based on lat/lon of airports
# Fixed bug where wipes would execute twice on map startup.
# Added admin.py for behinds the scenes variables to be stored. i.e. use_mos=1 to determine if bash files should or should not download MOS data.
# Added ability to detect a Rotary Switch is NOT installed and react accordingly.
# Added logging of Current RPI IP address whenever FAA weather update is retrieved
# Fixed bug where TAF XML reports OVC without a cloud level agl. It uses vert_vis_ft as a backup.
# Fixed bug when debug mode is changed to 'Debug'.
# Switch Version control over to Github at https://github.com/markyharris/livesectional
# Fixed METAR Decode routine to handle FAA results that don't include flight_category and forecast fields.
# Added routine to check time and reboot each night if setting in admin.py are set accordingly.
# Fixed bug that missed lowest sky_condition altitude on METARs not reporting flight categories.
"""

# This version retains the features included in metar-v3.py, including hi-wind blinking and lightning when thunderstorms are reported.
# However, this version adds representations for snow, rain, freezing rain, dust sand ash, and fog when reported in the metar.
# The LED's will show the appropriate color for the reported flight category (vfr, mvfr, ifr, lifr) then blink a specific color for the weather
# For instance, an airport reporting IFR with snow would display Red then blink white for a short period to denote snow. Blue for rain,
# purple for freezing rain, brown for dust sand ash, and silver for fog. This makes for a colorful map when weather is in the area.
# A home airport feature has been added as well. When enabled, the map can be dimmed in relation to the home airport as well as
# have the home alternate between weather color and a user defined marker color(s).
# Most of these features can be disabled to downgrade the map display in the user-defined variables below.

# For detailed instructions on building an Aviation Map, visit http://www.livesectional.com
# Hardware features are further explained on this site as well. However, this software allows for a power-on/update weather switch,
# and Power-off/Reboot switch. The use of a display is handled by metar-display.py and not this script.

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
import time
from enum import Enum, auto
from datetime import datetime

from datetime import time as time_

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
    OFF = auto()
    METAR = auto()
    HEATMAP = auto()
    TEST = auto()
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

        self.led_mode = LedMode.METAR
        # MOS/TAF Config settings
        # self.prob = self.conf.prob                      # probability threshhold in Percent to assume reported weather will be displayed on map or not. MOS Only.

        # Heat Map settings
        # self.bin_grad = self.conf.bin_grad              # 0 = Binary display, 1 = Gradient display
        # self.fade_yesno = self.conf.fade_yesno          # 0 = No, 1 = Yes, if using gradient display, fade in/out the home airport color. will override use_homeap.
        # self.use_homeap = self.conf.use_homeap          # 0 = No, 1 = Yes, Use a separate color to denote home airport.
        # delay in fading the home airport if used
        self.fade_delay = conf.get_float("rotaryswitch", "fade_delay")

        # MOS Config settings
        # self.prob = self.conf.prob                      # probability threshhold in Percent to assume reported weather will be displayed on map or not.

        # Specific settings for on/off timer. Used to turn off LED's at night if desired.
        # Verify Raspberry Pi is set to the correct time zone, otherwise the timer will be off.
        # self.usetimer = self.conf.usetimer              # 0 = No, 1 = Yes. Turn the timer on or off with this setting
        self.offhour = self.conf.get_int(
            "schedule", "offhour"
        )  # Use 24 hour time. Set hour to turn off display
        self.offminutes = self.conf.get_int(
            "schedule", "offminutes"
        )  # Set minutes to turn off display
        self.onhour = self.conf.get_int(
            "schedule", "onhour"
        )  # Use 24 hour time. Set hour to turn on display
        self.onminutes = self.conf.get_int(
            "schedule", "onminutes"
        )  # Set minutes to on display
        # Set number of MINUTES to turn map on temporarily during sleep mode
        self.tempsleepon = self.conf.get_int("schedule", "tempsleepon")

        # Number of LED pixels. Change this value to match the number of LED's being used on map
        self.LED_COUNT = self.conf.get_int("default", "led_count")

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

        # LED Cycle times - Can change if necessary.
        # These cycle times all added together will equal the total amount of time the LED takes to finish displaying one cycle.
        self.cycle0_wait = 0.9
        # Each  cycle, depending on flight category, winds and weather reported will have various colors assigned.
        self.cycle1_wait = 0.9
        # For instance, VFR with 20 kts winds will have the first 3 cycles assigned Green and the last 3 Black for blink effect.
        self.cycle2_wait = 0.08
        # The cycle times then reflect how long each color cycle will stay on, producing blinking or flashing effects.
        self.cycle3_wait = 0.1
        # Lightning effect uses the short intervals at cycle 2 and cycle 4 to create the quick flash. So be careful if you change them.
        self.cycle4_wait = 0.08
        self.cycle5_wait = 0.5

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

        # list definitions
        # Used to create weather designation effects.
        self.cycle_wait = [
            self.cycle0_wait,
            self.cycle1_wait,
            self.cycle2_wait,
            self.cycle3_wait,
            self.cycle4_wait,
            self.cycle5_wait,
        ]
        self.cycles = [0, 1, 2, 3, 4, 5]  # Used as a index for the cycle loop.

        # LED self.strip configuration:
        self.LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).

        # LED signal frequency in hertz (usually 800khz)
        self.LED_FREQ_HZ = 800_000
        self.LED_DMA = 5  # DMA channel to use for generating signal (try 5)

        # True to invert the signal (when using NPN transistor level shift)
        self.LED_INVERT = False
        self.LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
        self.LED_STRIP = ws.WS2811_STRIP_GRB  # Strip type and color ordering

        # starting brightness. It will be changed below.
        self.LED_BRIGHTNESS = self.conf.get_int("lights", "bright_value")

        # Timer calculations
        self.lights_out = time_(
            self.conf.get_int("schedule", "offhour"),
            self.conf.get_int("schedule", "offminutes"),
            0,
        )
        self.timeoff = self.lights_out
        self.lights_on = time_(self.onhour, self.onminutes, 0)
        self.end_time = self.lights_on
        # Set flag for next round if sleep timer is interrupted by button push.
        self.temp_lights_on = 0

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
        # Outer Dictionary, keyed by airport ID
        self.mos_dict = collections.OrderedDict()
        # Middle Dictionary, keyed by hour of forcast. Will contain a list of data for categories.
        self.hour_dict = collections.OrderedDict()
        # Used to determine that an airport from our airports file is currently being read.
        self.ap_flag = 0

        # TODO: Color Definitions - Move to Config
        # Used by Heat Map. Do not change - assumed by routines below.
        self.low_visits = (0, 0, 255)  # Start with Blue - Do Not Change
        # Increment to Red as visits get closer to 100 - Do Not Change
        self.high_visits = (255, 0, 0)
        self.fadehome = -1  # start with neg number
        self.homeap = self.conf.get_string(
            "colors", "color_vfr"
        )  # If 100, then home airport - designate with Green
        # color_fog2  # (10, 10, 10) # dk grey to denote airports never visited
        self.no_visits = (20, 20, 20)

        # Morse Code Dictionary
        self.CODE = {
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
            self.LED_COUNT,
            self.LED_PIN,
            self.LED_FREQ_HZ,
            self.LED_DMA,
            self.LED_INVERT,
            self.LED_BRIGHTNESS,
            self.LED_CHANNEL,
            self.LED_STRIP,
        )
        self.strip.begin()

    # Functions
    def setLedColor(self, led_id, hexcolor):
        """Convert color from HEX to RGB or GRB and apply to LED String"""
        # TODO: Add capability here to manage 'nullpins' and remove any mention of it from the code
        # This function should do all the color conversions
        rgb_color = utils_colors.RGB(hexcolor)
        color_ord = self.rgbtogrb(led_id, rgb_color, self.rgb_grb)
        pixel_data = Color(color_ord[0], color_ord[1], color_ord[2])
        self.strip.setPixelColor(led_id, pixel_data)

    def show(self):
        """Update LED strip to display current colors."""
        self.strip.show()

    def turnoff(self):
        """Set color to 0,0,0  - turning off LED."""
        for i in range(self.strip.numPixels()):
            self.setLedColor(i, utils_colors.black())
        self.show()

    def set_brightness(self, lux):
        """Update saved brightness value."""
        self.LED_BRIGHTNESS = round(lux)

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
        """Color codes assigned with heatmap"""
        if visits == "0":
            color = self.no_visits
        elif visits == "100":
            if self.conf.get_bool("rotaryswitch", "fade_yesno") and self.conf.get_bool(
                "rotaryswitch", "bin_grad"
            ):
                color = utils_colors.black()
            elif not self.conf.get_bool("rotaryswitch", "use_homeap"):
                color = self.high_visits
            else:
                color = self.homeap
        elif "1" <= visits <= "50":  # Working
            if self.conf.get_bool("rotaryswitch", "bin_grad"):
                red = self.low_visits[0]
                grn = self.low_visits[1]
                blu = self.low_visits[2]
                red = int(int(visits) * 5.1)
                color = (red, grn, blu)
            else:
                color = self.high_visits
        elif "51" <= visits <= "99":  # Working
            if self.conf.get_bool("rotaryswitch", "bin_grad"):
                red = self.high_visits[0]
                grn = self.high_visits[1]
                blu = self.high_visits[2]
                blu = 255 - int((int(visits) - 50) * 5.1)
                color = (red, grn, blu)
            else:
                color = self.high_visits
        else:
            color = utils_colors.black()
        return color

    def update_loop(self):
        """LED Display Loop - supporting multiple functions."""
        clocktick = 0
        BIGNUM = 1000000
        while True:
            # Going to use an index counter as a pseudo clock tick for
            # each LED module. It's going to continually increase through
            # each pass - and it's max value is a limiter on the number of LEDs
            # If each pass through this loop touches one LED ; then we need enough
            # clock cycles to cover every LED.
            clocktick = (clocktick + 1) % BIGNUM
            if self.led_mode == LedMode.METAR:
                led_color_dict = self.ledmode_metar(clocktick)
            if self.led_mode == LedMode.HEATMAP:
                led_color_dict = self.ledmode_heatmap(clocktick)
            if self.led_mode == LedMode.TEST:
                led_color_dict = self.ledmode_test(clocktick)
            if self.led_mode == LedMode.RABBIT:
                led_color_dict = self.ledmode_rabbit(clocktick)
            # debugging.info(f"LED Clocktick {clocktick}")
            self.update_ledstring(led_color_dict)
        return

    def update_ledstring(self, led_color_dict):
        """Iter across all the LEDs and set the color appropriately."""
        for ledindex, led_color in led_color_dict.items():
            self.setLedColor(ledindex, led_color)
        self.strip.setBrightness(self.LED_BRIGHTNESS)
        self.show()
        return

    def ledmode_test(self, clocktick):
        """Placeholder STUB"""
        # FIXME: Stub
        clocktick = clocktick  # Local scope ; no effect
        return {}

    def ledmode_heatmap(self, clocktick):
        """Placeholder STUB"""
        # FIXME: Stub
        clocktick = clocktick  # Local scope ; no effect
        return {}

    def ledmode_rabbit(self, clocktick):
        """Placeholder STUB"""
        # FIXME: Stub
        clocktick = clocktick  # Local scope ; no effect
        return {}

    def legend_color(self, airportwxsrc, cycle_num):
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
        for led_index in range(self.strip.numPixels()):
            led_updated_dict[led_index] = utils_colors.off()

        cycle_num = clocktick % len(self.cycles)

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

    # Turn on or off all the lights using the same color.
    def allonoff_wipes(self, color, wait):
        for led_pin in range(self.strip.numPixels()):
            if str(led_pin) in self.nullpins:
                # exclude NULL and LGND pins from wipe
                self.setLedColor(led_pin, utils_colors.black())
            else:
                self.setLedColor(led_pin, color)
        self.strip.show()
        time.sleep(wait)
