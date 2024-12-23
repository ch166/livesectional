# -*- coding: utf-8 -*- #

# import conf


class AppInfo:
    """Class to store information and data about the install environment."""

    # Gather information about the currently installed version, and check for new versions.
    # As this gets smarter - we should be able to handle
    # - Hardware Info
    # - Performance Data
    # - Crash Data
    # - Version Information
    # - Update Information

    def __init__(self):
        self.cur_version_info = "4.5"
        self.available_version = "3.0"
        self.refresh()

    def current_version(self) -> str:
        """Return Current Version."""
        return self.cur_version_info

    def refresh(self):
        """Update AppInfo data."""
        self.check_for_update()

    def update_available(self) -> bool:
        """Return True if update is available."""
        if self.available_version > self.cur_version_info:
            return True
        return False

    def check_for_update(self) -> bool:
        """Query for new versions."""
        return False
