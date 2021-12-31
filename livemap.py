#!/usr/bin/env python3
"""

Main livemap program

Takes care of all of the setup needed for each component in the system

Start individual threads
 a) update_airport thread - to keep METAR/TAF/MOS data up to date
 b) update_leds thread - keep the LEDs updated to reflect airport state
 c) update_oleds thread - keep the OLEDs updated to reflect state
 d) SOON: Web interface for config and maps

"""

# livemap.py - Main engine ; running threads to keep the data updated

# import os
# import sys
import threading
import time
# import logging
import debugging
import conf                                   # Config.py holds user settings used by the various scripts
# import admin

import utils
import sysinfo
# import appinfo

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

    debugging.loginit()

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
    led_thread = threading.Thread(target=LEDmgmt.update_loop, args=(conf,airport_database))

    debugging.info('Starting OLED updating thread')
    # threadOLEDs = threading.Thread(target=OLEDmgmt.updateLedLoop, args=(conf,))
    # threadOLEDs.start()

    airport_thread.start()
    led_thread.start()

    while True:
        MSG = "In Main Loop - Threadcount ({})"
        print(MSG.format(threading.active_count()))
        time.sleep(300)
