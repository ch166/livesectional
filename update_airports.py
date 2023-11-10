# -*- coding: utf-8 -*- #
"""
Created on Sat Jun 15 08:01:44 2019.

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
from datetime import datetime
import shutil

import csv
import json

import pytz

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
    """Airport Database - Keeping track of interesting sets of airport data."""

    def __init__(self, conf):
        """Create a database of Airports to be tracked."""

        # TODO: A lot of the class local variables are extras,
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

        # Subset of airport_json_list that is active for live HTML page
        self.airport_web_dict = {}

        # Subset of airport_json_list that is active for LEDs
        self.airport_led_dict = {}

        # Copy of raw json entries loaded from config
        self.airport_master_list = []

        # Live RAW XML Data
        self.metar_xml_dict = {}
        self.metar_update_time = None

        # Live RAW XML Data
        self.taf_xml_dict = {}
        self.taf_update_time = None

        # Runway Data
        self.runway_data = None

        debugging.debug("AirportDB : init")

        self.load_airport_db()
        debugging.info("AirportDB : init complete")

    def get_airport(self, airport_icao):
        """Return a single Airport"""
        return self.airport_master_dict[airport_icao]["airport"]

    def get_airport_taf(self, airport_icao):
        """Return a single Airport TAF."""
        result = None
        if airport_icao in self.taf_xml_dict:
            result = self.taf_xml_dict[airport_icao]
        return result

    def get_airportdb(self):
        """Return a single Airport."""
        return self.airport_master_dict

    def get_airportxml(self, airport_icao):
        """Return a single Airport."""
        return self.metar_xml_dict[airport_icao]

    def get_airportxmldb(self):
        """Return a single Airport."""
        return self.metar_xml_dict

    def get_airport_dict_led(self):
        """Return Airport LED dict."""
        return self.airport_led_dict

    def get_metar_update_time(self):
        """Return last update time of metar data."""
        return self.metar_update_time

    def update_airport_wx(self):
        """Update airport WX data for each known Airport."""
        for icao, arptdb_row in self.airport_master_dict.items():
            arpt = arptdb_row["airport"]
            debugging.debug("Updating WX for " + arpt.icaocode())
            if not arpt.active():
                continue
            try:
                arpt.update_wx(self.metar_xml_dict)
            except Exception as err:
                debug_string = (
                    "Error: update_airport_wx Exception handling for " + arpt.icaocode()
                )
                debugging.error(debug_string)
                debugging.crash(err)

    def save_data_from_db(self):
        """Create JSON data from Airport datasets."""
        airportdb_list = []
        for airport_db_id, airportdb_row in self.airport_master_dict.items():
            airport_save_record = {}
            arpt = airportdb_row["airport"]
            airport_save_record["active"] = str(arpt.active())
            airport_save_record["heatmap"] = arpt.heatmap_index()
            airport_save_record["icao"] = arpt.icaocode()
            airport_save_record["led"] = str(arpt.get_led_index())
            airport_save_record["purpose"] = airportdb_row["purpose"]
            airport_save_record["wxsrc"] = arpt.wxsrc()
            airportdb_list.append(airport_save_record)

        return airportdb_list

    def airport_dict_from_json(self, airport_jsondb):
        """Create Airport List from json src."""
        # Airport dict Entry
        #
        # Dictionary of Airport Entries
        # icao = Airport ICAO Code | NULL | LGND
        # ledindex = Index of LED on LED String
        # active = True / False
        # purpose = all | web | led

        airportdb_dict = {}

        for json_airport in airport_jsondb["airports"]:
            self.airport_master_list.append(json_airport)
            airportdb_row = {}
            airport_icao = json_airport["icao"]
            airport_icao = airport_icao.lower()
            debugging.debug(f"Parsing Json Airport List : {airport_icao}")
            # Need a Unique Key
            airportdb_row["icao"] = airport_icao
            airportdb_row["ledindex"] = int(json_airport["led"])
            airportdb_row["active"] = json_airport["active"]
            airportdb_row["purpose"] = json_airport["purpose"]
            airportdb_row["heatmap"] = json_airport["heatmap"]
            airport_db_id = airport_icao
            if airport_icao in ("null", "lgnd"):
                # Need a Unique Key if icao code is null or lgnd
                ledindex = airportdb_row["ledindex"]
                airport_db_id = f"{airport_icao}:{ledindex}"
            airport_obj = airport.Airport(
                airport_icao,
                airport_icao,
                json_airport["wxsrc"],
                airportdb_row["active"],
                airportdb_row["ledindex"],
                airportdb_row["purpose"],
                self.conf,
            )
            airport_obj.set_heatmap_index(airportdb_row["heatmap"])
            airportdb_row["airport"] = airport_obj
            airportdb_dict[airport_db_id] = airportdb_row
        return airportdb_dict

    def airport_dicts_update(self):
        """Update master database sub-lists from master list."""
        # LED List ( purpose: LED / NULL / LGND )
        # WEB List ( purpose: WEB / LGND )
        for airport_db_id, airportdb_row in self.airport_master_dict.items():
            # airport_icao = airportdb_row["icao"]
            airport_purpose = airportdb_row["purpose"]
            if airport_purpose in ("led", "all", "off"):
                self.airport_led_dict[airport_db_id] = airportdb_row
            if airport_purpose in ("web", "all"):
                self.airport_web_dict[airport_db_id] = airportdb_row
        return True

    def load_airport_db(self):
        """Load Airport Data file."""
        # FIXME: Add file error handling
        debugging.debug("Loading Airport List")
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
        airport_dict_new = self.airport_dict_from_json(new_airport_json_dict)
        # Update the master dictionary ; overwrite existing keys with new keys
        self.airport_master_dict.update(airport_dict_new)
        self.airport_dicts_update()
        debugging.debug("Airport Load and Merge complete")

    def save_airport_db(self):
        """Save Airport Data file."""
        debugging.debug("Saving Airport DB")
        json_save_data = {}
        json_save_data_airport = []
        airport_json_backup = self.conf.get_string("filenames", "airports_json_backup")
        airport_json_new = self.conf.get_string("filenames", "airports_json_new")
        airport_json = self.conf.get_string("filenames", "airports_json")

        shutil.move(airport_json, airport_json_backup)
        json_save_data_airport = self.save_data_from_db()
        json_save_data["airports"] = json_save_data_airport
        with open(airport_json_new, "w", encoding="utf8") as json_file:
            json.dump(json_save_data, json_file, sort_keys=True, indent=4)
        shutil.move(airport_json_new, airport_json)

    def update_airport_metar_xml(self):
        """Update Airport METAR DICT from XML."""
        # TODO: Add file error handling
        # Consider extracting only interesting airports from dict first
        debugging.debug("Updating Airport METAR DICT")
        metar_data = []
        metar_dict = {}
        metar_file = self.conf.get_string("filenames", "metar_xml_data")
        try:
            root = etree.parse(metar_file)
        except etree.ParseError as err:
            debugging.error("XML Parse METAR Error")
            debugging.error(err)
            debugging.debug("Not updating - returning")
            return False

        display_counter = 0

        for metar_data in root.iter("METAR"):
            if metar_data is None:
                return False
            station_id = metar_data.find("station_id").text
            station_id = station_id.lower()

            # Log an update every 20 stations parsed
            # Want to have some tracking of progress through the data set, but not
            # burden the log file with a huge volume of data
            display_counter += 1
            if display_counter % 20 == 0:
                msg = "xml:" + str(display_counter) + ":" + station_id
                debugging.debug(msg)

            # print(":" + station_id + ": ", end='')
            # FIXME: Move most of this code into an Airport Class function, where it belongs
            metar_dict[station_id] = {}
            metar_dict[station_id]["stationId"] = station_id
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
            next_object = metar_data.find("wind_dir_degrees")
            if next_object is not None:
                try:
                    next_val = int(next_object.text)
                except (TypeError, ValueError):
                    next_val_int = False
                else:
                    next_val_int = True
                if next_val_int:
                    metar_dict[station_id]["wind_dir_degrees"] = int(next_object.text)
                else:
                    # FIXME: Hack to handle complex wind definitions (eg: VRB)
                    debugging.info(
                        f"GRR: wind_dir_degrees parse mismatch - setting to zero; actual:{next_object.text}:"
                    )
                    metar_dict[station_id]["wind_dir_degrees"] = 0
            else:
                metar_dict[station_id]["wind_dir_degrees"] = 0
            next_object = metar_data.find("wind_speed_kt")
            if next_object is not None:
                try:
                    next_val = int(next_object.text)
                except (TypeError, ValueError):
                    next_val_int = False
                else:
                    next_val_int = True
                if next_val_int:
                    metar_dict[station_id]["wind_speed_kt"] = int(next_object.text)
                else:
                    # FIXME: Hack to handle complex wind definitions (eg: VRB)
                    debugging.info(
                        f"GRR: wind_speed_kt parse mismatch - setting to zero; actual:{next_object.text}:"
                    )
                    metar_dict[station_id]["wind_speed_kt"] = 0
            else:
                metar_dict[station_id]["wind_speed_kt"] = 0
            next_object = metar_data.find("metar_type")
            if next_object is not None:
                metar_dict[station_id]["metar_type"] = next_object.text
            else:
                metar_dict[station_id]["metar_type"] = "Missing"
            next_object = metar_data.find("wind_gust_kt")
            if next_object is not None:
                try:
                    next_val = int(next_object.text)
                except (TypeError, ValueError):
                    next_val_int = False
                else:
                    next_val_int = True
                if next_val_int:
                    metar_dict[station_id]["wind_gust_kt"] = int(next_object.text)
                else:
                    # FIXME: Hack to handle complex wind definitions (eg: VRB)
                    debugging.info(
                        f"GRR: wind_gust_kt parse mismatch - setting to zero; actual:{next_object.text}:"
                    )
                    metar_dict[station_id]["wind_gust_kt"] = 0
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
        self.metar_update_time = datetime.now(pytz.utc)
        debugging.debug("Updating Airport METAR from XML")
        return True

    def update_airport_taf_xml(self):
        """Update Airport TAF DICT from XML."""

        # Create a DICT containing TAF records per site
        #
        # ['site']
        # issue_time
        # - ['start time'] - ['end time'] - [conditions VFR/MVFR/IFR/LIFR/UKN]
        # - ['start time'] - ['end time'] - [conditions VFR/MVFR/IFR/LIFR/UKN]
        # - ['start time'] - ['end time'] - [conditions VFR/MVFR/IFR/LIFR/UKN]
        #
        # A query against an airport TAF record at a point X hours in the future
        # should return the expected conditions at that time
        #
        # TODO: Add file error handling

        debugging.debug("Updating Airport TAF DICT")

        taf_dict = {}

        taf_file = self.conf.get_string("filenames", "tafs_xml_data")
        try:
            root = etree.parse(taf_file)
        except etree.ParseError as err:
            debugging.error("XML Parse TAF Error")
            debugging.error(err)
            debugging.debug("Not updating - returning")
            return False

        for taf in root.iter("TAF"):
            if taf is None:
                return False
            taf_data = {}
            station_id = taf.find("station_id").text
            station_id = station_id.lower()
            issue_time = taf.find("issue_time").text
            raw_taf = taf.find("raw_text").text

            taf_data["stationId"] = station_id
            taf_data["issue_time"] = issue_time
            taf_data["raw_text"] = raw_taf

            debugging.debug(f"TAF: {station_id} - {issue_time}")
            fcast_index = 0
            taf_forecast = []

            for forecast in taf.findall("forecast"):
                fcast = {}
                fcast["start"] = forecast.find("fcst_time_from").text
                fcast["end"] = forecast.find("fcst_time_to").text

                if forecast.find("wx_string") is not None:
                    fcast["wx_string"] = forecast.find("wx_string").text

                if forecast.find("change_indicator") is not None:
                    fcast["change_indicator"] = forecast.find("change_indicator").text

                if forecast.find("wind_dir_degrees") is not None:
                    fcast["wind_dir_degrees"] = forecast.find("wind_dir_degrees").text

                if forecast.find("wind_speed_kt") is not None:
                    fcast["wind_speed_kt"] = forecast.find("wind_speed_kt").text

                if forecast.find("visibility_statute_mi") is not None:
                    fcast["visibility_statute_mi"] = forecast.find(
                        "visibility_statute_mi"
                    ).text

                if forecast.find("wind_gust_kt") is not None:
                    fcast["wind_gust_kt"] = forecast.find("wind_gust_kt").text

                # There can be multiple layers of clouds in each taf, but they are always listed lowest AGL first.
                # Check the lowest (first) layer and see if it's overcast, broken, or obscured. If it is, then compare to cloud base height to set $
                # This algorithm basically sets the flight category based on the lowest OVC, BKN or OVX layer.
                # for each sky_condition from the XML
                flightcategory = "VFR"
                for sky_condition in forecast.findall("sky_condition"):
                    # get the sky cover (BKN, OVC, SCT, etc)
                    sky_cvr = sky_condition.attrib["sky_cover"]
                    debugging.debug(sky_cvr)  # debug

                    # If the layer is OVC, BKN or OVX, set Flight category based on height AGL
                    if sky_cvr in ("OVC", "BKN", "OVX"):
                        try:
                            # get cloud base AGL from XML
                            cld_base_ft_agl = sky_condition.attrib["cloud_base_ft_agl"]
                            # debugging.debug(cld_base_ft_agl)  # debug
                        except Exception as err:
                            # get cloud base AGL from XML
                            # debugging.error(err)
                            cld_base_ft_agl = forecast.find("vert_vis_ft")
                            if cld_base_ft_agl is not None:
                                cld_base_ft_agl = cld_base_ft_agl.text
                            else:
                                # Default to low clouds
                                cld_base_ft_agl = "60000"

                        cld_base_ft_agl = int(cld_base_ft_agl)
                        if cld_base_ft_agl < 500:
                            flightcategory = "LIFR"
                            break
                        elif 500 <= cld_base_ft_agl < 1000:
                            flightcategory = "IFR"
                            break
                        elif 1000 <= cld_base_ft_agl <= 3000:
                            flightcategory = "MVFR"
                            break
                        elif cld_base_ft_agl > 3000:
                            flightcategory = "VFR"
                            break

                    # visibilty can also set flight category. If the clouds haven't set the fltcat to LIFR. See if visibility will
                    # if it's LIFR due to cloud layer, no reason to check any other things that can set flight category.
                    if flightcategory != "LIFR":
                        # check XML if visibility value exists
                        if forecast.find("visibility_statute_mi") is not None:
                            visibility_statute_mi = forecast.find(
                                "visibility_statute_mi"
                            ).text  # get visibility number
                            try:
                                next_val = float(visibility_statute_mi)
                            except (TypeError, ValueError):
                                next_val_float = False
                            else:
                                next_val_float = True
                            if next_val_float:
                                visibility_statute_mi = float(visibility_statute_mi)
                            else:
                                # FIXME: Hack for METAR parsing of complex valus
                                if visibility_statute_mi == "6+":
                                    visibility_statute_mi = 6
                                else:
                                    debugging.info(
                                        f"GRR: visibility_statute_ml parse mismatch - setting to ten (10) actual:{visibility_statute_mi}"
                                    )
                                    visibility_statute_mi = 10
                            debugging.debug(visibility_statute_mi)

                            if visibility_statute_mi < 1.0:
                                flightcategory = "LIFR"
                            elif 1.0 <= visibility_statute_mi < 3.0:
                                flightcategory = "IFR"
                            # if Flight Category was already set to IFR $
                            elif (
                                3.0 <= visibility_statute_mi <= 5.0
                                and flightcategory != "IFR"
                            ):
                                flightcategory = "MVFR"

                    debugging.debug("Airport - " + station_id)
                    debugging.debug("Flight Category - " + flightcategory)
                    if "wind_speed_kt" in fcast:
                        debugging.debug("Wind Speed - " + fcast["wind_speed_kt"])
                    if "wx_string" in fcast:
                        debugging.debug("WX String - " + fcast["wx_string"])
                    if "change_indicator" in fcast:
                        debugging.debug(
                            "Change Indicator - " + fcast["change_indicator"]
                        )
                    if "wind_dir_degrees" in fcast:
                        debugging.debug(
                            "Wind Director Degrees - " + fcast["wind_dir_degrees"]
                        )
                    if "wind_gust_kt" in fcast:
                        debugging.debug("Wind Gust - " + fcast["wind_gust_kt"])

                fcast["flightcategory"] = flightcategory
                taf_forecast.append(fcast)
                fcast_index = fcast_index + 1

            taf_data["forecast"] = taf_forecast
            taf_dict[station_id] = taf_data

            debugging.debug(f"TAF: {station_id} - {issue_time} - {fcast_index - 1}")

        self.taf_xml_dict = taf_dict
        self.taf_update_time = datetime.now(pytz.utc)
        debugging.debug("Updating Airport TAF from XML")
        return True

    def airport_runway_data(self, airport_id):
        """Find Airport data in Runway DICT."""
        runway_set = []
        if self.runway_data is None:
            return runway_set
        airport_id = airport_id.upper()
        for runway_info in self.runway_data:
            if runway_info["airport_ident"] == airport_id:
                debugging.debug(f"Airport Runway Data Found: {runway_info}")
                runway_set.append(runway_info)
        return runway_set

    def import_runways(self):
        """Load CSV Runways file."""
        runways_master_data = self.conf.get_string("filenames", "runways_master_data")
        runway_data = None
        index_counter = 0
        with open(runways_master_data, "r") as rway_file:
            runway_data = list(csv.DictReader(rway_file))
            index_counter += 1
        debugging.debug(f"CSV Load found {index_counter} rows")
        self.runway_data = runway_data
        return True

    def import_airports(self):
        """Load CSV Airports file."""
        airports_master_data = self.conf.get_string("filenames", "airports_master_data")
        airport_data = None
        index_counter = 0
        with open(airports_master_data, "r") as aprt_file:
            airport_data = list(csv.DictReader(aprt_file))
            index_counter += 1
        debugging.debug(f"CSV Load found {index_counter} rows")
        self.airport_data = airport_data
        return True

    def update_airport_runways(self):
        """Update airport RUNWAY data for each known Airport."""
        for icao, arptdb_row in self.airport_master_dict.items():
            arpt = arptdb_row["airport"]
            debugging.debug(f"Updating Runway for {arpt.icaocode()}")
            if not arpt.active():
                continue
            try:
                runway_dataset = self.airport_runway_data(icao)
                arpt.set_runway_data(runway_dataset)
            except Exception as err:
                debug_string = (
                    "Error: update_airport_runways Exception handling for "
                    + arpt.icaocode()
                )
                debugging.error(debug_string)
                debugging.crash(err)

    def update_loop(self, conf):
        """Master loop for keeping the airport data set current.

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
        runways_csv_url = conf.get_string("urls", "runways_csv_url")
        airports_csv_url = conf.get_string("urls", "airports_csv_url")
        runways_master_data = conf.get_string("filenames", "runways_master_data")
        airports_master_data = conf.get_string("filenames", "airports_master_data")
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

        # FIXME: This pre-seeds the data sets with whatever data is on disk.
        # This is great for a quick restart ; but bad for a reload after a period of time offline.
        # Worth adding logic here to check the age of the files on disk and only load if they are relatively recent.
        self.update_airport_metar_xml()
        self.update_airport_taf_xml()

        etag_metar = None
        etag_tafs = None
        etag_mos00 = None
        etag_mos06 = None
        etag_mos12 = None
        etag_mos18 = None
        etag_runways = None
        etag_airports = None

        while True:
            debugging.debug(
                "Updating Airport Data .. every aviation_weather_adds_timer ("
                + str(aviation_weather_adds_timer)
                + "m)"
            )

            https_session = requests.Session()

            ret, etag_metar = utils.download_newer_file(
                https_session,
                metar_xml_url,
                metar_file,
                decompress=True,
                etag=etag_metar,
            )
            if ret is True:
                debugging.debug("Downloaded METAR file")
                self.update_airport_metar_xml()
            elif ret is False:
                debugging.debug("Server side METAR older")

            ret, etag_tafs = utils.download_newer_file(
                https_session, tafs_xml_url, tafs_file, decompress=True, etag=etag_tafs
            )
            if ret is True:
                debugging.debug("Downloaded TAFS file")
                self.update_airport_taf_xml()
            elif ret is False:
                debugging.debug("Server side TAFS older")

            ret, etag_mos00 = utils.download_newer_file(
                https_session, mos00_xml_url, mos00_file, etag=etag_mos00
            )
            if ret is True:
                debugging.debug("Downloaded MOS00 file")
            elif ret is False:
                debugging.debug("Server side MOS00 older")

            ret, etag_mos06 = utils.download_newer_file(
                https_session, mos06_xml_url, mos06_file, etag=etag_mos06
            )
            if ret is True:
                debugging.debug("Downloaded MOS06 file")
            elif ret is False:
                debugging.debug("Server side MOS06 older")

            ret, etag_mos12 = utils.download_newer_file(
                https_session, mos12_xml_url, mos12_file, etag=etag_mos12
            )
            if ret is True:
                debugging.debug("Downloaded MOS12 file")
            elif ret is False:
                debugging.debug("Server side MOS12 older")

            ret, etag_runways = utils.download_newer_file(
                https_session, runways_csv_url, runways_master_data, etag=etag_runways
            )
            if ret is True:
                debugging.debug("Downloaded runways.csv")
                self.import_runways()
                self.update_airport_runways()
            elif ret is False:
                debugging.debug("Server side runways.csv older")

            ret, etag_airports = utils.download_newer_file(
                https_session,
                airports_csv_url,
                airports_master_data,
                etag=etag_airports,
            )
            if ret is True:
                debugging.debug("Downloaded airports.csv")
                self.import_airports()
                # self.update_airport_lat_lon()
                # Need to use the data in airports.csv to provide lat/lon data for any airports..
            elif ret is False:
                debugging.debug("Server side airports.csv older")

            ret, etag_mos18 = utils.download_newer_file(
                https_session, mos18_xml_url, mos18_file, etag=etag_mos18
            )
            if ret is True:
                debugging.debug("Downloaded MOS18 file")
            elif ret is False:
                debugging.debug("Server side MOS18 older")

            try:
                self.update_airport_wx()
            except Exception as err:
                debugging.error(
                    "Update Weather Loop: self.update_airport_wx() exception"
                )
                debugging.error(err)
            kbfi_taf = self.get_airport_taf("kbfi")
            debugging.debug(f"TAF Lookup: kbfi {kbfi_taf}")
            kbfi_runway = self.airport_runway_data("kbfi")
            debugging.debug(f"Runway data - kbfi :{kbfi_runway}:")
            time.sleep(aviation_weather_adds_timer * 60)

            # Clean UP HTTPS_Session
            https_session.close()
        debugging.error("Hit the exit of the airport update loop")
