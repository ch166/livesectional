# -*- coding: utf-8 -*- #


import utils


class AppInfo:
    """Class to store information and data about the installation environment."""

    # We track three different versions
    # Running Version - the contents of VERSION.txt when the application started. This shouldn't change except by restarting.
    # Current Version - the contents of VERSION.txt in the application directory
    #  This should be the same as the running version ; except when we've run the update script to copy new files into place.
    # Available Version - the contents of VERSION.txt in the git repo directory

    # Gather information about the currently installed version, and check for new versions.
    # As this gets smarter - we should be able to handle
    # - Hardware Info
    # - Performance Data
    # - Crash Data
    # - Version Information
    # - Update Information

    _app_conf = None
    _run_version = "0.0"
    _cur_version = "default"
    _git_version = "unknown"

    def __init__(self, app_conf):
        self._app_conf = app_conf
        local_version_dir = self._app_conf.get_string("filenames", "basedir")
        version_file = self._app_conf.get_string("filenames", "version_file")
        local_version_file = f"{local_version_dir}/{version_file}"
        self._run_version = utils.read_version(local_version_file)
        self.refresh()

        if utils.version_newer(self._cur_version, self._git_version):
            print("app info init - update available")

    def refresh(self):
        """Update flags on active version information."""
        local_version_dir = self._app_conf.get_string("filenames", "basedir")
        git_version_dir = self._app_conf.get_string("filenames", "gitrepo")
        version_file = self._app_conf.get_string("filenames", "version_file")

        local_version_file = f"{local_version_dir}/{version_file}"
        git_version_file = f"{git_version_dir}/{version_file}"

        self._cur_version = utils.read_version(local_version_file)
        self._git_version = utils.read_version(git_version_file)

    def running_version(self) -> str:
        """Return Current Version."""
        return self._run_version

    def current_version(self) -> str:
        """Return Current Version."""
        return self._cur_version

    def available_version(self) -> str:
        """Report on available version."""
        return self._git_version

    def update_ready(self) -> bool:
        """Return True if update is installed and ready to restart."""
        return utils.version_newer(self._cur_version, self._run_version)

    def update_available(self) -> bool:
        """Return True if update is available."""
        return utils.version_newer(self._cur_version, self._git_version)
