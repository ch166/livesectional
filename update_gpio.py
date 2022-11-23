# -*- coding: utf-8 -*- #

"""
# update_gpio.py
# This module updates a set of flags to track switches / buttons attached to GPIO pins
#
"""

# RPI GPIO Pinouts reference
###########################
# 3V3     (1) (2)  5V     #
# GPIO2   (3) (4)  5V     #
# GPIO3   (5) (6)  GND    #
# GPIO4   (7) (8)  GPIO14 #
# GND     (9) (10) GPIO15 #
# GPIO17 (11) (12) GPIO18 #
# GPIO27 (13) (14) GND    #
# GPIO22 (15) (16) GPIO23 #
# 3V3    (17) (18) GPIO24 #
# GPIO10 (19) (20) GND    #
# GPIO9  (21) (22) GPIO25 #
# GPIO11 (23) (24) GPIO8  #
# GND    (25) (26) GPIO7  #
# GPIO0  (27) (28) GPIO1  #
# GPIO5  (29) (30) GND    #
# GPIO6  (31) (32) GPIO12 #
# GPIO13 (33) (34) GND    #
# GPIO19 (35) (36) GPIO16 #
# GPIO26 (37) (38) GPIO20 #
# GND    (39) (40) GPIO21 #
###########################

# Import needed libraries

# Removing URL related actions from update_leds
# import urllib.request
# import urllib.error
# import urllib.parse
# import socket
# import xml.etree.ElementTree as ET
import time
from datetime import datetime
from datetime import timedelta
from datetime import time as time_

# import sys

try:
    import RPi.GPIO as GPIO
except ImportError:
    import fakeRPI.GPIO as GPIO

import debugging


