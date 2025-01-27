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
from enum import Enum, auto

import json
import shutil

from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306, ssd1309, ssd1325, ssd1331, sh1106

import debugging

import utils

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
    #
    # TODO: It's not even clear that we could query an i2c display and deduce the correct driver to use.
    #
    # The initial versions of this code are going to make some simplifying hardware assumptions.
    # More work can happen later to support multiple and mixed configuration options.
    # Initial data structures are going to assume that each OLED gets its own configuration data
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
    # update data for i2c device
    # lock i2c bus
    #    if necessary select i2c device
    #    push changes
    # release i2c bus lock
    #
    # the time spent inside the critical lock portion should be minimized, with as much prep work
    # completed before starting the lock.
    # This is to allow other threads to have as much time as possible to use the i2c bus

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

    ACTIVITY = [
        "(>---------)",  # moving -->
        "(->--------)",  # moving -->
        "(-->-------)",  # moving -->
        "(--->------)",  # moving -->
        "(---->-----)",  # moving -->
        "(----->----)",  # moving -->
        "(------>---)",  # moving -->
        "(------->--)",  # moving -->
        "(-------->-)",  # moving -->
        "(---------*)",  # moving -->
        "(---------<)",  # moving -->
        "(--------<-)",  # moving <--
        "(-------<--)",  # moving <--
        "(------<---)",  # moving <--
        "(-----<----)",  # moving <--
        "(----<-----)",  # moving <--
        "(---<------)",  # moving <--
        "(--<-------)",  # moving <--
        "(-<--------)",  # moving <--
        "(*---------)",  # moving <--
    ]

    reentry_check = False
    _app_conf = None
    _airport_database = None
    _i2cbus = None

    _device_count = 0

    _oled_device_config = {}
    _oled_metar_airports = []

    oled_list = []
    oled_dict_default = {
        "size": OLED_128x64,
        "mode": MONOCHROME,
        "chipset": OLEDCHIPSET.SH1106,
        "device": None,
        "active": False,
        "devid": 0,
    }

    def __init__(self, conf, sysdata, airport_database, i2cbus, led_mgmt):
        self._app_conf = conf
        self._led_mgmt = led_mgmt
        self._sysdata = sysdata
        self._airport_database = airport_database
        self._i2cbus = i2cbus
        device_count = self._app_conf.get_int("oled", "oled_count")

        debugging.debug(f"OLED: Config setup for {self._device_count} devices")

        self._oled_device_config = {}
        self.load_oled_conf()

        oled_dev_found = 0
        for device_idnum in range(0, device_count):
            debugging.debug(f"OLED: Polling for device: {device_idnum}")
            oled_device_discovery = self.oled_device_init(device_idnum)
            if oled_device_discovery["active"]:
                oled_dev_found += 1
                self.oled_list.insert(device_idnum, oled_device_discovery)
                self.oled_text(device_idnum, f"Init {device_idnum}")
        self._device_count = oled_dev_found

        # New OLED Conf

        debugging.debug(
            f"OLED: Init complete : oled_list len {len(self.oled_list)}/ conf {device_count}"
        )

    def load_oled_conf(self):
        """Load OLED configuration."""
        # FIXME: Add file error handling
        debugging.debug("Loading Airport List")
        oled_conf_json = self._app_conf.get_string("filenames", "oled_conf_json")
        # Opening JSON file
        if not utils.file_exists(oled_conf_json):
            debugging.debug(f"OLED conf json does not exist: {oled_conf_json}")
            return

        json_file = open(oled_conf_json, encoding="utf-8")
        # returns JSON object as a dictionary
        new_oled_json_dict = json.load(json_file)
        # Closing file
        json_file.close()

        self.oled_conf_from_json(new_oled_json_dict)
        debugging.debug("Airport Load and Merge complete")

    def save_oled_conf(self):
        """Save Airport Data file."""
        debugging.debug("Saving Airport DB")
        json_save_data = {}
        oled_json_backup = self._app_conf.get_string("filenames", "oled_conf_backup")
        oled_json_tmp = self._app_conf.get_string("filenames", "oled_conf_json_tmp")
        oled_json = self._app_conf.get_string("filenames", "oled_conf_json")

        shutil.move(oled_json, oled_json_backup)
        json_save_data = self.save_data_from_db()
        debugging.info(f"Saving OLED config : {json_save_data}")
        with open(oled_json_tmp, "w", encoding="utf-8") as json_file:
            json.dump(json_save_data, json_file, sort_keys=False, indent=4)
        shutil.move(oled_json_tmp, oled_json)

    def oled_conf_from_json(self, oled_json_dict):
        """Generate OLED conf from json data"""
        if oled_json_dict is None:
            return
        for oled_entry in oled_json_dict["oled"]:
            self._oled_device_config[oled_entry["id"]] = oled_entry
        self._oled_metar_airports = oled_json_dict["metar"]
        debugging.info(
            f"oled conf load: oled:{self._oled_device_config} / metar:{self._oled_metar_airports}"
        )

    def save_data_from_db(self):
        """Generate JSON data for saving."""
        json_save_data = {"oled": [], "metar": []}
        for oled_entry in self._oled_device_config:
            json_save_data["oled"].append(oled_entry)
        for metar_entry in self._oled_metar_airports:
            json_save_data["metar"].extend(metar_entry)
        return json_save_data

    def get_oled_model(self, modelstr):
        """Get OLED model from string"""
        if modelstr == "sh1106":
            return OLEDCHIPSET.SH1106
        elif modelstr == "ssd1306":
            return OLEDCHIPSET.SSD1306
        elif modelstr == "ssd1309":
            return OLEDCHIPSET.SSD1309
        elif modelstr == "ssd1325":
            return OLEDCHIPSET.SSD1325
        elif modelstr == "ssd1331":
            return OLEDCHIPSET.SSD1331
        elif modelstr == "ws0010":
            return OLEDCHIPSET.WS0010
        else:
            return None

    def oled_device_init(self, device_idnum):
        """Initialize individual OLED devices."""
        # This initial version just assumes all OLED devices are the same.
        # TODO: Get OLED config information from config.ini
        oled_dev = self.oled_dict_default.copy()
        oled_conf_def = self._oled_device_config[f"{device_idnum}"]
        oled_dev["active"] = False
        oled_dev["devid"] = device_idnum
        oled_dev["chipset"] = self.get_oled_model(oled_conf_def["model"])
        oled_dev["rotation"] = oled_conf_def["rotation"]
        oled_dev["purpose"] = oled_conf_def["purpose"]

        debugging.info(f"oled init {oled_dev}")
        device = None
        self.oled_select(oled_dev["devid"])
        if self._i2cbus.i2c_exists(self.OLEDI2CID):
            serial = i2c(port=1, address=self.OLEDI2CID)
            if oled_dev["chipset"] == OLEDCHIPSET.SH1106:
                device = sh1106(serial)
            elif oled_dev["chipset"] == OLEDCHIPSET.SSD1306:
                device = ssd1306(serial)
            elif oled_dev["chipset"] == OLEDCHIPSET.SSD1309:
                device = ssd1309(serial)
            elif oled_dev["chipset"] == OLEDCHIPSET.SSD1325:
                device = ssd1325(serial)
            elif oled_dev["chipset"] == OLEDCHIPSET.SSD1331:
                device = ssd1331(serial)
            oled_dev["device"] = device
            oled_dev["active"] = True
            debugging.debug("OLED: Activating: {device_idnum}")
        return oled_dev

    def oled_select(self, oled_id):
        """Activate a specific OLED."""
        # This should support a mapping of specific OLEDs to i2c channels
        # Simple for now - with a 1:1 mapping
        self._i2cbus.select(oled_id)

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
        # Make sure to create image with mode '1' for 1-bit color.
        # image = Image.new(oled_dev["mode"], (width, height))
        # draw = ImageDraw.Draw(image)
        # txt_w, txt_h = draw.textsize(txt, fnt)
        device = oled_dev["device"]
        device_i2cbus_id = oled_dev["devid"]

        debugging.debug(f"OLED: Writing to device: {oled_id} : Msg : {txt}")
        if self._i2cbus.bus_lock("oled_text"):
            try:
                self.oled_select(device_i2cbus_id)
                with canvas(device) as draw:
                    draw.rectangle(device.bounding_box, outline="white", fill="black")
                    draw.text((5, 5), txt, font=fnt, fill="white")
            finally:
                self._i2cbus.bus_unlock()
        else:
            debugging.info(f"Failed to grab lock for oled:{oled_id}")
            self._i2cbus.bus_unlock()

    def generate_info_image(self, oled_id):
        """Create the status/info image."""
        # Image Dimensions
        width = 320
        height = 200
        image_filename = f"static/oled_{oled_id}_oled_display.png"

        metarage = utils.time_format_hms(self._airport_database.get_metar_update_time())
        currtime = utils.time_format_hms(utils.current_time(self._app_conf))
        info_timestamp = f"time:{currtime} metar:{metarage}"
        info_ipaddr = f"ipaddr:{self._sysdata.local_ip()}"
        info_uptime = f"uptime:{self._sysdata.uptime()}"
        info_lightlevel = f"brt:{self._led_mgmt.get_brightness_level()}%"

        img = Image.new("RGB", (width, height), color=(73, 109, 137))
        oled_canvas = ImageDraw.Draw(img)

        # oled_canvas.text((10, 10), "Status Info", fill=(255, 255, 0))
        oled_canvas.text((10, 10), info_ipaddr, fill=(255, 255, 0))
        oled_canvas.text((10, 30), info_uptime, fill=(255, 255, 0))
        oled_canvas.text((10, 50), info_timestamp, fill=(255, 255, 0))
        oled_canvas.text((10, 50), info_lightlevel, fill=(255, 255, 0))

        img.save(image_filename)

    def generate_image(
        self, oled_id, airport, rway_label, rway_angle, winddir, windspeed
    ):
        """Create and save Web version of OLED display image."""
        # Image Dimensions
        width = 320
        height = 200
        image_filename = f"static/oled_{oled_id}_oled_display.png"

        # Runway Dimensions
        rway_width = 16
        rway_x = 15  # 15 pixel border
        rway_y = int(height / 2 - rway_width / 2)
        # TODO: Need to be smart about what we display ; use the current data to report important information.
        airport_details = f"{airport} {winddir}@{windspeed}"
        metarage = utils.time_format_hms(self._airport_database.get_metar_update_time())
        currtime = utils.time_format_hms(utils.current_time(self._app_conf))
        best_rway = f"Best runway: {rway_label}"
        information_timestamp = f"time:{currtime} metar:{metarage}\n{best_rway}"
        wind_poly = utils_gfx.create_wind_arrow(winddir, width, height)
        runway_poly = utils_gfx.create_runway(
            rway_x, rway_y, rway_width, rway_angle, width, height
        )

        img = Image.new("RGB", (width, height), color=(73, 109, 137))

        oled_canvas = ImageDraw.Draw(img)
        oled_canvas.text((10, 10), airport_details, fill=(255, 255, 0))
        oled_canvas.text((10, height - 40), information_timestamp, fill=(255, 255, 0))
        oled_canvas.polygon(wind_poly, fill="white", outline="white", width=1)
        oled_canvas.polygon(runway_poly, fill=None, outline="white", width=1)

        img.save(image_filename)

    def draw_nowx(self, oled_id, airport, rway_label, rway_angle, winddir, windspeed):
        """Draw NOWX message."""
        # TODO: This code assumes a single runway direction only. Need to handle airports with multiple runways
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
        device_i2cbus_id = oled_dev["devid"]
        display_font = ImageFont.load_default(size=20)

        airport_details = f"{airport} NOWX"

        if self._i2cbus.bus_lock("draw_nowx"):
            self.oled_select(device_i2cbus_id)
            with canvas(device) as draw:
                draw.text(
                    (5, height / 2), airport_details, font=display_font, fill="white"
                )
            self._i2cbus.bus_unlock()
        else:
            debugging.info(f"Failed to grab lock for oled:{oled_id}")
        return

    def draw_wind(
        self, oled_id, airport, best_runway_label, best_runway_deg, winddir, windspeed
    ):
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
        device_i2cbus_id = oled_dev["devid"]

        #
        font = ImageFont.load_default(size=12)

        # Runway Dimensions
        rway_width = 6
        rway_x = 5  # 5 pixel border
        rway_y = int(height / 2 - rway_width / 2)
        airport_details = f"{airport}\n{winddir}@{windspeed}"
        wind_poly = utils_gfx.create_wind_arrow(winddir, width, height)
        runway_poly = utils_gfx.create_runway(
            rway_x, rway_y, rway_width, best_runway_deg, width, height
        )
        runway_details = f"Best Runway {best_runway_label}"

        (tx_l, tx_t, tx_r, tx_b) = font.getbbox(text=runway_details)
        runway_details_height = tx_t + tx_b

        if self._i2cbus.bus_lock("draw_wind"):
            self.oled_select(device_i2cbus_id)
            with canvas(device) as draw:
                draw.text(
                    (10, 1),
                    airport_details,
                    font=ImageFont.load_default(size=12),
                    fill="white",
                )
                draw.polygon(wind_poly, fill="white", outline="white")
                draw.polygon(runway_poly, fill=None, outline="white")
                draw.text(
                    (1, height - runway_details_height),
                    runway_details,
                    font=ImageFont.load_default(14),
                    fill="white",
                )
            self._i2cbus.bus_unlock()
        else:
            debugging.info(f"Failed to grab lock for oled:{oled_id}")
        return

    def update_oled_wind(
        self, oled_id, airportcode, default_rwy_label, default_rwy_deg
    ):
        """Draw WIND Info on designated OLED."""
        # FIXME: Hardcoded data
        airport_list = self._airport_database.get_airport_dict_led()
        if airportcode not in airport_list:
            debugging.debug(
                f"Skipping OLED update {airportcode} not found in airport_list"
            )
            # Stop here if we don't have airport data yet
            return
        airport_obj = airport_list[airportcode]
        if airport_obj is None:
            debugging.debug(f"Skipping OLED update {airportcode} lookup returns :None:")
            # FIXME: We should not return here - we should update the OLED / Image with some signal that the information is out of date.
            return
        windspeed = airport_obj.wx_windspeed()
        if windspeed is None:
            windspeed = 0
        winddir = airport_obj.winddir_degrees()
        best_runway_label = airport_obj.best_runway()
        best_runway_deg = airport_obj.best_runway_deg()

        if best_runway_label is None:
            best_runway_label = default_rwy_label
            best_runway_deg = default_rwy_deg

        if (winddir is not None) and (best_runway_label is not None):
            debugging.debug(
                f"Updating OLED Wind: {airportcode} : rwy: {best_runway_label} : wind {winddir}"
            )
            self.draw_wind(
                oled_id,
                airportcode,
                best_runway_label,
                best_runway_deg,
                winddir,
                windspeed,
            )
            self.generate_image(
                oled_id,
                airportcode,
                best_runway_label,
                best_runway_deg,
                winddir,
                windspeed,
            )
        else:
            self.draw_nowx(
                oled_id,
                airportcode,
                best_runway_label,
                best_runway_deg,
                winddir,
                windspeed,
            )
            # FIXME: self.generate_nowx_image(oled_id, airportcode, best_runway, winddir, windspeed)
            debugging.info(
                f"NOT Updating OLED: {airportcode} : rwy: {best_runway_label} : wind {winddir}"
            )
        return

    def update_oled_status(self, oled_id, counter):
        """Status Update Display."""
        metarage = utils.time_format_hm(self._airport_database.get_metar_update_time())
        currtime = utils.time_format_hm(utils.current_time(self._app_conf))
        info_timestamp = f"tm:{currtime} metar:{metarage}"
        if self._sysdata.internet_connected():
            info_internet = "Y"
        else:
            info_internet = "N"
        info_ipaddr = f"ip:{self._sysdata.local_ip()} inet:{info_internet}"
        info_uptime = f"up:{self._sysdata.uptime()} "
        info_lightlevel = f"brt:{self._led_mgmt.get_brightness_level()}%"

        activity_char = self.ACTIVITY[counter % len(self.ACTIVITY)]

        oled_status_text = f"{info_timestamp}\n{info_ipaddr}\n{info_uptime}\n{activity_char} {info_lightlevel}"
        # Update OLED
        self.oled_text(oled_id, oled_status_text)
        # Update saved image
        self.generate_info_image(oled_id)

    def get_next_airport(self, metar_iter):
        """Get the next airport to be displayed on OLED display in rotation"""
        max_index = len(self._oled_metar_airports)
        airport_code = self._oled_metar_airports[metar_iter % max_index]
        airport_obj = self._airport_database.get_airport(airport_code)
        return airport_obj

    def update_loop(self):
        """Continuous Loop for Thread."""
        debugging.debug("OLED: Entering Update Loop")
        outerloop = True  # Set to TRUE for infinite outerloop
        count = 0
        update_oled_flag = False

        oled_update_frequency = 180  # Every 3 minutes
        oled_loop_interval = 5
        oled_loop_per_interval = int(oled_update_frequency / oled_loop_interval)
        #
        metar_iter = 0
        while outerloop:
            count += 1
            update_oled_flag = (count % oled_loop_per_interval) == 1
            if update_oled_flag:
                debugging.info(
                    f"OLED: Updating {self._device_count} OLEDs (loopcount: {count})"
                )

            for oled_id in range(0, self._device_count):
                # TODO: This is hardcoded
                # Move to configuration ..
                purpose = self._oled_device_config[f"{oled_id}"]["purpose"]
                if purpose is None:
                    continue
                if purpose == "info":
                    self.update_oled_status(oled_id, count)
                if purpose == "metar":
                    metar_iter += 1
                    airport_obj = self.get_next_airport(metar_iter)
                    if airport_obj is None:
                        continue
                    self.update_oled_wind(
                        oled_id,
                        airport_obj.icao_code(),
                        airport_obj.best_runway(),
                        airport_obj.best_runway_deg(),
                    )
                # if oled_id == 0:
                #     self.update_oled_status(oled_id, count)
                # if (oled_id == 1) and update_oled_flag:
                #     self.update_oled_wind(oled_id, "kbfi", "14", 140)
                # if (oled_id == 2) and update_oled_flag:
                #     self.update_oled_wind(oled_id, "ksea", "16", 160)
                # if (oled_id == 3) and update_oled_flag:
                #     self.update_oled_wind(oled_id, "kpae", "16", 160)
                # if (oled_id == 4) and update_oled_flag:
                #     self.update_oled_wind(oled_id, "kpwt", "20", 200)
                # if (oled_id == 5) and update_oled_flag:
                #     self.update_oled_wind(oled_id, "kfhr", "34", 340)
            time.sleep(oled_loop_interval)
