Apteligent importer
===================

Apteligent importer is a set of python scripts to poll the Apteligent REST API for data and send it to any
datastore that accepts one of the graphite protocols. This includes python-carbon, go-carbon, influxdb
and prometheus, but it was only thoroughly tested on python-carbon. Using this project requires you to setup
a datastore first. For development it is possible to use the 'dummy' protocol which writes data to the logs.

Development environment
-----------------------

I recommend the use of a python virtual environment for development. Both python 2.7 and 3.5 are supported.
To set up a python 2.7 dev environment on mac, do the following:

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
    | ``mv conf/apteligent-importer/* ~/.apteligent-importer``
7. Adapt the configuration to your liking.
8. Run any of the installed scripts.

Now cached files and logs will end up in /tmp.

Production environment
----------------------
There is no clear cut way how to set up an production environment. At eCG NOC we build debian packages with
``dh-virtualenv`` and handle configuration with puppet. You will need an ubuntu or debian build host to create the
packages. If all build dependencies of ``dh-virtualenv`` and python are met, building is easy:

1. Check if all build dependencies are met.
   ``dpkg-checkbuilddeps``
2. Install any missing build dependencies.
3. Add a changelog entry in debian/changelog manually or use ``dch`` from the _devscripts_ package.
4. Build an unsigned binary package:
    ``dpkg-buildpackage -us -uc -b``

In production the following directories are expected to be present and accessible to the user running the scripts

    =============  ========================  ====================
       Function            Directory         Environment Variable
    =============  ========================  ====================
    Configuration  ``/etc/<project>``        `CONFIG_DIR`
    Cache          ``/var/cache/<project>``  `CACHE_DIR`
    Logs           ``/var/log/<project>``    `LOG_DIR`
    =============  ========================  ====================

Where ``<project>`` is either *apteligent-importer* or set by the -p switch for each script. Each directory can be
overridden individually with an enviroment variable.

It is recommended to run the scripts under a service manager like supervisord or monit.

Scripts
-------

The import of Apteligent data is performed by four different scripts.

**dailyjobs.py**
    This script imports daily stats from Apteligent into graphite. Because the configured timezone determines
    when counters are reset, this script depends on the app_timezone.json config file. Commandline arguments::

        usage: dailyjobs.py [-h] [-p PROJECT] [-q]

        optional arguments:
         -h, --help            show this help message and exit
         -p PROJECT, --project PROJECT
                               Project name
         -q, --quiet           Suppress debug level log messages

**livestats.py**
    This script imports the apteligent livestats into graphite. This API is currently (november 2015) still in
    beta. All data is updated every 10 seconds, requiring this script to use a Thread pool to handle requests in
    parallel. Commandline arguments::

        usage: livestats.py [-h] [-p PROJECT] [-q] [-i INTERVAL]

        Script to import the apteligent livestats out of the current beta API every
        few minutes. Results are returned in 10 second buckets.

        optional arguments:
          -h, --help            show this help message and exit
          -p PROJECT, --project PROJECT
                                Project name
          -q, --quiet           Suppress debug level log messages
          -i INTERVAL, --interval INTERVAL
                                Polling interval in minutes from 1 upto 5.
**groupedby.py**
    This script imports totals for each app grouped by version string and by carrier. Because it is a running
    total you need a graphite function like nonNegativeDerivative() or perSecond() to convert the graph to a rate.
    Commandline arguments::

        usage: groupedby.py [-h] [-p PROJECT] [-q]

        Script to retreive grouped mobile app data from the Crittercism REST API and
        store it into graphite.

        optional arguments:
          -h, --help            show this help message and exit
          -p PROJECT, --project PROJECT
                                Project name
          -q, --quiet           Suppress debug level log messages

**servicestats.py**
    This script imports performance data of web services used by the apps from Apteligent. Please keep the
    services.whitelist file up to date. A whitelist is required because Apteligent regards things like WIFI
    hotspots as services. Commandline arguments::

        usage: servicestats.py [-h] [-p PROJECT] [-q]

        Import the web service performance stats from apteligent REST API into
        graphite.

        optional arguments:
          -h, --help            show this help message and exit
          -p PROJECT, --project PROJECT
                                Project name
          -q, --quiet           Suppress debug level log messages

Configuration files
-------------------

The following configuration files are required. You can find examples in ``conf/``.

**app.blacklist**
    Contains a list of Apteligent AppID's to block
**app_timezones.json**
    Every Apteligent has a timezone configured which determines the moment counters are reset.  Like Apteligent we use GMT offsets
**carrier.map**
    Structured file containing regexes for strings identifying mobile carriers in different countries.
**apteligent.json**
    Apteligent account details including credentials, clientID and API hostname.
**graphite.json**
    The connection to the carbon relay daemon is setup here. Use the 'dummy' protocol for testing.
**services.whitelist**
    Contains a list of web services we want to track through the crittercism API.
