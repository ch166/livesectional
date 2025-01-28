# -*- coding: utf-8 -*- #
""" Collection of shared utility functions for all modules ."""

import os
import os.path
import time
import shutil
import socket
import json
import urllib
import gzip
import tempfile

import datetime
from datetime import timedelta
from dateutil.parser import parse as parsedate

from pathlib import Path

import requests

# import wget
import pytz

import debugging


def file_exists(filename):
    """Check if a file exists."""
    if os.path.isfile(filename):
        return True
    return False


def is_connected():
    """Check to see if we can reach an endpoint on the Internet."""
    ipaddr = "unset"
    try:
        # connect to the host -- tells us if the host is actually
        # reachable
        sock = socket.create_connection(("ipv4.google.com", 80), timeout=3)
        if sock is not None:
            ipaddr = sock.getsockname()[0]
            sock.close()
        return (True, ipaddr)
    except OSError:
        pass
    return (False, "0.0.0.0")


def str2bool(input_str):
    """Simple check for truthiness of string."""
    return input_str.lower() in ["true", "1", "t", "y", "yes"]


def wait_for_internet():
    """Delay until Internet is up (return True) - or (return False)."""
    wait_count = 0
    while True:
        (online_status, ipaddr) = is_connected()
        if online_status:
            return True
        wait_count += 1
        if wait_count == 6:
            return False
        internet_delay = 30
        debugging.debug(f"Waiting {internet_delay} seconds for Internet")
        time.sleep(internet_delay)


def get_local_ip():
    """Create Socket to the Internet, Query Local IP."""
    ipaddr = "UNKN"
    try:
        # connect to the host -- tells us if the host is actually
        # reachable
        sock = socket.create_connection(("ipv4.google.com", 80))
        if sock is not None:
            ipaddr = sock.getsockname()[0]
            print("Closing socket")
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
# IP to Geo mapping is notoriously error-prone
# Going to look at python-geoip as a data source
def get_loc():
    """Try figure out approximate location from IP data."""
    loc_data = {}
    loc = {}

    url_loc = "https://extreme-ip-lookup.com/json/"
    geo_json_data = requests.get(url_loc, timeout=10)
    data = json.loads(geo_json_data.content.decode())

    ip_data = data["query"]
    loc_data["city"] = data["city"]
    loc_data["region"] = data["region"]
    loc_data["lat"] = data["lat"]
    loc_data["lon"] = data["lon"]
    loc[ip_data] = loc_data


def delete_file(target_path, filename):
    """Delete File."""
    # TODO: - Check to make sure filename is not relative
    if os.path.isfile(filename):
        try:
            os.remove(target_path + filename)
            debugging.debug("Deleted " + filename)
            return True
        except OSError as err:
            debugging.error(f"Error {err} while deleting file {target_path} {filename}")
            return False
    else:
        return False


def rgb2hex(rgb):
    """Convert RGB to HEX."""
    debugging.dprint(rgb)
    (red_value, green_value, blue_value) = rgb
    hexval = "#%02x%02x%02x" % (red_value, green_value, blue_value)
    return hexval


