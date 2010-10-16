#!/usr/bin/env python
# coding: utf-8
#
# Oraje Applet - Another Weather Applet for Gnome
# Copyright (C) 2010 Juan J. Martinez <jjm@usebox.net>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""Another Weather Applet for Gnome.

This is a Gnome applet to view Yahoo! Weather forecasts.

Oraje Applet requires:

 - gnome python bindings
 - xml.dom (minidom)
 - json (or simplejson)
 - urllib2

Optionally dbus is used to support NetworkManager and notifications.

This application uses Yahoo! Weather feeds and it's not endorsed or
promoted by Yahoo! in any way.

Author: Juan J. Martinez <jjm@usebox.net>
License: GPL3
"""

import pygtk
pygtk.require('2.0')

import gobject
import gtk
import gnomeapplet

import sys
import os
import logging
from getopt import getopt
try:
	import json
except:
	import simplejson as json

try:
	from xml.dom import minidom
except:
	logging.error('mindom is needed to run this application')
	exit(1)

import urllib2
from datetime import datetime
import locale

__version__='0.4'

class OrajeApplet(gnomeapplet.Applet):
	"""Module that implements gnomeapplet.Applet.
	"""

	PACKAGE = 'OrajeApplet'
	VERSION = __version__

	def __init__(self, applet, iid):

		self.YAHOO_API = 'http://xml.weather.yahoo.com/forecastrss?w=%s&u=%s'

		self.image = None
		self.size = None
		self.label = None

		self.sybus = None
		self.sebus = None
		self.notify = None

		self.status = None
		self.weather = None
		self.timeout = None
		self.last_fetch = None
		self.lc_time = locale.getlocale(locale.LC_TIME)

		self.error = True
		self.connection = False
		self.has_dbus = True
		self.has_nm = True

		self.conf_file = None
		self.conf = None
		self.theme = None

		self.prefs = None
		self.about = None
		self.details = None

		self.applet = applet
		self.applet.setup_menu_from_file (
			None, 'OrajeApplet.xml',
			None, [('Details', self.on_details), 
					('Refresh', self.on_refresh),
					('Prefs', self.on_preferences),
					('About', self.on_about)])

		(self.conf_file, self.conf) = self.load_configuration()
		logging.debug(self.conf)

		self.theme = self.load_theme(self.conf['theme'])
		if not self.theme:
			exit(1)

		# setup the size of the applet before loading a image
		self.size = self.applet.get_size()
		self.label = gtk.Label()

		# show something, in case the RSS it's slow
		self.set_status('loading')

		box = gtk.HBox()
		box.add(self.image)
		box.add(self.label)
		self.applet.add(box)
		self.applet.connect('change-size', self.change_size)
		self.applet.connect('change-background', self.change_background)
		self.applet.connect('button-press-event', self.button_press)
		self.applet.show_all()

		# NM support using DBUS
		try:
			import dbus
			from dbus.mainloop.glib import DBusGMainLoop
		except:
			logging.error("DBUS Python support not found, NM disabled")
			self.has_dbus = False
			self.has_nm = False
		else:
			try:
				DBusGMainLoop(set_as_default = True)
				self.sybus = dbus.SystemBus()
				self.init_nm()
			except:
				logging.error("Failed to access SystemBus, NM disabled")
				self.has_nm = False

			try:
				self.sebus = dbus.SessionBus()
				self.notify = dbus.Interface(self.sebus.get_object(
					'org.freedesktop.Notifications',
					'/org/freedesktop/Notifications'),
					'org.freedesktop.Notifications')
				if self.notify is not None:
					logging.debug('Notification support enabled')
			except:
				logging.error("Failed to access SessionBus, notifications disabled")

		if not self.has_nm:
			# assume we're connected, without NM help
			self.connection = True
			self.update_rss()
			self.timeout = gobject.timeout_add(
				int(self.conf['update'])*60*1000,
				update_rss_callback, self)


	def init_nm(self):
		"""Init NetworkManager support.

		We ask NM through DBUS to check if we have network connection.
		We also setup a callback on state changes.
		"""

		logging.debug('Init NM support')

		proxy = self.sybus.get_object(
			'org.freedesktop.NetworkManager', 
			'/org/freedesktop/NetworkManager')

		proxy.connect_to_signal('StateChanged', self.on_nm_state_changed)

		state = proxy.Get(
			'org.freedesktop.NetworkManager', 
			'State',
			dbus_interface="org.freedesktop.DBus.Properties")
		self.on_nm_state_changed(state)
		logging.debug('NM initial state is %d' % state)


	def on_nm_state_changed(self, state):
		"""Callback on NetworkManager state changes.

		The second argument it's a reference to the OrajeApplet, so
		update_rss() method is called to retrieve the RSS.
		"""

		logging.debug('on_nm_state_changed call, state is %d' % state)

		if state == 3:
			self.connected()
		else:
			self.connected(False)


	def connected(self, state = True):
		"""Changes connection state.

		When connected, automatically a rss update is performed.
		"""

		if state == True:
			logging.debug('Connected')

			if not self.connection:
				self.connection = True
				self.update_rss()
				if self.timeout is None:
					self.timeout = gobject.timeout_add(
						int(self.conf['update'])*60*1000,
						update_rss_callback, self)
		else:
			logging.debug('Disconnected')
			if self.connection:
				gobject.source_remove(self.timeout)
				self.timeout = None
				self.connection = False


	def update_rss(self):
		"""Update weather data using location and units in user configuration.
		"""

		self._update_rss(self.conf['location'], self.conf['units'])


	def _update_rss(self, w, c):

		if not self.connection:
			logging.warning('_update_rss called on disconnected state')
			return

		rss = self._get_rss(self.YAHOO_API % (w, c))
		if rss is None:
			self.error = True
			return

		try:
			self.weather = self.dom_to_weather(minidom.parse(rss))
			logging.debug(self.weather)

			self.set_status(self.theme['conditions'][self.weather['condition']['code']]['status'],
				_(self.theme['conditions'][self.weather['condition']['code']]['desc']).title())
		except Exception as e:
			logging.error('Error setting new status: %s' % e)

		rss.close()
		rss = None
		self.error = False


	def _get_rss(self, url):

		if not self.connection:
			return None

		try:
			request = urllib2.Request(url)
			if self.last_fetch:
				request.add_header('If-Modified-Since', self.last_fetch)

			rss = urllib2.urlopen(request)

		except urllib2.HTTPError, error: 
			if error.code == 304:
				logging.debug('RSS not modified, last_fetch: %s' % 
					self.last_fetch)
			else:
				logging.error('HTTP Error downloading the RSS: %s' % error)
			return None
		except urllib2.URLError, error:
			logging.error('Error downloading the RSS: %s' % error)
			return None

		locale.setlocale(locale.LC_TIME, 'en_US')
		self.last_fetch = datetime.utcnow().strftime('%a, %d %b %Y %T GMT')
		locale.setlocale(locale.LC_TIME, self.lc_time)
		return rss

	def _translate_wind(self, angle):

		table = [
			[348.75, 371.25, _('N')],
			[11.25, 33.75, _('NNE')],
			[33.75, 56.25, _('NE')],
			[56.25, 78.75, _('ENE')],
			[78.75, 101.25, _('E')],
			[101.25, 123.75, _('ESE')],
			[123.75, 146.25, _('SE')],
			[146.25, 168.75, _('SSE')],
			[168.75, 191.25, _('S')],
			[191.25, 213.75, _('SSW')],
			[213.75, 236.25, _('SW')],
			[236.25, 258.75, _('WSW')],
			[258.75, 281.25, _('W')],
			[281.25, 303.75, _('WNW')],
			[303.75, 326.25, _('NW')],
			[326.25, 348.75, _('NNW')]
		]

		angle = int(angle)

		# North is a special [348.75, 11.25]
		if angle <= 11.25:
			angle += 260

		for i in table:
			if angle >= i[0] and angle < i[1]:
				return i[2]

		return '?'


	def dom_to_weather(self, dom):
		"""Translates from Yahoo! Weather XML into Oraje weather dict.
		"""

		YWEATHER_NS = 'http://xml.weather.yahoo.com/ns/rss/1.0'
		
		tags = dict(
			location = ['city', 'country'],
			units = [ 'temperature', 'distance', 'pressure',
				'speed' ],
			wind = [ 'chill', 'direction', 'speed' ],
			atmosphere = [ 'humidity', 'visibility', 'pressure'
				,'rising'],
			astronomy = [ 'sunrise', 'sunset'], 
			condition = [ 'text', 'code', 'temp', 'date']
		)

		weather = dict()

		for t in tags.keys():
			element = dom.getElementsByTagNameNS(YWEATHER_NS, t)
			node = dict()
			for n in tags[t]:
				node[n] = element[0].getAttribute(n)
			weather[t] = node

		return weather


	def load_configuration(self):
		"""Loads user's configuration in JSON format.

		The configuration file (OrajeAppletRC.json) will be loaded
		from user's configuration directory determined by one of
		the following methods:

		- XDG_CONFIG_HOME environment variable
		- HOME environment variable followed by /.config/

		If the configuration file isn't found, some defaults will be
		used.
		"""

		if 'XDG_CONFIG_HOME' in os.environ:
			conf_file = os.environ['XDG_CONFIG_HOME']
		else:
			conf_file = '%s/.config/' % os.environ['HOME']

		conf_file += 'OrajeAppletRC.json'
		logging.debug('Configuration file: %s' % conf_file)
		conf = None

		try:
			conf_fd = open(conf_file, 'r')
		except:
			conf_fd = None
			logging.warning('Failed to load %s, using defaults' % conf_file)
			conf = dict(update='15', units = 'c', location = '32997',
				theme = '%s/share/OrajeApplet/theme.json' % sys.prefix,
				notify = False)
		
		if conf_fd:
			try:
				conf = json.load(conf_fd)
			except Exception as e:
				logging.error('Parsing error in %s: %s' % 
					(conf_file, e))
			conf_fd.close()

		# migration for configuration <= 0.2
		if not 'notify' in conf:
			logging.info('Configuration <= 0.2, converted')
			conf['notify'] = False

		return (conf_file, conf)


	def save_configuration(self):
		"""Save current configuration.

		A call to load_configuration it's needed before calling this one.
		"""

		if self.conf_file is None:
			logging.error('Trying to save the conf before loading it first')
			return

		try:
			conf_fd = open(self.conf_file, 'w')
		except:
			conf_fd = None
			logging.warning('Failed to save %s' % conf_file)
			return
		
		if conf_fd:
			try:
				conf = json.dump(self.conf, conf_fd)
			except Exception as e:
				logging.error('Error while saving in %s: %s' % 
					(self.conf_file, e))
			conf_fd.close()
		logging.debug("Configuration saved")


	def load_theme(self, theme_file):
		"""Loads a theme in JSON format.
		"""

		logging.debug("Loading theme: %s" % theme_file)

		try:
			theme_fd = open(theme_file, 'r')
		except:
			# this is fatal
			logging.error('Failed to load theme.json')
			return None
		
		try:
			theme = json.load(theme_fd)
		except Exception as e:
			logging.error('parsing error in theme.json: %s' % e)
			exit(1)
		theme_fd.close()

		return theme


	def set_status(self, status, desc=None, force=False):
		"""Sets the status checking it's supported by current theme.
		"""
	
		logging.debug('Status request: %s', status)

		new = False

		if status in self.theme['status']:
			if status != self.status or force:
				self.status = status
				logging.debug('Status changed')
				new = True
		else:
			logging.error('Unknown status %s, ignored' % status)
			return

		if self.weather is not None:
			temp = ' %s<sup><small>o</small></sup>%c' % (
				self.weather['condition']['temp'],
				self.weather['units']['temperature']
			)
			self.label.set_markup(temp)

			# prettify
			if not desc:
				desc = self.status
			desc = desc.title()

			tip = '%s (%s)\n<b>%s</b>,%s' % (
				self.weather['location']['city'], 
				self.weather['location']['country'],
				desc,
				temp
			)
			self.label.set_tooltip_markup(tip)

			if self.notify is not None and self.conf['notify'] and new:
				logging.debug('Sending a notification of new coditions')

				self.notify.Notify(self.PACKAGE, 0, 
					'file://%s%s' % (self.theme['base'],
						self.theme['status'][self.status]),
					_('New conditions'), tip, '', '', -1)
		else:
			tip = '...'

		prev = None
		if self.image:
			prev = self.image

		if new:
			self.image = self.load_image('%s%s' % 
				(self.theme['base'], self.theme['status'][self.status]),
					self.size, prev)

		self.image.set_tooltip_markup(tip)


	def load_image(self, file, size, prev = None):
		"""Load a image into a gtk.Image.
	
		The provided file must be a squared image. The call must provide
		the desired final image sice. It will replace an existing image
		if provided in prev argument.
		"""

		logging.debug('Loading image: %s' % file)

		if prev:
			image = prev
		else:
			image = gtk.Image()

		try:
			pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(file, size, size)
			image.set_from_pixbuf(pixbuf)
		except Exception as e:
			logging.error('Failed to load %s: %s' % (file, e))

		return image


	def change_size(self, applet, size):
		"""Change the size of the image if the panel size changes.
		"""

		logging.debug('Change size callback')
		self.size = size
		self.set_status(self.status, force=True)


	def change_background(self, applet, type, color, pixmap):
		"""Change applet background to fit planel theme/style.
		"""

		logging.debug('Change background callback')
		applet.set_style(None)
		applet.modify_style(gtk.RcStyle())

		if type == gnomeapplet.COLOR_BACKGROUND:
			applet.modify_bg(gtk.STATE_NORMAL, color)
		elif type == gnomeapplet.PIXMAP_BACKGROUND:
			applet.get_style().bg_pixmap[gtk.STATE_NORMAL] = pixmap


	def button_press(self, button, event):
		"""Left button shows the Details dialog.
		"""

		logging.debug('Button press callback')
		if event.button == 1:
			self.on_details(None, None)


	def on_refresh(self, component, verb):
		"""Refresh the RSS on demand.

		Remove the existing timeout before updating the RSS to avoid
		problems and restore it back after the update.
		"""

		logging.debug('Menu on_update')
		if self.details:
			logging.warning('Details dialog is open, update cancelled')
			return

		if self.connection:
			if self.timeout is not None:
				gobject.source_remove(self.timeout)

			self.update_rss()

			self.timeout = gobject.timeout_add(
				int(self.conf['update'])*60*1000,
				update_rss_callback, self)


	def on_preferences(self, component, verb):
		"""Preferences dialog.

		It updates the configuration on the fly, and saves it on close.
		"""
		if self.prefs:
			return
		self.prefs = True

		logging.debug('Menu on_preferences')
		ui = gtk.Builder()
		ui.set_translation_domain(self.PACKAGE)
		ui.add_from_file('%s/share/OrajeApplet/prefs.ui' % sys.prefix)
		dialog = ui.get_object('Preferences')
		dialog.set_title(self.PACKAGE + ' Preferences')

		woeid = ui.get_object('woeid')
		woeid.set_text(self.conf['location'])

		location = ui.get_object('location')
		if self.error or self.weather is None:
			location.set_markup('')
		else:
			location.set_markup('<small><i>%s (%s)</i></small>' % 
				(self.weather['location']['city'], 
				self.weather['location']['country']))

		woeid.connect('focus-out-event', self.on_woeid_change, location)

		interval = ui.get_object('interval')
		interval.set_value(float(self.conf['update']))
		interval.connect('focus-out-event', self.on_interval_change)

  		units = ui.get_object('units')
		units.append_text(_('Celsius'))
		units.append_text(_('Fahrenheit'))
		if self.conf['units'] == 'c':
			units.set_active(0)
		else:
			units.set_active(1)
		units.connect('changed', self.on_units_change)

		notify = ui.get_object('notify')
		notify.set_active(self.conf['notify'])
		if self.notify is not None:
			notify.connect('toggled', self.on_notify_toggle)
		else:
			notify.set_sensitive(False)

		dialog.show_all()
		dialog.run()
		dialog.destroy()
		logging.debug(self.conf)
		self.save_configuration()
		self.prefs = None


	def on_woeid_change(self, entry, event, label):
		"""Manage WEID change.

		Actually there's no way of looking for a location based on
		its name (city, region, country), so at least make it easy
		for the user to check the provided OID it's valid.

		The WOEID is checked before accepting it.
		"""
		logging.debug('Preferences, on_woeid_change')
		woeid = entry.get_text()
		if woeid != self.conf['location'] and self.connection:
			logging.debug('woeid changed, checking')
			label.set_markup(_('<small><i>Checking...</i></small>'))

			rss = self._get_rss(self.YAHOO_API % (woeid, self.conf['units']))
			if rss is None:
				logging.warning('Failed to get the RSS, woeid %s' % woeid)
				label.set_markup(_('<small><b>Error retrieving location</b></small>'))
				return

			try:
				weather = self.dom_to_weather(minidom.parse(rss))
			except:
				logging.warning('Failed to parse the RSS, woeid %s' % woeid)
				label.set_markup(_('<small><b>Error processing the location</b></small>'))
				return

			label.set_markup('<small><i>%s (%s)</i></small>' % 
				(weather['location']['city'], 
				weather['location']['country']))

			self.weather = weather
			self.conf['location'] = woeid
			self.set_status(self.theme['conditions'][self.weather['condition']['code']]['status'],
				_(self.theme['conditions'][self.weather['condition']['code']]['desc']).title())
		elif self.weather is not None:
			# in case there was a previous error, don't confuse
			# the user if he puts the old WOID back
			label.set_markup('<small><i>%s (%s)</i></small>' % 
				(self.weather['location']['city'], 
				self.weather['location']['country']))


	def on_interval_change(self, spin, event):
		"""Manage update interval change.
		"""

		logging.debug('Preferences, on_interval_change')
		interval = spin.get_text()
		if interval != self.conf['update']:
			logging.debug('interval changed')
			self.conf['update'] = interval
			if self.connection:
				if self.timeout is not None:
					gobject.source_remove(self.timeout)
				self.timeout = gobject.timeout_add(
					int(self.conf['update'])*60*1000, 
					update_rss_callback, self)


	def on_units_change(self, combo):
		"""Manage units change.

		Yahoo! Weather uses metric units when Celsius data is requested,
		so we only have to deal with Celsius and Fahrenheit.

		FIXME: use Fahrenheit and make the conversion internally.
		"""

		logging.debug('Preferences, on_units_change')
		text = combo.get_active_text()
		# FIXME: we shouldn't check the text
		if text == _('Celsius'):
			units = 'c'
		else:
			units = 'f'
		if units != self.conf['units']:
			logging.debug('units changed')
			self.conf['units'] = units
			# FIXME: not needed if we were using one type of unit
			# internally and converting it before showing it to the user
			if self.connection:
				self.update_rss()


	def on_notify_toggle(self, togglebutton):
		"""Manage notify change.
		"""

		logging.debug('Preferences, on_notify_change')
		self.conf['notify'] = togglebutton.get_active()


	def on_about(self, component, verb):
		"""Show an About dialog.
		"""

		if self.about:
			return
		self.about = True

		logging.debug('Menu on_about')

		icon = '%s/share/icons/OrajeApplet.svg' % sys.prefix

		about = gtk.AboutDialog()
		info = {
			'program-name': self.PACKAGE,
			'version': self.VERSION,
			'logo': gtk.gdk.pixbuf_new_from_file_at_size(icon, 96, 96),
			'comments': _('Another weather applet for Gnome'),
			'copyright': 
				u'Copyright © 2010 Juan J. Martínez <jjm@usebox.net>',
			'website': 'http://www.usebox.net/jjm/orajeapplet/'
		}
		for i, v in info.items():
			about.set_property(i, v)
		about.connect('response', lambda self, *args: self.destroy())
		about.set_icon_name('help-about')
		about.show_all()
		about.run()
		about.destroy()
		self.about = None

	def _set_details(self, ui):

		logging.debug('Setting details')

		image = ui.get_object('image')
		self.load_image('%s%s' % 
			(self.theme['base'], self.theme['status'][self.status]),
				96, image)

		if self.weather is None:
			logging.warning('no weather info available')
			return

		conditions = ui.get_object('conditions')
		conditions.set_markup(_(self.theme['conditions'][self.weather['condition']['code']]['desc']).title())
		temperature = ui.get_object('temperature')
		temperature.set_markup('<big><b>%s<sup><small>o</small></sup>%c</b></big>' % (
				self.weather['condition']['temp'],
				self.weather['units']['temperature']))

		location = ui.get_object('location')
		location.set_text('%s (%s)' % 
				(self.weather['location']['city'], 
				self.weather['location']['country']))

		date = ui.get_object('date')
		datestr = self.weather['condition']['date']
		locale.setlocale(locale.LC_TIME, 'en_US')
		datestr = datetime.strptime(datestr, '%a, %d %b %Y %I:%M %p %Z')
		locale.setlocale(locale.LC_TIME, self.lc_time)
		datestr = datetime.strftime(datestr, '%a %d %b, %H:%M')
		date.set_text(datestr)

		chill = ui.get_object('chill')
		chill.set_markup('%s<sup><small>o</small></sup>%c' % (
			self.weather['wind']['chill'],
			self.weather['units']['temperature']))

		pressure = ui.get_object('pressure')
		pressure.set_text('%s %s' % (
			self.weather['atmosphere']['pressure'],
			self.weather['units']['pressure']))

		humidity = ui.get_object('humidity')
		humidity.set_text('%s%%' % self.weather['atmosphere']['humidity'])

		visibility = ui.get_object('visibility')
		visibility.set_text('%s %s' % (
			self.weather['atmosphere']['visibility'],
			self.weather['units']['distance']))

		direction = self.weather['wind']['direction']
		direction = self._translate_wind(direction)

		wind = ui.get_object('wind')
		wind.set_text('%s %s %s' % (
			direction,
			self.weather['wind']['speed'],
			self.weather['units']['speed']))

		sunrise = ui.get_object('sunrise')
		sunrise.set_text(self.weather['astronomy']['sunrise'])

		sunset = ui.get_object('sunset')
		sunset.set_text(self.weather['astronomy']['sunset'])

	def on_details(self, component, verb):
		"""Details dialog.
		"""

		if self.details:
			return
		self.details = True

		logging.debug('Menu on_details')
		ui = gtk.Builder()
		ui.set_translation_domain(self.PACKAGE)
		ui.add_from_file('%s/share/OrajeApplet/details.ui' % sys.prefix)
		dialog = ui.get_object('Details')
		dialog.set_title('%s %s' % (self.PACKAGE, _('Details')))

		self._set_details(ui)

		update = ui.get_object('update')
		update.connect('clicked', self.on_details_update, ui, dialog)

		icon = '%s/share/icons/OrajeApplet.svg' % sys.prefix
		dialog.set_icon_from_file(icon)

		dialog.show_all()
		while True:
			if dialog.run() != 1:
				break
		dialog.destroy()
		self.details = None

	def on_details_update(self, button, ui, dialog):
		"""Update the forecast on Details dialog.
		"""
		logging.debug('on_details_update')
		if self.connection:
			if self.timeout is not None:
				gobject.source_remove(self.timeout)
				self.timeout = None
			self.update_rss()
			self.timeout = gobject.timeout_add(
				int(self.conf['update'])*60*1000,
				update_rss_callback, self)
		self._set_details(ui)
		dialog.response(1)


def OrajeFactory(applet, iid):
	"""Function to register OrajeApplet class.
	"""

	logging.debug('Starting OrajeApplet instance: %s %s' % (applet,iid))
	OrajeApplet(applet, iid)
	return True


def update_rss_callback(data):
	"""Function to be executed periodically.

	The argument it's a reference to the OrajeApplet, so update_rss()
	method is called to retrieve the RSS.
	"""

	logging.debug('Inside the callback')
	data.update_rss()
	logging.debug('Leaving the callback, see you later')
	return True


def usage():
	"""Show the help screen.
	"""

	print """%s
