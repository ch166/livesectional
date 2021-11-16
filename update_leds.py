#!/usr/bin/python3
# metar-v4.py - by Mark Harris. Capable of displaying METAR data, TAF or MOS data. Using a rotary switch to select 1 of 12 positions
#    Updated to run under Python 3.7
#    Added Sleep Timer routine to turn-off map at night if desired.
#    Added the ability to display TAF or MOS data along with METAR's
#    Note: MOS data is only available for United States, Puerto Rico, and the U.S. Virgin Islands.
#    The timeframe of the TAF, MOS data to display can be selected via the rotary switch. A switch with up to 12 positions can be used.
#    If no Rotary Switch is used, this script's config will set default data to display.
#    Added routine by by Nick Cirincione to decode flight category if flight category is not provided by the FAA.
#    Fixed bug that wouldn't allow the last airport to be 'NULL' without causing all LED's to show white.
#    Added auto restart when config.py is changed, so settings will be automatically re-loaded.
#    Added internet availability check and retry if necessary. This should help when power is disrupted and board reboots before router does.
#    Added Logging capabilities which is stored in /NeoSectional/logs/logfile.log with 3 backup files for older logfile data.
#    Added ability to specify specific LED pins to reverse the normal rgb_grb setting. For mixing models of LED strings.
#    Added a Heat Map of what airports the user has landed at. Not available through Rotary switch. Only Web interface.
#    Added new wipes, some based on lat/lon of airports
#    Fixed bug where wipes would execute twice on map startup.
#    Added admin.py for behinds the scenes variables to be stored. i.e. use_mos=1 to determine if bash files should or should not download MOS data.
#    Added ability to detect a Rotary Switch is NOT installed and react accordingly.
#    Added logging of Current RPI IP address whenever FAA weather update is retrieved
#    Fixed bug where TAF XML reports OVC without a cloud level agl. It uses vert_vis_ft as a backup.
#    Fixed bug when debug mode is changed to 'Debug'.
#    Switch Version control over to Github at https://github.com/markyharris/livesectional
#    Fixed METAR Decode routine to handle FAA results that don't include flight_category and forecast fields.
#    Added routine to check time and reboot each night if setting in admin.py are set accordingly.
#    Fixed bug that missed lowest sky_condition altitude on METARs not reporting flight categories.

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

# RPI GPIO Pinouts reference
###########################
#    3V3  (1) (2)  5V     #
#  GPIO2  (3) (4)  5V     #
#  GPIO3  (5) (6)  GND    #
#  GPIO4  (7) (8)  GPIO14 #
#    GND  (9) (10) GPIO15 #
# GPIO17 (11) (12) GPIO18 #
# GPIO27 (13) (14) GND    #
# GPIO22 (15) (16) GPIO23 #
#    3V3 (17) (18) GPIO24 #
# GPIO10 (19) (20) GND    #
#  GPIO9 (21) (22) GPIO25 #
# GPIO11 (23) (24) GPIO8  #
#    GND (25) (26) GPIO7  #
#  GPIO0 (27) (28) GPIO1  #
#  GPIO5 (29) (30) GND    #
#  GPIO6 (31) (32) GPIO12 #
# GPIO13 (33) (34) GND    #
# GPIO19 (35) (36) GPIO16 #
# GPIO26 (37) (38) GPIO20 #
#    GND (39) (40) GPIO21 #
###########################

# Import needed libraries
import urllib.request
import urllib.error
import urllib.parse
import socket
import xml.etree.ElementTree as ET
import time
from datetime import datetime
from datetime import timedelta
from datetime import time as time_
from rpi_ws281x import *  # works with python 3.7. sudo pip3 install rpi_ws281x
import sys
import os
from os.path import getmtime
import RPi.GPIO as GPIO
import collections
import re
# import logging
# import logzero #had to manually install logzero. https://logzero.readthedocs.io/en/latest/
# from logzero import logger
import config  # Config.py holds user settings used by the various scripts
import admin

import debugging
import utils


