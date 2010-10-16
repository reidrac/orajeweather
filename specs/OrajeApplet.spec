%{!?python_sitelib: %define python_sitelib %(%{__python} -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

%global basever 0.4

Name:		OrajeApplet
Version:	%{basever}
Release:	1%{?dist}
Summary:	A Gnome applet to view Yahoo! Weather forecasts
Group:		User Interface/Desktops
License:	GPLv2+
URL:		http://www.usebox.net/jjm/orajeapplet/
Source0:	http://www.usebox.net/jjm/orajeapplet/SOURCES/oraje-applet-%{basever}.tar.gz
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)

Requires:	python >= 2.6
Requires:	dbus-python >= 0.83.0
Requires:	pygtk2 >= 2.16.0
Requires:	gnome-python2
Requires:	gnome-python2-applet
BuildRequires:	python
BuildArch:	noarch

%description
Oraje Applet is a Gnome applet to view Yahoo! Weather forecasts.


%prep
%setup -q -n oraje-applet-%{basever}


%build
%{__python} setup.py build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install --prefix %{_prefix} -O1 --skip-build --root %{buildroot}
%find_lang %{name}

%clean
rm -rf %{buildroot}

%files -f %{name}.lang
%defattr(-,root,root,-)
%{python_sitelib}/%{name}-*.egg-info
%{_bindir}/%{name}.py
%{_datadir}/doc/%{name}-%{basever}
%{_datadir}/icons/%{name}.svg
%{_datadir}/gnome-2.0/ui/%{name}.xml
%{_libdir}/bonobo/servers/%{name}.server
%{_libdir}/%{name}


%changelog
* Sat Oct 16 2010 Juan J. Martinez <jjm@usebox.net> 0.4-1
- initial package build

