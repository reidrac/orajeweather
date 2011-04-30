Oraje Weather 
=============

This is a Gnome applet to view Yahoo! Weather forecasts.

This application uses Yahoo! Weather feeds and it's not endorsed or
promoted by Yahoo! in any way.

In case you're wondering, "Oraje" is a Spanish word that means "Weather".


Install
-------

This package requires:

 - Python >= 2.6
 - PyGTK2 >= 2.16.0
 - Gnome python bindings (including applet support)
 - Gnome 2 (also known as "Classic Gnome").

Optionally dbus is used to support NetworkManager and notifications.

$ sudo python setup.py install --prefix=/usr

PS: some distributions install the applet by default in /usr/local, and 
Bonobo doesn't find the files in that path. The 'prefix' switch it's
used to fix that, although it isn't necessary in all cases.


WOEID
-----

Yahoo! Weather API doesn't provide a way to find a location, so you have to
browse Yahoo! Weather (http://weather.yahoo.com/), find your location
and get the number at the end of the URL. That's your WOEID.

For example:

http://weather.yahoo.com/england/berkshire/reading-32997/

The WOEID for Reading (UK) is 32997.


License
-------

Copyright (C) 2010 Juan J. Martinez <jjm@usebox.net>

This program is free software under the terms of GPL version 3.
Please check COPYING file for further details.

http://www.usebox.net/jjm/orajeapplet/

