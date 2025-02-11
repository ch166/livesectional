#### Setup Process

Generic instructions have (actuals) in brackets

SD Card > 16Gb (32Gb) 

rpi-imager to install 32bit Debian Bookworm Lite 
Use the rpi-imager 'edit image' feature to set wifi and login user (pi/raspberry for the dev node)

Modern images will do some system housekeeping on first boot - including auto-expanding the filesystem; so this isn't required.

## Enable i2c
sudo raspi-config
-> 5 Interfacing Options
-> P5 I2C
-> Select *YES*

Reboot the device

## Update Software

pi@<hostname>: sudo su
root@<hostname>: apt update && apt-get -u dist-upgrade -y --download-only

root@<hostname>: apt-get -y dist-upgrade

### Install libxslt Library (for XML parsing)

root@<hostname>: apt install libxslt1.1  

### Install OpenJPEG lib (for image creation)

root@<hostmame>: apt install libopenjp2-7

### Install OpenBLAS library (for numpy)

root@<hostname>: apt install libopenblas0

### Pillow 11.0.0.0 requirements
root@<hostname>: apt install libjpeg-dev libpython3-dev zlib1g-dev

# Activate

systemctl enable livemap
systemctl start livemap

systemctl status livemap
