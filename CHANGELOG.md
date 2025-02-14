# Changelog

All notable changes to this project will be documented in this file. This changelog was started later in the dev cycle.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Feature: Announce via zeroconf to find other machines on the same network
- Feature: Change WiFi network connection via web interface
- Feature: Support for in-situ software upgrades
- Feature: Airports without METAR data can be added to use weather from adjacent airports *neigh:_code_*
- Feature: Calculate best active runway based on weather
- Script: Daily cron job to update git repos
- Script: update.sh - safely update installation
- Added TAF data to /wx/<icao> 
- Added MOS data to /wx/<icao> 
- Username/Password protection for destructive calls (eg: reboot / change wifi)
- Initial setup screen on first run
 - Admin user / password
 - TLS Enable (certificate upload)
- Ability to selectively disable individual modules (zeroconf/oled/led etc)
- Auto generate local tls host certificates

### Changed

- Use fontawesome from a separately downloaded directory on the system
- Upgraded to fontawesome 6.7.2
- Code cleanup: standardized access to color data / color naming
- Code cleanup: standardized lon/lat usage and argument ordering
- Code cleanup: added type hints
- Code cleanup: Standardized naming of class variables for consistency
- Bug fix: Fixed process for identifying best runway
- Bug fix: Rewrote ledmode RADAR code
- TAF code rewritten
- MOS code rewritten
- Added documentation / docs
- OLED Configuration being moved to config file
- Bug fix: Corrected URLs to aviationweather.gov
- Bug fix: Corrected URLs to airnav.com instead of rocketroute.com
- Bug fix: Better handling of airports and runway data sources going missing.
- Performance: minimize number of times we recalculate Metar data
- WWW: Heatmap popup shows size rather than pin ID
- Added support for VEML7700 light sensor
- Added bcrypt library as dependency for password salting
- Added crudini to allow better management of .ini files during updates

### Removed

- Installing fontawesome directly into /static directory as git submodule
- Unused config.ini variables removed
- Unused requirements.txt entries removed

## [December 2024] v4.5.1-beta.3









[December 2024] https://github.com/ch166/livesectional-stable/releases/tag/v4.5.1-beta.3