class updateLEDs:

    def __init__(self, conf):
        # Setup rotating logfile with 3 rotations, each with a maximum filesize of 1MB:
        self.version = admin.version  # Software version
        # self.loglevel = config.loglevel
        # self.loglevels = [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR]
        # self.logzero.loglevel(self.loglevels[self.loglevel])   #Choices in order; DEBUG, INFO, WARNING, ERROR
        # self.logzero.logfile("/NeoSectional/logs/logfile.log", maxBytes=1e6, backupCount=3)
        # self.debugging.info("\n\nStartup of metar-v4.py Script, Version " + self.version)
        # self.debugging.info("Log Level Set To: " + str(self.loglevels[self.loglevel]))

        # ****************************************************************************
        # * User defined items to be set below - Make changes to config.py, not here *
        # ****************************************************************************

        # Current Time Tracker
        self.currentzulu = ""

        # Local access to configuration data

        self.conf = conf
        self.cat = ""

        # list of pins that need to reverse the rgb_grb setting. To accommodate two different models of LED's are used.
        # self.rev_rgb_grb = config.rev_rgb_grb        #[] #['1', '2', '3', '4', '5', '6', '7', '8']

        # Specific Variables to default data to display if Rotary Switch is not installed.
        # hour_to_display #Offset in HOURS to choose which TAF/MOS to display
        self.hour_to_display = config.time_sw0
        # metar_taf_mos    #0 = Display TAF, 1 = Display METAR, 2 = Display MOS, 3 = Heat Map (Heat map not controlled by rotary switch)
        self.metar_taf_mos = config.data_sw0
        # Set toggle_sw to an initial value that forces rotary switch to dictate data displayed
        self.toggle_sw = -1
        self.toggle = ""

        self.root = ""

        # MOS/TAF Config settings
        # self.prob = config.prob                      #probability threshhold in Percent to assume reported weather will be displayed on map or not. MOS Only.

        # Heat Map settings
        # self.bin_grad = config.bin_grad              #0 = Binary display, 1 = Gradient display
        # self.fade_yesno = config.fade_yesno          #0 = No, 1 = Yes, if using gradient display, fade in/out the home airport color. will override use_homeap.
        # self.use_homeap = config.use_homeap          #0 = No, 1 = Yes, Use a separate color to denote home airport.
        # delay in fading the home airport if used
        self.fade_delay = conf.get_float("rotaryswitch", "fade_delay")

        # MOS Config settings
        # self.prob = config.prob                      #probability threshhold in Percent to assume reported weather will be displayed on map or not.

        # Specific settings for on/off timer. Used to turn off LED's at night if desired.
        # Verify Raspberry Pi is set to the correct time zone, otherwise the timer will be off.
        # self.usetimer = config.usetimer              #0 = No, 1 = Yes. Turn the timer on or off with this setting
        self.offhour = config.offhour  # Use 24 hour time. Set hour to turn off display
        self.offminutes = config.offminutes  # Set minutes to turn off display
        self.onhour = config.onhour  # Use 24 hour time. Set hour to turn on display
        self.onminutes = config.onminutes  # Set minutes to on display
        # Set number of MINUTES to turn map on temporarily during sleep mode
        self.tempsleepon = config.tempsleepon

        # Number of LED pixels. Change this value to match the number of LED's being used on map
        self.LED_COUNT = config.LED_COUNT

        # 1 = Yes, 0 = No. Blink the LED for high wind Airports.
        self.hiwindblink = config.hiwindblink
        # 1 = Yes, 0 = No. Flash the LED for an airport reporting severe weather like TSRA.
        self.lghtnflash = config.lghtnflash
        # 1 = Yes, 0 = No. Change colors to denote rain reported.
        self.rainshow = config.rainshow
        # 1 = Yes, 0 = No. Change colors to denote freezing rain reported.
        self.frrainshow = config.frrainshow
        # 1 = Yes, 0 = No. Change colors to denote snow reported.
        self.snowshow = config.snowshow
        # 1 = Yes, 0 = No. Change colors to denote dust, sand, or ash reported.
        self.dustsandashshow = config.dustsandashshow
        # 1 = Yes, 0 = No. Change colors to denote fog reported.
        self.fogshow = config.fogshow
        # 1 = Yes, 0 = No. Turn on/off home airport feature. The home airport will use a marker color on every other pass
        self.homeport = config.homeport

        # if 'homeport = 1' be sure to set these variables appropriately
        # Pin number of the home airport to display a marker color every other pass
        self.homeport_pin = config.homeport_pin
        # 2 = no color change, 1 = changing colors - user defined below by homeport_colors[], 0 = Solid color denoted by homeport_color below.
        self.homeport_display = config.homeport_display
        # Percentage of brightness to dim all other airports if homeport is being used. 0 = No dimming. 100 = completely off
        self.dim_value = config.dim_value

        # Misc settings
        # 0 = No, 1 = Yes, use wipes. Defined by configurator
        self.usewipes = config.usewipes
        # 1 = RGB color codes. 0 = GRB color codes. Populate color codes below with normal RGB codes and script will change if necessary
        self.rgb_grb = config.rgb_grb
        # In Knots. Any speed at or above will flash the LED for the appropriate airport if hiwindblink=1
        self.max_wind_speed = config.max_wind_speed
        # Number of MINUTES between FAA updates - 15 minutes is a good compromise. A pushbutton switch can be used to force update.
        self.update_interval = config.update_interval
        # Range is 0 - 255. This sets the value of LED brightness when light sensor detects low ambient light. Independent of homeport dimming.
        self.dimmed_value = config.dimmed_value
        # Range is 0 - 255. This sets the value of LED brightness when light sensor detects high ambient light
        self.bright_value = config.bright_value
        # Metar Age in HOURS. This will pull the latest metar that has been published within the timeframe listed here.
        self.metar_age = config.metar_age
        # If no Metar has been published within this timeframe, the LED will default to the color specified by color_nowx.
        # Used to determine if board should reboot every day at time set in setting below.
        self.use_reboot = admin.use_reboot
        # 24 hour time in this format, '2400' = midnight. Change these 2 settings in the admin.py file if desired.
        self.time_reboot = admin.time_reboot
        # Check to be sure Autorun on reboot is set to yes.
        self.autorun = config.autorun

        # Set Colors in RGB. Change numbers in paranthesis as desired. The order should be (Red,Green,Blue). This setup works for the WS2812 model of LED strips.
        # WS2811 strips uses GRB colors, so change "rgb_grb = 0" above if necessary. Range is 0-255. (https://www.rapidtables.com/web/color/RGB_Color.html)
        self.color_vfr = config.color_vfr  # Full bright Green for VFR
        self.color_mvfr = config.color_mvfr  # Full bright Blue for MVFR
        self.color_ifr = config.color_ifr  # Full bright Red for IFR
        self.color_lifr = config.color_lifr  # Full bright Magenta for LIFR
        self.color_nowx = config.color_nowx  # No weather for NO WX
        self.color_black = config.color_black  # Black/Off
        # Full bright Yellow to represent lightning strikes
        self.color_lghtn = config.color_lghtn
        self.color_snow1 = config.color_snow1  # White for Snow etc.
        self.color_snow2 = config.color_snow2  # Grey for Snow etc.
        self.color_rain1 = config.color_rain1  # Dark Blue for Rain etc.
        self.color_rain2 = config.color_rain2  # Blue for rain etc.
        self.color_frrain1 = config.color_frrain1  # Light Purple
        # Purple for freezing rain etc.
        self.color_frrain2 = config.color_frrain2
        self.color_dustsandash1 = config.color_dustsandash1  # Tan/Brown for Dust and Sand
        self.color_dustsandash2 = config.color_dustsandash2  # Dark Brown for Dust and Sand
        self.color_fog1 = config.color_fog1  # Silver for Fog
        self.color_fog2 = config.color_fog2  # Silver for Fog
        # Color to denote home airport every other LED cycle. Used if 'homeport_display = 0'
        self.color_homeport = config.color_homeport
        # if 'homeport_display=1'. Change these colors as desired.
        self.homeport_colors = config.homeport_colors

        # Legend on/off. The setting 'legend' must be set to 1 for any legend LED's to be enabled. But you can disable the other
        # legend types by defining it with a 0. No legend LED's, 5 basic legends LED's, 6, 7, 8, 9, 10, 11 or 12 total legend LED's can be used.
        # 1 = Yes, 0 = No. Provides for basic vfr, mvfr, ifr, lifr, nowx legend. If 'legend=0' then no legends will be enabled.
        self.legend = config.legend
        # 1 = Yes, 0 = No. With this enabled high winds legend will be displayed.
        self.legend_hiwinds = config.legend_hiwinds
        # 1 = Yes, 0 = No. With this enabled Lightning/Thunderstorm legend will be displayed as well
        self.legend_lghtn = config.legend_lghtn
        self.legend_snow = config.legend_snow  # 1 = Yes, 0 = No. Snow legend
        self.legend_rain = config.legend_rain  # 1 = Yes, 0 = No. Rain legend
        # 1 = Yes, 0 = No. Freezing Rain legend
        self.legend_frrain = config.legend_frrain
        # 1 = Yes, 0 = No. Dust, Sand and/or Ash legend
        self.legend_dustsandash = config.legend_dustsandash
        self.legend_fog = config.legend_fog  # 1 = Yes, 0 = No. Fog legend

        # Legend Pins assigned if used. Be sure that the 'airports' file has 'LGND' at these LED positions otherwise the legend will not display properly.
        self.leg_pin_vfr = config.leg_pin_vfr  # Set LED pin number for VFR Legend LED
        # Set LED pin number for MVFR Legend LED
        self.leg_pin_mvfr = config.leg_pin_mvfr
        self.leg_pin_ifr = config.leg_pin_ifr  # Set LED pin number for IFR Legend LED
        # Set LED pin number for LIFR Legend LED
        self.leg_pin_lifr = config.leg_pin_lifr
        # Set LED pin number for No Weather Legend LED
        self.leg_pin_nowx = config.leg_pin_nowx
        # Set LED pin number for High Winds Legend LED
        self.leg_pin_hiwinds = config.leg_pin_hiwinds
        # Set LED pin number for Thunderstorms Legend LED
        self.leg_pin_lghtn = config.leg_pin_lghtn
        # Set LED pin number for Snow Legend LED
        self.leg_pin_snow = config.leg_pin_snow
        # Set LED pin number for Rain Legend LED
        self.leg_pin_rain = config.leg_pin_rain
        # Set LED pin number for Freezing Rain Legend LED
        self.leg_pin_frrain = config.leg_pin_frrain
        # Set LED pin number for Dust/Sand/Ash Legend LED
        self.leg_pin_dustsandash = config.leg_pin_dustsandash
        self.leg_pin_fog = config.leg_pin_fog  # Set LED pin number for Fog Legend LED

        # ************************************************************
        # * End of User defined settings. Normally shouldn't change  *
        # * any thing under here unless you are confident in change. *
        # ************************************************************

        # 0 = do not turn refresh off, 1 = turn off the blanking refresh of the LED string between FAA updates.
        self.turnoffrefresh = 1

        # LED Cycle times - Can change if necessary.
        # These cycle times all added together will equal the total amount of time the LED takes to finish displaying one cycle.
        self.cycle0_wait = .9
        # Each  cycle, depending on flight category, winds and weather reported will have various colors assigned.
        self.cycle1_wait = .9
        # For instance, VFR with 20 kts winds will have the first 3 cycles assigned Green and the last 3 Black for blink effect.
        self.cycle2_wait = .08
        # The cycle times then reflect how long each color cycle will stay on, producing blinking or flashing effects.
        self.cycle3_wait = .1
        # Lightning effect uses the short intervals at cycle 2 and cycle 4 to create the quick flash. So be careful if you change them.
        self.cycle4_wait = .08
        self.cycle5_wait = .5

        # List of METAR weather categories to designate weather in area. Many Metars will report multiple conditions, i.e. '-RA BR'.
        # The code pulls the first/main weather reported to compare against the lists below. In this example it uses the '-RA' and ignores the 'BR'.
        # See https://www.aviationweather.gov/metar/symbol for descriptions. Add or subtract codes as desired.
        #Thunderstorm and lightning
        self.wx_lghtn_ck = ["TS", "TSRA", "TSGR", "+TSRA",
                            "TSRG", "FC", "SQ", "VCTS", "VCTSRA", "VCTSDZ", "LTG"]
        # Snow in various forms
        self.wx_snow_ck = ["BLSN", "DRSN", "-RASN", "RASN", "+RASN", "-SN", "SN", "+SN",
                           "SG", "IC", "PE", "PL", "-SHRASN", "SHRASN", "+SHRASN", "-SHSN", "SHSN", "+SHSN"]
        # Rain in various forms
        self.wx_rain_ck = ["-DZ", "DZ", "+DZ", "-DZRA", "DZRA", "-RA",
                           "RA", "+RA", "-SHRA", "SHRA", "+SHRA", "VIRGA", "VCSH"]
        # Freezing Rain
        self.wx_frrain_ck = ["-FZDZ", "FZDZ",
                             "+FZDZ", "-FZRA", "FZRA", "+FZRA"]
        # Dust Sand and/or Ash
        self.wx_dustsandash_ck = ["DU", "SA", "HZ", "FU",
                                  "VA", "BLDU", "BLSA", "PO", "VCSS", "SS", "+SS", ]
        # Fog
        self.wx_fog_ck = ["BR", "MIFG", "VCFG", "BCFG", "PRFG", "FG", "FZFG"]

        # list definitions
        # Used to create weather designation effects.
        self.cycle_wait = [self.cycle0_wait, self.cycle1_wait, self.cycle2_wait,
                           self.cycle3_wait, self.cycle4_wait, self.cycle5_wait]
        self.cycles = [0, 1, 2, 3, 4, 5]  # Used as a index for the cycle loop.
        self.legend_pins = [self.leg_pin_vfr, self.leg_pin_mvfr, self.leg_pin_ifr, self.leg_pin_lifr, self.leg_pin_nowx, self.leg_pin_hiwinds, self.leg_pin_lghtn,
                            self.leg_pin_snow, self.leg_pin_rain, self.leg_pin_frrain, self.leg_pin_dustsandash, self.leg_pin_fog]  # Used to build legend display

        # Setup for IC238 Light Sensor for LED Dimming, does not need to be commented out if sensor is not used, map will remain at full brightness.
        # For more info on the sensor visit; http://www.uugear.com/portfolio/using-light-sensor-module-with-raspberry-pi/

        # set mode to BCM and use BCM pin numbering, rather than BOARD pin numbering.
        GPIO.setmode(GPIO.BCM)
        # set pin 4 as input for light sensor, if one is used. If no sensor used board remains at high brightness always.
        GPIO.setup(4, GPIO.IN)
        # set pin 22 to momentary push button to force FAA Weather Data update if button is used.
        GPIO.setup(22, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # Setup GPIO pins for rotary switch to choose between Metars, or Tafs and which hour of TAF
        # Not all the pins are required to be used. If only METARS are desired, then no Rotary Switch is needed.
        # set pin 0 to ground for METARS
        GPIO.setup(0, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 5 to ground for TAF + 1 hour
        GPIO.setup(5, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 6 to ground for TAF + 2 hours
        GPIO.setup(6, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 13 to ground for TAF + 3 hours
        GPIO.setup(13, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 19 to ground for TAF + 4 hours
        GPIO.setup(19, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 26 to ground for TAF + 5 hours
        GPIO.setup(26, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 21 to ground for TAF + 6 hours
        GPIO.setup(21, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 20 to ground for TAF + 7 hours
        GPIO.setup(20, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 16 to ground for TAF + 8 hours
        GPIO.setup(16, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 12 to ground for TAF + 9 hours
        GPIO.setup(12, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 1 to ground for TAF + 10 hours
        GPIO.setup(1, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        # set pin 7 to ground for TAF + 11 hours
        GPIO.setup(7, GPIO.IN, pull_up_down=GPIO.PUD_UP)

        # LED strip configuration:
        self.LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).
        # LED signal frequency in hertz (usually 800khz)
        self.LED_FREQ_HZ = 800000
        self.LED_DMA = 5  # DMA channel to use for generating signal (try 5)
        # True to invert the signal (when using NPN transistor level shift)
        self.LED_INVERT = False
        self.LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
        self.LED_STRIP = ws.WS2811_STRIP_GRB  # Strip type and color ordering
        # 255    #starting brightness. It will be changed below.
        self.LED_BRIGHTNESS = self.bright_value

        # Setup paths for restart on change routine. Routine from;
        # https://blog.petrzemek.net/2014/03/23/restarting-a-python-script-within-itself
        self.LOCAL_CONFIG_FILE_PATH = '/NeoSectional/config.py'
        self.WATCHED_FILES = [self.LOCAL_CONFIG_FILE_PATH, __file__]
        self.WATCHED_FILES_MTIMES = [(f, getmtime(f))
                                     for f in self.WATCHED_FILES]
        debugging.info(
            'Watching ' + self.LOCAL_CONFIG_FILE_PATH + ' For Change')

        # Timer calculations
        self.now = datetime.now()  # Get current time and compare to timer setting
        self.lights_out = time_(self.conf.get_int("schedule", "offhour"),
                                self.conf.get_int("schedule", "offminutes"), 0)
        self.timeoff = self.lights_out
        self.lights_on = time_(self.onhour, self.onminutes, 0)
        self.end_time = self.lights_on
        # Number of seconds to delay before retrying to connect to the internet.
        self.delay_time = 10
        # Set flag for next round if sleep timer is interrupted by button push.
        self.temp_lights_on = 0

        # MOS Data Settings
        # location of the downloaded local MOS file.
        self.mos_filepath = '/NeoSectional/data/GFSMAV'
        self.categories = ['HR', 'CLD', 'WDR', 'WSP', 'P06',
                           'T06', 'POZ', 'POS', 'TYP', 'CIG', 'VIS', 'OBV']
        self.obv_wx = {'N': 'None', 'HZ': 'HZ', 'BR': 'RA',
                       'FG': 'FG', 'BL': 'HZ'}  # Decode from MOS to TAF/METAR
        # Decode from MOS to TAF/METAR
        self.typ_wx = {'S': 'SN', 'Z': 'FZRA', 'R': 'RA'}
        # Outer Dictionary, keyed by airport ID
        self.mos_dict = collections.OrderedDict()
        # Middle Dictionary, keyed by hour of forcast. Will contain a list of data for categories.
        self.hour_dict = collections.OrderedDict()
        # Used to determine that an airport from our airports file is currently being read.
        self.ap_flag = 0

        # Used by Heat Map. Do not change - assumed by routines below.
        self.low_visits = (0, 0, 255)  # Start with Blue - Do Not Change
        # Increment to Red as visits get closer to 100 - Do Not Change
        self.high_visits = (255, 0, 0)
        self.fadehome = -1  # start with neg number
        self.homeap = self.color_vfr  # If 100, then home airport - designate with Green
        # color_fog2                     #(10, 10, 10)        #dk grey to denote airports never visited
        self.no_visits = (20, 20, 20)
        self.black = self.color_black  # (0,0,0)

        # Misc Settings
        # Toggle used for logging when ambient sensor changes from bright to dim.
        self.ambient_toggle = 0

        debugging.info("metar-v4.py Settings Loaded")

        # Create an instance of NeoPixel
        self.strip = Adafruit_NeoPixel(self.LED_COUNT,
                                       self.LED_PIN,
                                       self.LED_FREQ_HZ,
                                       self.LED_DMA,
                                       self.LED_INVERT,
                                       self.LED_BRIGHTNESS,
                                       self.LED_CHANNEL,
                                       self.LED_STRIP)
        self.strip.begin()

    # Functions

    def turnoff(self, strip):
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0, 0, 0))
        self.strip.show()

    # Reduces the brightness of the colors for every airport except for the "homeport_pin" designated airport, which remains at the brightness set by
    # "bright_value" above in user setting. "data" is the airport color to display and "value" is the percentage of the brightness to be dimmed.
    # For instance if full bright white (255,255,255) is provided and the desired dimming is 50%, then the color returned will be (128,128,128),
    # or half as bright. The dim_value is set in the user defined area.
    def dim(self, data, value):
        red = data[0] - ((value * data[0])/100)
        if red < 0:
            red = 0

        grn = data[1] - ((value * data[1])/100)
        if grn < 0:
            grn = 0

        blu = data[2] - ((value * data[2])/100)
        if blu < 0:
            blu = 0

        data = [red, grn, blu]
        return data

    # Change color code to work with various led strips. For instance, WS2812 model strip uses RGB where WS2811 model uses GRB
    # Set the "rgb_grb" user setting above. 1 for RGB LED strip, and 0 for GRB strip.
    # If necessary, populate the list rev_rgb_grb with pin numbers of LED's that use the opposite color scheme.
    def rgbtogrb(self, pin, data, order=0):
        # rev_rgb_grb #list of pins that need to use the reverse of the normal order setting.
        # This accommodates the use of both models of LED strings on one map.
        if str(pin) in self.conf.get_string("lights", "rev_rgb_grb"):
            order = not order
            debugging.info(
                'Reversing rgb2grb Routine Output for PIN ' + str(pin))

        red = data[0]
        grn = data[1]
        blu = data[2]

        if order:
            data = [red, grn, blu]
        else:
            data = [grn, red, blu]
        return data

    # Compare current time plus offset to TAF's time period and return difference
    def comp_time(self, taf_time):
        # global current_zulu
        datetimeFormat = ('%Y-%m-%dT%H:%M:%SZ')
        date1 = taf_time
        date2 = self.current_zulu
        diff = datetime.strptime(date1, datetimeFormat) - \
            datetime.strptime(date2, datetimeFormat)
        diff_minutes = int(diff.seconds/60)
        diff_hours = int(diff_minutes/60)
        return diff.seconds, diff_minutes, diff_hours, diff.days

    # See if a time falls within a range
    def time_in_range(self, start, end, x):
        if start <= end:
            return start <= x <= end
        else:
            return start <= x or x <= end

    # Used by MOS decode routine. This routine builds mos_dict nested with hours_dict
    def set_data(self):
        # global hour_dict
        # global mos_dict
        # global dat0, dat1, dat2, dat3, dat4, dat5, dat6, dat7
        # global apid
        # global temp
        # global keys

        # Clean up line of MOS data.
        # this check is unneeded. Put here to vary length of list to clean up.
        if len(self.temp) >= 0:
            temp1 = []
            tmp_sw = 0

            for val in self.temp:  # Check each item in the list
                val = val.lstrip()  # remove leading white space
                val = val.rstrip('/')  # remove trailing /

                if len(val) == 6:  # this is for T06 to build appropriate length list
                    # add a '0' to the front of the list. T06 doesn't report data in first 3 hours.
                    temp1.append('0')
                    # add back the original value taken from T06
                    temp1.append(val)
                    # Turn on switch so we don't go through it again.
                    tmp_sw = 1

                # and tmp_sw == 0: #if item is 1 or 2 chars long, then bypass. Otherwise fix.
                elif len(val) > 2 and tmp_sw == 0:
                    pos = val.find('100')  # locate first 100
                    # capture the first value which is not a 100
                    tmp = val[0:pos]
                    temp1.append(tmp)  # and store it in temp list.

                    k = 0
                    for j in range(pos, len(val), 3):  # now iterate through remainder
                        temp1.append(val[j:j+3])  # and capture all the 100's
                        k += 1
                else:
                    temp1.append(val)  # Store the normal values too.

            self.temp = temp1

        # load data into appropriate lists by hours designated by current MOS file
        # clean up data by removing '/' and spaces
        self.temp0 = ([x.strip() for x in self.temp[0].split('/')])
        self.temp1 = ([x.strip() for x in self.temp[1].split('/')])
        self.temp2 = ([x.strip() for x in self.temp[2].split('/')])
        self.temp3 = ([x.strip() for x in self.temp[3].split('/')])
        self.temp4 = ([x.strip() for x in self.temp[4].split('/')])
        self.temp5 = ([x.strip() for x in self.temp[5].split('/')])
        self.temp6 = ([x.strip() for x in self.temp[6].split('/')])
        self.temp7 = ([x.strip() for x in self.temp[7].split('/')])

        # build a list for each data group. grab 1st element [0] in list to store.
        self.dat0.append(self.temp0[0])
        self.dat1.append(self.temp1[0])
        self.dat2.append(self.temp2[0])
        self.dat3.append(self.temp3[0])
        self.dat4.append(self.temp4[0])
        self.dat5.append(self.temp5[0])
        self.dat6.append(self.temp6[0])
        self.dat7.append(self.temp7[0])

        j = 0
        for key in self.keys:  # add cat data to the hour_dict by hour

            if j == 0:
                self.hour_dict[key] = self.dat0
            elif j == 1:
                self.hour_dict[key] = self.dat1
            elif j == 2:
                self.hour_dict[key] = self.dat2
            elif j == 3:
                self.hour_dict[key] = self.dat3
            elif j == 4:
                self.hour_dict[key] = self.dat4
            elif j == 5:
                self.hour_dict[key] = self.dat5
            elif j == 6:
                self.hour_dict[key] = self.dat6
            elif j == 7:
                self.hour_dict[key] = self.dat7
            j += 1

            # marry the hour_dict to the proper key in mos_dict
            self.mos_dict[apid] = self.hour_dict

    # For Heat Map. Based on visits, assign color. Using a 0 to 100 scale where 0 is never visted and 100 is home airport.
    # Can choose to display binary colors with homeap.
    def assign_color(self, visits):
        if visits == '0':
            color = self.no_visits

        elif visits == '100':
            if self.conf.get_bool("rotaryswitch", "fade_yesno") and self.conf.get_bool("rotaryswitch", "bin_grad"):
                color = self.black
            elif self.conf.get_bool("rotaryswitch", "use_homeap") == False:
                color = self.high_visits
            else:
                color = self.homeap

        elif '1' <= visits <= '50':  # Working
            if self.conf.get_bool("rotaryswitch", "bin_grad"):
                red = self.low_visits[0]
                grn = self.low_visits[1]
                blu = self.low_visits[2]
                red = int(int(visits) * 5.1)
                color = (red, grn, blu)
            else:
                color = self.high_visits

        elif '51' <= visits <= '99':  # Working
            if self.conf.get_bool("rotaryswitch", "bin_grad"):
                red = self.high_visits[0]
                grn = self.high_visits[1]
                blu = self.high_visits[2]
                blu = (255 - int((int(visits)-50) * 5.1))
                color = (red, grn, blu)
            else:
                color = self.high_visits

        else:
            color = self.black

        return color

    def load_airports(self):
        # read airports file - read each time weather is updated in case a change to "airports" file was made while script was running.
        try:
            with open('/NeoSectional/data/airports') as f:
                self.airports = f.readlines()
        except IOError as error:
            debugging.error('Airports file could not be loaded.')
            debugging.error(error)
            return False

        self.airports = [x.strip() for x in self.airports]
        debugging.info('Airports File Loaded')
        return True


    def wipe_displays(self):
        # Call script and execute desired wipe(s) while data is being updated.
        # FIXME to make this imported
        if self.usewipes == 1 and self.toggle_sw != -1:
            # Get latest ip's to display in editors
            # FIXME: Move wipes-v4 to be an included module, call here
            exec(compile(open("/NeoSectional/wipes-v4.py", "rb").read(),
                         "/NeoSectional/wipes-v4.py", 'exec'))
            debugging.info("Calling wipes script")
        return True


    def check_heat_map(self, stationiddict, windsdict, wxstringdict):
        # MOS decode routine
        # MOS data is downloaded daily from; https://www.weather.gov/mdl/mos_gfsmos_mav to the local drive by crontab scheduling.
        # Then this routine reads through the entire file looking for those airports that are in the airports file. If airport is
        # found, the data needed to display the weather for the next 24 hours is captured into mos_dict, which is nested with
        # hour_dict, which holds the airport's MOS data by 3 hour chunks. See; https://www.weather.gov/mdl/mos_gfsmos_mavcard for
        # a breakdown of what the MOS data looks like and what each line represents.
        if self.metar_taf_mos == 2:
            debugging.info("Starting MOS Data Display")
            # Read current MOS text file
            try:
                file = open(self.mos_filepath, 'r')
                lines = file.readlines()
            except IOError as error:
                debugging.error('MOS data file could not be loaded.')
                debugging.error(error)
                return error

            for line in lines:  # read the MOS data file line by line0
                line = str(line)

                # Ignore blank lines of MOS airport
                if line.startswith('     '):
                    ap_flag = 0
                    continue

                # Check for and grab date of MOS
                if 'DT /' in line:
                    unused, dt_cat, month, unused, unused, day, unused = line.split(
                        " ", 6)
                    continue

                # Check for and grab the Airport ID of the current MOS
                if 'MOS' in line:
                    unused, apid, mos_date = line.split(" ", 2)

                    # If this Airport ID is in the airports file then grab all the info needed from this MOS
                    if apid in self.airports:
                        ap_flag = 1
                        # used to determine if a category is being reported in MOS or not. If not, need to inject it.
                        cat_counter = 0
                        self.dat0, self.dat1, self.dat2, self.dat3, self.dat4, self.dat5, self.dat6, self.dat7 = (
                            [] for i in range(8))  # Clear lists
                    continue

                # If we just found an airport that is in our airports file, then grab the appropriate weather data from it's MOS
                if ap_flag:
                    # capture the category the line read represents
                    xtra, cat, value = line.split(" ", 2)
                    # Check if the needed categories are being read and if so, grab its data
                    if self.cat in self.categories:
                        cat_counter += 1  # used to check if a category is not in mos report for airport
                        if self.cat == 'HR':  # hour designation
                            # grab all the hours from line read
                            temp = (re.findall(
                                r'\s?(\s*\S+)', value.rstrip()))
                            for j in range(8):
                                tmp = temp[j].strip()
                                # create hour dictionary based on mos data
                                self.hour_dict[tmp] = ''
                            # Get the hours which are the keys in this dict, so they can be properly poplulated
                            self.keys = list(self.hour_dict.keys())

                        else:
                            # Checking for missing lines of data and x out if necessary.
                            if (cat_counter == 5 and self.cat != 'P06')\
                                    or (cat_counter == 6 and self.cat != 'T06')\
                                    or (cat_counter == 7 and self.cat != 'POZ')\
                                    or (cat_counter == 8 and self.cat != 'POS')\
                                    or (cat_counter == 9 and self.cat != 'TYP'):

                                # calculate the number of consecutive missing cats and inject 9's into those positions
                                a = self.categories.index(self.last_cat)+1
                                b = self.categories.index(cat)+1
                                c = b - a - 1
                                debugging.debug(
                                    apid, self.last_cat, cat, a, b, c)

                                for j in range(c):
                                    temp = ['9', '9', '9', '9', '9', '9', '9', '9', '9',
                                            '9', '9', '9', '9', '9', '9', '9', '9', '9', '9']
                                    self.set_data()
                                    cat_counter += 1

                                # Now write the orignal cat data read from the line in the mos file
                                cat_counter += 1
                                # clear out hour_dict for next airport
                                self.hour_dict = collections.OrderedDict()
                                self.last_cat = self.cat
                                # add the actual line of data read
                                temp = (re.findall(
                                    r'\s?(\s*\S+)', value.rstrip()))
                                self.set_data()
                                # clear out hour_dict for next airport
                                self.hour_dict = collections.OrderedDict()

                            else:
                                # continue to decode the next category data that was read.
                                # store what the last read cat was.
                                self.last_cat = self.cat
                                temp = (re.findall(
                                    r'\s?(\s*\S+)', value.rstrip()))
                                self.set_data()
                                # clear out hour_dict for next airport
                                self.hour_dict = collections.OrderedDict()

            # Now grab the data needed to display on map. Key: [airport][hr][j] - using nested dictionaries
            #   airport = from airport file, 4 character ID. hr = 1 of 8 three-hour periods of time, 00 03 06 09 12 15 18 21
            #   j = index to weather categories, in this order; 'CLD','WDR','WSP','P06', 'T06', 'POZ', 'POS', 'TYP','CIG','VIS','OBV'.
            #   See; https://www.weather.gov/mdl/mos_gfsmos_mavcard for description of available data.
            for airport in self.airports:
                if airport in self.mos_dict:
                    debugging.debug('\n' + airport)  # debug
                    debugging.debug(self.categories)  # debug

                    mos_time = int(self.current_hr_zulu) + \
                        self.hour_to_display
                    if mos_time >= 24:  # check for reset at 00z
                        mos_time = mos_time - 24

                    for hr in self.keys:
                        if int(hr) <= mos_time <= int(hr)+2.99:

                            cld = (self.mos_dict[airport][hr][0])
                            # make wind direction end in zero
                            wdr = (
                                self.mos_dict[airport][hr][1]) + '0'
                            wsp = (self.mos_dict[airport][hr][2])
                            p06 = (self.mos_dict[airport][hr][3])
                            t06 = (self.mos_dict[airport][hr][4])
                            poz = (self.mos_dict[airport][hr][5])
                            pos = (self.mos_dict[airport][hr][6])
                            typ = (self.mos_dict[airport][hr][7])
                            cig = (self.mos_dict[airport][hr][8])
                            vis = (self.mos_dict[airport][hr][9])
                            obv = (self.mos_dict[airport][hr][10])

                            debugging.debug(
                                mos_date + hr + cld + wdr + wsp + p06 + t06 + poz + pos + typ + cig + vis + obv)  # debug

                            # decode the weather for each airport to display on the livesectional map
                            flightcategory = "VFR"  # start with VFR as the assumption
                            # If the layer is OVC, BKN, set Flight category based on height of layer
                            if cld in ("OV", "BK"):

                                if cig <= '2':  # AGL is less than 500:
                                    flightcategory = "LIFR"

                                elif cig == '3':  # AGL is between 500 and 1000
                                    flightcategory = "IFR"
                                elif '4' <= cig <= '5':  # AGL is between 1000 and 3000:
                                    flightcategory = "MVFR"

                                elif cig >= '6':  # AGL is above 3000
                                    flightcategory = "VFR"

                            # Check visability too.
                            if flightcategory != "LIFR":  # if it's LIFR due to cloud layer, no reason to check any other things that can set fl$

                                if vis <= '2':  # vis < 1.0 mile:
                                    flightcategory = "LIFR"

                                elif '3' <= vis < '4':  # 1.0 <= vis < 3.0 miles:
                                    flightcategory = "IFR"

                                elif vis == '5' and flightcategory != "IFR":  # 3.0 <= vis <= 5.0 miles
                                    flightcategory = "MVFR"

                            debugging.debug(flightcategory + " |"),
                            debugging.debug(
                                'Windspeed = ' + wsp + ' | Wind dir = ' + wdr + ' |'),

                            # decode reported weather using probabilities provided.
                            if typ == '9':  # check to see if rain, freezing rain or snow is reported. If not use obv weather
                                # Get proper representation for obv designator
                                wx = self.obv_wx[obv]
                            else:
                                # Get proper representation for typ designator
                                wx = self.typ_wx[typ]

                                if wx == 'RA' and int(p06) < self.conf.get_int("rotaryswitch", "prob"):
                                    if obv != 'N':
                                        wx = self.obv_wx[obv]
                                    else:
                                        wx = 'NONE'

                                if wx == 'SN' and int(pos) < self.conf.get_int("rotaryswitch", "prob"):
                                    wx = 'NONE'

                                if wx == 'FZRA' and int(poz) < self.conf.get_int("rotaryswitch", "prob"):
                                    wx = 'NONE'

    #                            print (t06,apid) #debug
                                if t06 == '' or t06 is None:
                                    t06 = '0'

                                # check for thunderstorms
                                if int(t06) > self.conf.get_int("rotaryswitch", "prob"):
                                    wx = 'TSRA'
                                else:
                                    wx = 'NONE'

                            debugging.debug('Reported Weather = ' + wx)

                    # Connect the information from MOS to the board
                    stationId = airport

                    # grab wind speeds from returned MOS data
                    if wsp == None:  # if wind speed is blank, then bypass
                        windspeedkt = 0
                    elif wsp == '99':  # Check to see if MOS data is not reporting windspeed for this airport
                        windspeedkt = 0
                    else:
                        windspeedkt = int(wsp)

                    # grab Weather info from returned FAA data
                    if wx is None:  # if weather string is blank, then bypass
                        wxstring = "NONE"
                    else:
                        wxstring = wx

                    debugging.debug(
                        stationId + ", " + str(windspeedkt) + ", " + wxstring)  # debug

                    # Check for duplicate airport identifier and skip if found, otherwise store in dictionary. covers for dups in "airports" file
                    if stationId in stationiddict:
                        debugging.info(
                            stationId + " Duplicate, only saved first metar category")
                    else:
                        # build category dictionary
                        stationiddict[stationId] = flightcategory

                    if stationId in windsdict:
                        debugging.info(
                            stationId + " Duplicate, only saved the first winds")
                    else:
                        # build windspeed dictionary
                        windsdict[stationId] = windspeedkt

                    if stationId in wxstringdict:
                        debugging.info(
                            stationId + " Duplicate, only saved the first weather")
                    else:
                        # build weather dictionary
                        wxstringdict[stationId] = wxstring
            debugging.info("Decoded MOS Data for Display")
        return True


    def wx_display_loop(self, stationiddict, windsdict, wxstringdict):
        # "+str(display_num)+" Cycle Loop # "+str(loopcount)+": ",end="")
        print("\nWX Display")
        # Start main loop. This loop will create all the necessary colors to display the weather one time.
        # cycle through the strip 6 times, setting the color then displaying to create various effects.
        for cycle_num in self.cycles:
                    print(" " + str(cycle_num), end='')
                    sys.stdout.flush()

                    # Inner Loop. Increments through each LED in the strip setting the appropriate color to each individual LED.
                    i = 0
                    for airportcode in self.airports:

                        # Pull the next flight category from dictionary.
                        flightcategory = stationiddict.get(airportcode, "NONE")
                        # Pull the winds from the dictionary.
                        airportwinds = windsdict.get(airportcode, 0)
                        # Pull the weather reported for the airport from dictionary.
                        airportwx_long = wxstringdict.get(airportcode, "NONE")
                        # Grab only the first parameter of the weather reported.
                        airportwx = airportwx_long.split(" ", 1)[0]

                        # debug print out
                        if self.metar_taf_mos == 0:
                            debugging.debug(
                                "TAF Time +" + str(self.hour_to_display) + " Hour")
                        elif self.metar_taf_mos == 1:
                            debugging.debug("METAR")
                        elif self.metar_taf_mos == 2:
                            debugging.debug(
                                "MOS Time +" + str(self.hour_to_display) + " Hour")
                        elif self.metar_taf_mos == 3:
                            debugging.debug("Heat Map + ")

                        debugging.debug((airportcode + " " + flightcategory + " " + str(
                            airportwinds) + " " + airportwx + " " + str(cycle_num) + " "))  # debug

                        # Check to see if airport code is a NULL and set to black.
                        if airportcode == "NULL" or airportcode == "LGND":
                            color = self.color_black

                        # Build and display Legend. "legend" must be set to 1 in the user defined section and "LGND" set in airports file.
                        if self.legend and airportcode == "LGND" and (i in self.legend_pins):
                            if i == self.leg_pin_vfr:
                                color = self.color_vfr

                            if i == self.leg_pin_mvfr:
                                color = self.color_mvfr

                            if i == self.leg_pin_ifr:
                                color = self.color_ifr

                            if i == self.leg_pin_lifr:
                                color = self.color_lifr

                            if i == self.leg_pin_nowx:
                                color = self.color_nowx

                            if i == self.leg_pin_hiwinds and self.legend_hiwinds:
                                if (cycle_num == 3 or cycle_num == 4 or cycle_num == 5):
                                    color = self.color_black
                                else:
                                    color = self.color_ifr

                            if i == self.leg_pin_lghtn and self.legend_lghtn:
                                if (cycle_num == 2 or cycle_num == 4):  # Check for Thunderstorms
                                    color = self.color_lghtn

                                elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 3 or cycle_num == 5):
                                    color = self.color_mvfr

                            if i == self.leg_pin_snow and self.legend_snow:
                                if (cycle_num == 3 or cycle_num == 5):  # Check for Snow
                                    color = self.color_snow1

                                if (cycle_num == 4):
                                    color = self.color_snow2

                                elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                                    color = self.color_lifr

                            if i == self.leg_pin_rain and self.legend_rain:
                                if (cycle_num == 3 or cycle_num == 5):  # Check for Rain
                                    color = self.color_rain1

                                if (cycle_num == 4):
                                    color = self.color_rain2

                                elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                                    color = self.color_vfr

                            if i == self.leg_pin_frrain and self.legend_frrain:
                                if (cycle_num == 3 or cycle_num == 5):  # Check for Freezing Rain
                                    color = self.color_frrain1

                                if (cycle_num == 4):
                                    color = self.color_frrain2

                                elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                                    color = self.color_mvfr

                            if i == self.leg_pin_dustsandash and self.legend_dustsandash:
                                if (cycle_num == 3 or cycle_num == 5):  # Check for Dust, Sand or Ash
                                    color = self.color_dustsandash1

                                if (cycle_num == 4):
                                    color = self.color_dustsandash2

                                elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                                    color = self.color_vfr

                            if i == self.leg_pin_fog and self.legend_fog:
                                if (cycle_num == 3 or cycle_num == 5):  # Check for Fog
                                    color = self.color_fog1

                                if (cycle_num == 4):
                                    color = self.color_fog2

                                elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                                    color = self.color_ifr

                        # Start of weather display code for each airport in the "airports" file
                        # Check flight category and set the appropriate color to display
                        if flightcategory != "NONE":
                            if flightcategory == "VFR":  # Visual Flight Rules
                                color = self.color_vfr
                            elif flightcategory == "MVFR":  # Marginal Visual Flight Rules
                                color = self.color_mvfr
                            elif flightcategory == "IFR":  # Instrument Flight Rules
                                color = self.color_ifr
                            elif flightcategory == "LIFR":  # Low Instrument Flight Rules
                                color = self.color_lifr
                            else:
                                color = self.color_nowx

                        # 3.01 bug fix by adding "LGND" test
                        elif flightcategory == "NONE" and airportcode != "LGND" and airportcode != "NULL":
                            color = self.color_nowx  # No Weather reported.

                        # Check winds and set the 2nd half of cycles to black to create blink effect
                        if self.hiwindblink:  # bypass if "hiwindblink" is set to 0
                            if (int(airportwinds) >= self.max_wind_speed and (cycle_num == 3 or cycle_num == 4 or cycle_num == 5)):
                                color = self.color_black
                                # debug
                                print(("HIGH WINDS-> " + airportcode +
                                       " Winds = " + str(airportwinds) + " "))

                        # Check the wxstring from FAA for reported weather and create color changes in LED for weather effect.
                        if airportwx != "NONE":
                            if self.lghtnflash:
                                # Check for Thunderstorms
                                if (airportwx in self.wx_lghtn_ck and (cycle_num == 2 or cycle_num == 4)):
                                    color = self.color_lghtn

                            if self.snowshow:
                                # Check for Snow
                                if (airportwx in self.wx_snow_ck and (cycle_num == 3 or cycle_num == 5)):
                                    color = self.color_snow1

                                if (airportwx in self.wx_snow_ck and cycle_num == 4):
                                    color = self.color_snow2

                            if self.rainshow:
                                # Check for Rain
                                if (airportwx in self.wx_rain_ck and (cycle_num == 3 or cycle_num == 4)):
                                    color = self.color_rain1

                                if (airportwx in self.wx_rain_ck and cycle_num == 5):
                                    color = self.color_rain2

                            if self.frrainshow:
                                # Check for Freezing Rain
                                if (airportwx in self.wx_frrain_ck and (cycle_num == 3 or cycle_num == 5)):
                                    color = self.color_frrain1

                                if (airportwx in self.wx_frrain_ck and cycle_num == 4):
                                    color = self.color_frrain2

                            if self.dustsandashshow:
                                # Check for Dust, Sand or Ash
                                if (airportwx in self.wx_dustsandash_ck and (cycle_num == 3 or cycle_num == 5)):
                                    color = self.color_dustsandash1

                                if (airportwx in self.wx_dustsandash_ck and cycle_num == 4):
                                    color = self.color_dustsandash2

                            if self.fogshow:
                                # Check for Fog
                                if (airportwx in self.wx_fog_ck and (cycle_num == 3 or cycle_num == 5)):
                                    color = self.color_fog1

                                if (airportwx in self.wx_fog_ck and cycle_num == 4):
                                    color = self.color_fog2

                        # If homeport is set to 1 then turn on the appropriate LED using a specific color, This will toggle
                        # so that every other time through, the color will display the proper weather, then homeport color(s).
                        if i == self.homeport_pin and self.homeport and self.toggle:
                            if self.homeport_display == 1:
                                color = self.homeport_colors[cycle_num]
                            elif self.homeport_display == 2:
                                pass
                            else:
                                color = self.color_homeport

                        # pass pin, color and format. Check and change color code for RGB or GRB format
                        self.xcolor = self.rgbtogrb(i, color, self.rgb_grb)

                        if i == self.homeport_pin and self.homeport:  # if this is the home airport, don't dim out the brightness
                            self.norm_color = self.xcolor
                            self.xcolor = Color(
                                self.norm_color[0], self.norm_color[1], self.norm_color[2])
                        elif self.homeport:  # if this is not the home airport, dim out the brightness
                            self.dim_color = self.dim(
                                self.xcolor, self.dim_value)
                            self.xcolor = Color(int(self.dim_color[0]), int(
                                self.dim_color[1]), int(self.dim_color[2]))
                        else:  # if home airport feature is disabled, then don't dim out any airports brightness
                            self.norm_color = self.xcolor
                            self.xcolor = Color(
                                self.norm_color[0], self.norm_color[1], self.norm_color[2])

                        # set color to display on a specific LED for the current cycle_num cycle.
                        self.strip.setPixelColor(i, self.xcolor)
                        i = i + 1  # set next LED pin in strip

                    print("/LED.", end='')
                    sys.stdout.flush()
                    # Display strip with newly assigned colors for the current cycle_num cycle.
                    self.strip.show()
                    print(".", end='')
                    # cycle_wait time is a user defined value
                    self.wait_time = self.cycle_wait[cycle_num]
                    # pause between cycles. pauses are setup in user definitions.
                    time.sleep(self.wait_time)


    def update_metar_data(self,  stationiddict, windsdict, wxstringdict):
        # depending on what data is to be displayed, either use an URL for METARs and TAFs or read file from drive (pass).
        # Check to see if the script should display TAF data (0), METAR data (1) or MOS data (2)
        if self.metar_taf_mos == 1:
            # Define URL to get weather METARS. If no METAR reported withing the last 2.5 hours, Airport LED will be white (nowx).
            url = "https://www.aviationweather.gov/adds/dataserver_current/httpparam?dataSource=metars&requestType=retrieve&format=xml&mostRecentForEachStation=constraint&hoursBeforeNow=" + \
                str(self.metar_age)+"&stationString="
            debugging.info("METAR Data Loading")

        elif self.metar_taf_mos == 0:
            # Define URL to get weather URL for TAF. If no TAF reported for an airport, the Airport LED will be white (nowx).
            url = "https://www.aviationweather.gov/adds/dataserver_current/httpparam?dataSource=tafs&requestType=retrieve&format=xml&mostRecentForEachStation=constraint&hoursBeforeNow=" + \
                str(self.metar_age)+"&stationString="
            debugging.info("TAF Data Loading")

        # MOS data is not accessible in the same way as METARs and TAF's. A large file is downloaded by crontab everyday that gets read.
        elif self.metar_taf_mos == 2:
            pass  # This elif is not strictly needed and is only here for clarity
            debugging.info("MOS Data Loading")

        elif self.metar_taf_mos == 3:  # Heat Map
            pass
            debugging.info("Heat Map Data Loading")

        # Build URL to submit to FAA with the proper airports from the airports file for METARs and TAF's but not MOS data
        if self.metar_taf_mos != 2 and self.metar_taf_mos != 3:
            for airportcode in self.airports:
                if airportcode == "NULL" or airportcode == "LGND":
                    continue
                url = url + airportcode + ","
            url = url[:-1]  # strip trailing comma from string
            debugging.info(url)  # debug

            utils.wait_for_internet()

            content = urllib.request.urlopen(url).read()

            # Process XML data returned from FAA
            self.root = ET.fromstring(content)


    def reboot_if_time(self):
        # Check time and reboot machine if time equals time_reboot and if use_reboot along with autorun are both set to 1
        if self.use_reboot == 1 and self.autorun == 1:
            now = datetime.now()
            rb_time = now.strftime("%H:%M")
            debugging.info("**Current Time=" + str(rb_time) +
                           " - **Reboot Time=" + str(self.time_reboot))
            print("**Current Time=" + str(rb_time) +
                  " - **Reboot Time=" + str(self.time_reboot))  # debug

            if rb_time == self.time_reboot:
                debugging.info("Rebooting at " + self.time_reboot)
                time.sleep(1)
                os.system("sudo reboot now")


    def decode_taf_data(self, stationiddict, windsdict, wxstringdict):
        # TAF decode routine
        # 0 equals display TAF. This routine will decode the TAF, pick the appropriate time frame to display.
        if self.metar_taf_mos == 0:
            debugging.info("Starting TAF Data Display")
            # start of TAF decoding routine
            for data in self.root.iter('data'):
                # get number of airports reporting TAFs to be used for diagnosis only
                num_results = data.attrib['num_results']
                debugging.info("\nNum of Airport TAFs = " +
                               num_results)  # debug

            for taf in self.root.iter('TAF'):  # iterate through each airport's TAF
                stationId = taf.find('station_id').text  # debug
                debugging.info(stationId)  # debug
                debugging.info('Current+Offset Zulu - ' +
                               self.current_zulu)  # debug
                taf_wx_string = ""
                taf_change_indicator = ""
                taf_wind_dir_degrees = ""
                taf_wind_speed_kt = ""
                taf_wind_gust_kt = ""

                # Now look at the forecasts for the airport
                for forecast in taf.findall('forecast'):

                    # Routine inspired by Nick Cirincione.
                    flightcategory = "VFR"  # intialize flight category
                    taf_time_from = forecast.find(
                        'fcst_time_from').text  # get taf's from time
                    taf_time_to = forecast.find(
                        'fcst_time_to').text  # get taf's to time

                    if forecast.find('wx_string') is not None:
                        taf_wx_string = forecast.find(
                            'wx_string').text  # get weather conditions

                    if forecast.find('change_indicator') is not None:
                        taf_change_indicator = forecast.find(
                            'change_indicator').text  # get change indicator

                    if forecast.find('wind_dir_degrees') is not None:
                        taf_wind_dir_degrees = forecast.find(
                            'wind_dir_degrees').text  # get wind direction

                    if forecast.find('wind_speed_kt') is not None:
                        taf_wind_speed_kt = forecast.find(
                            'wind_speed_kt').text  # get wind speed

                    if forecast.find('wind_gust_kt') is not None:
                        taf_wind_gust_kt = forecast.find(
                            'wind_gust_kt').text  # get wind gust speed

                    # test if current time plus offset falls within taf's timeframe
                    if taf_time_from <= self.current_zulu <= taf_time_to:
                        debugging.info('FROM - ' + taf_time_from)
                        debugging.info(self.comp_time(taf_time_from))
                        debugging.info('TO - ' + taf_time_to)
                        debugging.info(self.comp_time(taf_time_to))

                        # There can be multiple layers of clouds in each taf, but they are always listed lowest AGL first.
                        # Check the lowest (first) layer and see if it's overcast, broken, or obscured. If it is, then compare to cloud base height to set $
                        # This algorithm basically sets the flight category based on the lowest OVC, BKN or OVX layer.
                        # for each sky_condition from the XML
                        for sky_condition in forecast.findall('sky_condition'):
                            # get the sky cover (BKN, OVC, SCT, etc)
                            sky_cvr = sky_condition.attrib['sky_cover']
                            debugging.info(sky_cvr)  # debug

                            # If the layer is OVC, BKN or OVX, set Flight category based on height AGL
                            if sky_cvr in ("OVC", "BKN", "OVX"):

                                try:
                                    # get cloud base AGL from XML
                                    cld_base_ft_agl = sky_condition.attrib['cloud_base_ft_agl']
                                    debugging.info(
                                        cld_base_ft_agl)  # debug
                                except:
                                    # get cloud base AGL from XML
                                    cld_base_ft_agl = forecast.find(
                                        'vert_vis_ft').text

    #                            cld_base_ft_agl = sky_condition.attrib['cloud_base_ft_agl'] #get cloud base AGL from XML
    #                            debugging.info(cld_base_ft_agl) #debug

                                cld_base_ft_agl = int(cld_base_ft_agl)
                                if cld_base_ft_agl < 500:
                                    flightcategory = "LIFR"
                                    break

                                elif 500 <= cld_base_ft_agl < 1000:
                                    flightcategory = "IFR"
                                    break

                                elif 1000 <= cld_base_ft_agl <= 3000:
                                    flightcategory = "MVFR"
                                    break

                                elif cld_base_ft_agl > 3000:
                                    flightcategory = "VFR"
                                    break

                        # visibilty can also set flight category. If the clouds haven't set the fltcat to LIFR. See if visibility will
                        # if it's LIFR due to cloud layer, no reason to check any other things that can set flight category.
                        if flightcategory != "LIFR":
                            # check XML if visibility value exists
                            if forecast.find('visibility_statute_mi') is not None:
                                visibility_statute_mi = forecast.find(
                                    'visibility_statute_mi').text  # get visibility number
                                visibility_statute_mi = float(
                                    visibility_statute_mi)
                                debugging.info(visibility_statute_mi)

                                if visibility_statute_mi < 1.0:
                                    flightcategory = "LIFR"

                                elif 1.0 <= visibility_statute_mi < 3.0:
                                    flightcategory = "IFR"

                                # if Flight Category was already set to IFR $
                                elif 3.0 <= visibility_statute_mi <= 5.0 and flightcategory != "IFR":
                                    flightcategory = "MVFR"

                        # Print out TAF data to screen for diagnosis only
                        debugging.info('Airport - ' + stationId)
                        debugging.info(
                            'Flight Category - ' + flightcategory)
                        debugging.info('Wind Speed - ' + taf_wind_speed_kt)
                        debugging.info('WX String - ' + taf_wx_string)
                        debugging.info(
                            'Change Indicator - ' + taf_change_indicator)
                        debugging.info(
                            'Wind Director Degrees - ' + taf_wind_dir_degrees)
                        debugging.info('Wind Gust - ' + taf_wind_gust_kt)

                        # grab flightcategory from returned FAA data
                        if flightcategory is None:  # if wind speed is blank, then bypass
                            flightcategory = None

                        # grab wind speeds from returned FAA data
                        if taf_wind_speed_kt is None:  # if wind speed is blank, then bypass
                            windspeedkt = 0
                        else:
                            windspeedkt = taf_wind_speed_kt

                        # grab Weather info from returned FAA data
                        if taf_wx_string is None:  # if weather string is blank, then bypass
                            wxstring = "NONE"
                        else:
                            wxstring = taf_wx_string

                # Check for duplicate airport identifier and skip if found, otherwise store in dictionary. covers for dups in "airports" file
                if stationId in stationiddict:
                    debugging.info(
                        stationId + " Duplicate, only saved first metar category")
                else:
                    # build category dictionary
                    stationiddict[stationId] = flightcategory

                if stationId in windsdict:
                    debugging.info(
                        stationId + " Duplicate, only saved the first winds")
                else:
                    # build windspeed dictionary
                    windsdict[stationId] = windspeedkt

                if stationId in wxstringdict:
                    debugging.info(
                        stationId + " Duplicate, only saved the first weather")
                else:
                    # build weather dictionary
                    wxstringdict[stationId] = wxstring
            debugging.info("Decoded TAF Data for Display")

        elif self.metar_taf_mos == 1:
            debugging.info("Starting METAR Data Display")
            # start of METAR decode routine if 'metar_taf_mos' equals 1. Script will default to this routine without a rotary switch installed.
            # grab the airport category, wind speed and various weather from the results given from FAA.
            for metar in self.root.iter('METAR'):
                stationId = metar.find('station_id').text

            # METAR Decode Routine to create flight category via cloud cover and/or visability when flight category is not reported.
            # Routine contributed to project by Nick Cirincione. Thank you for your contribution.
                # if category is blank, then see if there's a sky condition or vis that would dictate flight category
                if metar.find('flight_category') is None or metar.find('flight_category') == 'NONE':
                    flightcategory = "VFR"  # intialize flight category
                    sky_cvr = "SKC"  # Initialize to Sky Clear
                    debugging.info(
                        stationId + " Not Reporting Flight Category through the API.")

                    # There can be multiple layers of clouds in each METAR, but they are always listed lowest AGL first.
                    # Check the lowest (first) layer and see if it's overcast, broken, or obscured. If it is, then compare to cloud base height to set flight category.
                    # This algorithm basically sets the flight category based on the lowest OVC, BKN or OVX layer.
                    # First check to see if the FAA provided the forecast field, if not get the sky_condition.
                    if metar.find('forecast') is None or metar.find('forecast') == 'NONE':
                        debugging.info(
                            'FAA xml data is NOT providing the forecast field for this airport')
                        # for each sky_condition from the XML
                        for sky_condition in metar.findall('./sky_condition'):
                            # get the sky cover (BKN, OVC, SCT, etc)
                            sky_cvr = sky_condition.attrib['sky_cover']
                            debugging.info('Sky Cover = ' + sky_cvr)

                            # Break out of for loop once we find one of these conditions
                            if sky_cvr in ("OVC", "BKN", "OVX"):
                                break

                    else:
                        debugging.info(
                            'FAA xml data IS providing the forecast field for this airport')
                        # for each sky_condition from the XML
                        for sky_condition in metar.findall('./forecast/sky_condition'):
                            # get the sky cover (BKN, OVC, SCT, etc)
                            sky_cvr = sky_condition.attrib['sky_cover']
                            debugging.info('Sky Cover = ' + sky_cvr)
                            debugging.info(metar.find(
                                './forecast/fcst_time_from').text)

                            # Break out of for loop once we find one of these conditions
                            if sky_cvr in ("OVC", "BKN", "OVX"):
                                break

                    # If the layer is OVC, BKN or OVX, set Flight category based on height AGL
                    if sky_cvr in ("OVC", "BKN", "OVX"):
                        try:
                            # get cloud base AGL from XML
                            cld_base_ft_agl = sky_condition.attrib['cloud_base_ft_agl']
                        except:
                            # get cloud base AGL from XML
                            cld_base_ft_agl = forecast.find(
                                'vert_vis_ft').text

                        debugging.info('Cloud Base = ' + cld_base_ft_agl)
                        cld_base_ft_agl = int(cld_base_ft_agl)

                        if cld_base_ft_agl < 500:
                            flightcategory = "LIFR"
    #                        break
                        elif 500 <= cld_base_ft_agl < 1000:
                            flightcategory = "IFR"
    #                        break
                        elif 1000 <= cld_base_ft_agl <= 3000:
                            flightcategory = "MVFR"
    #                        break
                        elif cld_base_ft_agl > 3000:
                            flightcategory = "VFR"
    #                        break

                    # visibilty can also set flight category. If the clouds haven't set the fltcat to LIFR. See if visibility will
                    # if it's LIFR due to cloud layer, no reason to check any other things that can set flight category.
                    if flightcategory != "LIFR":
                        # check XML if visibility value exists
                        if metar.find('./forecast/visibility_statute_mi') is not None:
                            visibility_statute_mi = metar.find(
                                './forecast/visibility_statute_mi').text  # get visibility number
                            visibility_statute_mi = float(
                                visibility_statute_mi)

                            if visibility_statute_mi < 1.0:
                                flightcategory = "LIFR"

                            elif 1.0 <= visibility_statute_mi < 3.0:
                                flightcategory = "IFR"

                            # if Flight Category was already set to IFR by clouds, it can't be reduced to MVFR
                            elif 3.0 <= visibility_statute_mi <= 5.0 and flightcategory != "IFR":
                                flightcategory = "MVFR"

                    debugging.info(
                        stationId + " flight category is Decode script-determined as " + flightcategory)

                else:
                    debugging.info(stationId + ': FAA is reporting ' +
                                   metar.find('flight_category').text + ' through their API')
                    # pull flight category if it exists and save all the algoritm above
                    flightcategory = metar.find('flight_category').text
                # End of METAR Decode added routine to create flight category via cloud cover and/or visability when flight category is not reported.

                # grab wind speeds from returned FAA data
                # if wind speed is blank, then bypass
                if metar.find('wind_speed_kt') is None:
                    windspeedkt = 0
                else:
                    windspeedkt = metar.find('wind_speed_kt').text

                # grab Weather info from returned FAA data
                # if weather string is blank, then bypass
                if metar.find('wx_string') is None:
                    wxstring = "NONE"
                else:
                    wxstring = metar.find('wx_string').text

                # Check for duplicate airport identifier and skip if found, otherwise store in dictionary. covers for dups in "airports" file
                if stationId in stationiddict:
                    debugging.info(
                        stationId + " Duplicate, only saved first metar category")
                else:
                    # build category dictionary
                    stationiddict[stationId] = flightcategory

                if stationId in windsdict:
                    debugging.info(
                        stationId + " Duplicate, only saved the first winds")
                else:
                    # build windspeed dictionary
                    windsdict[stationId] = windspeedkt

                if stationId in wxstringdict:
                    debugging.info(
                        stationId + " Duplicate, only saved the first weather")
                else:
                    # build weather dictionary
                    wxstringdict[stationId] = wxstring
            debugging.info("Decoded METAR Data for Display")


    def update_gpio_flags(self, toggle_value, time_sw, data_sw):
        self.toggle_sw = toggle_value
        # Offset in HOURS to choose which TAF to display
        self.hour_to_display = time_sw
        self.metar_taf_mos = data_sw  # 0 = Display TAF.
        # debugging.info( 'Switch in position ' )


    def updateLedLoop(self):
        ##########################
        # Start of executed code #
        ##########################
        toggle = 0  # used for homeport display
        outerloop = True  # Set to TRUE for infinite outerloop
        display_num = 0
        while (outerloop):
            display_num = display_num + 1

            # Time calculations, dependent on 'hour_to_display' offset. this determines how far in the future the TAF data should be.
            # This time is recalculated everytime the FAA data gets updated
            # Get current time plus Offset
            zulu = datetime.utcnow() + timedelta(hours=self.hour_to_display)
            # Format time to match whats reported in TAF. ie. 2020-03-24T18:21:54Z
            self.current_zulu = zulu.strftime('%Y-%m-%dT%H:%M:%SZ')
            # Zulu time formated for just the hour, to compare to MOS data
            self.current_hr_zulu = zulu.strftime('%H')

            # Dictionary definitions. Need to reset whenever new weather is received
            stationiddict = {}
            windsdict = {"": ""}
            wxstringdict = {"": ""}

            if self.wipe_displays() == False:
                debugging.error("Error returned while trying to wipe LEDs and Displays")
            if self.load_airports() == False:
                break

            self.update_metar_data( stationiddict, windsdict, wxstringdict)

            if self.turnoffrefresh == 0:
                # turn off led before repainting them. If Rainbow stays on, it has hung up before this.
                self.turnoff(self.strip)

            if self.check_heat_map(stationiddict, windsdict, wxstringdict) == False:
                break

            self.decode_taf_data( stationiddict, windsdict, wxstringdict)

            # Setup timed loop for updating FAA Weather that will run based on the value of 'update_interval' which is a user setting
            # Start the timer. When timer hits user-defined value, go back to outer loop to update FAA Weather.
            timeout_end = time.time() + (self.update_interval * 60)
            loopcount = 0
            # take 'update_interval' which is in minutes and turn into seconds
            while time.time() < timeout_end:
                # This while statement sets an expiry time for when the next section must complete.
                loopcount = loopcount + 1

                self.reboot_if_time()

                # Routine to restart this script if config.py is changed while this script is running.
                for f, mtime in self.WATCHED_FILES_MTIMES:
                    if getmtime(f) != mtime:
                        debugging.info("Restarting from awake" +
                                       __file__ + " in 2 sec...")
                        time.sleep(2)
                        # '/NeoSectional/metar-v4.py'])
                        os.execv(sys.executable, [sys.executable] + [__file__])

                # Timer routine, used to turn off LED's at night if desired. Use 24 hour time in settings.
                # check to see if the user wants to use a timer.
                if self.conf.get_bool("schedule", "usetimer"):

                    if self.time_in_range(self.timeoff, self.end_time, datetime.now().time()):

                        # If temporary lights-on period from refresh button has expired, restore the original light schedule
                        if self.temp_lights_on == 1:
                            self.end_time = self.lights_on
                            self.timeoff = self.lights_out
                            self.temp_lights_on = 0

                        # Escape codes to render Blue text on screen
                        sys.stdout.write("\n\033[1;34;40m Sleeping-  ")
                        sys.stdout.flush()
                        self.turnoff(self.strip)
                        debugging.info("Map Going to Sleep")

                        while self.time_in_range(self.timeoff, self.end_time, datetime.now().time()):
                            sys.stdout.write("z")
                            sys.stdout.flush()
                            time.sleep(1)
                            # Pushbutton for Refresh. check to see if we should turn on temporarily during sleep mode
                            if GPIO.input(22) == False:
                                # Set to turn lights on two seconds ago to make sure we hit the loop next time through
                                self.end_time = (
                                    datetime.now()-timedelta(seconds=2)).time()
                                self.timeoff = (
                                    datetime.now()+timedelta(minutes=self.tempsleepon)).time()
                                self.temp_lights_on = 1  # Set this to 1 if button is pressed
                                debugging.info(
                                    "Sleep interrupted by button push")

                            # Routine to restart this script if config.py is changed while this script is running.
                            for f, mtime in self.WATCHED_FILES_MTIMES:
                                if getmtime(f) != mtime:
                                    print("\033[0;0m\n")  # Turn off Blue text.
                                    debugging.info(
                                        "Restarting from sleep" + __file__ + " in 2 sec...")
                                    time.sleep(2)
                                    # restart this script.
                                    os.execv(sys.executable, [
                                             sys.executable] + [__file__])

                        print("\033[0;0m\n")  # Turn off Blue text.

                # Check if rotary switch is used, and what position it is in. This will determine what to display, METAR, TAF and MOS data.
                # If TAF or MOS data, what time offset should be displayed, i.e. 0 hour, 1 hour, 2 hour etc.
                # If there is no rotary switch installed, then all these tests will fail and will display the defaulted data from switch position 0
                if GPIO.input(0) == False and self.toggle_sw != 0:
                    self.update_gpio_flags(0, self.conf.get_int("rotaryswitch", "time_sw0"), 
                            self.conf.get_int("rotaryswitch", "data_sw0"))
                    break

                elif GPIO.input(5) == False and self.toggle_sw != 1:
                    self.update_gpio_flags(1, self.conf.get_int("rotaryswitch", "time_sw1"), 
                        self.conf.get_int("rotaryswitch", "data_sw1"))
                    break

                elif GPIO.input(6) == False and self.toggle_sw != 2:
                    self.update_gpio_flags(2, self.conf.get_int("rotaryswitch", "time_sw2"), 
                        self.conf.get_int("rotaryswitch", "data_sw2"))
                    break

                elif GPIO.input(13) == False and self.toggle_sw != 3:
                    self.update_gpio_flags(3, self.conf.get_int("rotaryswitch", "time_sw3"), 
                        self.conf.get_int("rotaryswitch", "data_sw3"))
                    break

                elif GPIO.input(19) == False and self.toggle_sw != 4:
                    self.update_gpio_flags(4, self.conf.get_int("rotaryswitch", "time_sw4"), 
                        self.conf.get_int("rotaryswitch", "data_sw4"))
                    break

                elif GPIO.input(26) == False and self.toggle_sw != 5:
                    self.update_gpio_flags(5, self.conf.get_int("rotaryswitch", "time_sw5"), 
                        self.conf.get_int("rotaryswitch", "data_sw5"))
                    break

                elif GPIO.input(21) == False and self.toggle_sw != 6:
                    self.update_gpio_flags(6, self.conf.get_int("rotaryswitch", "time_sw6"), 
                        self.conf.get_int("rotaryswitch", "data_sw6"))
                    break

                elif GPIO.input(20) == False and self.toggle_sw != 7:
                    self.update_gpio_flags(7, self.conf.get_int("rotaryswitch", "time_sw7"), 
                        self.conf.get_int("rotaryswitch", "data_sw7"))
                    break

                elif GPIO.input(16) == False and self.toggle_sw != 8:
                    self.update_gpio_flags(8, self.conf.get_int("rotaryswitch", "time_sw8"), 
                        self.conf.get_int("rotaryswitch", "data_sw8"))
                    break

                elif GPIO.input(12) == False and self.toggle_sw != 9:
                    self.update_gpio_flags(9, self.conf.get_int("rotaryswitch", "time_sw9"), 
                        self.conf.get_int("rotaryswitch", "data_sw9"))
                    break

                elif GPIO.input(1) == False and self.toggle_sw != 10:
                    self.update_gpio_flags(10, self.conf.get_int("rotaryswitch", "time_sw10"), 
                        self.conf.get_int("rotaryswitch", "data_sw10"))
                    break

                elif GPIO.input(7) == False and self.toggle_sw != 11:
                    self.update_gpio_flags(11, self.conf.get_int("rotaryswitch", "time_sw11"), 
                        self.conf.get_int("rotaryswitch", "data_sw11"))
                    break

                elif self.toggle_sw == -1:  # used if no Rotary Switch is installed
                    self.update_gpio_flags(12, self.conf.get_int("rotaryswitch", "time_sw0"), 
                        self.conf.get_int("rotaryswitch", "data_sw0"))
                    break

                # Check to see if pushbutton is pressed to force an update of FAA Weather
                # If no button is connected, then this is bypassed and will only update when 'update_interval' is met
                if GPIO.input(22) == False:
                    debugging.info(
                        'Refresh Pushbutton Pressed. Breaking out of loop to refresh FAA Data')
                    break

                # Bright light will provide a low state (0) on GPIO. Dark light will provide a high state (1).
                # Full brightness will be used if no light sensor is installed.
                if GPIO.input(4) == 1:
                    self.LED_BRIGHTNESS = self.dimmed_value
                    if self.ambient_toggle == 1:
                        debugging.info(
                            "Ambient Sensor set brightness to dimmed_value")
                        self.ambient_toggle = 0
                else:
                    self.LED_BRIGHTNESS = self.bright_value
                    if self.ambient_toggle == 0:
                        debugging.info(
                            "Ambient Sensor set brightness to bright_value")
                        self.ambient_toggle = 1

                self.strip.setBrightness(self.LED_BRIGHTNESS)

                # Used to determine if the homeport color should be displayed if "homeport = 1"
                toggle = not(toggle)

                self.wx_display_loop(stationiddict, windsdict, wxstringdict)
