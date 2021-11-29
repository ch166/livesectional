#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jun 15 08:01:44 2019

@author: Chris Higgins
"""

import os
import time
from datetime import datetime
from datetime import timedelta
from distutils import util
from enum import Enum
from urllib.request import urlopen
import urllib.error
import requests
import socket
import shutil

from metar import Metar

import debugging
import ledstrip
import gzip
import json
from dateutil.parser import parse as parsedate


# XML Handling
import xml.etree.ElementTree as ET



class WxConditions(Enum):
    '''
    ENUM Identifying Weather Conditions
    '''
    HIGHWINDS = 1
    GUSTS = 2
    SNOW = 3
    LIGHTNING = 4
    FOG = 5


class AirportFlightCategory(Enum):
    '''
    ENUM Flight Categories
    '''
    VFR = ledstrip.LedStrip.GREEN
    MVFR = ledstrip.LedStrip.BLUE
    IFR = ledstrip.LedStrip.RED
    LIFR = ledstrip.LedStrip.MAGENTA
    OLD = ledstrip.LedStrip.YELLOW
    UNKNOWN = ledstrip.LedStrip.WHITE


class Airport:
    """ Class to identify Airports that are known to livemap
    Initially it's all location data - but as livemap gets smarter
    we should be able to include more sources like
    - runway information
    - weather information
    """
    METAR_URL_USA = "https://tgftp.nws.noaa.gov/data/observations/metar/stations"
    METAREXPIRY = 5  # minutes

    def __init__(self, icao, iata, wxsrc, active_led, led_index):
        """ Init object and set initial values for internals """
        self.icao = icao
        self.iata = iata
        self.enabled = True
        self.active_led = util.strtobool(active_led)
        self.led_index = led_index
        self.create_time = datetime.now()
        self.updated_time = datetime.now()
        self.wxsrc = wxsrc
        self.metar = None
        self.metar_prev = None
        self.metar_date = datetime.now() - timedelta(days=1)  # Make initial date "old"
        self.observation = None
        self.led_active_state = None
        self.wx_conditions = ()
        self.wx_visibility = None
        self.wx_ceiling = None
        self.wx_windspeed = None
        self.wx_windgust = None
        self.wx_category = None
        self.wx_category_str = "UNSET"
        self.metar_returncode = ""

    def created(self):
        """ Get created time """
        return self.create_time

    def updated(self):
        """ Get last updated time """
        return self.updated_time

    def icaocode(self):
        """ airport ICAO (4 letter) code """
        return self.icao

    def iatacode(self):
        """ airport IATA (3 letter) Code """
        return self.iata

    def set_metar(self, metartext):
        """ Get Current METAR """
        self.metar_prev = self.metar
        self.metar = metartext
        self.metar_date = datetime.now()

    def get_metarage(self):
        """ Return Timestamp of METAR """
        return self.metar_date

    def get_ca_metar(self):
        """ Try get Fresh METAR data for Canadian Airports """
        return False

    def get_airport_wx_xml(self):
        """ Pull Airport XML data from ADDS XML """
        

    def get_adds_metar(self, metar_xml_dict):
        """ Try get Fresh METAR data from local Aviation Digital Data Service (ADDS) download """
        print("Poking at METAR_XML_DICT")
        print(json.dumps(metar_xml_dict))
        return False

    def get_usa_metar(self):
        """ Try get Fresh METAR Data if current data is more than METAREXPIRY minutes old"""
        timenow = datetime.now()
        if not self.enabled:
            return True
        expiredtime = timenow - timedelta(minutes=self.METAREXPIRY)
        if self.metar_date > expiredtime:
            # Metar Data still fresh
            debugging.debug("METAR is fresh  : " + self.icao + " - " + self.wx_category_str)
            return True
        url = "%s/%s.TXT" % (self.METAR_URL_USA, self.icao.upper())
        debugging.info("Retrieving METAR from: " + url)
        urlh = None
        try:
            urlh = urlopen(url)
            report = ""
            for line in urlh:
                if not isinstance(line, str):
                    line = line.decode()  # convert Python3 bytes buffer to string
                if line.startswith(self.icao.upper()):
                    report = line.strip()
                    self.metar_date = timenow
                    self.metar_prev = self.metar
                    self.metar = report
                    debugging.info(report)
            if not report:
                debugging.info("No data for " + self.icao)
        except urllib.error.HTTPError:
            debugging.info("HTTPError retrieving " + self.icao + " data")
        except urllib.error.URLError:
            # import traceback
            # debugging.info(traceback.format_exc())
            debugging.info("URLError retrieving " + self.icao + " data")
            if urlh:
                if urlh.getcode() == 404:
                    self.metar_date = timenow
                    self.metar_prev = self.metar
                    self.metar = "URL 404 Error : Disabling"
                    self.enabled = False
                    return True
                else:
                    # self.metar_date = timenow
                    self.metar_prev = self.metar
                    self.metar = "Transient Error"
                    return True
            else:
                debugging.debug("URLError: urlh not set")
                # self.metar_date = timenow
                self.metar_prev = self.metar
                self.metar = "Transient Error"
                return True
        except (socket.error, socket.gaierror):
            debugging.info("Socket Error retrieving " + self.icao)
            # self.metar_date = timenow
            self.metar_prev = self.metar
            self.metar = "Transient Error"
            return True
        return False

    def cloud_height(self):
        """ Calculate Height to Broken Layer """
        # debugging.info(self.observation.sky)
        lowest_ceiling = 100000
        for cloudlayer in self.observation.sky:
            key = cloudlayer[0]
            if key == "VV":
                debugging.debug("Metar: VV Found")
                # Vertical Visibilty Code
            if key in ('CLR', 'SKC', 'NSC', 'NCD'):
                # python metar codes for clear skies.
                return lowest_ceiling
            if not cloudlayer[1]:
                # Not sure why we are here - should have a cloud layer with altitudes
                debugging.debug("Cloud Layer without altitude values " + cloudlayer[0])
                return -1
            layer_altitude = cloudlayer[1].value()
            debugging.debug("LOC: " + self.icao + " Layer: " + key + " Alt: " + str(layer_altitude))
            if key in ('OVC', 'BKN'):
                # Overcast or Broken are considered ceiling
                if layer_altitude < lowest_ceiling:
                    lowest_ceiling = layer_altitude
            if key == 'VV':
                # """
                # From the AIM - Vertical Visibility (indefinite ceilingheight).
                # The height into an indefinite ceiling is preceded by “VV” and followed
                # by three digits indicating the vertical visibility in hundreds of feet.
                # This layer indicates total obscuration
                # """
                if layer_altitude < lowest_ceiling:
                    lowest_ceiling = layer_altitude
            debugging.debug("Ceiling : " + str(lowest_ceiling))

        return lowest_ceiling

    def update_wx(self, metar_xml_dict):
        """ Update Weather Data - Get fresh METAR"""
        freshness = False
        if self.wxsrc == "adds":
            debugging.info("Update USA Metar: ADDS " + self.icao)
            freshness = self.get_adds_metar(metar_xml_dict)
        if self.wxsrc == "usa-metar":
            debugging.info("Update USA Metar: " + self.icao + " - " + self.wx_category_str)
            freshness = self.get_usa_metar()
        elif self.wxsrc == "ca-metar":
            debugging.info("Update CA Metar: " + self.icao + " and skip")
            freshness = self.get_ca_metar()
            self.wx_category = AirportFlightCategory.UNKNOWN
            self.wx_category_str = "UNK"
            return
        if freshness:
            # Get**Metar returned 'true' so data was fresh so we
            # skipped updating. Shouldn't need to continue
            return
        # Should have Good METAR data in self.metar
        # Need to Figure out Airport State
        try:
            if not self.observation:
                debugging.warn("Observation data for " + self.icao + " Missing")
            else:
                self.observation = Metar.Metar(self.metar)
        except Metar.ParserError as exc:
            debugging.info("Parse Error for METAR code: " + self.metar)
            self.wx_category = AirportFlightCategory.UNKNOWN
            self.wx_category_str = "UNK"
            self.metar_returncode = ", ".join(exc.args)
            # TODO - Need to make sure this error handling is complete
            # especially for repeat errors and that we're updating the
            # other flags in the airport definition
            # Need to handle the logging for this issue specifically ; so that
            # we can submit fixes to the metar parsing project
            return

        if not self.observation:
            return False

        if self.observation.wind_gust:
            self.wx_windgust = self.observation.wind_gust.value()
        else:
            self.wx_windgust = 0
        if self.observation.wind_speed:
            self.wx_windspeed = self.observation.wind_speed.value()
        else:
            self.wx_windspeed = 0
        if self.observation.vis:
            self.wx_visibility = self.observation.vis.value()
        else:
            # Set visiblity to -1 to flag as unknown
            self.wx_visibility = -1

        self.wx_ceiling = self.cloud_height()

        # Calculate Flight Category
        if self.wx_ceiling == -1 or self.wx_visibility == -1:
            self.wx_category = AirportFlightCategory.UNKNOWN
            self.wx_category_str = "UNK"
        elif self.wx_visibility < 1 or self.wx_ceiling < 500:
            self.wx_category = AirportFlightCategory.LIFR
            self.wx_category_str = "LIFR"
        elif 1 <= self.wx_visibility < 3 or 500 <= self.wx_ceiling < 1000:
            self.wx_category = AirportFlightCategory.IFR
            self.wx_category_str = "IFR"
        elif 3 <= self.wx_visibility <= 5 or 1000 <= self.wx_ceiling <= 3000:
            self.wx_category = AirportFlightCategory.MVFR
            self.wx_category_str = "MVFR"
        elif self.wx_visibility > 5 and self.wx_ceiling > 3000:
            self.wx_category = AirportFlightCategory.VFR
            self.wx_category_str = "VFR"
        else:
            self.wx_category = AirportFlightCategory.UNKNOWN
            self.wx_category_str = "UNK"
        debugging.info("Airport: Ceiling " + str(self.wx_ceiling) +
                   " Visibility " + str(self.wx_visibility))
        debugging.info("Airport " + self.icao + " - " + self.wx_category_str)
        return

    def calc_wx_conditions(self):
        '''
        Compute Wind Conditions
        '''
        wx_conditions = ()
        if self.wx_windspeed > 20:
            wx_conditions = wx_conditions + (WxConditions.HIGHWINDS, )
        if self.wx_windgust > 0:
            wx_conditions = wx_conditions + (WxConditions.GUSTS, )
        return wx_conditions

