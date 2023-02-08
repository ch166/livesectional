# -*- coding: utf-8 -*- #
"""
Created on Mon Sept 5 08:01:44 2022.

@author: Chris Higgins
"""

# This is the collection and aggregation of all functions that
# parse METAR, Weather, TAF data

# It includes supporting utility functions

from datetime import datetime
from datetime import timedelta

# from distutils import util
from enum import Enum
from urllib.request import urlopen
import urllib.error
import socket


from metar import Metar
import debugging

# import utils


class WxConditions(Enum):
    """ENUM Identifying Weather Conditions."""

    HIGHWINDS = 1
    GUSTS = 2
    SNOW = 3
    LIGHTNING = 4
    FOG = 5


def get_usa_metar(airport_data):
    """Try get Fresh METAR Data if current data is more than METAREXPIRY minutes old."""
    # TODO: This code is no longer the primary source of METAR data.
    # There is an opportunity to use it as a fallback path for METAR data missing from the
    # full XML data.
    #
    timenow = datetime.now()
    if not airport_data.enabled:
        return True
    # TODO: Move this to config
    metarexpiry = 5
    expiredtime = timenow - timedelta(minutes=metarexpiry)
    if airport_data.metar_date > expiredtime:
        # Metar Data still fresh
        debugging.debug(
            f"METAR is fresh  : {airport_data.icao} - {airport_data.wx_category_str}"
        )
        return True
    # TODO: Move this to config
    metar_url_usa = "https://tgftp.nws.noaa.gov/data/observations/metar/stations"
    url = f"{metar_url_usa}/{airport_data.icao.upper()}.TXT"
    debugging.debug("Retrieving METAR from: " + url)
    urlh = None
    try:
        urlh = urlopen(url)
        report = ""
        for line in urlh:
            if not isinstance(line, str):
                line = line.decode()  # convert Python3 bytes buffer to string
            if line.startswith(airport_data.icao.upper()):
                report = line.strip()
                airport_data.metar_date = timenow
                airport_data.metar_prev = airport_data.metar
                airport_data.metar = report
                debugging.debug(report)
        if not report:
            debugging.debug("No data for " + airport_data.icao)
    except urllib.error.HTTPError:
        debugging.debug("HTTPError retrieving " + airport_data.icao + " data")
    except urllib.error.URLError:
        # import traceback
        # debugging.debug(traceback.format_exc())
        debugging.debug("URLError retrieving " + airport_data.icao + " data")
        if urlh:
            if urlh.getcode() == 404:
                airport_data.metar_date = timenow
                airport_data.metar_prev = airport_data.metar
                airport_data.metar = "URL 404 Error : Disabling"
                airport_data.enabled = False
                return True
            else:
                # airport_data.metar_date = timenow
                airport_data.metar_prev = airport_data.metar
                airport_data.metar = "Transient Error"
                return True
        else:
            debugging.debug("URLError: urlh not set")
            # airport_data.metar_date = timenow
            airport_data.metar_prev = airport_data.metar
            airport_data.metar = "Transient Error"
            return True
    except (socket.error, socket.gaierror):
        debugging.debug("Socket Error retrieving " + airport_data.icao)
        # airport_data.metar_date = timenow
        airport_data.metar_prev = airport_data.metar
        airport_data.metar = "Transient Error"
        return True
    return False


def cloud_height(wx_metar):
    """Calculate Height to Broken Layer. wx_metar - METAR String."""
    # debugging.debug(wx_data.observation.sky)
    wx_data = Metar.Metar(wx_metar)
    lowest_ceiling = 100000
    for cloudlayer in wx_data.sky:
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
            "LOC: " + wx_metar + " Layer: " + key + " Alt: " + str(layer_altitude)
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


