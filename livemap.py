#!/usr/bin/env python3

# livemap.py - Main engine ; running threads to keep the data updated

import os
import sys
import threading
import time
import logging
import debugging
import conf                                   # Config.py holds user settings used by the various scripts
import admin

import conf
import utils
import sysinfo
import appinfo

import update_airports
import update_leds
# import update_oled


if __name__ == '__main__':
    # Startup and run the threads to operate the LEDs, Displays etc.

    # Initialize configuration file
    conf = conf.Conf()

    # Generate System Data
    sysdata = sysinfo.SystemData()
    sysdata.refresh()

    if utils.wait_for_internet():
        # Check for working Internet access
        debugging.info("Internet Available")
    else:
        debugging.warn("Internet NOT Available")

    ipaddr = sysdata.local_ip()

    debugging.info('Livemap Startup - IP: ' + ipaddr)
    debugging.info('Base Directory :' +
            conf.get_string("filenames", "basedir"))


    # Start Threads

    # Load Airports
    debugging.info('Starting Airport data management thread')
    airport_database = update_airports.AirportDB(conf)
    airport_database.load_airport_db()
    airport_thread = threading.Thread(target=airport_database.update_loop, args=(conf,))

    # Start updating LEDs
    debugging.info('Starting LED updating thread')
    LEDmgmt = update_leds.updateLEDs(conf, airport_database)
    led_thread = threading.Thread(target=LEDmgmt.update_loop, args=(conf,))

    debugging.info('Starting OLED updating thread')
    # threadOLEDs = threading.Thread(target=OLEDmgmt.updateLedLoop, args=(conf,))
    # threadOLEDs.start()

    airport_thread.start()
    led_thread.start()

    while(True):
        print("In Main Loop")
        time.sleep(300)
