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

    _app_conf = None
    _cur_version = "default"
    available_version = "unknown"

    def __init__(self, app_conf):
        self._app_conf = app_conf
        self.refresh()

    def refresh(self):
        """Update flags on active version information."""
        local_version_dir = self._app_conf.get_string("filenames", "basedir")
        git_version_dir = self._app_conf.get_string("filenames", "gitrepo")
        version_file = self._app_conf.get_string("filenames", "version_file")

        local_version_file = f"{local_version_dir}/{version_file}"
        git_version_file = f"{git_version_dir}/{version_file}"

        with open(local_version_file, "r", encoding="utf-8") as fp:
            for line in fp:
                if line.startswith("version:"):
                    label, version = line.split(" ")
                    self._cur_version = version.strip()
                    continue

        with open(git_version_file, "r", encoding="utf-8") as fp:
            for line in fp:
                if line.startswith("version:"):
                    label, version = line.split(" ")
                    self.git_version_info = version.strip()
                    continue

    def current_version(self) -> str:
        """Return Current Version."""
        return self._cur_version

    def semver(self, versionstring):
        """Extract major, minor and patch numbers from version info."""
        major, minor, patch = versionstring.split(".")
        return int(major), int(minor), int(patch)

    def update_available(self) -> bool:
        """Return True if update is available."""
        c_major, c_minor, c_patch = self.semver(self._cur_version)
        n_major, n_minor, n_patch = self.semver(self.available_version)
        major_rev = n_major > c_major
        minor_rev = n_minor > c_minor
        patch_rev = n_patch > c_patch
        if major_rev or minor_rev or patch_rev:
            return True
        return False
