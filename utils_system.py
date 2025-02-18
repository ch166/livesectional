# -*- coding: utf-8 -*- #
"""
Utilities for running system activities

Created on Jan 21st 2025

@author: chris
"""

import os
import sys
from datetime import datetime, timedelta
import pytz
import math
from pathlib import Path

import bcrypt

import debugging
import subprocess
import utils
import conf


def execute_script(script_path):
    """Try to safely execute scripts."""

    script_result = None

    try:
        script_result = subprocess.run(
            script_path, stderr=subprocess.STDOUT, stdout=subprocess.PIPE
        )
    except OSError as err:
        debugging.error(f"script OSError: {script_path} err: {err}")
        return 1, "None provided"
    if script_result.returncode != 0:
        debugging.error(f"script: {script_path} returned: {script_result.returncode}")
    return script_result.returncode, script_result.stdout


def rpi_config_expand_rootfs():
    """Use raspi-config to expand rootfs."""
    result, output = execute_script(
        [
            "raspi-config",
            "nonint",
            "do_expand_rootfs",
        ]
    )
    return result


def rpi_config_wifi(ssid, passphrase):
    """Use raspi-config to set wifi settings."""
    result, output = execute_script(
        [
            "raspi-config",
            "nonint",
            "do_wifi_ssid_passphrase",
            ssid,
            passphrase,
            "0",
            "0",
        ]
    )
    return result


def rpi_config_hostname(new_hostname):
    """Use raspi-config to set hostname."""
    result, output = execute_script(
        [
            "raspi-config",
            "nonint",
            "do_hostname",
            new_hostname,
        ]
    )
    return result


def wifi_list_ssid():
    """Get list of WIFI SSIDs"""
    # nmcli \
    #       --colors no
    #       --escape no
    #       --fields "SSID, IN-USE"
    #       --mode tabular
    #       --terse
    #       device wifi list
    #       --rescan auto

    #
    COMMAND = [
        "nmcli",
        "--colors",
        "no",
        "--escape",
        "no",
        "--fields",
        "SSID,IN-USE",
        "--mode",
        "tabular",
        "--terse",
        "device",
        "wifi",
        "list",
        "--rescan",
        "auto",
    ]
    result, output = execute_script(COMMAND)
    decoded = output.decode("ascii")
    ssids = {}
    active_ssid = "default not set"
    if result == 0:
        for line in decoded.splitlines():
            ssid, active = line.split(":")
            if ssid == "":
                # Hidden SSID
                continue
            ssids[ssid] = True
            if active == "*":
                active_ssid = ssid
    return active_ssid, ssids


def system_reboot():
    """Sync filesystems and trigger reboot."""
    result, output = execute_script("sync")
    result, output = execute_script("sync")
    result, output = execute_script("/sbin/reboot")
    return result


def fresh_daily(app_conf):
    """Check to see if the timestamp on the daily update flag file is less than 24hrs old"""
    fn = app_conf.get_string("filenames", "daily_update")
    try:
        daily_data = Path(app_conf.get_string("filenames", "daily_update")).read_text(
            encoding="utf-8"
        )
    except FileNotFoundError as err:
        daily_data = "File Not Found"
    return daily_data


def encrypt_password(password):
    """Use bcrypt to salt a password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())


def match_password(password, encrypted_password):
    """Check if password matches encrypted password."""
    if encrypted_password is None:
        return False
    return bcrypt.checkpw(password, encrypted_password)