class AirportDB:

    def __init__(self, conf):
        """ Create a database of Airports to be tracked """
        self.conf = conf
        self.airport_json_list = []

        self.airport_data = []

        self.tafs_xml_data = []
        self.metar_xml_dict = []
        self.metar_xml_list = []

        # FIXME: Not sure if we want to try load/save on init
        self.load_airport_db()
        self.create_airport_data()
        self.update_airport_metar_xml()
        self.save_airport_db()


    def create_airport_data(self):
        """ Update airport data """
        # FIXME: Want to have airport_data become a list of active airports
        debugging.info("Updating active airport list")
        for i in self.airport_json_list['airports']:
            airport_icao = i['icao']
            airport_led = i['led']
            airport_wxsrc = i['wxsrc']
            airport_active = i['active']
            airport_index = i['led']
            new_airport = Airport(airport_icao,
                airport_icao,
                airport_wxsrc,
                airport_active,
                airport_index)
            self.airport_data.append(new_airport)

    def update_airport_data(self):
        """ Update airport data """
        # FIXME: Want to have airport_data become a list of active airports
        for arpt in self.airport_data:
            debugging.info("Updating WX for " + arpt.icao)
            arpt.update_wx(self.metar_xml_dict)

    def load_airport_db(self):
        """ Load Airport Data file """
        # FIXME: Add file error handling
        debugging.info("Loading Airport List")
        airport_json = self.conf.get_string("filenames", "airports_json")
        # Opening JSON file
        f = open(airport_json)
 
        # returns JSON object as
        # a dictionary
        self.airport_json_list = json.load(f)
 
        # Iterating through the json
        # list
        for i in self.airport_json_list['airports']:
            print(i)
 
        # Closing file
        f.close()


    def save_airport_db(self):
        """ Save Airport Data file """
        # FIXME: Add file error handling
        # Should only overwrite destination file if this is succesful

        debugging.info("Saving Airport DB")
        airport_json_backup = self.conf.get_string("filenames", "airports_json_backup")
        airport_json_new = self.conf.get_string("filenames", "airports_json_new")
        airport_json = self.conf.get_string("filenames", "airports_json")

        shutil.move(airport_json, airport_json_backup)

        # Opening JSON file
        with open(airport_json_new, 'w') as f:
            json.dump(self.airport_json_list, f, sort_keys=True, indent=4)
        #s FIXME:  Only if write was successful, then we should 
        #   mv airport_json_new over airport_json
        shutil.move(airport_json_new, airport_json)


    def download_file(self, url, filename):
        """
        Download a gzip compressed file from URL if the 
        last-modified header is newer than our timestamp
        """

        # Do a HTTP GET to pull headers so we can check timestamps
        r = requests.head(url)

        # Technically this isn't the same timestamp as our filename 
        # there is a race condition where the server updates the 
        # file as we're in the middle of downloading it. When we 
        # finish downloading we then save the file. That new local 
        # file has a time stamp based on the file save time, which 
        # could happen after the server side file is updated. Our 
        # next update check will be wrong. We will remain
        # wrong until the server side file is updated.
        url_time = r.headers['last-modified']
        url_date = parsedate(url_time)
        file_time = datetime.fromtimestamp(os.path.getmtime(filename))
        if url_date.timestamp() > file_time.timestamp() :
            # Download archive
            try:
            # Read the file inside the .gz archive located at url
                with urllib.request.urlopen(url) as response:
                    with gzip.GzipFile(fileobj=response) as uncompressed:
                        file_content = uncompressed.read()

            # write to file in binary mode 'wb'
                with open(filename, 'wb') as f:
                    f.write(file_content)
                    f.close()
                    return 0

            except Exception as e:
                debugging.error(e)
                return 1
        return 3

    def update_airport_metar_xml(self):
        """ Update Airport METAR DICT from XML """
        # FIXME: Add file error handling
        # Consider extracting only interesting airports from dict first
        debugging.info("Updating Airport METAR DICT")
        airport_metar_list = {}
        metar_data = []
        metar_dict = {}
        metar_file = self.conf.get_string("filenames", "metar_xml_data")
        root = ET.parse(metar_file)
        for metar_data in root.iter('METAR'):
            stationId = metar_data.find('station_id').text
            print(stationId + " : ", end='')
            metar_dict[stationId] = {}
            metar_dict[stationId]['stationId'] = stationId
            next_object = metar_data.find('raw_text')
            if next_object:
                metar_dict[stationId]['raw_text'] = next_object.text
            next_object = metar_data.find('observation_time')
            if next_object:
                metar_dict[stationId]['observation_time'] = next_object.text
            next_object = metar_data.find('wind_speed_kt')
            if next_object:
                metar_dict[stationId]['wind_speed_kt'] = next_object.text
            next_object = metar_data.find('metar_type')
            if next_object:
                metar_dict[stationId]['metar_type'] = next_object.text
            next_object = metar_data.find('wind_gust_kt')
            if next_object:
                metar_dict[stationId]['wind_gust_kt'] = next_object.text
            next_object = metar_data.find('sky_condition')
            if next_object:
                metar_dict[stationId]['sky_condition'] = next_object.text
            next_object = metar_data.find('flight_category')
            if next_object:
                metar_dict[stationId]['flight_category'] = next_object.text
        self.metar_xml_dict = metar_dict
        #print(self.metar_xml_list)
            

    def update_loop(self, conf):
        """ Master loop for keeping the airport data set current """

        """
        Infinite Loop
         1/ Update METAR for all Airports in DB
         2/ Update TAF for all Airports in DB
         3/ Update MOS for all Airports
         ...
         9/ Wait for update interval timer to expire

        Triggered Update
        """

        metar_xml_url = conf.get_string("urls", "metar_xml_gz")
        tafs_xml_url = conf.get_string("urls", "tafs_xml_gz")
        metar_file = conf.get_string("filenames", "metar_xml_data")
        tafs_file = conf.get_string("filenames", "tafs_xml_data")

        # aviation_weather_adds_timer = 5 * 60
        aviation_weather_adds_timer = 30

        while(True):
            debugging.info("Updating Airport Data .. every aviation_weather_adds_timer (" + str(aviation_weather_adds_timer) + "s)" )

            ret = self.download_file(metar_xml_url, metar_file)
            if ret == 0:
                debugging.info("Downloaded METAR file")
                self.update_airport_metar_xml()
                print(self.metar_xml_list)
            elif ret == 3:
                debugging.info("Server side METAR older")
            ret = self.download_file(tafs_xml_url, tafs_file)
            if ret == 0:
                debugging.info("Downloaded TAFS file")
                # Need to trigger update of Airport TAFS data
            elif ret == 3:
                debugging.info("Server side TAFS older")

            time.sleep(aviation_weather_adds_timer)
            self.update_airport_data()



