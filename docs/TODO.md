
"""
Created on Fri Dec  2 14:55:12 2022

@author: chris
"""

# TODO

This is the overall list of things to do - with notes on progress / blockers

## Secure

### Not Run As Root

Unix permissions for GPIO operations are now available by running code as a user with gpio group membership.
That doesn't work for WS2812 PWM signaling. Until the PWM signaling is available to non-root users; we're still constrained to run as root.


## Simpler Code

### Run as multi threaded program

Running all the actions as one process with separate threads allows for inter-process communication to drive consistency across all the threads.
Updates for METAR data happen once, and are shared.
Updates to the configuration happen in a single place and are consistent.

### Restructure code to share common code

Moving code that is used a lot into a shared function allows the more complex code to be easier to read.


## Group functions by use

### Split functionality by purpose / frequency

- Raspberry PI management actions should be infrequent / perhaps better solved by other tools (webmin)
- LED/OLED configuration management should only happen broadly once when a build is happening
- Home Airport / Live MAP / Log analysis - should happen more frequently
- Network configuration updates ( wifi hotspot etc.. ) should happen infrequently

### Configuration Management should focus on like-subsets of the configuration information
- mostly-one time configuration (config to match the hardware)
- ongoing display tuning (colors, home airport data)

## OS Integration

### Run at boot
- Now installed as a script managed by systemd

### howto bootstrap networking
- is it possible to run a hotspot on all the raspberry pi systems ?
-- if so , is that the 'bootstrap' setup for initial networking
-- does the initial default web page take care of that configuration

### Package management
- support software upgrades
- perhaps run as docker container - need to see what that does for permissions and access to GPIO and PWN pins

## New Features

### HDMI output
- can we have a HDMI display output version of the data set - so that a standard RPI could be used to drive a monitor variant of this?
-- This should be a version of the existing LED map ; with additional information (legend / status )


