# -*- coding: utf-8 -*- #
# Update i2c attached devices
"""
Manage OLED Devices.

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

# import math
# import cmath
# import random

from enum import Enum, auto

# import datetime

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1309, ssd1325, ssd1331, sh1106, ws0010

import debugging

# import utils
# import utils_i2c
import utils_gfx

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont


class OLEDCHIPSET(Enum):
    """Support a range of chipsets ; with different features."""

    SSD1306 = auto()  # SSD1306, 128x64/128x32, Monochrome
    SSD1309 = auto()  # SSD1309, 128x64, Monochrome
    SSD1325 = auto()
    SSD1331 = auto()
    SH1106 = auto()
    WS0010 = auto()


class UpdateOLEDs:
    """Class to manage OLED panels."""

    # There are a few different hardware configuration options that could be used.
    # Writing code to automatically handle all of them would make the code very complex, as the
    # code would need to do discovery and verification - and handle different IDs for
    # the devices.
    # TODO: It's not even clear that we could query an i2c display and deduce the correct driver to use.
    #
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
    # before it is used ; and only one device is visible on the i2c bus at a time.
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
    # the time spent inside the critical lock portion should be minimized
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

    OLED_128x64 = {"w": 128, "h": 64}
    OLED_128x32 = {"w": 128, "h": 32}
    OLED_96x36 = {"w": 96, "h": 36}
    OLED_96x16 = {"w": 96, "h": 16}
    OLED_240x320 = {"w": 240, "h": 320}

    reentry_check = False
    conf = None
    airport_database = None
    i2cbus = None

    device_count = 0

    oled_list = []
    oled_dict_default = {
        "size": OLED_128x64,
        "mode": MONOCHROME,
        "chipset": "sh1106",
        "device": None,
        "active": False,
        "devid": 0,
    }

    def __init__(self, conf, airport_database, i2cbus):
        self.conf = conf
        self.airport_database = airport_database
        self.i2cbus = i2cbus
        self.device_count = self.conf.get_int("oled", "oled_count")

        debugging.debug("OLED: Config setup for {self.device_count} devices")

        for device_idnum in range(0, (self.device_count)):
            debugging.debug(f"OLED: Polling for device: {device_idnum}")
            self.oled_list.insert(device_idnum, self.oled_device_init(device_idnum))
            self.oled_text(device_idnum, f"Init {device_idnum}")

        debugging.debug(f"OLED: Init complete : oled_list len {len(self.oled_list)}")

    def oled_device_init(self, device_idnum):
        """Initialize individual OLED devices."""
        # Initial version just assumes all OLED devices are the same.
        oled_dev = self.oled_dict_default.copy()
        oled_dev["active"] = False
        oled_dev["devid"] = device_idnum
        device = None
        self.oled_select(device_idnum)
        if self.i2cbus.i2c_exists(self.OLEDI2CID):
            serial = i2c(port=1, address=self.OLEDI2CID)
            if oled_dev["chipset"] == "sh1106":
                device = sh1106(serial)
            elif oled_dev["chipset"] == "ssd1306":
                device = ssd1306(serial)
            oled_dev["device"] = device
            oled_dev["active"] = True
            debugging.debug("OLED: Activating: {device_idnum}")
        return oled_dev

    def oled_select(self, oled_id):
        """Activate a specific OLED"""
        # This should support a mapping of specific OLEDs to i2c channels
        # Simple for now - with a 1:1 mapping
        self.i2cbus.select(oled_id)

    def oled_text(self, oled_id, txt):
        """Update oled_id with the message from txt."""
        if oled_id > len(self.oled_list):
            debugging.warn("OLED: Attempt to access index beyond list length {oled_id}")
            return
        oled_dev = self.oled_list[oled_id]
        if oled_dev["active"] is False:
            debugging.warn(f"OLED: Attempting to update disabled OLED : {oled_id}")
            return

        fnt = ImageFont.load_default()
        # image = Image.new(oled_dev["mode"], (width, height))  # Make sure to create image with mode '1' for 1-bit color.
        # draw = ImageDraw.Draw(image)
        # txt_w, txt_h = draw.textsize(txt, fnt)
        device = oled_dev["device"]
        debugging.debug(f"OLED: Writing to device: {oled_id} : Msg : {txt}")
        self.oled_select(oled_id)
        self.i2cbus.bus_lock()
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((30, 40), txt, font=fnt, fill="white")
        self.i2cbus.bus_unlock()

    def generate_image(self, oled_id, airport, rway_angle, winddir, windspeed):
        """Create and save Web version of OLED display image"""

        # Image Dimensions
        width = 320
        height = 200
        image_filename = f"static/oled_{oled_id}_oled_display.png"

        # Runway Dimensions
        rway_width = 16
        rway_x = 15  # 15 pixel border
        rway_y = int(height / 2 - rway_width / 2)
        airport_details = f"{airport} {winddir}@{windspeed}"
        wind_poly = utils_gfx.create_wind_arrow(winddir, width, height)
        runway_poly = utils_gfx.create_runway(
            rway_x, rway_y, rway_width, rway_angle, width, height
        )

        img = Image.new("RGB", (width, height), color=(73, 109, 137))

        d = ImageDraw.Draw(img)
        d.text((10, 10), airport_details, fill=(255, 255, 0))
        d.polygon(wind_poly, fill="white", outline="white", width=1)
        d.polygon(runway_poly, fill=None, outline="white", width=1)

        img.save(image_filename)

    def draw_wind(self, oled_id, airport, rway_angle, winddir, windspeed):
        """Draw Wind Arrow and Runway."""
        if oled_id > len(self.oled_list):
            debugging.warn("OLED: Attempt to access index beyond list length {oled_id}")
            return
        oled_dev = self.oled_list[oled_id]
        if oled_dev["active"] is False:
            debugging.warn(f"OLED: Attempting to update disabled OLED : {oled_id}")
            return

        device = oled_dev["device"]
        width = oled_dev["size"]["w"]
        height = oled_dev["size"]["h"]

        # Runway Dimensions
        rway_width = 6
        rway_x = 5  # 5 pixel border
        rway_y = int(height / 2 - rway_width / 2)
        airport_details = f"{airport} {winddir}@{windspeed}"
        wind_poly = utils_gfx.create_wind_arrow(winddir, width, height)
        runway_poly = utils_gfx.create_runway(
            rway_x, rway_y, rway_width, rway_angle, width, height
        )

        self.i2cbus.bus_lock()
        with canvas(device) as draw:
            draw.text(
                (1, 1), airport_details, font=ImageFont.load_default(), fill="white"
            )
            draw.polygon(wind_poly, fill="white", outline="white")
            draw.polygon(runway_poly, fill=None, outline="white")
        self.i2cbus.bus_unlock()
        return

    def update_oled_wind(self, oled_id, airportcode, default_rwy):
        """Draw WIND Info on designated OLED."""
        # FIXME: Hardcoded data
        airport_list = self.airport_database.get_airport_dict_led()
        airport_record = airport_list[airportcode]["airport"]
        if airport_record is None:
            debugging.debug(f"Skipping OLED update {airportcode} lookup returns :None:")
            return
        windspeed = airport_record.get_wx_windspeed()
        if windspeed is None:
            windspeed = 0
        winddir = airport_record.get_wx_dir_degrees()
        best_runway = airport_record.best_runway()
        if best_runway is None:
            best_runway = default_rwy
        if (winddir is not None) and (best_runway is not None):
            debugging.info(
                f"Updating OLED Wind: {airportcode} : rwy: {best_runway} : wind {winddir}"
            )
            self.draw_wind(oled_id, airportcode, best_runway, winddir, windspeed)
            self.generate_image(oled_id, airportcode, best_runway, winddir, windspeed)
        return

    def update_oled_status(self, oled_id):
        """Status Update Display"""

        return

    def update_loop(self):
        """Continuous Loop for Thread."""
        debugging.debug("OLED: Entering Update Loop")
        outerloop = True  # Set to TRUE for infinite outerloop
        count = 0
        while outerloop:
            count += 1
            debugging.info("OLED: Updating OLEDs")
            for oled_id in range(0, (self.device_count)):
                self.oled_text(oled_id, f"run({count}): {oled_id}")
                # TODO: This is hardcoded
                if oled_id == 1:
                    self.update_oled_wind(oled_id, "kbfi", 140)
                if oled_id == 2:
                    self.update_oled_wind(oled_id, "ksea", 160)
                if oled_id == 3:
                    self.update_oled_wind(oled_id, "kpae", 160)
                if oled_id == 4:
                    self.update_oled_wind(oled_id, "kpwt", 200)
                if oled_id == 5:
                    self.update_oled_wind(oled_id, "kfhr", 340)
                if oled_id == 6:
                    self.update_oled_status(oled_id)
            # time.sleep(20)
            time.sleep(180)
