# -*- coding: utf-8 -*- #
"""
Created on Sat Jun 15 08:01:44 2019

@author: Chris Higgins
"""

# This is the collection and aggregation of all functions that manage Airports and airport weather
# products. It's initially focused on processing METARs, but will end up including all of the functions
# related to TAFs and MOS data.
#
# It is comprised of an AirportDB class - which provides collections of Airport objects
# - List of airports associated with LED Strings (airports, null, legend etc)
# - List of airports associated with OLED displays
# - List of airports associated with HDMI displays (future)
# - List of airports associated with Web Pages (future)
#
# Each list is comprised of an Airport object ( airport.py )
# The airport object stores all of the interesting data for an airport
# - Airport ICAO code
# - Weather Source ( adds , metar URL, future options)
# - Airport Code to use for WX data (future - for airports without active ASOS/AWOS reporting)
# - Current conditions
# - etc.

# The update_loop function is intended to be called in a discrete thread, so that it can run
# forever, checking for updated weather data - and processing that data to keep the Airport
# objects up to date with current conditions.
# This should be the only place that is creating and writing to airport objects.
# - The airport DB and airport objects should be effectively readonly in all other threads


# import os
import time

# from datetime import datetime
# from datetime import timedelta
# from distutils import util
# from enum import Enum
# from urllib.request import urlopen
# import urllib.error
# import socket
import shutil

# import gzip
import json

# Moving to use requests instead of urllib
import requests

# XML Handling
# import xml.etree.ElementTree as ET

from lxml import etree

# from metar import Metar

import debugging

# import ledstrip
import utils

import airport


