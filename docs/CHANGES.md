
This version contains a lot of changes from the v4 original source.

This is a high level list of those changes ; and some of the rational behind them.

1. Created classes for Airports, AirportDB, Config, Logging etc.
   The original code had places where code was duplicated - the creation of the classes is intended to 
   simplify the core functions by pushing lots of the related details inside a class.

2. Moved away from multiple separate programs
   Each of the individual programs had to do duplicate work - getting and parsing METAR data
   Having all of the METAR parsing in *one* place means that there are only one set of metar parsing bugs, not several
   Running as one program - keeps the config in sync across the entire set of functions.

3. Running as separate threads
   Separate threads means that each activity can happen inside its own thread, at it's own cadence.
   This means that the timings are simpler across the functions. 
   The thread handling the LEDs doesn't have to stop and get METAR updates
   The thread getting METAR updates can be fast or slow, without impacting LED or OLED displays

