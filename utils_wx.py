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
from enum import Enum
from urllib.request import urlopen
import urllib.error
import socket

from metar import Metar
import debugging


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
    transient_err = "Transient Error"
    timenow = datetime.now()
    if not airport_data.enabled:
        return True
    # TODO: Move this to config
    metarexpiry = 5
    expiredtime = timenow - timedelta(minutes=metarexpiry)
    if airport_data.metar_date > expiredtime:
        # Metar Data still fresh
        debugging.debug(
            f"METAR is fresh  : {airport_data.icao} - {airport_data.flight_category}"
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
            debugging.debug(f"No data for {airport_data.icao}")
    except urllib.error.HTTPError:
        debugging.debug(f"HTTPError retrieving {airport_data.icao} data")
    except urllib.error.URLError:
        debugging.debug(f"URLError retrieving {airport_data.icao} data")
        if urlh:
            if urlh.getcode() == 404:
                airport_data.metar_date = timenow
                airport_data.metar_prev = airport_data.metar
                airport_data.metar = "URL 404 Error : Disabling"
                airport_data.enabled = False
                return True
            else:
                airport_data.metar_prev = airport_data.metar
                airport_data.metar = transient_err
                return True
        else:
            debugging.debug("URLError: urlh not set")
            airport_data.metar_prev = airport_data.metar
            airport_data.metar = transient_err
            return True
    except (socket.error, socket.gaierror):
        debugging.debug("Socket Error retrieving " + airport_data.icao)
        airport_data.metar_prev = airport_data.metar
        airport_data.metar = transient_err
        return True
    return False


def cloud_height(wx_metar):
    """Calculate Height to Broken Layer. wx_metar - METAR String."""
    wx_data = Metar.Metar(wx_metar)
    lowest_ceiling = 100000
    for cloudlayer in wx_data.sky:
        key = cloudlayer[0]
        if key == "VV":
            debugging.debug("Metar: VV Found")
            # Vertical visibilty code
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
            lowest_ceiling = min(layer_altitude, lowest_ceiling)
        if key == "VV":
            # """
            # From the AIM - Vertical Visibility (indefinite ceilingheight).
            # The height into an indefinite ceiling is preceded by "VV" and followed
            # by three digits indicating the vertical visibility in hundreds of feet.
            # This layer indicates total obscuration
            # """
            lowest_ceiling = min(layer_altitude, lowest_ceiling)
        debugging.debug("Ceiling : " + str(lowest_ceiling))
    return lowest_ceiling


def update_wx(airport_data, metar_xml_dict):
    """Update Weather Data - Get fresh METAR."""
    freshness = False
    if airport_data.wxsrc == "adds":
        try:
            debugging.debug("Update USA Metar: ADDS " + airport_data.icao)
            freshness = airport_data.get_adds_metar(metar_xml_dict[airport_data.icao])
            if freshness:
                return
        except Exception as err:
            debugging.error(err)
    elif airport_data.wxsrc == "usa-metar":
        debugging.debug(
            f"Update USA Metar: {airport_data.icao} - {airport_data.flight_category}"
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
        airport_data.flight_category = "UNKN"
        airport_data.set_wx_category(airport_data.flight_category)
    return freshness


def calculate_wx_from_metar(airport_data):
    """Use METAR data to work out wx conditions."""
    # Should have Good METAR data in airport_data.metar
    # Need to Figure out Airport State

    if airport_data is None:
        return
    if airport_data.raw_metar() is None:
        return

    try:
        airport_data_observation = Metar.Metar(airport_data.raw_metar())
    except Metar.ParserError as err:
        debugging.debug("Parse Error for METAR code: " + airport_data.raw_metar())
        debugging.error(err)
        airport_data._flight_category = "UNKN"
        airport_data.set_wx_category(airport_data._flight_category)
        return False

    if not airport_data_observation:
        debugging.info("Have no observations for " + airport_data._icao)
        return False

    if airport_data_observation.wind_dir:
        airport_data._wind_dir_degrees = airport_data_observation.wind_dir.value()
    else:
        airport_data._wind_dir_degrees = 0

    if airport_data_observation.wind_speed:
        airport_data._wind_speed_kt = airport_data_observation.wind_speed.value()
    else:
        # Should have wind speed in each update - don't want to override any existing numbers unless we get something new.
        if airport_data._wind_speed_kt is None:
            airport_data._wind_speed_kt = 0.0

    if airport_data_observation.wind_gust:
        airport_data._wx_wind_gust = airport_data_observation.wind_gust.value()
    else:
        airport_data._wx_wind_gust = 0

    if airport_data_observation.vis:
        airport_data._wx_visibility = airport_data_observation.vis.value()
    else:
        # Set visibility to -1 to flag as unknown
        airport_data._wx_visibility = -1

    try:
        airport_data._wx_ceiling = cloud_height(airport_data.raw_metar())
    except Exception as err:
        msg = "airport_data.cloud_height() failed for " + airport_data.icao
        debugging.error(msg)
        debugging.error(err)

    # Calculate Flight Category
    if airport_data._wx_ceiling == -1 or airport_data._wx_visibility == -1:
        airport_data._flight_category = "UNKN"
    elif airport_data._wx_visibility < 1 or airport_data._wx_ceiling < 500:
        airport_data._flight_category = "LIFR"
    elif 1 <= airport_data._wx_visibility < 3 or 500 <= airport_data._wx_ceiling < 1000:
        airport_data._flight_category = "IFR"
    elif (
        3 <= airport_data._wx_visibility <= 5
        or 1000 <= airport_data._wx_ceiling <= 3000
    ):
        airport_data._flight_category = "MVFR"
    elif airport_data._wx_visibility > 5 and airport_data._wx_ceiling > 3000:
        airport_data._flight_category = "VFR"
    else:
        airport_data._flight_category = "UNKN"

    airport_data.set_wx_category(airport_data._flight_category)

    if airport_data.icao_code() == "11s":
        debugging.info(
            f"calculate wx from metar {airport_data.icao_code()} /_wx_windspeed_kt : {airport_data._wind_speed_kt} / {airport_data.raw_metar()}"
        )

    debugging.debug(
        f"Airport: Ceiling {airport_data._wx_ceiling} + Visibility : {airport_data._wx_visibility}"
    )
    debugging.debug(
        f"Airport {airport_data._icao} - {airport_data._flight_category} - {airport_data.raw_metar()}"
    )
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