class UpdateGPIO:
    """Class to manage GPIO pins"""

    def __init__(self, conf, airport_database):
        # ****************************************************************************
        # * User defined items to be set below - Make changes to config.py, not here *
        # ****************************************************************************

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
        self.onhour = self.conf.get_int("schedule", "onhour")
        self.offhour = self.conf.get_int("schedule", "offhour")
        self.onminutes = self.conf.get_int("schedule", "onminutes")
        self.offminutes = self.conf.get_int("schedule", "offminutes")

        # delay in fading the home airport if used
        self.fade_delay = conf.get_float("rotaryswitch", "fade_delay")

        # Misc settings
        # 0 = No, 1 = Yes, use wipes. Defined by configurator
        self.usewipes = self.conf.get_int("rotaryswitch", "usewipes")
        # 1 = RGB color codes. 0 = GRB color codes. Populate color codes below with normal RGB codes and script will change if necessary

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

        # True to invert the signal (when using NPN transistor level shift)
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

        # Misc Settings
        # Toggle used for logging when ambient sensor changes from bright to dim.
        self.ambient_toggle = 0

    def update_gpio_flags(self, toggle_value, time_sw, data_sw):
        self.toggle_sw = toggle_value
        # Offset in HOURS to choose which TAF to display
        self.hour_to_display = time_sw
        self.metar_taf_mos = data_sw  # 0 = Display TAF.
        # debugging.info( 'Switch in position ' )

    def update_loop(self):
        # #########################
        # Start of executed code  #
        # #########################
        outerloop = True  # Set to TRUE for infinite outerloop
        tempsleepon = self.conf.get_int("schedule", "tempsleepon")

        while outerloop:

            # Pushbutton for Refresh. check to see if we should turn on temporarily during sleep mode
            if GPIO.input(22) is False:
                # Set to turn lights on two seconds ago to make sure we hit the loop next time through
                self.end_time = (datetime.now() - timedelta(seconds=2)).time()
                self.timeoff = (datetime.now() + timedelta(minutes=tempsleepon)).time()
                self.temp_lights_on = 1  # Set this to 1 if button is pressed

            # Check if rotary switch is used, and what position it is in. This will determine what to display, METAR, TAF and MOS data.
            # If TAF or MOS data, what time offset should be displayed, i.e. 0 hour, 1 hour, 2 hour etc.
            # If there is no rotary switch installed, then all these tests will fail and will display the defaulted data from switch position 0
            if GPIO.input(0) is False and self.toggle_sw != 0:
                self.update_gpio_flags(
                    0,
                    self.conf.get_int("rotaryswitch", "time_sw0"),
                    self.conf.get_int("rotaryswitch", "data_sw0"),
                )

            elif GPIO.input(5) is False and self.toggle_sw != 1:
                self.update_gpio_flags(
                    1,
                    self.conf.get_int("rotaryswitch", "time_sw1"),
                    self.conf.get_int("rotaryswitch", "data_sw1"),
                )

            elif GPIO.input(6) is False and self.toggle_sw != 2:
                self.update_gpio_flags(
                    2,
                    self.conf.get_int("rotaryswitch", "time_sw2"),
                    self.conf.get_int("rotaryswitch", "data_sw2"),
                )

            elif GPIO.input(13) is False and self.toggle_sw != 3:
                self.update_gpio_flags(
                    3,
                    self.conf.get_int("rotaryswitch", "time_sw3"),
                    self.conf.get_int("rotaryswitch", "data_sw3"),
                )

            elif GPIO.input(19) is False and self.toggle_sw != 4:
                self.update_gpio_flags(
                    4,
                    self.conf.get_int("rotaryswitch", "time_sw4"),
                    self.conf.get_int("rotaryswitch", "data_sw4"),
                )

            elif GPIO.input(26) is False and self.toggle_sw != 5:
                self.update_gpio_flags(
                    5,
                    self.conf.get_int("rotaryswitch", "time_sw5"),
                    self.conf.get_int("rotaryswitch", "data_sw5"),
                )

            elif GPIO.input(21) is False and self.toggle_sw != 6:
                self.update_gpio_flags(
                    6,
                    self.conf.get_int("rotaryswitch", "time_sw6"),
                    self.conf.get_int("rotaryswitch", "data_sw6"),
                )

            elif GPIO.input(20) is False and self.toggle_sw != 7:
                self.update_gpio_flags(
                    7,
                    self.conf.get_int("rotaryswitch", "time_sw7"),
                    self.conf.get_int("rotaryswitch", "data_sw7"),
                )

            elif GPIO.input(16) is False and self.toggle_sw != 8:
                self.update_gpio_flags(
                    8,
                    self.conf.get_int("rotaryswitch", "time_sw8"),
                    self.conf.get_int("rotaryswitch", "data_sw8"),
                )

            elif GPIO.input(12) is False and self.toggle_sw != 9:
                self.update_gpio_flags(
                    9,
                    self.conf.get_int("rotaryswitch", "time_sw9"),
                    self.conf.get_int("rotaryswitch", "data_sw9"),
                )

            elif GPIO.input(1) is False and self.toggle_sw != 10:
                self.update_gpio_flags(
                    10,
                    self.conf.get_int("rotaryswitch", "time_sw10"),
                    self.conf.get_int("rotaryswitch", "data_sw10"),
                )

            elif GPIO.input(7) is False and self.toggle_sw != 11:
                self.update_gpio_flags(
                    11,
                    self.conf.get_int("rotaryswitch", "time_sw11"),
                    self.conf.get_int("rotaryswitch", "data_sw11"),
                )

            elif self.toggle_sw == -1:  # used if no Rotary Switch is installed
                self.update_gpio_flags(
                    12,
                    self.conf.get_int("rotaryswitch", "time_sw0"),
                    self.conf.get_int("rotaryswitch", "data_sw0"),
                )

                # Check to see if pushbutton is pressed to force an update of FAA Weather
                # If no button is connected, then this is bypassed and will only update when 'update_interval' is met
            if GPIO.input(22) is False:
                debugging.info(
                    "Refresh Pushbutton Pressed. Breaking out of loop to refresh FAA Data"
                )

            # Light sensor has ability to send interrupts..
            # TODO: Come back to here and figure out if we're handling that code here
            # or if we should handle it elsewhere
            #
            # Bright light will provide a low state (0) on GPIO. Dark light will provide a high state (1).
            # Full brightness will be used if no light sensor is installed.
            #
            # if GPIO.input(4) == 1:
            #     self.LED_BRIGHTNESS = self.conf.get_int("lights", "dimmed_value")
            #    if self.ambient_toggle == 1:
            #        debugging.info("Ambient Sensor set brightness to dimmed_value")
            #        self.ambient_toggle = 0
            # else:
            #    self.LED_BRIGHTNESS = self.conf.get_int("lights", "bright_value")
            #    if self.ambient_toggle == 0:
            #        debugging.info("Ambient Sensor set brightness to bright_value")
            #        self.ambient_toggle = 1
            time.sleep(5)
