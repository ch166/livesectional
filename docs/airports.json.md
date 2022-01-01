# Airport JSON config file

This contains an entry for each interesting airport with the following data

* "active": True/False - Is this entry to be updated 
* "icao": ICAO code for airport , NULL for blank LED, LGND for Legend Key
* "led": Index to LED value
* "purpose": Which use is active for this airport
  * ALL: Active for all outputs
  * LED: This is active on an LED string only
  * OLED: This is active on an OLED display
  * HTTP: This is active for the HTTP page
  * HDMI: This is active for the HDMI output
* "wxsrc": Which weather source for this airport
  * adds : USA Digital Data Set
  * usa-metar : Direct METAR query
  * ca-metar : Direct CA METAR query
* "heatmap": Priority setting for Heatmap data
