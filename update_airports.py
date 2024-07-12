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

from lxml import etree

import debugging

import utils
import airport


class AirportDB:
    """Airport Database - Keeping track of interesting sets of airport data."""

    def __init__(self, conf, dataset_thread):
        """Create a database of Airports to be tracked."""
        # TODO: A lot of the class local variables are extras,
        # left over from the restructuring of the code.
        # for example: Some are just copies of config file data, and it
        # should be remove them as class-local variables and access the
        # config file directly as needed

        # Reference to Global Configuration Data
        self.__conf = conf
        self.__dataset = dataset_thread

        self._metar_serial = -1
        self._taf_serial = -1
        self._mos_serial = -1
        self._runway_serial = -1
        self._airport_serial = -1

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

        # Primary WX Data Sources
        # Live RAW XML Data
        self.metar_xml_dict = {}
        self.metar_update_time = None

        # Live RAW XML Data
        self.taf_xml_dict = {}
        self.taf_update_time = None

        # Primary Data Sets - Imported from Internet/External Sources
        # Runway Data
        self.runway_data = None
        # Airport Data
        self.airport_data = None

        self.load_airport_db()
        debugging.info("AirportDB : init complete")

    def stats(self):
        """Return string containing pertinant stats."""
        return f"Statistics:\n\tairport master dict {len(self.airport_master_dict)} entries\n\tairport_web_dict: {len(self.airport_web_dict)}\n\tairport_led_dict: {len(self.airport_led_dict)}"

    def create_new_airport_record(self, station_id, metar_data):
        """Create new DB record for station_id seeded with metar_data."""
        debugging.debug(f"New Airport DB Record :{station_id}:")
        airport_obj = airport.Airport(station_id, metar_data)
        return airport_obj

    def get_airport(self, airport_icao):
        """Return a single Airport."""
        return self.airport_master_dict[airport_icao]

    def __get_airport_taf(self, airport_icao):
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
        for icao, airport_obj in self.airport_master_dict.items():
            debugging.debug(f"Updating WX for :{airport_obj.icaocode()}:")
            if not airport_obj.active():
                continue
            try:
                airport_obj.update_wx(self.metar_xml_dict)
            except Exception as err:
                debug_string = f"Error: update_airport_wx Exception handling for {airport_obj.icaocode()} ICAO:{icao}:"
                debugging.error(debug_string)
                debugging.crash(err)

    def save_data_from_db(self):
        """Create JSON data from Airport datasets."""
        airportdb_list = []
        for __airport_db_id, airport_obj in self.airport_master_dict.items():
            if not airport_obj.save_in_config():
                continue
            airport_save_record = {}
            airport_save_record["active"] = str(airport_obj.active())
            airport_save_record["heatmap"] = airport_obj.heatmap_index()
            airport_save_record["icao"] = airport_obj.icaocode()
            airport_save_record["led"] = str(airport_obj.get_led_index())
            airport_save_record["purpose"] = airport_obj.purpose()
            airport_save_record["wxsrc"] = airport_obj.wxsrc()
            airportdb_list.append(airport_save_record)
        return airportdb_list

    def airport_dict_from_json(self, airport_jsondb):
        """Update Airport Master List from json src."""
        # Update self.airport_master_dict with entries from JSON file.
        # TODO: Should also mark those appropriately so they are saved out

        for json_airport in airport_jsondb["airports"]:
            self.airport_master_list.append(json_airport)
            airport_icao = json_airport["icao"]
            airport_icao = airport_icao.lower()
            debugging.info(f"Parsing Json Airport List : {airport_icao}")

            if airport_icao in ("null", "lgnd"):
                # Need a Primary Key if icao code is null or lgnd
                ledindex = json_airport["led"]
                airport_icao = f"{airport_icao}:{ledindex}"

            if airport_icao not in self.airport_master_dict.keys():
                debugging.info(f"Adding {airport_icao} to airport_master_dict")
                new_airport_object = self.create_new_airport_record(airport_icao, None)
                self.airport_master_dict.update({airport_icao: new_airport_object})
            else:
                new_airport_object = self.airport_master_dict[airport_icao]

            new_airport_object.set_wxsrc(json_airport["wxsrc"])
            new_airport_object.set_purpose(json_airport["purpose"])
            new_airport_object.set_led_index(int(json_airport["led"]))
            new_airport_object.set_heatmap_index(json_airport["heatmap"])

            new_airport_object.loaded_from_config()

            if utils.str2bool(json_airport["active"]):
                debugging.info(f"Loaded and activated airport :{airport_icao}:")
                new_airport_object.set_active()
            else:
                new_airport_object.set_inactive()
        debugging.info(
            f"Completed loading dict from json : {len(self.airport_master_dict)} items"
        )
        return True

    def airport_dicts_update(self):
        """Update master database sub-lists from master list."""
        # LED List ( purpose: LED / NULL / LGND )
        # WEB List ( purpose: WEB / LGND )
        debugging.info(
            f"Copying master dict to other lists {len(self.airport_master_dict)} items"
        )
        for airport_icao, airport_obj in self.airport_master_dict.items():
            debugging.info(f"Airport dicts update for : {airport_icao} :")
            airport_purpose = airport_obj.purpose()
            if airport_purpose in ("led", "all", "off"):
                self.airport_led_dict.update({airport_icao: airport_obj})
                debugging.info(f"Adding Airport to airport_led_dict : {airport_icao}")
            if airport_purpose in ("web", "all"):
                self.airport_web_dict.update({airport_icao: airport_obj})
                debugging.info(f"Adding airport to airport_web_dict : {airport_icao}")

        return True

    def load_airport_db(self):
        """Load Airport Data file."""
        # FIXME: Add file error handling
        debugging.debug("Loading Airport List")
        airport_json = self.__conf.get_string("filenames", "airports_json")
        # Opening JSON file
        if not utils.file_exists(airport_json):
            debugging.debug(f"Airport json does not exist: {airport_json}")
            return False

        json_file = open(airport_json, encoding="utf8")
        # returns JSON object as a dictionary
        new_airport_json_dict = json.load(json_file)
        # Closing file
        json_file.close()

        # Need to merge this data set into the existing data set
        # On initial boot ; the saved data set could be empty
        # - This will need to create all the objects
        # On update ; some records will already exist, but may have updates
        self.airport_dict_from_json(new_airport_json_dict)
        # Update the master dictionary ; overwrite existing keys with new keys
        self.airport_dicts_update()
        debugging.debug("Airport Load and Merge complete")

    def save_airport_db(self):
        """Save Airport Data file."""
        debugging.debug("Saving Airport DB")
        json_save_data = {}
        json_save_data_airport = []
        airport_json_backup = self.__conf.get_string(
            "filenames", "airports_json_backup"
        )
        airport_json_new = self.__conf.get_string("filenames", "airports_json_new")
        airport_json = self.__conf.get_string("filenames", "airports_json")

        shutil.move(airport_json, airport_json_backup)
        json_save_data_airport = self.save_data_from_db()
        json_save_data["airports"] = json_save_data_airport
        with open(airport_json_new, "w", encoding="utf8") as json_file:
            json.dump(json_save_data, json_file, sort_keys=True, indent=4)
        shutil.move(airport_json_new, airport_json)

    def update_airportdb_metar_xml(self):
        """Update Airport METAR DICT from XML."""
        # TODO: Add file error handling
        # Consider extracting only interesting airports from dict first
        debugging.debug("Updating Airports: Starting")
        metar_file = self.__conf.get_string("filenames", "metar_xml_data")
        if not utils.file_exists(metar_file):
            debugging.info(f"File missing {metar_file} - skipping xml parsing")
            return

        try:
            root = etree.parse(metar_file)
        except etree.ParseError as err:
            debugging.error("Updating Airports: XML Parse METAR Error")
            debugging.error(err)
            debugging.debug(
                "Updating Airports: XML Parse Error - Not updating airport data"
            )
            return False
        except OSError as err:
            debugging.error("Updating Airports: OS Error")
            debugging.error(err)
            debugging.debug(
                "Updating Airports: OS - Not updating airport data"
            )
            return False

        debugging.debug("Updating Airports: XML Parse Complete")
        metar_data = []
        display_counter = 0

        for metar_data in root.iter("METAR"):
            if metar_data is None:
                break
            station_id = metar_data.find("station_id").text
            station_id = station_id.lower()
            metar_raw = metar_data.find("raw_text").text
            # Log an update every 200 stations parsed
            # Want to have some tracking of progress through the data set, but not
            # burden the log file with a huge volume of data
            display_counter += 1
            if display_counter % 200 == 0:
                msg = f"xml parsing: entry:{str(display_counter)}  station_id:{station_id}"
                debugging.debug(msg)
            if station_id not in self.airport_master_dict:
                new_airport_object = self.create_new_airport_record(
                    station_id, metar_raw
                )
                self.airport_master_dict[station_id] = new_airport_object
            self.airport_master_dict[station_id].set_metar(metar_raw)
            self.airport_master_dict[station_id].update_airport_xml(
                station_id, metar_data
            )

            if station_id in ("kbfi", "ksea"):
                debugging.info(
                    f"***\nAIRPORT OF INTEREST\n\t{station_id}\t{metar_raw}\n\n"
                )

        self.metar_xml_dict = metar_data
        self.metar_update_time = datetime.now(pytz.utc)
        debugging.debug("Updating Airports: METAR from XML Complete")
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

        taf_file = self.__conf.get_string("filenames", "tafs_xml_data")

        if not utils.file_exists(taf_file):
            debugging.info(f"File missing {taf_file} - skipping xml parsing")
            return
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
                            debugging.debug(err)
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
                        if 500 <= cld_base_ft_agl < 1000:
                            flightcategory = "IFR"
                            break
                        if 1000 <= cld_base_ft_agl <= 3000:
                            flightcategory = "MVFR"
                            break
                        if cld_base_ft_agl > 3000:
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
                                visibility_statute_mi = next_val
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
        runways_master_data = self.__conf.get_string("filenames", "runways_master_data")
        if not utils.file_exists(runways_master_data):
            debugging.debug(f"Runways file does not exist: {runways_master_data}")
            return False
        runway_data = None
        index_counter = 0
        with open(runways_master_data, "r", encoding="utf-8") as rway_file:
            runway_data = list(csv.DictReader(rway_file))
            index_counter += 1
        debugging.debug(f"CSV Load found {index_counter} rows")
        self.runway_data = runway_data
        return True

    def import_airport_geo_data(self):
        """Load CSV Airports metadata file."""
        airport_master_metadata_set = self.__conf.get_string(
            "filenames", "airports_master_data"
        )
        if not utils.file_exists(airport_master_metadata_set):
            debugging.debug(f"Airport dataset does not exist: {airport_master_metadata_set}")
            return False

        airport_data = None
        index_counter = 0
        with open(airport_master_metadata_set, "r", encoding="utf-8") as aprt_file:
            airport_data = list(csv.DictReader(aprt_file))
            index_counter += 1
        debugging.debug(f"CSV Load found {index_counter} rows")
        self.airport_data = airport_data
        return True

    def update_airport_runways(self):
        """Update airport RUNWAY data for each known Airport."""
        for icao, airport_obj in self.airport_master_dict.items():
            debugging.debug(f"Updating Runway for {airport_obj.icaocode()}")
            if not airport_obj.active():
                continue
            try:
                runway_dataset = self.airport_runway_data(icao)
                airport_obj.set_runway_data(runway_dataset)
            except Exception as err:
                debug_string = f"Error: update_airport_runways Exception handling for {airport_obj.icaocode()}"
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

        # TODO: Should these files be updated in a separate thread
        # should this update loop focus on creating and managing complete database records for only the
        # airports that we currently care about ?

        while True:
            debugging.debug(
                f"Updating Airport Data .. every aviation_weather_adds_timer ({aviation_weather_adds_timer})m)"
            )

            if self._metar_serial < self.__dataset.metar_serial():
                debugging.debug("Processing updated METAR data")
                self._metar_serial = self.__dataset.metar_serial()
                self.update_airportdb_metar_xml()

            if self._taf_serial < self.__dataset.taf_serial():
                debugging.debug("Processing updated TAF data")
                self._taf_serial = self.__dataset.taf_serial()
                self.update_airport_taf_xml()

            if self._runway_serial < self.__dataset.runway_serial():
                debugging.debug("Processing updated Runway data")
                self._runway_serial = self.__dataset.runway_serial()
                self.import_runways()
                # TODO: Figure out when this should be run - if not every time
                self.update_airport_runways()

            if self._airport_serial < self.__dataset.airport_serial():
                debugging.debug("Processing updated Airport data")
                self._airport_serial = self.__dataset.airport_serial()
                self.import_airport_geo_data()
                # self.update_airport_lat_lon()
                # Need to use the data in airports.csv to provide lat/lon data for any airports..

            # TODO: Add back in MOS processing in whatever new form it takes

            # FIXME: Key airport data - useful for debugging / health updates
            # Remove eventually
            kbfi_taf = self.__get_airport_taf("kbfi")
            debugging.debug(f"TAF Lookup: kbfi {kbfi_taf}")
            kbfi_runway = self.airport_runway_data("kbfi")
            debugging.debug(f"Runway data - kbfi :{kbfi_runway}:")
            time.sleep(aviation_weather_adds_timer * 60)

        debugging.error("Hit the exit of the airport update loop")
