# -*- coding: utf-8 -*-
"""
Created on Sat Oct 15 10:51:49 2022

i2c utils

@author: chris
"""


# Raspberry PI - Increase i2c bus speed
#
# /boot/config.txt
# dtparam=i2c_arm=on,i2c_arm_baudrate=400000


import time

from threading import Lock

import board
from board import SCL, SDA
import busio

import smbus2
import utils
import debugging


# the channel for the mux board
# there are 8 available channels, write a single bit
# to the specific channel to switch it

# TODO: - compute this rather than pregenerate it ; it's not exactly the hardest binary math.
I2C_ch = [
    0b00000001,  # Channel 0 active
    0b00000010,  # Channel 1 active
    0b00000100,  # Channel 2 active
    0b00001000,  # Channel 3 active
    0b00010000,  # Channel 4 active
    0b00100000,  # Channel 5 active
    0b01000000,  # Channel 6 active
    0b10000000,  # Channel 7 active
]


class I2CBus:
    """Class to manage I2C Bus access."""

    # the raspberry pi i2c bus number
    # This code is assuming we're on a raspberry PI ; and that we're using i2c bus 1
    #
    rpi_bus_number = 1

    # This is the default address of the TCA9548A multiplexer
    # The actual i2c address of the TCA9548a is set using the three address lines A0/A1/A2
    # on the chip. In a complex circuit these addresses can be changed dynamically.
    # Hard coding here for the default A0=A1=A2=0=GND
    # Not sure how valuable moving this to a configurable value would be
    MUX_DEVICE_ID = 0x70
    mux_active = False

    conf = None

    bus = None
    i2c = None

    lock = None
    lock_count = 0

    # Channels that are always on
    always_enabled = 0x0
    current_enabled = 0x0

    def __init__(self, conf):
        """Setup i2c bus - look for default hardware"""
        self.conf = conf
        self.lock = Lock()
        self.bus = smbus2.SMBus(self.rpi_bus_number)
        self.i2c = busio.I2C(board.SCL, board.SDA)
        if self.i2c_exists(self.MUX_DEVICE_ID):
            self.mux_active = True
            self.i2c_mux_default()
        if not self.i2c_update():
            debugging.error("OLED: init - error calling i2c_update")

    def select(self, channel_id):
        """Enable MUX."""
        result = False
        if self.mux_active:
            if self.i2c_exists(self.MUX_DEVICE_ID):
                self.i2c_mux_select(channel_id)
                result = True
            else:
                debugging.error("i2c: mux missing")
        return result

    def i2c_exists(self, device_id):
        """Iterate across the list of i2c devices."""
        found_device = False
        with self.lock:
            active_devices = self.i2c.scan()
        # length = len(active_devices)
        # debugging.debug("i2c: scan device count = " + str(length))
        for dev_id in active_devices:
            # debugging.debug("i2c: device id " + hex(dev_id))
            if dev_id == device_id:
                # debugging.debug("i2c: device id match " + hex(dev_id))
                found_device = True
        return found_device

    def bus_lock(self):
        """Grab bus lock."""
        self.lock_count += 1
        if self.lock.locked():
            debugging.warn("bus_lock: Lock already acquired")
        self.lock.acquire()

    def bus_unlock(self):
        """Release bus lock."""
        self.lock.release()

    def set_always_on(self, channel_id):
        """Set channel to be always on."""
        self.always_enabled = I2C_ch[channel_id]
        if not self.i2c_update():
            debugging.error("OLED: set_always_on - error calling i2c_update")

    def add_always_on(self, channel_id):
        """Add a channel to the always on flag."""
        self.always_enabled = self.always_enabled | I2C_ch[channel_id]
        if not self.i2c_update():
            debugging.error("OLED: add_always_on - error calling i2c_update")

    def clear_always_on(self):
        """Clear Always On Flag."""
        self.always_enabled = 0x0
        if not self.i2c_update():
            debugging.error("OLED: clear_always_on - error calling i2c_update")

    def i2c_mux_select(self, channel_id):
        """Enable i2c channel."""
        # This switches to channel 1
        debugging.debug(f"i2c_mux_select({channel_id})")
        self.current_enabled = I2C_ch[channel_id]
        if not self.i2c_update():
            debugging.error("OLED: i2c_mux_select - error calling i2c_update")

    def i2c_mux_default(self):
        """Update MUX settings."""
        # This switches to channel 1
        if self.mux_active:
            with self.lock:
                self.bus.write_byte(self.MUX_DEVICE_ID, self.always_enabled)
            if not self.i2c_update():
                debugging.error("OLED: i2c_mux_default - error calling i2c_update")

    def i2c_update(self):
        """Send message to MUX."""
        if self.mux_active:
            try:
                mux_select_flags = self.always_enabled | self.current_enabled
                with self.lock:
                    self.bus.write_byte_data(self.MUX_DEVICE_ID, 0, mux_select_flags)
                return True
            except Exception as err:
                self.lock.release()
                debugging.error(err)
        return False