class AirportDB:
    """Airport Database - Keeping track of interesting sets of airport data"""

    def __init__(self, conf):
        """Create a database of Airports to be tracked"""

        # TODO:
        # A lot of the class local variables are extras,
        # left over from the restructuring of the code.
        # for example: Some are just copies of config file data, and it
        # should be remove them as class-local variables and access the
        # config file directly as needed

        # Reference to Global Configuration Data
        self.conf = conf

        # Active Airport Information
        # All lists use lowercase key information to identify airports
        # Full list of interesting Airports loaded from JSON data
        self.airport_master_dict = {}

        self.airport_master_list = []

        # Subset of airport_json_list that is active for live HTML page
        self.airport_web_dict = {}

        # Subset of airport_json_list that is active for LEDs
        self.airport_led_dict = {}

        self.tafs_xml_data = []
        self.metar_xml_dict = {}

        debugging.info("AirportDB : init")

        self.load_airport_db()
        # self.update_airport_metar_xml()
        # self.save_airport_db()
        debugging.info("AirportDB : init complete")

    def get_airport(self, airport_icao):
        """Return a single Airport"""
        return self.airport_master_dict[airport_icao]

    def get_airportdb(self):
        """Return a single Airport"""
        return self.airport_master_dict

    def get_airportxml(self, airport_icao):
        """Return a single Airport"""
        return self.metar_xml_dict[airport_icao]

    def get_airportxmldb(self):
        """Return a single Airport"""
        return self.metar_xml_dict

    def get_airport_dict_led(self):
        """Return Airport LED dict"""
        return self.airport_led_dict

    def update_airport_wx(self):
        """Update airport WX data for each known Airport"""
        for icao, arpt in self.airport_master_dict.items():
            debugging.info("Updating WX for " + arpt.icao)
            try:
                arpt.update_wx(self.metar_xml_dict)
            except Exception as e:
                debug_string = "Error: update_airport_wx Exception handling for " + arpt.icao
                debugging.error(debug_string)
                debugging.crash(e)

    def load_airport_db(self):
        """Load Airport Data file"""
        # FIXME: Add file error handling
        debugging.info("Loading Airport List")
        airport_json = self.conf.get_string("filenames", "airports_json")
        # Opening JSON file
        json_file = open(airport_json, encoding="utf8")
        # returns JSON object as a dictionary
        new_airport_json_dict = json.load(json_file)
        # Closing file
        json_file.close()

        # Need to merge this data set into the existing data set
        # On initial boot ; the saved data set could be empty
        # - This will need to create all the objects
        # On update ; some records will already exist, but may have updates
        for json_airport in new_airport_json_dict["airports"]:
            debugging.info("Merging Airport List")
            # print(json_airport, flush = True)
            json_airport_icao = json_airport["icao"]
            json_airport_icao = json_airport_icao.lower()
            if json_airport_icao == "null":
                # Null entry in config file
                # Need to add entry into master airport list and into LED list
                # FIXME: Do something useful
                self.airport_master_list.append(json_airport)
                continue
            if json_airport_icao == "lgnd":
                # Legend entry in config file
                # Need to add entry into master airport list and into LED list
                # FIXME: Do something useful
                self.airport_master_list.append(json_airport)
                continue
            # print(json_airport_icao, flush = True)
            if json_airport_icao in self.airport_master_dict:
                #  Airport exists already - need to update rather than  create new
                # This will need to handle changes in LED and STATE for airports
                # FIXME: Need to add handling for changed purpose - remove / delete old object
                # perhaps change the sequence of this to do an optional create first, and then
                # do all the insertions every time regardless.
                debugging.info("Updating existing airport on list")
                debugging.info(self.airport_master_dict[json_airport_icao])
                self.airport_master_dict[json_airport_icao].set_led_index(int(json_airport["led"]))
                self.airport_master_dict[json_airport_icao].set_wxsrc(json_airport["wxsrc"])
                if json_airport["active"]:
                    self.airport_master_dict[json_airport_icao].set_active()
                else:
                    self.airport_master_dict[json_airport_icao].set_inactive()
                break
            else:
                # New Airport in config - need to create the airport object
                self.airport_master_list.append(json_airport)
                airport_icao = json_airport["icao"]
                airport_led = int(json_airport["led"])
                airport_wxsrc = json_airport["wxsrc"]
                airport_active = json_airport["active"]
                new_airport_obj = airport.Airport(
                    airport_icao,
                    airport_icao,
                    airport_wxsrc,
                    airport_active,
                    airport_led,
                    self.conf,
                )
                debugging.info(f"Adding airport to list : {airport_icao} led: {airport_led}")
                self.airport_master_dict[airport_icao] = new_airport_obj
                if json_airport["purpose"] == "led" or json_airport["purpose"] == "all":
                    self.airport_led_dict[airport_icao] = new_airport_obj
                if json_airport["purpose"] == "web" or json_airport["purpose"] == "all":
                    self.airport_web_dict[airport_icao] = new_airport_obj
        debugging.info("Airport Load and Merge complete")

    def save_airport_db(self):
        """Save Airport Data file"""
        # FIXME: Add file error handling
        # Should only overwrite destination file if this is succesful

        debugging.info("Saving Airport DB")
        airport_json_backup = self.conf.get_string("filenames", "airports_json_backup")
        airport_json_new = self.conf.get_string("filenames", "airports_json_new")
        airport_json = self.conf.get_string("filenames", "airports_json")

        shutil.move(airport_json, airport_json_backup)

        json_save_data = {"airports": self.airport_master_list}
        # Opening JSON file
        with open(airport_json_new, "w", encoding="utf8") as json_file:
            json.dump(json_save_data, json_file, sort_keys=True, indent=4)
        # FIXME:  Only if write was successful, then we should
        # mv airport_json_new over airport_json
        shutil.move(airport_json_new, airport_json)

    def update_airport_metar_xml(self):
        """Update Airport METAR DICT from XML"""
        # FIXME: Add file error handling
        # Consider extracting only interesting airports from dict first
        debugging.info("Updating Airport METAR DICT")
        metar_data = []
        metar_dict = {}
        metar_file = self.conf.get_string("filenames", "metar_xml_data")
        try:
            root = etree.parse(metar_file)
        except etree.ParseError as e:
            debugging.error("XML Parse Error")
            debugging.error(e)
            debugging.info("Not updating - returning")
            return False

        display_counter = 0

        for metar_data in root.iter("METAR"):
            station_id = metar_data.find("station_id").text
            station_id = station_id.lower()

            # Log an update every 20 stations parsed
            # Want to have some tracking of progress through the data set, but not
            # burden the log file with a huge volume of data
            display_counter += 1
            if display_counter % 20 == 0:
                msg = "xml:" + str(display_counter) + ":" + station_id
                debugging.info(msg)

            # print(":" + station_id + ": ", end='')
            # FIXME: Move most of this code into an Airport Class function, where it belongs
            metar_dict[station_id] = {}
            metar_dict[station_id]["station_id"] = station_id
            next_object = metar_data.find("raw_text")
            if next_object is not None:
                metar_dict[station_id]["raw_text"] = next_object.text
            else:
                metar_dict[station_id]["raw_text"] = "Missing"
            next_object = metar_data.find("observation_time")
            if next_object is not None:
                metar_dict[station_id]["observation_time"] = next_object.text
            else:
                metar_dict[station_id]["observation_time"] = "Missing"
            next_object = metar_data.find("wind_speed_kt")
            if next_object is not None:
                metar_dict[station_id]["wind_speed_kt"] = int(next_object.text)
            else:
                metar_dict[station_id]["wind_speed_kt"] = 0
            next_object = metar_data.find("metar_type")
            if next_object is not None:
                metar_dict[station_id]["metar_type"] = next_object.text
            else:
                metar_dict[station_id]["metar_type"] = "Missing"
            next_object = metar_data.find("wind_gust_kt")
            if next_object is not None:
                metar_dict[station_id]["wind_gust_kt"] = int(next_object.text)
            else:
                metar_dict[station_id]["wind_gust_kt"] = 0
            next_object = metar_data.find("sky_condition")
            if next_object is not None:
                metar_dict[station_id]["sky_condition"] = next_object.text
            else:
                metar_dict[station_id]["sky_condition"] = "Missing"
            next_object = metar_data.find("flight_category")
            if next_object is not None:
                metar_dict[station_id]["flight_category"] = next_object.text
            else:
                metar_dict[station_id]["flight_category"] = "Missing"
            next_object = metar_data.find("ceiling")
            if next_object is not None:
                metar_dict[station_id]["ceiling"] = next_object.text
            else:
                metar_dict[station_id]["ceiling"] = "Missing"
            next_object = metar_data.find("visibility_statute_mi")
            if next_object is not None:
                metar_dict[station_id]["visibility"] = next_object.text
            else:
                metar_dict[station_id]["visibility"] = "Missing"
            next_object = metar_data.find("latitude")
            if next_object is not None:
                metar_dict[station_id]["latitude"] = next_object.text
            else:
                metar_dict[station_id]["latitude"] = "Missing"
            next_object = metar_data.find("longitude")
            if next_object is not None:
                metar_dict[station_id]["longitude"] = next_object.text
            else:
                metar_dict[station_id]["longitude"] = "Missing"
        self.metar_xml_dict = metar_dict
        debugging.info("Updating Airport METAR from XML")
        return True

    def update_loop(self, conf):
        """Master loop for keeping the airport data set current

        Infinite Loop
         1/ Update METAR for all Airports in DB
         2/ Update TAF for all Airports in DB
         3/ Update MOS for all Airports
         ...
         9/ Wait for update interval timer to expire

        Triggered Update
        """

        aviation_weather_adds_timer = conf.get_int("metar", "wx_update_interval")

        # TODO: Do we really need these, or can we just do the conf lookup when needed
        metar_xml_url = conf.get_string("urls", "metar_xml_gz")
        metar_file = conf.get_string("filenames", "metar_xml_data")
        tafs_xml_url = conf.get_string("urls", "tafs_xml_gz")
        tafs_file = conf.get_string("filenames", "tafs_xml_data")
        mos00_xml_url = conf.get_string("urls", "mos00_data_gz")
        mos00_file = conf.get_string("filenames", "mos00_xml_data")
        mos06_xml_url = conf.get_string("urls", "mos06_data_gz")
        mos06_file = conf.get_string("filenames", "mos06_xml_data")
        mos12_xml_url = conf.get_string("urls", "mos12_data_gz")
        mos12_file = conf.get_string("filenames", "mos12_xml_data")
        mos18_xml_url = conf.get_string("urls", "mos18_data_gz")
        mos18_file = conf.get_string("filenames", "mos18_xml_data")

        https_session = requests.Session()

        self.update_airport_metar_xml()

        while True:
            debugging.info("Updating Airport Data .. every aviation_weather_adds_timer (" + str(aviation_weather_adds_timer) + "m)")

            ret = utils.download_newer_file(https_session, metar_xml_url, metar_file, decompress=True)
            if ret == 0:
                debugging.info("Downloaded METAR file")
                self.update_airport_metar_xml()
            elif ret == 3:
                debugging.info("Server side METAR older")

            ret = utils.download_newer_file(https_session, tafs_xml_url, tafs_file, decompress=True)
            if ret == 0:
                debugging.info("Downloaded TAFS file")
                # Need to trigger update of Airport TAFS data
            elif ret == 3:
                debugging.info("Server side TAFS older")

            ret = utils.download_newer_file(https_session, mos00_xml_url, mos00_file)
            if ret == 0:
                debugging.info("Downloaded MOS00 file")
            elif ret == 3:
                debugging.info("Server side MOS00 older")

            ret = utils.download_newer_file(https_session, mos06_xml_url, mos06_file)
            if ret == 0:
                debugging.info("Downloaded MOS06 file")
            elif ret == 3:
                debugging.info("Server side MOS06 older")

            ret = utils.download_newer_file(https_session, mos12_xml_url, mos12_file)
            if ret == 0:
                debugging.info("Downloaded MOS12 file")
            elif ret == 3:
                debugging.info("Server side MOS12 older")

            ret = utils.download_newer_file(https_session, mos18_xml_url, mos18_file)
            if ret == 0:
                debugging.info("Downloaded MOS18 file")
            elif ret == 3:
                debugging.info("Server side MOS18 older")

            try:
                self.update_airport_wx()
            except Exception as e:
                debugging.error("Update Weather Loop: self.update_airport_wx() exception")
                debugging.error(e)
            time.sleep(aviation_weather_adds_timer * 60)
        debugging.error("Hit the exit of the airport update loop")
