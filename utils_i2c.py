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

import threading

import board
from board import SCL, SDA
import busio

import smbus2
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

    _app_conf = None

    bus = None
    _i2c_device = None

    lock = None
    _lock_count = 0
    _lock_events = None

    _bus_lock_owner = None
    _bus_lock_starttime = None

    # Channels that are always on
    always_enabled = 0x0
    current_enabled = 0x0

    # Stats
    _average__lock_count = 0
    _average_lock_duration = 0
    _average_lock_start = None
    _average_lock_total = 0
    _max_lock_duration = 0
    _max_lock_owner = None
    _lock_fail_count = 0

    def __init__(self, app_conf):
        """Do setup for i2c bus - look for default hardware."""
        self._app_conf = app_conf
        self.lock = threading.Lock()
        try:
            self.bus = smbus2.SMBus(self.rpi_bus_number)
        except IOError:
            # Error here may indicate that the i2c kernel modules is not loaded
            self.bus = None
        if self.bus is None:
            return
        self._i2c_device = busio.I2C(board.SCL, board.SDA)
        if self.i2c_exists(self.MUX_DEVICE_ID):
            self.mux_active = True
            self.i2c_mux_default()
        if not self.i2c_update():
            debugging.error("OLED: init - error calling i2c_update")
        self._lock_events = 0
        self._lock_count = 0

    def select(self, channel_id):
        """Enable MUX."""
        result = False
        if self.bus is None:
            return
        if self.mux_active:
            if self.i2c_exists(self.MUX_DEVICE_ID):
                self.i2c_mux_select(channel_id)
                result = True
            else:
                debugging.error("i2c: mux missing")
        return result

    def i2c_exists(self, device_id):
        """Iterate across the list of i2c devices."""
        if self.bus is None:
            return
        found_device = False
        # with self.lock:
        active_devices = self._i2c_device.scan()
        # length = len(active_devices)
        # debugging.debug("i2c: scan device count = " + str(length))
        for dev_id in active_devices:
            # debugging.debug("i2c: device id " + hex(dev_id))
            if dev_id == device_id:
                # debugging.debug("i2c: device id match " + hex(dev_id))
                found_device = True
        return found_device

    def i2cdevice(self):
        """Return i2c bus device to be used in init of components"""
        return self._i2c_device

    def bus_lock(self, owner) -> bool:
        """Grab bus lock."""
        if self.bus is None:
            return False
        for counter in range(1, 11):
            acquired = self.lock.acquire(blocking=True, timeout=0.1)
            if acquired:
                self._lock_events += 1
                self._lock_count += 1
                self._bus_lock_owner = owner
                self._average__lock_count += 1
                self._average_lock_start = time.time()
                return True
        lock_duration = time.time() - self._average_lock_start
        self._lock_fail_count += 1
        debugging.warn(
            f"bus_lock: request by {owner} when lock is held: count:{self._lock_count}: events:{self._lock_events}: owner:{self._bus_lock_owner} duration:{lock_duration}"
        )
        return False

    def bus_unlock(self):
        """Release bus lock."""
        if self.bus is None:
            return
        if self.lock.locked():
            self._lock_count -= 1
            try:
                self.lock.release()
                lock_duration = time.time() - self._average_lock_start
                self._average_lock_total = self._average_lock_total + lock_duration
                self._average_lock_duration = (
                    self._average_lock_total / self._average__lock_count
                )
                if lock_duration > self._max_lock_duration:
                    self._max_lock_duration = lock_duration
                    self._max_lock_owner = self._bus_lock_owner
            except Exception as unlock_err:
                debugging.error(f"bus_unlock release failed :{unlock_err}:")
        else:
            debugging.warn(
                f"bus_unlock: Request to release lock that wasn't acquired - lock_count :{self._lock_count}:{self._lock_events}:{self._bus_lock_owner}"
            )

    def set_always_on(self, channel_id):
        """Set channel to be always on."""
        if self.bus is None:
            return
        self.always_enabled = I2C_ch[channel_id]
        if not self.i2c_update():
            debugging.error("OLED: set_always_on - error calling i2c_update")

    def add_always_on(self, channel_id):
        """Add a channel to the always on flag."""
        if self.bus is None:
            return
        self.always_enabled = self.always_enabled | I2C_ch[channel_id]
        if not self.i2c_update():
            debugging.error("OLED: add_always_on - error calling i2c_update")

    def clear_always_on(self):
        """Clear Always On Flag."""
        if self.bus is None:
            return
        self.always_enabled = 0x0
        if not self.i2c_update():
            debugging.error("OLED: clear_always_on - error calling i2c_update")

    def i2c_mux_select(self, channel_id):
        """Enable i2c channel."""
        # This switches to channel 1
        if self.bus is None:
            return
        debugging.debug(f"i2c_mux_select({channel_id})")
        self.current_enabled = I2C_ch[channel_id]
        if not self.i2c_update():
            debugging.error("OLED: i2c_mux_select - error calling i2c_update")

    def i2c_mux_default(self):
        """Update MUX settings."""
        # This switches to channel 1
        if self.bus is None:
            return
        if self.mux_active:
            # with self.lock:
            self.bus.write_byte(self.MUX_DEVICE_ID, self.always_enabled)
            if not self.i2c_update():
                debugging.error("OLED: i2c_mux_default - error calling i2c_update")

    def i2c_update(self):
        """Send message to MUX."""
        if self.bus is None:
            return
        if self.mux_active:
            try:
                mux_select_flags = self.always_enabled | self.current_enabled
                # with self.lock:
                self.bus.write_byte_data(self.MUX_DEVICE_ID, 0, mux_select_flags)
                return True
            except Exception as err:
                # self.lock.release()
                debugging.error(err)
        return False

    def stats(self):
        """Return lock stats"""
        average = round(self._average_lock_duration, 2)
        maxlock = round(self._max_lock_duration, 2)
        lockfail = self._lock_fail_count
        stats_txt = f"i2cbus lock stats\n\tAverage duration:{average}\n\tMax:{maxlock}/Owner:{self._max_lock_owner}\n\tLock fail (expired):{lockfail}"
        return stats_txt