def hex2rgb(value):
    """Hex to RGB."""
    value = value.lstrip("#")
    length_v = len(value)
    return tuple(
        int(value[i : i + length_v // 3], 16) for i in range(0, length_v, length_v // 3)
    )


def download_newer_file(session, url, filename, decompress=False, etag=None):
    """
    Attempt to download a file only if it appears newer / different from the server side copy.
    Download a file from URL if the
    last-modified header is newer than our timestamp

    Return Values: result, etag
    Result:
        True - Download completed
        False - Download not attempted
    Etag:
        Etag Header

    ."""
    debugging.debug("Starting download_newer_file" + filename)
    url_time = url_date = url_etag = None
    download = False

    # Do a HTTP GET to pull headers so we can check timestamps
    try:
        req = session.head(url, allow_redirects=True, timeout=5)
    except ConnectionError as err:
        debugging.debug(f"Connection Error :{url}:")
        debugging.error(err)
        return False, url_etag
    except TimeoutError as err:
        debugging.debug(f"Timeout Error :{url}:")
        debugging.error(err)
        return False, url_etag
    except Exception as err:
        debugging.debug(f"Generic error checking HEAD :{url}:")
        debugging.error(err)
        return False, url_etag

    if "last-modified" in req.headers:
        url_time = req.headers["last-modified"]
        url_date = parsedate(url_time)
    if "etag" in req.headers:
        url_etag = req.headers["etag"]

    if not os.path.isfile(filename):
        # File doesn't exist, so we need to download it
        debugging.info(
            f"Download request for {filename}; file not found ; download scheduled"
        )
        download = True
    else:
        # File exists - we might have a last-modified header
        # or we might be using etag comparisons to decide if something is newer/different
        if url_time is not None:
            file_time = datetime.datetime.fromtimestamp(os.path.getmtime(filename))
            if url_date.timestamp() > file_time.timestamp():
                # Time stamp of local file is older than timestamp on server
                download = True
            else:
                # Server side file is same or older, our file is up to date
                msg = (
                    f"Timestamp check - Server side: {datetime.datetime.fromtimestamp(url_date.timestamp())}"
                    f"Local : {datetime.datetime.fromtimestamp(file_time.timestamp())}"
                )
                debugging.debug(msg)
        if (url_etag is not None) and (etag != url_etag):
            # Check to see if downloaded etag and value passed in are the same. If not - download is true
            download = True

    if download:
        debugging.debug(f"Starting download_newer_file {filename}")
        try:
            # Download file to temporary object
            download_object = tempfile.NamedTemporaryFile(delete=False)
            try:
                urllib.request.urlretrieve(url, download_object.name)
            except ConnectionError as err:
                debugging.info(f"Connection error in download :{url}:")
                debugging.error(err)
                return False, url_etag
            except TimeoutError as err:
                debugging.info(f"Timeout Error :{url}:")
                debugging.error(err)
                return False, url_etag
            except Exception as err:
                debugging.info(f"Generic error in urlretrieve :{url}:")
                debugging.error(err)
                return False, url_etag

            if decompress:
                uncompress_object = tempfile.NamedTemporaryFile(delete=False)
                try:
                    decompress_file_gz(download_object.name, uncompress_object.name)
                except Exception as err:
                    debugging.info(f"File decompression failed for : {filename}")
                    debugging.error(err)
                os.remove(download_object.name)
                download_object = uncompress_object

            shutil.copyfile(download_object.name, filename)
            os.remove(download_object.name)
            # Set the timestamp of the downloaded file to
            # match the HEAD date stamp / or 'now' for etag headers
            if url_date is None:
                file_timestamp = datetime.datetime.now().timestamp()
            else:
                file_timestamp = datetime.datetime.timestamp(url_date)
            os.utime(filename, (file_timestamp, file_timestamp))
            return download, url_etag
        except Exception as err:
            debugging.error(err)
            return False, url_etag
    return download, url_etag


def decompress_file_gz(srcfile, dstfile):
    """use gzip to decompress a file."""
    try:
        # Decompress the file
        with gzip.open(srcfile, "rb") as f_in:
            with open(dstfile, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
        return True
    except Exception as err:
        # Something went wrong
        debugging.info(f"File gzip decompress error f:{srcfile}:")
        debugging.error(err)
        return False

def read_file(fn):
    """Read a file into a variable"""
    return Path(fn).read_text(encoding="utf-8")


def time_in_range(start_time, end_time, check_time):
    """See if a time falls within range."""
    if start_time < end_time:
        return start_time <= check_time <= end_time
    else:  # overnight
        return (check_time >= start_time) or (check_time <= end_time)


def reboot_if_time(app_conf):
    """Check to see if it's time to reboot."""
    # Check time and reboot machine if time equals
    # time_reboot and if use_reboot
    use_reboot = app_conf.get_bool("default", "nightly_reboot")
    reboot_time = app_conf.get_string("default", "nightly_reboot_hr")
    if use_reboot:
        now = datetime.datetime.now()
        rb_time = now.strftime("%H:%M")
        debugging.debug(
            "**Current Time=" + str(rb_time) + " - **Reboot Time=" + str(reboot_time)
        )
        print(
            "**Current Time=" + str(rb_time) + " - **Reboot Time=" + str(reboot_time)
        )  # debug

        # FIXME: Reference to 'self' here
        # if rb_time == self.time_reboot:
        #    debugging.debug("Rebooting at " + self.time_reboot)
        #    time.sleep(1)
        # This process should be more secure
        # and have some sanity checks - that we aren't in a reboot loop.
        # Also should handle daylight savings time changes (avoid double reboot)
        # If using sudo - need to make sure that install scripts
        # set sudo perms for this command only
        #    os.system("sudo reboot now")


def time_format_taf(raw_time):
    """Convert raw time into TAF formatted printable string."""
    if raw_time is None:
        raw_time = datetime.datetime(1970, 1, 1)
    return raw_time.strftime("%Y-%m-%dT%H:%M:%SZ")


def time_format_hm(raw_time):
    """Convert raw time into standardized printable string."""
    if raw_time is None:
        raw_time = datetime.datetime(1970, 1, 1)
    return raw_time.strftime("%H:%M")


def time_format_hms(raw_time):
    """Convert raw time into standardized printable string."""
    if raw_time is None:
        raw_time = datetime.datetime(1970, 1, 1)
    return raw_time.strftime("%H:%M:%S")


def time_format(raw_time):
    """Convert raw time into standardized printable string."""
    if raw_time is None:
        raw_time = datetime.datetime(1970, 1, 1)
    return raw_time.strftime("%H:%M:%S - %b %d, %Y")


def current_time_hr_utc(app_conf):
    """Get current HR in UTC."""
    curr_time = datetime.datetime.now(pytz.utc)
    return int(curr_time.strftime("%H"))


def current_time_utc(app_conf):
    """Get time in UTC."""
    return datetime.datetime.now(pytz.utc)


def current_time_utc_plus_hr(app_conf, hour_interval):
    """Get time in UTC."""
    return datetime.datetime.now(pytz.utc) + datetime.timedelta(hours=hour_interval)


def current_time(app_conf):
    """Get time Now."""
    return datetime.datetime.now(
        pytz.timezone(app_conf.get_string("default", "timezone"))
    )


def set_timezone(app_conf, newtimezone):
    """Set timezone configuration string."""
    # Doo stuff to set the timezone
    app_conf.set_string("default", "timezone", newtimezone)
    app_conf.save_config()


def get_timezone(app_conf):
    """Return timezone configuration."""
    return app_conf.get_string("default", "timezone")
