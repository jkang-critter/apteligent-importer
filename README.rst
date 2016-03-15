Apteligent importer
===================

Apteligent importer is a set of python scripts to poll the Apteligent REST API for data and send it to any
datastore that accepts one of the graphite protocols. This includes python-carbon, go-carbon, influxdb
and prometheus, but it was only thoroughly tested on python-carbon. Using this project requires you to setup
a datastore first. For development it is possible to use the 'dummy' protocol which writes data to the logs.

Development environment
-----------------------

I recommend the use of a python virtual environment for development. The scripts are only tested on Python 2.7
but a port to python3 compatible code is in the works. To set up a dev environment on mac, do the following:

0. Unpack tar or git clone this project. cd into its directory
1. Install the latest python 2.7 with homebrew.
    ``brew install python``
2. Install latest virtualenv with pip.
    ``pip install virtualenv``
3. Create virtualenv inside source directory.
    ``virtualenv venv``
4. Activate virtualenv.
    ``source venv/bin/activate``
5. Install all the packages as editable into this environment.
    ``pip install -e .``
6. Create a hidden directory named after the project in you home directory and move all examples configuration.
    | ``mkdir ~/.apteligent-importer``
    | ``mv etc/apteligent-importer/* ~/.apteligent-importer``
7. Adapt the configuration to your liking.
8. Run any of the installed scripts.

Now cached files and logs will end up in /tmp.

Production environment
----------------------
There is no clear cut way how to set up an production environment. At eCG NOC we build debian packages with
`dh-virtualenv` and handle configuration with puppet. You will need an ubuntu or debian build host to create the
packages. If all build dependencies of `dh-virtualenv` and python are met, building is easy:

1. Check if all build dependencies are met.
   ``dpkg-checkbuilddeps``
2. Add a changelog entry in debian/changelog manually or use ``dch`` from the _devscripts_ package.
3. Build an unsigned package:
    ``dpkg-buildpackage -us -uc``

In production the following directories are expected to be present and accessible to the user running the scripts

    =============  ========================  ====================
    Function       Directory                 Environment Variable
    =============  ========================  ====================
    Configuration  ``/etc/<project>``        `CONFIG_DIR`
    Cache          ``/var/cache/<project>``  `CACHE_DIR`
    Logs           ``/var/log/<project>``    `LOG_DIR`
    =============  ========================  ====================

Where <project> is either *apteligent-importer* or set by the -p switch for each script. Each directory can be
overridden individually with an enviroment variable.

It is recommended to run the scripts under a service manager like supervisord or monit.

Scripts
-------

The following scripts are included.

* dailyjobs.py:
    This script imports daily stats from Apteligent into graphite. Because the configured timezone determines
    when counters are reset, this script depends on the app_timezone.json config file.
* livestats.py:
    This script imports the apteligent livestats into graphite. This API is currently (november 2015) still in
    beta. All data is updated every 10 seconds, requiring this script to use a Thread pool to handle requests in
    parallel.
* groupedby.py:
    This script imports totals for each app grouped by version string and by carrier. Because it is a running
    total you need a graphite function like nonNegativeDerivative() or perSecond() to convert the graph to a rate.
* servicestats.py:
    This script imports performance data of web services used by the apps from Apteligent. Please keep the
    services.whitelist file up to date. A whitelist is required because Apteligent regards things like WIFI
    hotspots as services.

Configuration files
-------------------

* app.blacklist:
    Contains a list of Crittercism AppID's to block
* app_timezones.json:
    Every Crittercism has a timezone configured which determines the moment counters are reset.  Like Crittercism we use GMT offsets
* carrier.map:
    Structured file containing regexes for strings identifying mobile carriers in different countries.
* apteligent.json:
    Apteligent account details including credentials, clientID and API hostname.
* graphite.json:
    The connection to the carbon relay daemon is setup here. Use the 'dummy' protocol for testing.
* pingdom.json:
    Credentials for the Pingdom API are configured here. They can be found in the shared keepass file under external > 'Pingdom api account'
* services.whitelist:
    Contains a list of web services we want to track through the crittercism API.
