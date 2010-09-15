from distutils.core import setup
from OrajeApplet import __version__

setup(name='OrajeApplet',
	version=__version__,
	description='Weather Applet for Gnome',
	author='Juan J. Martinez',
	author_email='jjm@usebox.net',
	url='http://github.com/reidrac/orajeweather',
	license='http://www.gnu.org/licenses/gpl-3.0.html',
	scripts=['OrajeApplet.py'],
	data_files=[('lib/bonobo/servers/', ['OrajeApplet.server']),
		('share/gnome-2.0/ui/', ['OrajeApplet.xml']),
		('lib/OrajeApplet/', ['theme.json']),
		('share/doc/OrajeApplet/', ['README.md', 'CHANGES', 'COPYING'])],
	)

