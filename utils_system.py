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
