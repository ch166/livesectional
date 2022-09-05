#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jun 15 08:01:44 2019

@author: Chris Higgins
"""

# This is the collection and aggregation of all functions that manage Airports and airport weather
# products. It's initially focused on processing METARs, but will end up including all of the functions
# related to TAFs and MOS data.
#
# This file is the management of the Airport object
# The airport object stores all of the interesting data for an airport
# - Airport ICAO code
# - Weather Source ( adds , metar URL, future options)
# - Airport Code to use for WX data (future - for airports without active ASOS/AWOS reporting)
# - Current conditions
# - etc.


# import os
import time
from datetime import datetime
from datetime import timedelta
from distutils import util
from enum import Enum
from urllib.request import urlopen
import urllib.error
import socket
import shutil

# import gzip
import json

# Moving to use requests instead of urllib
import requests

# from dateutil.parser import parse as parsedate


# XML Handling
import xml.etree.ElementTree as ET
from metar import Metar

import debugging
import ledstrip
import utils


class WxConditions(Enum):
    """
    ENUM Identifying Weather Conditions
    """

    HIGHWINDS = 1
    GUSTS = 2
    SNOW = 3
    LIGHTNING = 4
    FOG = 5


class AirportFlightCategory(Enum):
    """
    ENUM Flight Categories
    """

    VFR = ledstrip.LedStrip.GREEN
    MVFR = ledstrip.LedStrip.BLUE
    IFR = ledstrip.LedStrip.RED
    LIFR = ledstrip.LedStrip.MAGENTA
    OLD = ledstrip.LedStrip.YELLOW
    UNKNOWN = ledstrip.LedStrip.WHITE


class Airport:
    """Class to identify Airports that are known to livemap
    Initially it's all location data - but as livemap gets smarter
    we should be able to include more sources like
    - runway information
    - weather information
    """

    METAR_URL_USA = "https://tgftp.nws.noaa.gov/data/observations/metar/stations"
    METAREXPIRY = 5  # minutes

    def __init__(self, icao, iata, wxsrc, active_led, led_index, conf):
        """Init object and set initial values for internals"""
        self.icao = icao
        self.iata = iata
        self.conf = conf
        self.enabled = True
        self.active_led = util.strtobool(active_led)
        self.led_index = led_index
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
        self.latitude = 0
        self.longitude = 0
        self.metar_returncode = ""

    def last_updated(self):
        """Get last updated time"""
        return self.updated_time

    def get_latitude(self):
        """Return Airport Latitude"""
        return self.latitude

    def get_longitude(self):
        """Return Airport longitude"""
        return self.longitude

    def icaocode(self):
        """airport ICAO (4 letter) code"""
        return self.icao

    def iatacode(self):
        """airport IATA (3 letter) Code"""
        return self.iata

    def set_metar(self, metartext):
        """Get Current METAR"""
        self.metar_prev = self.metar
        self.metar = metartext
        self.metar_date = datetime.now()
        self.updated_time = datetime.now()

    def get_raw_metar(self):
        """Return raw METAR data"""
        return self.metar

    def get_metarage(self):
        """Return Timestamp of METAR"""
        return self.metar_date

    def get_ca_metar(self):
        """Try get Fresh METAR data for Canadian Airports"""
        # TODO: Stub for now
        return False

    def get_airport_wx_xml(self):
        """Pull Airport XML data from ADDS XML"""
        # TODO: Stub

    def set_led_index(self, led_index):
        """Update LED ID"""
        self.led_index = led_index

    def get_led_index(self):
        """Return LED ID"""
        return self.led_index

    def set_wxsrc(self, wxsrc):
        """Set Weather source"""
        self.wxsrc = wxsrc

    def set_active(self):
        """Mark Airport as Active"""
        self.active_led = True

    def active(self):
        """Active"""
        return self.active_led

    def set_inactive(self):
        """Mark Airport as Inactive"""
        self.active_led = False

    def get_wx_category_str(self):
        """Return string form of airport weather category"""
        return self.wx_category_str

    def get_wx_windspeed(self):
        """Return reported windspeed"""
        return self.wx_windspeed

    def get_adds_metar(self, metar_dict):
        """Try get Fresh METAR data from local Aviation Digital Data Service (ADDS) download"""
        debugging.info("Updating WX from adds for " + self.icao)
        if self.icao not in metar_dict:
            # TODO: If METAR data is missing from the ADDS dataset, then it hasn't been updated
            # We have the option to try a direct query for the data ; but don't have any hint
            # on which alternative source to use.
            debugging.debug("metar_dict WX for " + self.icao + " missing")
            self.wx_category = AirportFlightCategory.UNKNOWN
            self.wx_category_str = "UNK"
            self.metar_date = datetime.now()
            self.set_metar(None)
            return
        self.set_metar(metar_dict[self.icao]["raw_text"])
        self.wx_visibility = metar_dict[self.icao]["visibility"]
        self.wx_ceiling = metar_dict[self.icao]["ceiling"]
        self.wx_windspeed = metar_dict[self.icao]["wind_speed_kt"]
        self.wx_windgust = metar_dict[self.icao]["wind_gust_kt"]
        self.wx_category = metar_dict[self.icao]["flight_category"]
        self.wx_category_str = metar_dict[self.icao]["flight_category"]
        self.latitude = float(metar_dict[self.icao]["latitude"])
        self.longitude = float(metar_dict[self.icao]["longitude"])
        self.calculate_wx_from_metar()
        return False

    def get_usa_metar(self):
        """Try get Fresh METAR Data if current data is more than METAREXPIRY minutes old"""
        timenow = datetime.now()
        if not self.enabled:
            return True
        expiredtime = timenow - timedelta(minutes=self.METAREXPIRY)
        if self.metar_date > expiredtime:
            # Metar Data still fresh
            debugging.debug(
                "METAR is fresh  : " + self.icao + " - " + self.wx_category_str
            )
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
                debugging.debug("No data for " + self.icao)
        except urllib.error.HTTPError:
            debugging.debug("HTTPError retrieving " + self.icao + " data")
        except urllib.error.URLError:
            # import traceback
            # debugging.info(traceback.format_exc())
            debugging.debug("URLError retrieving " + self.icao + " data")
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
        """Calculate Height to Broken Layer"""
        # debugging.info(self.observation.sky)
        lowest_ceiling = 100000
        for cloudlayer in self.observation.sky:
            key = cloudlayer[0]
            if key == "VV":
                debugging.debug("Metar: VV Found")
                # Vertical Visibilty Code
            if key in ("CLR", "SKC", "NSC", "NCD"):
                # python metar codes for clear skies.
                return lowest_ceiling
            if not cloudlayer[1]:
                # Not sure why we are here - should have a cloud layer with altitudes
                debugging.debug("Cloud Layer without altitude values " + cloudlayer[0])
                return -1
            layer_altitude = cloudlayer[1].value()
            debugging.debug(
                "LOC: " + self.icao + " Layer: " + key + " Alt: " + str(layer_altitude)
            )
            if key in ("OVC", "BKN"):
                # Overcast or Broken are considered ceiling
                if layer_altitude < lowest_ceiling:
                    lowest_ceiling = layer_altitude
            if key == "VV":
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
        """Update Weather Data - Get fresh METAR"""
        freshness = False
        if self.wxsrc == "adds":
            try:
                debugging.info("Update USA Metar: ADDS " + self.icao)
                freshness = self.get_adds_metar(metar_xml_dict)
            except Exception as err:
                debugging.error(err)
        elif self.wxsrc == "usa-metar":
            debugging.info(
                "Update USA Metar: " + self.icao + " - " + self.wx_category_str
            )
            freshness = self.get_usa_metar()
            if freshness:
                # get_*_metar() returned true, so weather is still fresh
                return
            self.calculate_wx_from_metar()
        elif self.wxsrc == "ca-metar":
            debugging.info("Update CA Metar: " + self.icao + " and skip")
            freshness = self.get_ca_metar()
            if freshness:
                # get_*_metar() returned true, so weather is still fresh
                return
            self.wx_category = AirportFlightCategory.UNKNOWN
            self.wx_category_str = "UNK"
        return

    def calculate_wx_from_metar(self):
        # Should have Good METAR data in self.metar
        # Need to Figure out Airport State
        try:
            self.observation = Metar.Metar(self.metar)
            # if self.observation is None:
            #     debugging.warn("Observation data for " + self.icao + " Missing")
            #     self.observation = Metar.Metar(self.metar)
            # else:
            #     self.observation = Metar.Metar(self.metar)
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
            debugging.warn("Have no observations for " + self.icao)
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
        try:
            self.wx_ceiling = self.cloud_height()
        except Exception as err:
            msg = "self.cloud_height() failed for " + self.icao
            debugging.error(msg)
            debugging.error(err)

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
        debugging.debug(
            "Airport: Ceiling "
            + str(self.wx_ceiling)
            + " Visibility "
            + str(self.wx_visibility)
        )
        debugging.info("Airport " + self.icao + " - " + self.wx_category_str)
        return

    def calc_wx_conditions(self):
        """
        Compute Wind Conditions
        """
        wx_conditions = ()
        if self.wx_windspeed > 20:
            wx_conditions = wx_conditions + (WxConditions.HIGHWINDS,)
        if self.wx_windgust > 0:
            wx_conditions = wx_conditions + (WxConditions.GUSTS,)
        return wx_conditions

    def decode_taf_data(
        self, stationiddict, windsdict, wxstringdict, metar_taf_mos, root_data
    ):
        # FIXME: Moved from update_leds ; fix references to variables over there, that aren't here.
        # TAF decode routine
        # 0 equals display TAF. This routine will decode the TAF, pick the appropriate time frame to display.
        if metar_taf_mos == 0:
            debugging.info("Starting TAF Data Display")
            # start of TAF decoding routine
            for data in root_data.iter("data"):
                # get number of airports reporting TAFs to be used for diagnosis only
                num_results = data.attrib["num_results"]
                debugging.info("\nNum of Airport TAFs = " + num_results)  # debug

            for taf in root_data.iter("TAF"):  # iterate through each airport's TAF
                stationId = taf.find("station_id").text  # debug
                debugging.info(stationId)  # debug
                # debugging.info('Current+Offset Zulu - ' + self.current_zulu)  # debug
                taf_wx_string = ""
                taf_change_indicator = ""
                taf_wind_dir_degrees = ""
                taf_wind_speed_kt = ""
                taf_wind_gust_kt = ""

                # Now look at the forecasts for the airport
                for forecast in taf.findall("forecast"):

                    # Routine inspired by Nick Cirincione.
                    flightcategory = "VFR"  # intialize flight category
                    taf_time_from = forecast.find(
                        "fcst_time_from"
                    ).text  # get taf's from time
                    taf_time_to = forecast.find(
                        "fcst_time_to"
                    ).text  # get taf's to time

                    if forecast.find("wx_string") is not None:
                        taf_wx_string = forecast.find(
                            "wx_string"
                        ).text  # get weather conditions

                    if forecast.find("change_indicator") is not None:
                        taf_change_indicator = forecast.find(
                            "change_indicator"
                        ).text  # get change indicator

                    if forecast.find("wind_dir_degrees") is not None:
                        taf_wind_dir_degrees = forecast.find(
                            "wind_dir_degrees"
                        ).text  # get wind direction

                    if forecast.find("wind_speed_kt") is not None:
                        taf_wind_speed_kt = forecast.find(
                            "wind_speed_kt"
                        ).text  # get wind speed

                    if forecast.find("wind_gust_kt") is not None:
                        taf_wind_gust_kt = forecast.find(
                            "wind_gust_kt"
                        ).text  # get wind gust speed

                    # test if current time plus offset falls within taf's timeframe
                    if (
                        taf_time_from
                        <= utils.current_time_utc(self.conf)
                        <= taf_time_to
                    ):
                        debugging.info("FROM - " + taf_time_from)
                        debugging.info(
                            utils.comp_time(
                                utils.current_time_utc(self.conf), taf_time_from
                            )
                        )
                        debugging.info("TO - " + taf_time_to)
                        debugging.info(
                            utils.comp_time(
                                utils.current_time_utc(self.conf), taf_time_to
                            )
                        )

                        # There can be multiple layers of clouds in each taf, but they are always listed lowest AGL first.
                        # Check the lowest (first) layer and see if it's overcast, broken, or obscured. If it is, then compare to cloud base height to set $
                        # This algorithm basically sets the flight category based on the lowest OVC, BKN or OVX layer.
                        # for each sky_condition from the XML
                        for sky_condition in forecast.findall("sky_condition"):
                            # get the sky cover (BKN, OVC, SCT, etc)
                            sky_cvr = sky_condition.attrib["sky_cover"]
                            debugging.info(sky_cvr)  # debug

                            # If the layer is OVC, BKN or OVX, set Flight category based on height AGL
                            if sky_cvr in ("OVC", "BKN", "OVX"):

                                try:
                                    # get cloud base AGL from XML
                                    cld_base_ft_agl = sky_condition.attrib[
                                        "cloud_base_ft_agl"
                                    ]
                                    debugging.info(cld_base_ft_agl)  # debug
                                except Exception as err:
                                    # get cloud base AGL from XML
                                    cld_base_ft_agl = forecast.find("vert_vis_ft").text

                                #  cld_base_ft_agl = sky_condition.attrib['cloud_base_ft_agl'] #get cloud base AGL from XML
                                #  debugging.info(cld_base_ft_agl) #debug

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
                                visibility_statute_mi = float(visibility_statute_mi)
                                debugging.info(visibility_statute_mi)

                                if visibility_statute_mi < 1.0:
                                    flightcategory = "LIFR"

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

                        # Print out TAF data to screen for diagnosis only
                        debugging.info("Airport - " + stationId)
                        debugging.info("Flight Category - " + flightcategory)
                        debugging.info("Wind Speed - " + taf_wind_speed_kt)
                        debugging.info("WX String - " + taf_wx_string)
                        debugging.info("Change Indicator - " + taf_change_indicator)
                        debugging.info(
                            "Wind Director Degrees - " + taf_wind_dir_degrees
                        )
                        debugging.info("Wind Gust - " + taf_wind_gust_kt)

                        # grab flightcategory from returned FAA data
                        if (
                            flightcategory is None
                        ):  # if wind speed is blank, then bypass
                            flightcategory = None

                        # grab wind speeds from returned FAA data
                        if (
                            taf_wind_speed_kt is None
                        ):  # if wind speed is blank, then bypass
                            windspeedkt = 0
                        else:
                            windspeedkt = taf_wind_speed_kt

                        # grab Weather info from returned FAA data
                        if (
                            taf_wx_string is None
                        ):  # if weather string is blank, then bypass
                            wxstring = "NONE"
                        else:
                            wxstring = taf_wx_string

                # Check for duplicate airport identifier and skip if found, otherwise store in dictionary. covers for dups in "airports" file
                if stationId in stationiddict:
                    debugging.info(
                        stationId + " Duplicate, only saved first metar category"
                    )
                else:
                    # build category dictionary
                    stationiddict[stationId] = flightcategory

                if stationId in windsdict:
                    debugging.info(stationId + " Duplicate, only saved the first winds")
                else:
                    # build windspeed dictionary
                    windsdict[stationId] = windspeedkt

                if stationId in wxstringdict:
                    debugging.info(
                        stationId + " Duplicate, only saved the first weather"
                    )
                else:
                    # build weather dictionary
                    wxstringdict[stationId] = wxstring
            debugging.info("Decoded TAF Data for Display")

        elif metar_taf_mos == 1:
            debugging.info("Starting METAR Data Display")
            # start of METAR decode routine if 'metar_taf_mos' equals 1. Script will default to this routine without a rotary switch installed.
            # grab the airport category, wind speed and various weather from the results given from FAA.
            for metar in root_data.iter("METAR"):
                stationId = metar.find("station_id").text

                # METAR Decode Routine to create flight category via cloud cover and/or visability when flight category is not reported.
                # Routine contributed to project by Nick Cirincione. Thank you for your contribution.
                # if category is blank, then see if there's a sky condition or vis that would dictate flight category
                if (
                    metar.find("flight_category") is None
                    or metar.find("flight_category") == "NONE"
                ):
                    flightcategory = "VFR"  # intialize flight category
                    sky_cvr = "SKC"  # Initialize to Sky Clear
                    debugging.info(
                        stationId + " Not Reporting Flight Category through the API."
                    )

                    # There can be multiple layers of clouds in each METAR, but they are always listed lowest AGL first.
                    # Check the lowest (first) layer and see if it's overcast, broken, or obscured. If it is, then compare to cloud base height to set flight category.
                    # This algorithm basically sets the flight category based on the lowest OVC, BKN or OVX layer.
                    # First check to see if the FAA provided the forecast field, if not get the sky_condition.
                    if (
                        metar.find("forecast") is None
                        or metar.find("forecast") == "NONE"
                    ):
                        debugging.info(
                            "FAA xml data is NOT providing the forecast field for this airport"
                        )
                        # for each sky_condition from the XML
                        for sky_condition in metar.findall("./sky_condition"):
                            # get the sky cover (BKN, OVC, SCT, etc)
                            sky_cvr = sky_condition.attrib["sky_cover"]
                            debugging.info("Sky Cover = " + sky_cvr)

                            # Break out of for loop once we find one of these conditions
                            if sky_cvr in ("OVC", "BKN", "OVX"):
                                break

                    else:
                        debugging.info(
                            "FAA xml data IS providing the forecast field for this airport"
                        )
                        # for each sky_condition from the XML
                        for sky_condition in metar.findall("./forecast/sky_condition"):
                            # get the sky cover (BKN, OVC, SCT, etc)
                            sky_cvr = sky_condition.attrib["sky_cover"]
                            debugging.info("Sky Cover = " + sky_cvr)
                            debugging.info(metar.find("./forecast/fcst_time_from").text)

                            # Break out of for loop once we find one of these conditions
                            if sky_cvr in ("OVC", "BKN", "OVX"):
                                break

                    # If the layer is OVC, BKN or OVX, set Flight category based on height AGL
                    if sky_cvr in ("OVC", "BKN", "OVX"):
                        try:
                            # get cloud base AGL from XML
                            cld_base_ft_agl = sky_condition.attrib["cloud_base_ft_agl"]
                        except:
                            # get cloud base AGL from XML
                            cld_base_ft_agl = forecast.find("vert_vis_ft").text

                        debugging.info("Cloud Base = " + cld_base_ft_agl)
                        cld_base_ft_agl = int(cld_base_ft_agl)

                        if cld_base_ft_agl < 500:
                            flightcategory = "LIFR"
                            # break
                        elif 500 <= cld_base_ft_agl < 1000:
                            flightcategory = "IFR"
                            # break
                        elif 1000 <= cld_base_ft_agl <= 3000:
                            flightcategory = "MVFR"
                            # break
                        elif cld_base_ft_agl > 3000:
                            flightcategory = "VFR"
                            # break

                    # visibilty can also set flight category. If the clouds haven't set the fltcat to LIFR. See if visibility will
                    # if it's LIFR due to cloud layer, no reason to check any other things that can set flight category.
                    if flightcategory != "LIFR":
                        # check XML if visibility value exists
                        if metar.find("./forecast/visibility_statute_mi") is not None:
                            visibility_statute_mi = metar.find(
                                "./forecast/visibility_statute_mi"
                            ).text  # get visibility number
                            visibility_statute_mi = float(visibility_statute_mi)

                            if visibility_statute_mi < 1.0:
                                flightcategory = "LIFR"

                            elif 1.0 <= visibility_statute_mi < 3.0:
                                flightcategory = "IFR"

                            # if Flight Category was already set to IFR by clouds, it can't be reduced to MVFR
                            elif (
                                3.0 <= visibility_statute_mi <= 5.0
                                and flightcategory != "IFR"
                            ):
                                flightcategory = "MVFR"

                    debugging.info(
                        stationId
                        + " flight category is Decode script-determined as "
                        + flightcategory
                    )

                else:
                    debugging.info(
                        stationId
                        + ": FAA is reporting "
                        + metar.find("flight_category").text
                        + " through their API"
                    )
                    # pull flight category if it exists and save all the algoritm above
                    flightcategory = metar.find("flight_category").text
                # End of METAR Decode added routine to create flight category via cloud cover and/or visability when flight category is not reported.
                # grab wind speeds from returned FAA data
                # if wind speed is blank, then bypass
                if metar.find("wind_speed_kt") is None:
                    windspeedkt = 0
                else:
                    windspeedkt = metar.find("wind_speed_kt").text

                # grab Weather info from returned FAA data
                # if weather string is blank, then bypass
                if metar.find("wx_string") is None:
                    wxstring = "NONE"
                else:
                    wxstring = metar.find("wx_string").text

                # Check for duplicate airport identifier and skip if found, otherwise store in dictionary. covers for dups in "airports" file
                if stationId in stationiddict:
                    debugging.info(
                        stationId + " Duplicate, only saved first metar category"
                    )
                else:
                    # build category dictionary
                    stationiddict[stationId] = flightcategory

                if stationId in windsdict:
                    debugging.info(stationId + " Duplicate, only saved the first winds")
                else:
                    # build windspeed dictionary
                    windsdict[stationId] = windspeedkt

                if stationId in wxstringdict:
                    debugging.info(
                        stationId + " Duplicate, only saved the first weather"
                    )
                else:
                    # build weather dictionary
                    wxstringdict[stationId] = wxstring
            debugging.info("Decoded METAR Data for Display")
