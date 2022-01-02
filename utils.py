#!/usr/bin/env python3
""" Collection of shared utility functions for all of the modules """

import os
import time
import socket
import json
import urllib
import gzip

from datetime import datetime
from datetime import timedelta
from dateutil.parser import parse as parsedate

import requests
import wget
import pytz

import debugging

# import conf

def is_connected():
    ''' Check to see if we can reach an endpoint on the Internet '''
    try:
        # connect to the host -- tells us if the host is actually
        # reachable
        sock = socket.create_connection(("ipv4.google.com", 80))
        if sock is not None:
            print('Closing socket')
            sock.close()
        return True
    except OSError:
        pass
    return False


def wait_for_internet():
    ''' Delay until Internet is up (return True) - or (return False) '''
    wait_count = 0
    while True:
        if is_connected():
            return True
        wait_count += 1
        if wait_count == 6:
            return False
        time.sleep(30)


def get_local_ip():
    ''' Create Socket to the Internet, Query Local IP '''
    ipaddr = "UNKN"
    try:
        # connect to the host -- tells us if the host is actually
        # reachable
        sock = socket.create_connection(("ipv4.google.com", 80))
        if sock is not None:
            ipaddr = sock.getsockname()[0]
            print('Closing socket')
            sock.close()
        return ipaddr
    except OSError:
        pass
    return "0.0.0.0"


# May be used to display user location on map in user interface.
# TESTING Not working consistently, not used
# This is not working for at least the following reasons
# 1. extreme-ip-lookup wants an API key
# 2. extreme-ip-lookup.com is on some pihole blocklists
#
# IP to Geo mapping is notoriously error prone
# Going to look at python-geoip as a data source
def get_loc():
    """ Try figure out approximate location from IP data """
    loc_data = {}
    loc = {}

    url_loc = 'https://extreme-ip-lookup.com/json/'
    geo_json_data = requests.get(url_loc)
    data = json.loads(geo_json_data.content.decode())

    ip_data = data['query']
    loc_data['city'] = data['city']
    loc_data['region'] = data['region']
    loc_data['lat'] = data['lat']
    loc_data['lon'] = data['lon']
    loc[ip_data] = loc_data


def delete_file(target_path, filename):
    """Delete File"""  # FIXME - Check to make sure filename is not relative
    try:
        os.remove(target_path + filename)
        debugging.info('Deleted ' + filename)
    except OSError as error:
        debugging.error("Error " + error.__str__() +
                        " while deleting file " +
                        target_path +
                        filename)


def rgb2hex(rgb):
    """Convert RGB to HEX"""
    debugging.dprint(rgb)
    (red_value, green_value, blue_value) = rgb
    hexval = '#%02x%02x%02x' % (red_value, green_value, blue_value)
    return hexval


def hex2rgb(value):
    """Hex to RGB"""
    value = value.lstrip('#')
    length_v = len(value)
    return tuple(int(value[i:i+length_v//3], 16)
                 for i in range(0, length_v, length_v//3))


def download_file(url, filename):
    """ Download a file """
    wget.download(url, filename)
    debugging.info('Downloaded ' + filename + ' from neoupdate')


def download_newer_gz_file(url, filename):
    """
    Download a gzip compressed file from URL if the
    last-modified header is newer than our timestamp
    """

    # Do a HTTP GET to pull headers so we can check timestamps
    req = requests.head(url)

    # Technically this isn't the same timestamp as our filename
    # there is a race condition where the server updates the
    # file as we're in the middle of downloading it. When we
    # finish downloading we then save the file. That new local
    # file has a time stamp based on the file save time, which
    # could happen after the server side file is updated. Our
    # next update check will be wrong. We will remain
    # wrong until the server side file is updated.
    url_time = req.headers['last-modified']
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


def time_in_range(start, end, x_time):
    """ See if a time falls within range """
    if start <= end:
        return start <= x_time <= end
    return end <= x_time <= start


# Compare current time plus offset to TAF's time period and return difference
def comp_time(zulu_time, taf_time):
    """ Compare time plus offset to TAF """
    # global current_zulu
    date_time_format = ('%Y-%m-%dT%H:%M:%SZ')
    date1 = taf_time
    date2 = zulu_time
    diff = datetime.strptime(date1, date_time_format) - \
    datetime.strptime(date2, date_time_format)
    diff_minutes = int(diff.seconds/60)
    diff_hours = int(diff_minutes/60)
    return diff.seconds, diff_minutes, diff_hours, diff.days


def reboot_if_time(conf):
    """ Check to see if it's time to reboot """
    # Check time and reboot machine if time equals
    # time_reboot and if use_reboot along with autorun are both set to 1
    use_reboot = conf.get_bool("default", "nightly_reboot")
    use_autorun = conf.get_bool("default", "autorun")
    reboot_time = conf.get_string("default", "nightly_reboot_hr")
    if use_reboot and use_autorun:
        now = datetime.now()
        rb_time = now.strftime("%H:%M")
        debugging.info("**Current Time=" + str(rb_time) +
            " - **Reboot Time=" + str(reboot_time))
        print("**Current Time=" + str(rb_time) +
            " - **Reboot Time=" + str(reboot_time))  # debug

        # FIXME: Reference to 'self' here
        # if rb_time == self.time_reboot:
        #    debugging.info("Rebooting at " + self.time_reboot)
        #    time.sleep(1)
            # FIXME: This should use a more secure mechanism,
            # and have some sanity checks - that we aren't in a reboot loop.
            # Also should handle daylight savings time changes (avoid double reboot)
            # If using sudo - need to make sure that install scripts
            # set sudo perms for this command only
        #    os.system("sudo reboot now")


def time_format_taf(raw_time):
    """ Convert raw time into TAF formatted printable string """
    return raw_time.strftime("%Y-%m-%dT%H:%M:%SZ")


def time_format(raw_time):
    """ Convert raw time into standardized printable string """
    return raw_time.strftime("%H:%M:%S - %b %d, %Y")


def current_time_utc(conf):
    """ Get time in UTC """
    UTC = pytz.utc
    curr_time = datetime.now(UTC)
    return curr_time


def current_time(conf):
    """ Get time Now """
    TMZONE = pytz.timezone(conf.get_string("default", "timezone"))
    curr_time = datetime.now(TMZONE)
    return curr_time


def current_time_taf_offset(conf):
    """ Get time for TAF period selected (UTC) """
    UTC = pytz.utc
    offset = conf.get_int("rotaryswitch", "hour_to_display")
    curr_time = datetime.now(UTC) +  timedelta(hours=offset)
    return curr_time


def set_timezone(conf, newtimezone):
    """ Set timezone configuration string """
    # Doo stuff to set the timezone
    conf.set_string("default", "timezone", newtimezone)
    conf.save_config()


def get_timezone(conf):
    """ Return timezone configuration """
    return conf.get_string("default", "timezone")
