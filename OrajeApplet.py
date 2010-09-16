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
 - urllib

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

import urllib

__version__='0.1 ALPHA'

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

		self.status = None
		self.weather = None
		self.timeout = None

		self.conf_file = None
		self.conf = None
		self.theme = None

		self.applet = applet
		self.applet.setup_menu_from_file (
			None, 'OrajeApplet.xml',
			None, [('Details', self.on_details), 
					('Update', self.on_update),
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
		self.applet.show_all()

		self.update_rss()

		self.timeout = gobject.timeout_add(int(self.conf['update'])*60*1000,
			update_rss_callback, self)

	def update_rss(self):
		"""Update weather data using location and units in user configuration.
		"""

		self._update_rss(self.conf['location'], self.conf['units'])

	def _update_rss(self, w, c):

		try:
			rss = urllib.urlopen(self.YAHOO_API % (w, c))
		except Exception as e:
			logging.error('Error downloading the RSS: %s' % e)
			return

		try:
			self.weather = self.dom_to_weather(minidom.parse(rss))
			logging.debug(self.weather)

			self.set_status(self.theme['conditions'][self.weather['condition']['code']]['status'],
				self.weather['condition']['text'])
		except Exception as e:
			logging.error('Error setting new status: %s' % e)

		rss = None

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
			astronomy = [ 'surise', 'sunset'], 
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
				theme = '%s/lib/OrajeApplet/theme.json' % sys.prefix)
		
		if conf_fd:
			try:
				conf = json.load(conf_fd)
			except Exception as e:
				logging.error('Parsing error in %s: %s' % 
					(conf_file, e))
			conf_fd.close()

		return (conf_file, conf)

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

		if self.weather:
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

	def on_details(self, component, verb):
		logging.debug('Menu on_details')

	def on_update(self, component, verb):
		"""Update the RSS on demand.

		Remove the existing timeout before updating the RSS to avoid
		problems and restore it back after the update.
		"""
		logging.debug('Menu on_update')
		gobject.source_remove(self.timeout)
		self.update_rss()
		self.timeout = gobject.timeout_add(int(self.conf['update'])*60*1000,
			update_rss_callback, self)

	def on_preferences(self, component, verb):
		logging.debug('Menu on_preferences')
		ui = gtk.Builder()
		ui.add_from_file('%s/lib/OrajeApplet/prefs.ui' % sys.prefix)
		dialog = ui.get_object('Preferences')
		dialog.set_title(self.PACKAGE + ' Preferences')

		woeid = ui.get_object('woeid')
		woeid.set_text(self.conf['location'])

		interval = ui.get_object('interval')
		interval.set_value(float(self.conf['update']))

  		units = ui.get_object('units')
		units.append_text('Celsius')
		units.append_text('Farenheit')
		if self.conf['units'] == 'c':
			units.set_active(0)
		else:
			units.set_active(1)

		dialog.show_all()
		dialog.run()
		dialog.destroy()

	def on_about(self, component, verb):
		"""Show an About dialog.

		Use the 'storm' icon from current theme.
		"""
		logging.debug('Menu on_about')

		icon = '%s%s' % (self.theme['base'], self.theme['status']['storm'])

		about = gtk.AboutDialog()
		info = {
			'program-name': self.PACKAGE,
			'version': self.VERSION,
			'logo': gtk.gdk.pixbuf_new_from_file_at_size(icon, 96, 96),
			'comments': 'Another weather applet for Gnome',
			'copyright': u'Copyright © 2010 Juan J. Martínez'
		}
		for i, v in info.items():
			about.set_property(i, v)
		about.set_icon_from_file(icon)
		about.connect('response', lambda self, *args: self.destroy())
		about.show_all()

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
	-w, --window        Launch in a standalong window for testing (debug=on)

This application uses Yahoo! Weather feeds and it's not endorsed or
promoted by Yahoo! in any way.
""" % (OrajeApplet.PACKAGE, sys.argv[0])

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
