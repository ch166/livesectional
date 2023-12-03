# Hardware Notes

## Single Board Computer

### Raspberry PI 2W
The RPI2W is the small form factor RPI. It has through hole GPIO connections, which requires soldering direct to the device.

WiFi has problems - the wifi card doesn't do well with modern wifi connections.

It appears to be a known issue 
- https://forums.raspberrypi.com/viewtopic.php?t=327169
- https://forums.raspberrypi.com/viewtopic.php?t=348367

On a unifi wifi network with PMF as optional; progressive updates to the unifi firmware have caused progressively more problems.

Other full size RPI devices connecting to the same access point have had no problems.

## Voltages

### Logic Chips

In a simple setup, the RPI needs 5v, the LEDs are 5v or 12v.
However adding in more chips to do light sensing, OLED displays, LCD displays, touch screens - brings a wider range of chipsets into the circuit.


### LEDs

#### WS2812B

Appears as 5v and 12v versions.

## i2c devices

Adding a single i2c device is straight forward; adding multiple requires some thought. Devices on an i2c bus need to have a unique ID. Multiple copies of the same type of device either need to have a way to give them different IDs. If they don't, then an i2c multiplexer is required to select which device is active.

### OLED

ssd3306 displays work

### Light Sensor

TSL 2591 works