def update_wx(airport_data, metar_xml_dict):
    """Update Weather Data - Get fresh METAR."""
    freshness = False
    if airport_data.wxsrc == "adds":
        try:
            debugging.debug("Update USA Metar: ADDS " + airport_data.icao)
            freshness = airport_data.get_adds_metar(metar_xml_dict)
        except Exception as err:
            debugging.error(err)
    elif airport_data.wxsrc == "usa-metar":
        debugging.debug(
            f"Update USA Metar: {airport_data.icao} - {airport_data.wx_category_str}"
        )
        freshness = get_usa_metar(airport_data)
        if freshness:
            # get_*_metar() returned true, so weather is still fresh
            return
        calculate_wx_from_metar(airport_data)
    elif airport_data.wxsrc == "ca-metar":
        debugging.debug("Update CA Metar: " + airport_data.icao + " and skip")
        freshness = airport_data.get_ca_metar()
        if freshness:
            # get_*_metar() returned true, so weather is still fresh
            return
        airport_data.wx_category_str = "UNKN"
        airport_data.set_wx_category(airport_data.wx_category_str)
    return


def calculate_wx_from_metar(airport_data):
    """Use METAR data to work out wx conditions."""
    # Should have Good METAR data in airport_data.metar
    # Need to Figure out Airport State
    try:
        airport_data_observation = Metar.Metar(airport_data.metar)
    except Metar.ParserError as err:
        debugging.debug("Parse Error for METAR code: " + airport_data.metar)
        debugging.error(err)
        airport_data.wx_category_str = "UNKN"
        airport_data.set_wx_category(airport_data.wx_category_str)
        return False

    if not airport_data_observation:
        debugging.warn("Have no observations for " + airport_data.icao)
        return False

    if airport_data_observation.wind_gust:
        airport_data.wx_windgust = airport_data_observation.wind_gust.value()
    else:
        airport_data.wx_windgust = 0
    if airport_data.observation.wind_speed:
        airport_data.wx_windspeed = airport_data_observation.wind_speed.value()
    else:
        airport_data.wx_windspeed = 0
    if airport_data.observation.vis:
        airport_data.wx_visibility = airport_data_observation.vis.value()
    else:
        # Set visiblity to -1 to flag as unknown
        airport_data.wx_visibility = -1
    try:
        airport_data.wx_ceiling = cloud_height(airport_data.metar)
    except Exception as err:
        msg = "airport_data.cloud_height() failed for " + airport_data.icao
        debugging.error(msg)
        debugging.error(err)

    # Calculate Flight Category
    if airport_data.wx_ceiling == -1 or airport_data.wx_visibility == -1:
        airport_data.wx_category_str = "UNKN"
    elif airport_data.wx_visibility < 1 or airport_data.wx_ceiling < 500:
        airport_data.wx_category_str = "LIFR"
    elif 1 <= airport_data.wx_visibility < 3 or 500 <= airport_data.wx_ceiling < 1000:
        airport_data.wx_category_str = "IFR"
    elif (
        3 <= airport_data.wx_visibility <= 5 or 1000 <= airport_data.wx_ceiling <= 3000
    ):
        airport_data.wx_category_str = "MVFR"
    elif airport_data.wx_visibility > 5 and airport_data.wx_ceiling > 3000:
        airport_data.wx_category_str = "VFR"
    else:
        airport_data.wx_category_str = "UNKN"

    airport_data.set_wx_category(airport_data.wx_category_str)

    debugging.debug(
        f"Airport: Ceiling {airport_data.wx_ceiling} + Visibility : {airport_data.wx_visibility}"
    )
    debugging.debug(f"Airport {airport_data.icao} - {airport_data.wx_category_str}")
    return True


def calc_wx_conditions(wx_metar):
    """Compute Wind Conditions."""
    wx_conditions = ()
    wx_data = Metar.Metar(wx_metar)

    if wx_data.wind_speed > 20:
        wx_conditions = wx_conditions + (WxConditions.HIGHWINDS,)
    if wx_data.wind_gust > 0:
        wx_conditions = wx_conditions + (WxConditions.GUSTS,)
    return wx_conditions
