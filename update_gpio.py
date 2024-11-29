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
import time
from datetime import datetime
from datetime import timedelta
from datetime import time as time_

# try:
#     import RPi.GPIO as GPIO
# except ImportError:
#     import fakeRPI.GPIO as GPIO

# Migrating to gpiozero
import gpiozero

import debugging


class UpdateGPIO:
    """Class to manage GPIO pins"""

    # Pin reservations in docs/HARDWARE.md
    #

    conf = None
    airport_database = None

    # Hardware Features
    led_enabled = False
    led_style = "RGB"
    light_sensor = False
    oled_enabled = False
    oled_count = 0

    encoder0 = None
    encoder1 = None
    encoder2 = None

    feature0 = None
    feature1 = None
    feature2 = None
    feature3 = None
    feature4 = None
    feature5 = None

    switch_positions = None

    def __init__(self, conf, airport_database):
        """Init"""
        # ****************************************************************************
        # * User defined items to be set below - Make changes to config.py, not here *
        # ****************************************************************************

        self.conf = conf
        self.airport_database = airport_database

        # set mode to BCM and use BCM pin numbering, rather than BOARD pin numbering.
        # Not required as gpiozero defaults to BCM numbering
        # GPIO.setmode(GPIO.BCM)

        # Setup GPIO pins for rotary switch connected through 8-3 octal encoder
        #  8->3 encoder - GPIO 5(pin 29),6(pin 31),13(pin 33)
        self.encoder0 = gpiozero.Button(5, pull_up=False, bounce_time=1)
        self.encoder1 = gpiozero.Button(6, pull_up=False, bounce_time=1)
        self.encoder2 = gpiozero.Button(13, pull_up=False, bounce_time=1)

        # Setup GPIO pins for Hardware Feature jumpers
        self.feature0 = gpiozero.Button(17, pull_up=False, bounce_time=1)
        self.feature1 = gpiozero.Button(27, pull_up=False, bounce_time=1)
        self.feature2 = gpiozero.Button(22, pull_up=False, bounce_time=1)
        self.feature3 = gpiozero.Button(23, pull_up=False, bounce_time=1)
        self.feature4 = gpiozero.Button(24, pull_up=False, bounce_time=1)
        self.feature5 = gpiozero.Button(25, pull_up=False, bounce_time=1)

        # Setup Interrupt monitoring for pin 32 (GPIO12)
        # Wake UP / Refresh
        self.wakeup = gpiozero.Button(12, pull_up=False, bounce_time=2)
        self.wakeup.when_pressed = self.intr_handler_wakeup

        # Setup Interrupt monitoring for pin 36 (GPIO16)
        # Wake UP / Refresh
        self.modechange = gpiozero.Button(16, pull_up=False, bounce_time=2)
        self.modechange.when_pressed = self.intr_handler_mode

        self.read_hardware_settings()

        # Switch Position Controls
        # time = Future Offset Hours
        # data = 0:Metar ; 1:TAF ; 2:MOS
        switch_positions = [
            {
                "data": self.conf.get_int("rotaryswitch", "data_sw0"),
                "time": self.conf.get_int("rotaryswitch", "time_sw0"),
            },
            {
                "data": self.conf.get_int("rotaryswitch", "data_sw1"),
                "time": self.conf.get_int("rotaryswitch", "time_sw1"),
            },
            {
                "data": self.conf.get_int("rotaryswitch", "data_sw2"),
                "time": self.conf.get_int("rotaryswitch", "time_sw2"),
            },
            {
                "data": self.conf.get_int("rotaryswitch", "data_sw3"),
                "time": self.conf.get_int("rotaryswitch", "time_sw3"),
            },
            {
                "data": self.conf.get_int("rotaryswitch", "data_sw4"),
                "time": self.conf.get_int("rotaryswitch", "time_sw4"),
            },
            {
                "data": self.conf.get_int("rotaryswitch", "data_sw5"),
                "time": self.conf.get_int("rotaryswitch", "time_sw5"),
            },
            {
                "data": self.conf.get_int("rotaryswitch", "data_sw6"),
                "time": self.conf.get_int("rotaryswitch", "time_sw6"),
            },
            {
                "data": self.conf.get_int("rotaryswitch", "data_sw7"),
                "time": self.conf.get_int("rotaryswitch", "time_sw7"),
            },
        ]

    def rotary_switch_value(self):
        """Read current value from octal encoder on pins 29/31/33"""
        pin0 = 0
        pin1 = 0
        pin2 = 0
        if self.encoder0.is_pressed:
            pin0 = 1
        if self.encoder1.is_pressed:
            pin1 = 1
        if self.encoder2.is_pressed:
            pin2 = 1
        switch_value = int(f"{pin2}{pin1}{pin0}", 2)
        return switch_value

    def intr_handler_wakeup(self):
        """Interrupt Handler for Wakeup button"""
        debugging.info("Interrupt handling for wakeup button")
        # Pushbutton for Refresh. check to see if we should turn on temporarily during sleep mode
        # Set to turn lights on two seconds ago to make sure we hit the loop next time through
        #
        # self.end_time = (datetime.now() - timedelta(seconds=2)).time()
        # self.timeoff = (datetime.now() + timedelta(minutes=tempsleepon)).time()
        # self.temp_lights_on = 1  # Set this to 1 if button is pressed
        # return

    def intr_handler_mode(self):
        """Interrupt Handler for LED Mode button"""
        debugging.info("Interrupt handling for mode button")
        return

    def read_hardware_settings(self):
        """Read current value from pins"""
        if self.feature0.is_pressed:
            self.led_enabled = True
        else:
            self.led_enabled = False
        if self.feature1.is_pressed:
            self.led_style = "GRB"
        else:
            self.led_style = "RGB"
        if self.feature2.is_pressed:
            self.light_sensor = True
        else:
            self.light_sensor = False

        # Process the OLED flags
        pin0 = 0
        pin1 = 0
        if self.feature3.is_pressed:
            pin0 = 1
        if self.feature4.is_pressed:
            pin1 = 1
        oled_flags = int(f"{pin1}{pin0}", 2)

        if oled_flags == 0:
            self.oled_enabled = False
        else:
            self.oled_enabled = True
        self.oled_count = 0
        if oled_flags == 1:
            self.oled_count = 4
        elif oled_flags == 2:
            self.oled_count = 6
        elif oled_flags == 3:
            self.oled_count = 8

    def old_original__init__(self, conf, airport_database):
        """Deleting this.."""
        # ****************************************************************************
        # * User defined items to be set below - Make changes to config.py, not here *
        # ****************************************************************************

        # Specific Variables to default data to display if Rotary Switch is not installed.
        # hour_to_display # Offset in HOURS to choose which TAF/MOS to display
        self.hour_to_display = self.conf.get_int("rotaryswitch", "time_sw0")
        # metar_taf_mos
        # 0 = Display TAF,
        # 1 = Display METAR,
        # 2 = Display MOS,
        # 3 = Heat Map (Heat map not controlled by rotary switch)
        self.metar_taf_mos = self.conf.get_int("rotaryswitch", "data_sw0")
        # Set toggle_sw to an initial value that forces rotary switch to dictate data displayed
        self.toggle_sw = -1
        self.onhour = self.conf.get_int("schedule", "onhour")
        self.offhour = self.conf.get_int("schedule", "offhour")
        self.onminutes = self.conf.get_int("schedule", "onminutes")
        self.offminutes = self.conf.get_int("schedule", "offminutes")

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

    def update_gpio_flags(self, time_sw, data_sw):
        """Offset in HRS to select appropriate TAF"""
        self.hour_to_display = time_sw
        self.metar_taf_mos = data_sw

    def update_loop(self):
        """Main thread loop"""
        # #########################
        # Start of executed code  #
        # #########################
        outerloop = True  # Set to TRUE for infinite outerloop
        tempsleepon = self.conf.get_int("schedule", "tempsleepon")

        while outerloop:
            self.read_hardware_settings()
            rotary_switch = self.rotary_switch_value()

            # Check if rotary switch is used, and what position it is in. This will determine what to display, METAR, TAF and MOS data.
            # If TAF or MOS data, what time offset should be displayed, i.e. 0 hour, 1 hour, 2 hour etc.
            # If there is no rotary switch installed, then all these tests will fail and will display the defaulted data from switch position 0
            self.update_gpio_flags(
                self.switch_positions[rotary_switch]["time"],
                self.switch_positions[rotary_switch]["data"],
            )

            time.sleep(5)
