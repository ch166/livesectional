# -*- coding: utf-8 -*- #
""" Manage i2c Light Sensors. """

# Update i2c attached devices
import time

import traceback
import random

import adafruit_veml7700
import adafruit_tsl2591

import debugging


class LightSensor:
    """Class to manage Light Sensors."""

    # This started with support for the TSL2591 only.
    # It now supports either the TSL2591 or the VEML7700
    # It also assumes that these are directly on the I2C bus rather than being behind an I2C mux

    # TSL2591 Light Sensor - i2c device id (0x29)
    # VEML7700 Light Sensor - i2c device id (0x10)

    # Operations interacting with devices on the i2c bus should not assume that the bus
    # configuration is unchanged - and should also ensure that access does not lock out other
    # users of the bus

    led_mgmt = None
    conf = None

    _i2cbus = None

    # Hardware Info
    sensor_device = False
    hardware_tsl2591 = False
    hardware_veml7700 = False

    # devices
    dev_tsl2591 = None
    dev_veml7700 = None

    def __init__(self, conf, i2cbus, led_mgmt):
        self.conf = conf
        self.sensor_device = False
        self._i2cbus = i2cbus
        self.led_mgmt = led_mgmt
        self.i2c_scan()
        # self.enable_i2c_device()

    def i2c_scan(self):
        """Scan i2c bus for supported light sensors."""
        self.sensor_device = False
        # FIXME:
        #  Either remove assumption about device behind i2c mux,
        #  or add as configurable hardware feature.
        #  In which case - move hardcoded 7 to config.ini
        self._i2cbus.set_always_on(7)  # Enable Channel 7
        if self._i2cbus.i2c_exists(0x29):
            # Looks like TSL2591 device
            debugging.info("lightsensor: i2c scan sees TSL2591 type device")
            self.hardware_tsl2591 = True
            self.sensor_device = True
            self.activate_tsl2591()
        if self._i2cbus.i2c_exists(0x10):
            debugging.info("lightsensor: i2c scan sees VEML7700 type device")
            self.hardware_veml7700 = True
            self.sensor_device = True
            self.activate_veml7700()
        return

    def activate_veml7700(self):
        """VEML7700 Device Setup."""
        self.dev_veml7700 = adafruit_veml7700.VEML7700(self._i2cbus.i2cdevice())
        # Setting Gain to 2 and Integration time to 400ms
        self.dev_veml7700.light_gain = self.dev_veml7700.ALS_GAIN_2
        self.dev_veml7700.light_integration_time = self.dev_veml7700.ALS_400MS

    def activate_tsl2591(self):
        """TSL2591 Device Enable."""
        self.dev_tsl2591 = adafruit_tsl2591.TSL2591(self._i2cbus.i2cdevice())

    def read_tsl2591(self):
        """Read LUX value from tsl2591."""
        lux = 0
        if self._i2cbus.bus_lock("light sensor update loop : tsl2591"):
            try:
                lux = self.dev_tsl2591.lux
            except OSError as err:
                debugging.info(f"tsl2591 light sensor read failure: {err}")
                self.i2c_scan()
                lux = 100
            except Exception as e:
                debugging.error(e)
                debugging.error(traceback.format_exc())
            finally:
                self._i2cbus.bus_unlock()
        debugging.debug(f"tsl2591:raw {lux} lux")
        lux = max(lux, 10)
        lux = min(lux, 255)
        return lux

    def read_veml7700(self):
        """Read LUX value from veml7700."""
        lux = 0
        if self._i2cbus.bus_lock("light sensor update loop : veml7700"):
            try:
                lux = self.dev_veml7700.lux
            except OSError as err:
                debugging.info(f"veml7700 light sensor read failure: {err}")
                self.i2c_scan()
                lux = 100
            except Exception as e:
                debugging.error(e)
                debugging.error(traceback.format_exc())
            finally:
                self._i2cbus.bus_unlock()
        debugging.debug(f"veml7700:raw {lux} lux")
        lux = max(lux, 10)
        lux = min(lux, 255)
        return lux

    def update_loop(self, conf):
        """Thread Main Loop."""
        self.conf = conf
        outerloop = True  # Set to TRUE for infinite outerloop
        lux = 250
        loop_counter = 0
        while outerloop:
            if (self.hardware_tsl2591 is False) and (self.hardware_veml7700 is False):
                debugging.info(
                    "No light sensor hardware found for tsl2591 and veml7700"
                )
                if (loop_counter % 500) == 0:
                    self.i2c_scan()
            old_lux = lux
            old_lux_min = int(lux * 0.9)
            old_lux_max = int(lux * 1.1)
            if self.hardware_tsl2591:
                lux = self.read_tsl2591()
                debugging.debug(f"tsl2591 lux [{lux}]")
            if self.hardware_veml7700:
                lux = self.read_veml7700()
                debugging.debug(f"veml7700 lux [{lux}]")
            lux = round(lux, 0)
            if (lux < old_lux_min) or (lux > old_lux_max):
                debugging.info(f"Light sensor LUX change > 10%: {old_lux} -> {lux}")
            debugging.debug(f"Setting light levels: {lux}")
            self.led_mgmt.set_brightness(lux)
            sleep_interval = 5 + random.randint(0, 5)
            time.sleep(sleep_interval)
            loop_counter += 1
