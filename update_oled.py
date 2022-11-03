# -*- coding: utf-8 -*- #
# Update i2c attached devices
"""
Manage OLED Devices

Support a discrete thread that updates OLED display devices

OLED Display devices can be used to share

1/ Configuration Information
2/ Home Airport information
3/ Wind / Runway info
4/ Airport MOS information
5/ Alerts
6/ Status Information
6a/ Errors
6b/ Age of Updates
6c/ ???

"""

import time

from enum import Enum, auto

# import datetime

from luma.core.interface.serial import i2c, spi, pcf8574
from luma.core.interface.parallel import bitbang_6800
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1309, ssd1325, ssd1331, sh1106, ws0010

import debugging
import utils
import utils_i2c

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


class OLEDCHIPSET(Enum):
    """Support a range of chipsets ; with different features"""

    SSD1306 = auto()  # SSD1306, 128x64/128x32, Monochrome
    SSD1309 = auto()  # SSD1309, 128x64, Monochrome
    SSD1325 = auto()
    SSD1331 = auto()
    SH1106 = auto()
    WS0010 = auto()


class UpdateOLEDs:
    """Class to manage OLED panels"""

    # There are a few different hardware configuration options that could be used.
    # Writing code to automatically handle all of them would make the code very complex, as the
    # code would need to do discovery and verification - and handle different IDs for
    # the devices
    # The initial versions of this code are going to make some simplifying hardware assumptions.
    # More work can happen later to support multiple and mixed configuration options.
    # Inital data structures are going to assume that each OLED gets its own configuration data
    # and doesn't rely on all OLEDs being the same size, orientation, color etc.

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
    # This is to allow other threads to make requests to update data

    # Looking to track data about individual OLED screens ; to allow support for multiple options
    #
    # Chipset : SSD1306 | SH1106
    # Size : 128x32 | 128x64
    # Orientation : Top of OLED pointing towards :  N | S | E | W

    # OLED purpose
    # Exclusive :  Yes | No
    # Wind: Numeric | Image
    # Runway : Data | Picture
    # Config Data : Version | IP  | uptime
    # Metar : Age

    # Draw Behavior
    # Brightness : Low | High | TrackSensor
    # Font :
    # Font Size :
    # Color :
    # Border :

    OLEDI2CID = 0x3C
    MONOCHROME = "1"  # Single bit color mode for ssd1306 / sh1106

    OLED_128x64 = {"h": 128, "w": 64}
    OLED_128x32 = {"h": 128, "w": 32}

    reentry_check = False
    conf = None
    airport_database = None
    i2cbus = None

    oled_list = []
    oled_dict_default = {"size": OLED_128x64, "mode": MONOCHROME, "chipset": "sh1106", "device": None, "active": False}

    def __init__(self, conf, airport_database, i2cbus):

        if self.reentry_check:
            debugging.error("OLED: reentry check failed")
        self.reentry_check = True
        self.conf = conf
        self.airport_database = airport_database
        self.i2cbus = i2cbus

        # rev.1 users set port=0
        # substitute spi(device=0, port=0) below if using that interface
        # substitute bitbang_6800(RS=7, E=8, PINS=[25,24,23,27]) below if using that interface

        self.device_count = self.conf.get_int("oled", "oled_count")

        debugging.info("OLED: Config setup for " + str(self.device_count) + " devices")

        for device_idnum in range(0, (self.device_count)):
            debugging.info("OLED: Trying to add device :" + str(device_idnum))
            self.oled_list.insert(device_idnum, self.oled_init(device_idnum))

    def oled_init(self, device_idnum):
        """Initialize individual OLED devices"""
        # Initial version just assumes all OLED devices are the same.
        oled_dev = self.oled_dict_default
        oled_dev["active"] = False
        device = None
        # TODO: Store OLED model information in configuration data, and use that data
        self.oled_select(device_idnum)
        if self.i2cbus.i2c_exists(self.OLEDI2CID):
            serial = i2c(port=1, address=self.OLEDI2CID)
            if oled_dev["chipset"] == "sh1106":
                device = sh1106(serial)
            elif oled_dev["chipset"] == "ssd1306":
                device = ssd1306(serial)
            oled_dev["device"] = device
            oled_dev["active"] = True
            debugging.info("OLED: Set device active : " + str(device_idnum))
        return oled_dev

    def oled_select(self, oled_id):
        """Activate a specific OLED"""
        # This should support a mapping of specific OLEDs to i2c channels
        # Simple for now - with a 1:1 mapping
        self.i2cbus.select(oled_id)

    def oled_text(self, oled_id, txt):
        """Update oled_id with the message from txt"""
        if oled_id > len(self.oled_list):
            debugging.info("OLED: Attempt to access index beyond list length" + str(oled_id))
            return
        oled_dev = self.oled_list[oled_id]
        if oled_dev["active"] is False:
            debugging.info("OLED: Attempting to update disabled OLED : " + str(oled_id))
            return
        width = oled_dev["size"]["w"]
        height = oled_dev["size"]["h"]

        fnt = ImageFont.load_default()
        image = Image.new(oled_dev["mode"], (width, height))  # Make sure to create image with mode '1' for 1-bit color.
        # draw = ImageDraw.Draw(image)
        # txt_w, txt_h = draw.textsize(txt, fnt)
        device = oled_dev["device"]
        self.oled_select(oled_id)
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((30, 40), txt, fill="white")

    def update_loop(self):
        """Continuous Loop for Thread"""
        debugging.info("OLED: Entering Update Loop")
        for oled_id in range(0, (self.device_count)):
            debugging.info("OLED: Init message " + str(oled_id))
            self.oled_text(oled_id, "booting " + str(oled_id))
        outerloop = True  # Set to TRUE for infinite outerloop
        count = 0
        while outerloop:
            count += 1
            debugging.info("OLED: Updating OLEDs")
            for oled_id in range(0, (self.device_count)):
                self.oled_text(oled_id, "run(" + str(count) + "):" + str(oled_id))
            time.sleep(180)
