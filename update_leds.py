#!/usr/bin/python3
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
# on managing an LED strip
#
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

## Removing URL related actions from update_leds
# import urllib.request
# import urllib.error
# import urllib.parse
# import socket
# import xml.etree.ElementTree as ET
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

# Moved logging activities to debugging.py
# import logging
# import logzero #had to manually install logzero. https://logzero.readthedocs.io/en/latest/
# from logzero import logger
# import config  # Config.py holds user settings used by the various scripts
import admin

import debugging
import utils


class updateLEDs:
    """ Class to manage LSD strips """

    def __init__(self, conf, airport_database):
        # Setup rotating logfile with 3 rotations, each with a maximum filesize of 1MB:
        self.version = admin.version  # Software version
        # self.loglevel = self.conf.loglevel
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

        # list of pins that need to reverse the rgb_grb setting. To accommodate two different models of LED's are used.
        # self.rev_rgb_grb = self.conf.rev_rgb_grb        #[] #['1', '2', '3', '4', '5', '6', '7', '8']

        # Specific Variables to default data to display if Rotary Switch is not installed.
        # hour_to_display #Offset in HOURS to choose which TAF/MOS to display
        self.hour_to_display = self.conf.get_int("rotaryswitch","time_sw0")
        # metar_taf_mos    #0 = Display TAF, 1 = Display METAR, 2 = Display MOS, 3 = Heat Map (Heat map not controlled by rotary switch)
        self.metar_taf_mos = self.conf.get_int("rotaryswitch"."data_sw0")
        # Set toggle_sw to an initial value that forces rotary switch to dictate data displayed
        self.toggle_sw = -1


        # MOS/TAF Config settings
        # self.prob = self.conf.prob                      #probability threshhold in Percent to assume reported weather will be displayed on map or not. MOS Only.

        # Heat Map settings
        # self.bin_grad = self.conf.bin_grad              #0 = Binary display, 1 = Gradient display
        # self.fade_yesno = self.conf.fade_yesno          #0 = No, 1 = Yes, if using gradient display, fade in/out the home airport color. will override use_homeap.
        # self.use_homeap = self.conf.use_homeap          #0 = No, 1 = Yes, Use a separate color to denote home airport.
        # delay in fading the home airport if used
        self.fade_delay = conf.get_float("rotaryswitch", "fade_delay")

        # MOS Config settings
        # self.prob = self.conf.prob                      #probability threshhold in Percent to assume reported weather will be displayed on map or not.

        # Specific settings for on/off timer. Used to turn off LED's at night if desired.
        # Verify Raspberry Pi is set to the correct time zone, otherwise the timer will be off.
        # self.usetimer = self.conf.usetimer              #0 = No, 1 = Yes. Turn the timer on or off with this setting
        self.offhour = self.conf.get_int("schedule","offhour")  # Use 24 hour time. Set hour to turn off display
        self.offminutes = self.conf.get_int("schedule","offminutes")  # Set minutes to turn off display
        self.onhour = self.conf.get_int("schedule","onhour")  # Use 24 hour time. Set hour to turn on display
        self.onminutes = self.conf.get_int("schedule","onminutes")  # Set minutes to on display
        # Set number of MINUTES to turn map on temporarily during sleep mode
        self.tempsleepon = self.conf.get_int("schedule","tempsleepon")

        # Number of LED pixels. Change this value to match the number of LED's being used on map
        self.LED_COUNT = self.conf.get_int("default","led_count")

        # Misc settings
        # 0 = No, 1 = Yes, use wipes. Defined by configurator
        self.usewipes = self.conf.get_int("rotaryswitch", "usewipes")
        # 1 = RGB color codes. 0 = GRB color codes. Populate color codes below with normal RGB codes and script will change if necessary
        self.rgb_grb = self.conf.get_int("lights", "rgb_grb")
        # Used to determine if board should reboot every day at time set in setting below.
        self.use_reboot = admin.use_reboot
        # 24 hour time in this format, '2400' = midnight. Change these 2 settings in the admin.py file if desired.
        self.time_reboot = admin.time_reboot

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
        self.legend_pins = [self.conf.get_int("lights","leg_pin_vfr"),
                self.conf.get_int("lights","leg_pin_mvfr"), 
                self.conf.get_int("lights","leg_pin_ifr"),
                self.conf.get_int("lights","leg_pin_lifr"), 
                self.conf.get_int("lights","leg_pin_nowx"), 
                self.conf.get_int("lights","leg_pin_hiwinds"),
                self.conf.get_int("lights","leg_pin_lghtn"), 
                self.conf.get_int("lights","leg_pin_snow"), 
                self.conf.get_int("lights","leg_pin_rain"), 
                self.conf.get_int("lights","leg_pin_frrain"), 
                self.conf.get_int("lights","leg_pin_dustandash"), 
                self.conf.get_int("lights","leg_pin_fog")]  # Used to build legend display

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
        self.LED_BRIGHTNESS = self.conf.get_int("lights","bright_value")

        # Setup paths for restart on change routine. Routine from;
        # https://blog.petrzemek.net/2014/03/23/restarting-a-python-script-within-itself
        self.LOCAL_CONFIG_FILE_PATH = '/NeoSectional/config.py'
        self.WATCHED_FILES = [self.LOCAL_CONFIG_FILE_PATH, __file__]
        self.WATCHED_FILES_MTIMES = [(f, getmtime(f))
                                     for f in self.WATCHED_FILES]
        debugging.info(
            'Watching ' + self.LOCAL_CONFIG_FILE_PATH + ' For Change')

        # Timer calculations
        self.lights_out = time_(self.conf.get_int("schedule", "offhour"),
                                self.conf.get_int("schedule", "offminutes"), 0)
        self.timeoff = self.lights_out
        self.lights_on = time_(self.onhour, self.onminutes, 0)
        self.end_time = self.lights_on
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
        self.homeap = self.conf.get_string("colors","color_vfr")  # If 100, then home airport - designate with Green
        # color_fog2                     #(10, 10, 10)        #dk grey to denote airports never visited
        self.no_visits = (20, 20, 20)
        self.black = self.conf.get_color("colors","color_black")  # (0,0,0)

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

    def turnoff(self):
        """ Set color to 0,0,0  - turning off LED """
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0, 0, 0))
        self.strip.show()


    def dim(self, data, value):
        """ 
        # Reduces the brightness of the colors for every airport except for the "homeport_pin" designated airport, which remains at the brightness set by
        # "bright_value" above in user setting. "data" is the airport color to display and "value" is the percentage of the brightness to be dimmed.
        # For instance if full bright white (255,255,255) is provided and the desired dimming is 50%, then the color returned will be (128,128,128),
        # or half as bright. The dim_value is set in the user defined area. 
        """
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
        """ Change colorcode to match strip RGB / GRB style """
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

    # Used by MOS decode routine. This routine builds mos_dict nested with hours_dict
    def set_data(self):
        """ FIXME: Needs reworking for MOS data """
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
        """ Color codes assigned with heatmap """
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


    def wipe_displays(self):
        """ FIXME: Retire this function, and import the functions from wipes-v4.py """
        # Call script and execute desired wipe(s) while data is being updated.
        # FIXME to make this imported
        # if self.usewipes == 1 and self.toggle_sw != -1:
            # Get latest ip's to display in editors
            # FIXME: Move wipes-v4 to be an included module, call here
            # exec(compile(open("/NeoSectional/wipes-v4.py", "rb", encoding="utf8").read(),
            #              "/NeoSectional/wipes-v4.py", 'exec'))
            # debugging.info("Calling wipes script")
        return True


    def check_heat_map(self, stationiddict, windsdict, wxstringdict):
        """
        # MOS decode routine
        # MOS data is downloaded daily from; https://www.weather.gov/mdl/mos_gfsmos_mav to the local drive by crontab scheduling.
        # Then this routine reads through the entire file looking for those airports that are in the airports file. If airport is
        # found, the data needed to display the weather for the next 24 hours is captured into mos_dict, which is nested with
        # hour_dict, which holds the airport's MOS data by 3 hour chunks. See; https://www.weather.gov/mdl/mos_gfsmos_mavcard for
        # a breakdown of what the MOS data looks like and what each line represents.
        """
        if self.metar_taf_mos == 2:
            debugging.info("Starting MOS Data Display")
            # Read current MOS text file
            try:
                file = open(self.mos_filepath, 'r', encoding="utf8")
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
                    unused1, dt_cat, month, unused2, unused3, day, unused4 = line.split(
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
                    if cat in self.categories:
                        cat_counter += 1  # used to check if a category is not in mos report for airport
                        if cat == 'HR':  # hour designation
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
                            if (cat_counter == 5 and cat != 'P06')\
                                    or (cat_counter == 6 and cat != 'T06')\
                                    or (cat_counter == 7 and cat != 'POZ')\
                                    or (cat_counter == 8 and cat != 'POS')\
                                    or (cat_counter == 9 and cat != 'TYP'):
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
                                self.last_cat = cat
                                # add the actual line of data read
                                temp = (re.findall(
                                    r'\s?(\s*\S+)', value.rstrip()))
                                self.set_data()
                                # clear out hour_dict for next airport
                                self.hour_dict = collections.OrderedDict()
                            else:
                                # continue to decode the next category data that was read.
                                # store what the last read cat was.
                                self.last_cat = cat
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

                            debugging.debug(flightcategory + " |")
                            debugging.debug(
                                'Windspeed = ' + wsp + ' | Wind dir = ' + wdr + ' |')

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

                                # print (t06,apid) #debug
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


    def wx_display_loop(self, stationiddict, windsdict, wxstringdict, airport_database):
        # "+str(display_num)+" Cycle Loop # "+str(loopcount)+": ",end="")
        debugging.info("\nWX Display")

        color = 0
        xcolor = 0
        # Start main loop. This loop will create all the necessary colors to display the weather one time.
        # cycle through the strip 6 times, setting the color then displaying to create various effects.

        airport_list = airport_database.get_airport_dict_led()

        for cycle_num in self.cycles:
            print(" " + str(cycle_num), end='')
            sys.stdout.flush()

            # Inner Loop. Increments through each LED in the strip setting the appropriate color to each individual LED.
            i = 0
            for airport_key in airport_list:

                airport_record = airport_list[airport_key]
                airportcode = airport_record.icaocode()

                if not airportcode:
                    break

                # FIXME: Cheating by updating here
                # airport_record.calculate_wx_from_metar()


                #
                # debugging.info("WX Display Loop : " + airportcode)
                # Pull the next flight category from dictionary.
                flightcategory = airport_record.get_wx_category_str()
                if not flightcategory:
                    flightcategory = "UNKN"
                # debugging.info("WX Display Loop - flight category : " + flightcategory)
                # Pull the winds from the dictionary.
                airportwinds = airport_record.get_wx_windspeed()
                if not airportwinds:
                    airportwinds = -1
                # Pull the weather reported for the airport from dictionary.
                # airportwx_long = wxstringdict.get(airportcode, "NONE")
                # Grab only the first parameter of the weather reported.
                # airportwx = airportwx_long.split(" ", 1)[0]
                # FIXME:
                airportwx = "NONE"

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

                debugging.debug((airportcode + " " + str(flightcategory) +
                    " " + str(airportwinds) +
                    " " + airportwx + " " + str(cycle_num) + " "))  # debug

                # Check to see if airport code is a NULL and set to black.
                if airportcode == "NULL" or airportcode == "LGND":
                    color = self.conf.get_color("colors","color_black")

                # Build and display Legend. "legend" must be set to 1 in the user defined section and "LGND" set in airports file.
                if self.conf.get_boolean("default","legend") and airportcode == "LGND" and (i in self.legend_pins):
                    if i == self.conf.get_int("lights","leg_pin_vfr"):
                        color = self.conf.get_int("colors","color_vfr")

                    if i == self.conf.get_int("lights","leg_pin_mvfr"):
                        color = self.conf.get_int("colors","color_mvfr")

                    if i == self.conf.get_int("lights","leg_pin_ifr"):
                        color = self.conf.get_int("colors","color_ifr")

                    if i == self.conf.get_int("lights","leg_pin_lifr"):
                        color = self.conf.get_int("colors","color_lifr")

                    if i == self.conf.get_int("lights","leg_pin_nowx"):
                        color = self.conf.get_int("colors","color_nowx")

                    if i == self.conf.get_int("lights","leg_pin_hiwinds") and self.conf.get_int("lights","legend_hiwinds"):
                        if (cycle_num == 3 or cycle_num == 4 or cycle_num == 5):
                            color = self.conf.get_int("colors","color_black")
                        else:
                            color = self.conf.get_int("colors","color_ifr")

                    if i == self.conf.get_int("lights","leg_pin_lghtn") and self.conf.get_int("lights","legend_lghtn"):
                        if (cycle_num == 2 or cycle_num == 4):  # Check for Thunderstorms
                            color = self.conf.get_int("colors","color_lghtn")

                        elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 3 or cycle_num == 5):
                            color = self.conf.get_int("colors","color_mvfr")

                    if i == self.conf.get_int("lights","leg_pin_snow") and self.conf.get_int("lights","legend_snow"):
                        if (cycle_num == 3 or cycle_num == 5):  # Check for Snow
                            color = self.conf.get_int("colors","color_snow1")

                        if (cycle_num == 4):
                            color = self.conf.get_int("colors","color_snow2")

                        elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                            color = self.conf.get_int("colors","color_lifr")

                    if i == self.conf.get_int("lights","leg_pin_rain") and self.conf.get_int("lights","legend_rain"):
                        if (cycle_num == 3 or cycle_num == 5):  # Check for Rain
                            color = self.conf.get_int("colors","color_rain1")

                        if (cycle_num == 4):
                            color = self.conf.get_int("colors","color_rain2")

                        elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                            color = self.conf.get_int("colors","color_vfr")

                    if i == self.conf.get_int("lights","leg_pin_frrain") and self.conf.get_int("lights","legend_frrain"):
                        if (cycle_num == 3 or cycle_num == 5):  # Check for Freezing Rain
                            color = self.conf.get_int("colors","color_frrain1")

                        if (cycle_num == 4):
                            color = self.conf.get_int("colors","color_frrain2")

                        elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                            color = self.conf.get_int("colors","color_mvfr")

                    if i == self.conf.get_int("lights","leg_pin_dustsandash") and self.conf.get_int("lights","legend_dustsandash"):
                        if (cycle_num == 3 or cycle_num == 5):  # Check for Dust, Sand or Ash
                            color = self.conf.get_int("colors","color_dustsandash1")

                        if (cycle_num == 4):
                            color = self.conf.get_int("colors","color_dustsandash2")

                        elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                            color = self.conf.get_int("colors","color_vfr")

                    if i == self.conf.get_int("lights","leg_pin_fog") and self.conf.get_int("lights","legend_fog"):
                        if (cycle_num == 3 or cycle_num == 5):  # Check for Fog
                            color = self.conf.get_int("colors","color_fog1")

                        if (cycle_num == 4):
                            color = self.conf.get_int("colors","color_fog2")

                        elif (cycle_num == 0 or cycle_num == 1 or cycle_num == 2):
                            color = self.conf.get_int("colors","color_ifr")

                # Start of weather display code for each airport in the "airports" file
                # Check flight category and set the appropriate color to display
                if flightcategory != "NONE":
                    if flightcategory == "VFR":  # Visual Flight Rules
                        color = self.conf.get_int("colors","color_vfr")
                    elif flightcategory == "MVFR":  # Marginal Visual Flight Rules
                        color = self.conf.get_int("colors","color_mvfr")
                    elif flightcategory == "IFR":  # Instrument Flight Rules
                        color = self.conf.get_int("colors","color_ifr")
                    elif flightcategory == "LIFR":  # Low Instrument Flight Rules
                        color = self.conf.get_int("colors","color_lifr")
                    else:
                        color = self.conf.get_int("colors","color_nowx")

                # 3.01 bug fix by adding "LGND" test
                elif flightcategory == "NONE" and airportcode != "LGND" and airportcode != "NULL":
                    color = self.conf.get_int("colors","color_nowx")  # No Weather reported.

                # Check winds and set the 2nd half of cycles to black to create blink effect
                if self.conf.hiwindblink:  # bypass if "hiwindblink" is set to 0
                    if (int(airportwinds) >= self.conf.max_wind_speed and (cycle_num == 3 or cycle_num == 4 or cycle_num == 5)):
                        color = self.conf.get_int("colors","color_black")
                        # debug
                        debugging.debug(("HIGH WINDS-> " + airportcode +
                               " Winds = " + str(airportwinds) + " "))

                # Check the wxstring from FAA for reported weather and create color changes in LED for weather effect.
                if airportwx != "NONE":
                    if self.conf.get_boolean("lights","lghtnflash"):
                        # Check for Thunderstorms
                        if (airportwx in self.wx_lghtn_ck and (cycle_num == 2 or cycle_num == 4)):
                            color = self.conf.get_int("colors","color_lghtn")

                    if self.conf.get_boolean("lights","snowshow"):
                        # Check for Snow
                        if (airportwx in self.wx_snow_ck and (cycle_num == 3 or cycle_num == 5)):
                            color = self.conf.get_int("colors","color_snow1")

                        if (airportwx in self.wx_snow_ck and cycle_num == 4):
                            color = self.conf.get_int("colors","color_snow2")

                    if self.conf.get_boolean("lights","rainshow"):
                        # Check for Rain
                        if (airportwx in self.wx_rain_ck and (cycle_num == 3 or cycle_num == 4)):
                            color = self.conf.get_int("colors","color_rain1")

                        if (airportwx in self.wx_rain_ck and cycle_num == 5):
                            color = self.conf.get_int("colors","color_rain2")

                    if self.conf.get_boolean("lights","frrainshow"):
                        # Check for Freezing Rain
                        if (airportwx in self.wx_frrain_ck and (cycle_num == 3 or cycle_num == 5)):
                            color = self.conf.get_int("colors","color_frrain1")

                        if (airportwx in self.wx_frrain_ck and cycle_num == 4):
                            color = self.conf.get_int("colors","color_frrain2")

                    if self.conf.get_boolean("lights","dustandashshow"):
                        # Check for Dust, Sand or Ash
                        if (airportwx in self.wx_dustsandash_ck and (cycle_num == 3 or cycle_num == 5)):
                            color = self.conf.get_int("colors","color_dustsandash1")

                        if (airportwx in self.wx_dustsandash_ck and cycle_num == 4):
                            color = self.conf.get_int("colors","color_dustsandash2")

                    if self.conf.get_boolean("lights", "fogshow"):
                        # Check for Fog
                        if (airportwx in self.wx_fog_ck and (cycle_num == 3 or cycle_num == 5)):
                            color = self.conf.get_int("colors","color_fog1")

                        if (airportwx in self.wx_fog_ck and cycle_num == 4):
                            color = self.conf.get_int("colors","color_fog2")

                # If homeport is set to 1 then turn on the appropriate LED using a specific color, This will toggle
                # so that every other time through, the color will display the proper weather, then homeport color(s).
                if i == self.conf.get_int("lights", "homeport_pin") and self.conf.get_boolean("lights", "homeport") and self.toggle:
                    if self.conf.get_int("lights", "homeport_display") == 1:
                        color = self.conf.homeport_colors[cycle_num]
                    elif self.conf.get_int("lights", "homeport_display") == 2:
                        pass
                    else:
                        color = self.conf.get_int("colors","color_homeport")

                # pass pin, color and format. Check and change color code for RGB or GRB format
                xcolor = self.rgbtogrb(i, color, self.rgb_grb)

                if i == self.conf.homeport_pin and self.conf.homeport:  # if this is the home airport, don't dim out the brightness
                    norm_color = xcolor
                    xcolor = Color(norm_color[0], norm_color[1], norm_color[2])
                elif self.conf.homeport:  # if this is not the home airport, dim out the brightness
                    dim_color = self.dim(xcolor, self.conf.dim_value)
                    xcolor = Color(int(dim_color[0]), int(dim_color[1]), int(dim_color[2]))
                else:  # if home airport feature is disabled, then don't dim out any airports brightness
                    norm_color = xcolor
                    xcolor = Color(norm_color[0], norm_color[1], norm_color[2])

                # set color to display on a specific LED for the current cycle_num cycle.
                # if i == 1 or i == 3:
                #         debugging.info("Airport:" + airportcode +
                #               " Flight Category: " + flightcategory +
                #               " Color: " + str(color)  + 
                #               " xColor: " + str(xcolor) + 
                #               " LED(i) " + str(i))
                self.strip.setPixelColor(i, xcolor)
                i = i + 1  # set next LED pin in strip

            print("/LED.", end='')
            sys.stdout.flush()
            # Display strip with newly assigned colors for the current cycle_num cycle.
            self.strip.show()
            print(".", end='')
            # cycle_wait time is a user defined value
            wait_time = self.cycle_wait[cycle_num]
            # pause between cycles. pauses are setup in user definitions.
            time.sleep(wait_time)


    def calculate_wx_conditions(self, ceiling, visibility):
        wx_conditions = "VFR"
        return wx_conditions


    def update_gpio_flags(self, toggle_value, time_sw, data_sw):
        self.toggle_sw = toggle_value
        # Offset in HOURS to choose which TAF to display
        self.hour_to_display = time_sw
        self.metar_taf_mos = data_sw  # 0 = Display TAF.
        # debugging.info( 'Switch in position ' )


    def update_loop(self, conf, airport_database):
        ##########################
        # Start of executed code #
        ##########################
        toggle = 0  # used for homeport display
        outerloop = True  # Set to TRUE for infinite outerloop
        display_num = 0
        while outerloop:
            display_num = display_num + 1

            # Time calculations, dependent on 'hour_to_display' offset. this determines how far in the future the TAF data should be.
            # This time is recalculated everytime the FAA data gets updated
            # Get current time plus Offset
            zulu = utils.current_time_taf_offset(conf)
            # Format time to match whats reported in TAF. ie. 2020-03-24T18:21:54Z
            self.current_zulu = utils.time_format_taf(utils.current_time(conf))
            # Zulu time formated for just the hour, to compare to MOS data
            self.current_hr_zulu = zulu.strftime('%H')

            # Dictionary definitions. Need to reset whenever new weather is received
            stationiddict = {}
            windsdict = {"": ""}
            wxstringdict = {"": ""}

            if self.wipe_displays() == False:
                debugging.error("Error returned while trying to wipe LEDs and Displays")
            # if self.load_airports() == False:
            #     break

            # FIXME: These will be empty - need to clean them up
            # self.update_metar_data(stationiddict, windsdict, wxstringdict)

            if self.turnoffrefresh == 0:
                # turn off led before repainting them. If Rainbow stays on, it has hung up before this.
                self.turnoff()

            if self.check_heat_map(stationiddict, windsdict, wxstringdict) == False:
                break

            # FIXME: This goes away - airport information will be in airport_database
            # self.decode_taf_data(stationiddict, windsdict, wxstringdict, self.metar_taf_mos, self.root)

            # Setup timed loop for updating FAA Weather that will run based on the value of 'update_interval' which is a user setting
            # Start the timer. When timer hits user-defined value, go back to outer loop to update FAA Weather.
            timeout_end = time.time() + (self.conf.update_interval * 60)
            loopcount = 0
            # take 'update_interval' which is in minutes and turn into seconds
            while time.time() < timeout_end:
                # This while statement sets an expiry time for when the next section must complete.
                loopcount = loopcount + 1

                utils.reboot_if_time(self.conf)

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

                    if utils.time_in_range(self.timeoff, self.end_time, datetime.now().time()):

                        # If temporary lights-on period from refresh button has expired, restore the original light schedule
                        if self.temp_lights_on == 1:
                            self.end_time = self.lights_on
                            self.timeoff = self.lights_out
                            self.temp_lights_on = 0

                        # Escape codes to render Blue text on screen
                        sys.stdout.write("\n\033[1;34;40m Sleeping-  ")
                        sys.stdout.flush()
                        self.turnoff()
                        debugging.info("Map Going to Sleep")

                        while utils.time_in_range(self.timeoff, self.end_time, datetime.now().time()):
                            sys.stdout.write("z")
                            sys.stdout.flush()
                            time.sleep(1)
                            # Pushbutton for Refresh. check to see if we should turn on temporarily during sleep mode
                            if GPIO.input(22) == False:
                                # Set to turn lights on two seconds ago to make sure we hit the loop next time through
                                self.end_time = (datetime.now()-timedelta(seconds=2)).time()
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
                    self.LED_BRIGHTNESS = self.conf.dimmed_value
                    if self.ambient_toggle == 1:
                        debugging.info(
                            "Ambient Sensor set brightness to dimmed_value")
                        self.ambient_toggle = 0
                else:
                    self.LED_BRIGHTNESS = self.conf.bright_value
                    if self.ambient_toggle == 0:
                        debugging.info(
                            "Ambient Sensor set brightness to bright_value")
                        self.ambient_toggle = 1

                self.strip.setBrightness(self.LED_BRIGHTNESS)

                # Used to determine if the homeport color should be displayed if "homeport = 1"
                toggle = not toggle

                self.wx_display_loop(stationiddict, windsdict, wxstringdict, airport_database)
