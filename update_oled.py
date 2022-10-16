# -*- coding: utf-8 -*- #

# Update i2c attached devices


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


import time
import datetime

from luma.core.interface.serial import i2c, spi, pcf8574
from luma.core.interface.parallel import bitbang_6800
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1309, ssd1325, ssd1331, sh1106, ws0010

import debugging
import utils
import utils_i2c


class UpdateOLEDs:
    """Class to manage OLED panels"""

    # There are a few different hardware configuration options that could be used.
    # Writing code to automatically handle all of them would make the code very complex, as the
    # code would need to do discovery and verification - and handle different IDs for
    # the devices

    # Broad option 1 - Single OLED device
    # There is a single OLED device (SH1106 or SSD1306 or similar)
    # It will exist on a single i2c device id

    # Broad option 2 - Multiple OLED devices connected via an i2c multiplexer
    # for example: TCA9548A i2c Multiplexer
    # In this scenario - a call is made to the mux to enable a single i2c device
    # before it is used ; and only one device is visible at a time.
    # Many OLED devices can be connected ; and they can all have the same device ID;
    # as they will only be used when they are selected by the mux ; and at the point
    # they are the only visible device with that id

    # Broad option 3 - Multiple OLED devices on the i2c bus at the same time
    # This requires each device to have a unique i2c address, which can require
    # physical modification of the device (jumper / soldering / cut trace)

    # The i2c bus may be used to handle other devices ( light sensor / temp sensor etc. )
    # so operations on the i2c bus should be moved to a common i2c module.
    # Operations interacting with devices on the i2c bus should not assume that the bus
    # configuration is unchanged - and should also ensure that access does not lock out other
    # users of the bus

    # Broad patterns of access should look like
    # prep data
    # do work
    # update i2c device
    #   lock i2c bus
    #   select i2c device
    #   push changes
    #   release i2c lock
    #
    # the time spend inside the critical lock portion should be minimized

    def __init__(self, conf, airport_database):
        self.conf = conf

        self.airport_database = airport_database

        # rev.1 users set port=0
        # substitute spi(device=0, port=0) below if using that interface
        # substitute bitbang_6800(RS=7, E=8, PINS=[25,24,23,27]) below if using that interface

        # TODO: Move all i2c functions out to a utils_i2c.py module
        serial = i2c(port=1, address=0x3C)

        # substitute ssd1331(...) or sh1106(...) below if using that device
        # device = ssd1306(serial)
        device = sh1106(serial)

        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((30, 40), "Hello World", fill="white")

    def update_loop(self):
        toggle = 0  # used for homeport display
        outerloop = True  # Set to TRUE for infinite outerloop
        display_num = 0
        while outerloop:
            display_num = display_num + 1

            # Dictionary definitions. Need to reset whenever new weather is received
            stationiddict = {}
            windsdict = {"": ""}
            wxstringdict = {"": ""}
