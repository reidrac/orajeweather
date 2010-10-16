from distutils.core import setup
from distutils import cmd
from distutils.command.build import build as _build
from distutils.command.install_data import install_data as _install_data

try:
	import sysconfig
	_lib = sysconfig.get_path('stdlib').split('/')[2]
except:
	import platform
	if platform.architecture()[0] == '64bits':
		_lib = 'lib64'
	else:
		_lib = 'lib'

__version__ = '0.5'

import os
try:
	import msgfmt
except:
	print "msgfmt Python module is required to build this application"
	exit(1)

class build(_build):
	def run(self):
		for path, names, filenames in os.walk('./po'):
			for f in filenames:
				if f.endswith('.po'):
					lang = f[:-3]
					src = os.path.join(path, f)
					dest_path = os.path.join('build', 'locale',
						lang, 'LC_MESSAGES')
					dest = os.path.join(dest_path, 'OrajeApplet.mo')
					if not os.path.exists(dest_path):
						os.makedirs(dest_path)
					print 'Compiling %s' % src
					msgfmt.make(src, dest)

		print 'Setup theme.json for %s' % _lib
		theme_fd = open('theme.json', 'r')
		theme = theme_fd.read()
		theme_fd.close()

		theme = theme.replace('/lib/', '/%s/' % _lib)
		theme_fd = open('build/theme.json', 'w')
		theme_fd.write(theme)
		theme_fd.close()

		_build.run(self)

class install_data(_install_data):
	def run(self):
		for lang in os.listdir('build/locale/'):
			lang_dir = os.path.join('share', 'locale',
				lang, 'LC_MESSAGES')
			lang_file = os.path.join('build', 'locale',
				lang, 'LC_MESSAGES', 'OrajeApplet.mo')
			self.data_files.append((lang_dir, [lang_file]))

		self.data_files.append(('%s/OrajeApplet/' % _lib,
			['build/theme.json']))

		_install_data.run(self)

setup(name='OrajeApplet',
	version=__version__,
	description='Weather Applet for Gnome',
	author='Juan J. Martinez',
	author_email='jjm@usebox.net',
	url='http://www.usebox.net/jjm/orajeapplet/',
	license='http://www.gnu.org/licenses/gpl-3.0.html',
	cmdclass={ 'build': build, 'install_data': install_data },
	scripts=['OrajeApplet.py'],
	data_files=[('%s/bonobo/servers/' % _lib, ['OrajeApplet.server']),
		('share/gnome-2.0/ui/', ['OrajeApplet.xml']),
		('%s/OrajeApplet/' % _lib,
			['ui/prefs.ui', 'ui/details.ui',
			'icons/loading-icon.svg',
			'icons/weather-clear-night.svg',
			'icons/weather-clear.svg',
			'icons/weather-few-clouds-night.svg',
			'icons/weather-few-clouds.svg',
			'icons/weather-fog.svg',
			'icons/weather-overcast.svg',
			'icons/weather-severe-alert.svg',
			'icons/weather-showers-scattered.svg',
			'icons/weather-showers.svg',
			'icons/weather-snow.svg',
			'icons/weather-storm.svg',
			]),
		('share/icons/', ['OrajeApplet.svg']),
		('share/doc/OrajeApplet-%s' % __version__,
			['README.md', 'CHANGES', 'COPYING'])],
	)

