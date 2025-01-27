# -*- coding: utf-8 -*- #
"""
Utilities for running system activities

Created on Jan 21st 2025

@author: chris
"""

import math
import debugging
import subprocess
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
        debugging.error(f"script: {script_path} returned: {script_result.return_code}")
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


def system_reboot():
    """Sync filesystems and trigger reboot."""
    result, output = execute_script("sync")
    result, output = execute_script("sync")
    result, output = execute_script("/sbin/reboot")
    return result
