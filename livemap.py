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
import conf  # Config.py holds user settings used by the various scripts

# import admin

from flask import Flask

import utils
import sysinfo

# import appinfo

import update_airports
import update_leds
import appinfo
import webviews

# import update_oled


if __name__ == "__main__":
    # Startup and run the threads to operate the LEDs, Displays etc.

    # Initialize configuration
    conf = conf.Conf()
    appinfo = appinfo.AppInfo()

    # Setup Logging
    debugging.loginit()

    # Check for working Internet
    if utils.wait_for_internet():
        # Check for working Internet access
        debugging.info("Internet Available")
    else:
        debugging.warn("Internet NOT Available")

    # Generate System Data
    sysdata = sysinfo.SystemData()
    sysdata.refresh()
    ipaddr = sysdata.local_ip()

    # Setup Airport DB
    airport_database = update_airports.AirportDB(conf)
    airport_database.load_airport_db()

    # Setup LED Management
    LEDmgmt = update_leds.UpdateLEDs(conf, airport_database)

    # Setup Flask APP
    web_app = webviews.WebViews(conf, sysdata, airport_database, appinfo)

    # Almost Setup
    debugging.info("Livemap Startup - IP: " + ipaddr)
    debugging.info("Base Directory :" + conf.get_string("filenames", "basedir"))

    #
    # Setup Threads
    #

    # Load Airports
    debugging.info("Starting Airport data management thread")
    airport_thread = threading.Thread(target=airport_database.update_loop, args=(conf,))

    # Updating LEDs
    debugging.info("Starting LED updating thread")
    # LEDmgmt = update_leds.UpdateLEDs(conf, airport_database)
    led_thread = threading.Thread(target=LEDmgmt.update_loop, args=())

    # Updating OLEDs
    debugging.info("Starting OLED updating thread")
    # threadOLEDs = threading.Thread(target=OLEDmgmt.updateLedLoop, args=(conf,))

    # Flask Thread
    debugging.info("Creating Flask Thread")
    flask_thread = threading.Thread(target=web_app.run, args=())

    #
    # Start Executing Threads
    #
    debugging.info("Starting threads")
    airport_thread.start()
    led_thread.start()
    flask_thread.start()

    main_loop_sleep = 5

    while True:
        MSG = "In Main Loop - Threadcount ({}), Sleep for {}m"
        active_thread_count = threading.active_count()
        debugging.info(MSG.format(active_thread_count, main_loop_sleep))
        # TODO: We should get around to generating and reporting health
        # metrics in this loop.
        time.sleep(main_loop_sleep * 60)
