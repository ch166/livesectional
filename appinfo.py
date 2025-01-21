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
    _run_version = "0.0"
    _cur_version = "default"
    _git_version = "unknown"

    def __init__(self, app_conf):
        self._app_conf = app_conf
        local_version_dir = self._app_conf.get_string("filenames", "basedir")
        version_file = self._app_conf.get_string("filenames", "version_file")
        local_version_file = f"{local_version_dir}/{version_file}"
        self._run_version = self.read_version(local_version_file)
        self.refresh()
        if self.update_available():
            print("app info init - update available")

    def read_version(self, filename):
        """Read version info from file."""
        file_version = "version not found"
        with open(filename, "r", encoding="utf-8") as fp:
            for line in fp:
                if line.startswith("version:"):
                    label, version = line.split(" ")
                    file_version = version.strip()
                    continue
        return file_version

    def refresh(self):
        """Update flags on active version information."""
        local_version_dir = self._app_conf.get_string("filenames", "basedir")
        git_version_dir = self._app_conf.get_string("filenames", "gitrepo")
        version_file = self._app_conf.get_string("filenames", "version_file")

        local_version_file = f"{local_version_dir}/{version_file}"
        git_version_file = f"{git_version_dir}/{version_file}"

        self._cur_version = self.read_version(local_version_file)
        self._git_version = self.read_version(git_version_file)

    def running_version(self) -> str:
        """Return Current Version."""
        return self._run_version

    def current_version(self) -> str:
        """Return Current Version."""
        return self._cur_version

    def available_version(self) -> str:
        """Report on available version."""
        return self._git_version

    def semver(self, versionstring):
        """Extract major, minor and patch numbers from version info."""
        major, minor, patch = versionstring.split(".")
        return int(major), int(minor), int(patch)

    def update_ready(self) -> bool:
        """Return True if update is installed and ready to restart."""
        # debugging.info(f"Version: {self._cur_version} / {self._git_version} : update available check")
        c_major, c_minor, c_patch = self.semver(self._cur_version)
        r_major, r_minor, r_patch = self.semver(self._run_version)
        major_rev = c_major > r_major
        minor_rev = c_minor > r_minor
        patch_rev = c_patch > r_patch
        if major_rev or minor_rev or patch_rev:
            # debugging.info(f"Version: {self._cur_version} / {self._git_version} : UPDATE AVAILABLE")
            return True
        return False

    def update_available(self) -> bool:
        """Return True if update is available."""
        # debugging.info(f"Version: {self._cur_version} / {self._git_version} : update available check")
        c_major, c_minor, c_patch = self.semver(self._cur_version)
        n_major, n_minor, n_patch = self.semver(self._git_version)
        major_rev = n_major > c_major
        minor_rev = n_minor > c_minor
        patch_rev = n_patch > c_patch
        if major_rev or minor_rev or patch_rev:
            # debugging.info(f"Version: {self._cur_version} / {self._git_version} : UPDATE AVAILABLE")
            return True
        return False