Usage: %s [OPTIONS]

OPTIONS:
	-h, --help          This help screen
	-v, --version       Show version and exit
	-d, --debug         Enable debug output
	-w, --window        Launch in a standalone window for testing (debug=on)

This application uses Yahoo! Weather feeds and it's not endorsed or
promoted by Yahoo! in any way.
""" % (OrajeApplet.PACKAGE, sys.argv[0])

import gettext
gettext.install(OrajeApplet.PACKAGE, unicode=1)
locale.textdomain(OrajeApplet.PACKAGE)

if __name__ == '__main__':
	gobject.type_register(OrajeApplet)

	logging.getLogger().setLevel(logging.ERROR)

	try:
		(opts, args) = getopt(sys.argv[1:], 'hvdw', 
			['help', 'version', 'debug', 'window'])
	except Exception as e:
		opts = []
		args = sys.argv[1:]

	for op, ar in opts:
		if op in ('-h', '--help'):
			usage()
			exit(0)
		elif op in ('-v', '--version'):
			print OrajeApplet.VERSION
			exit(0)
		elif op in ('-d', '--debug'):
			logging.getLogger().setLevel(logging.DEBUG)
			logging.debug('Running in debug mode')
		elif op in ('-w', '--window'):
			logging.getLogger().setLevel(logging.DEBUG)
			logging.debug('Running in standalone window')

			import gnome
			gnome.init(OrajeApplet.PACKAGE, OrajeApplet.VERSION)

			app = gtk.Window(gtk.WINDOW_TOPLEVEL)
			app.set_title(OrajeApplet.PACKAGE)
			app.connect('destroy', gtk.main_quit)
			app.set_property('resizable', False)

			applet = gnomeapplet.Applet()
			OrajeFactory(applet, None)
			applet.reparent(app)

			app.show_all()
			gtk.main()
			exit(0)

	gnomeapplet.bonobo_factory(
		'OAFIID:Oraje_Applet_Factory',
		OrajeApplet.__gtype__,
		OrajeApplet.PACKAGE,
		OrajeApplet.VERSION,
		OrajeFactory)

# EOF
