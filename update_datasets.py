# -*- coding: utf-8 -*- #

"""
Created on Sat Jun 15 08:01:44 2019.

@author: Chris Higgins
"""

# The update_loop function is intended to be called in a discrete thread, so that it can run
# forever, checking for updated datasets and downloading those data sets to that they can be
# processed.
#

# TODO: Get any/all the error handling for connectivity issues moved here


# import os
import time
import requests

import debugging
import utils
import utils_mos


class DataSets:
    """Dataset Sync - Keeping track of datasets."""

    _app_conf = None
    _metar_update_time = None
    _metar_serial_num = 0
    _mos_update_time = None
    _mos_serial_num = 0
    _taf_update_time = None
    _taf_serial_num = 0
    _runway_update_time = None
    _runway_serial_num = 0
    _airport_update_time = None
    _airport_serial_num = 0

    _mos_forecast_updated = False
    _mos_forecast = None

    def __init__(self, app_conf):
        """Tracking freshness of data sets ; internally using the time stamp of when the updated was pulled
        Clients of this class use a serial number - so that the ability to determine if something was updated is straightforward.
        Also allows clients to determine how many updates have happened since they completed their last test
        Assumes that we won't have integer wraparound (which appears to occur at sys.maxsize) before an app restart.
        """
        self._app_conf = app_conf
        self._metar_update_time = None
        self._metar_serial_num = 0
        self._mos_update_time = None
        self._mos_serial_num = 0
        self._taf_update_time = None
        self._taf_serial_num = 0
        self._runway_update_time = None
        self._runway_serial_num = 0
        self._airport_update_time = None
        self._airport_serial_num = 0

    def metar_update_time(self):
        """Get last time metar data was updated."""
        return self._metar_update_time

    def metar_serial(self):
        """Get dataset serial number."""
        return self._metar_serial_num

    def mos_update_time(self):
        """Get last time MOS data was updated."""
        return self._mos_update_time

    def mos_serial(self):
        """Get dataset serial number."""
        return self._mos_serial_num

    def mos_forecast_updated(self):
        """Check if MOS forecast has been updated."""
        return self._mos_forecast_updated

    def mos_forecast(self):
        """Get MOS Forecast."""
        return self._mos_forecast

    def taf_update_time(self):
        """Get last time TAF data was updated."""
        return self._taf_update_time

    def taf_serial(self):
        """Get dataset serial number."""
        return self._taf_serial_num

    def runway_update_time(self):
        """Get last time runways.csv data was updated."""
        return self._runway_update_time

    def runway_serial(self):
        """Get dataset serial number."""
        return self._runway_serial_num

    def airport_update_time(self):
        """Get last time airport geo location data was updated."""
        return self._airport_update_time

    def airport_serial(self):
        """Get dataset serial number."""
        return self._airport_serial_num

    def stats(self):
        """Return string containing pertinant stats."""
        return f"Statistics:\n\tMetar Refresh {self.metar_serial()}/{self._metar_update_time}\n\tMOS refresh: {self.mos_serial()}/{self._mos_update_time}\n\tTAF Refresh: {self.taf_serial()}/{self._taf_update_time}"

    def mos_refresh(self, https_session, etag_mos, mos_file, mos_xml_url):
        """Refresh MOS Data."""
        ret, new_etag_mos = utils.download_newer_file(
            https_session, mos_xml_url, mos_file, etag=etag_mos
        )
        if ret is True:
            debugging.debug(f"Downloaded :{mos_file}: file")
        elif ret is False:
            debugging.debug(f"Server side :{mos_file}: older")
            return False, etag_mos

        try:
            self._mos_forecast_updated, self._mos_forecast = (
                utils_mos.mos_analyze_datafile(
                    self._app_conf,
                )
            )
            # For each airplane in airplanedb ;
            # get MOS data
            # push to airplane db
        except Exception as err:
            debugging.error("MOS Refresh")
            debugging.error(err)

        return True, new_etag_mos

    def update_loop(self, app_conf):
        """Master loop for keeping the data set current.

        Infinite Loop
         1/ Update METAR data sets
         2/ Update TAF data sets
         3/ Update MOS data sets
         4/ Update Airport Runway DB
         ...
         9/ Wait for update interval timer to expire

        Triggered Update
        """
        aviation_weather_adds_timer = app_conf.get_int("metar", "wx_update_interval")

        # TODO: Do we really need these, or can we just do the conf lookup when needed
        # Might be better to pull them from the conf file on demand,
        # to allow the config to be dynamically updated without needing a restart
        metar_xml_url = app_conf.get_string("urls", "metar_xml_gz")
        metar_file = app_conf.get_string("filenames", "metar_xml_data")
        runways_csv_url = app_conf.get_string("urls", "runways_csv_url")
        airports_csv_url = app_conf.get_string("urls", "airports_csv_url")
        runways_master_data = app_conf.get_string("filenames", "runways_master_data")
        airport_master_metadata_set = app_conf.get_string(
            "filenames", "airports_master_data"
        )
        tafs_xml_url = app_conf.get_string("urls", "tafs_xml_gz")
        tafs_file = app_conf.get_string("filenames", "tafs_xml_data")
        mos00_xml_url = app_conf.get_string("urls", "mos00_data_gz")
        mos00_file = app_conf.get_string("filenames", "mos00_xml_data")
        # mos06_xml_url = app_conf.get_string("urls", "mos06_data_gz")
        # mos06_file = app_conf.get_string("filenames", "mos06_xml_data")
        # mos12_xml_url = app_conf.get_string("urls", "mos12_data_gz")
        # mos12_file = app_conf.get_string("filenames", "mos12_xml_data")
        # mos18_xml_url = app_conf.get_string("urls", "mos18_data_gz")
        # mos18_file = app_conf.get_string("filenames", "mos18_xml_data")

        etag_metar = None
        etag_tafs = None
        etag_mos00 = None
        # etag_mos06 = None
        # etag_mos12 = None
        # etag_mos18 = None
        etag_runways = None
        etag_airports = None

        # Initial load of MOS data set
        if self._mos_forecast_updated == False:
            self._mos_forecast_updated, self._mos_forecast = (
                utils_mos.mos_analyze_datafile(
                    self._app_conf,
                )
            )

        while True:
            debugging.debug(
                f"Updating Airport Data .. every aviation_weather_adds_timer {aviation_weather_adds_timer}m)"
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
                self._metar_update_time = utils.current_time_utc(app_conf)
                self._metar_serial_num += 1
            elif ret is False:
                debugging.debug("Server side METAR older")

            ret, etag_tafs = utils.download_newer_file(
                https_session, tafs_xml_url, tafs_file, decompress=True, etag=etag_tafs
            )
            if ret is True:
                debugging.debug("Downloaded TAFS file")
                self._taf_update_time = utils.current_time_utc(app_conf)
                self._taf_serial_num += 1
            elif ret is False:
                debugging.debug("Server side TAFS older")

            ret, etag_runways = utils.download_newer_file(
                https_session, runways_csv_url, runways_master_data, etag=etag_runways
            )
            if ret is True:
                debugging.debug("Downloaded runways.csv")
                self._runway_update_time = utils.current_time_utc(app_conf)
                self._runway_serial_num += 1
            elif ret is False:
                debugging.debug("Server side runways.csv older")

            ret, etag_airports = utils.download_newer_file(
                https_session,
                airports_csv_url,
                airport_master_metadata_set,
                etag=etag_airports,
            )
            if ret is True:
                debugging.debug("Downloaded airports.csv")
                self._airport_update_time = utils.current_time_utc(app_conf)
                self._airport_serial_num += 1
            elif ret is False:
                debugging.debug("Server side airports.csv older")

            etag_mos00 = self.mos_refresh(
                https_session, etag_mos00, mos00_file, mos00_xml_url
            )
            if ret is True:
                debugging.debug("Downloaded new MOS data")
                self._mos_update_time = utils.current_time_utc(app_conf)
                self._mos_serial_num += 1
            elif ret is False:
                debugging.debug("Server side MOS data older")

            # Limiting to a single MOS data set for now; as the data differs
            # across the data sets for the same time period ; so there isn't an
            # obvious way to merge the data.
            #
            # etag_mos06 = self.mos_refresh(
            #     https_session, etag_mos06, mos06_file, mos06_xml_url
            # )
            # etag_mos12 = self.mos_refresh(
            #     https_session, etag_mos12, mos12_file, mos12_xml_url
            # )
            # etag_mos18 = self.mos_refresh(
            #     https_session, etag_mos18, mos18_file, mos18_xml_url
            # )

            # Clean UP HTTPS_Session
            https_session.close()

            time.sleep(aviation_weather_adds_timer * 60)
