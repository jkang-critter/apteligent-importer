# NOC graphite scripts

TBD

## Development environment

TBD

## Production environment

TBD

## Packaging

TBD

## Scripts

The following scripts are located in scripts/:

* _dailyjobs.py_:
    This script imports daily stats from Crittercism into graphite. Because the configured timezone determines
    when counters are reset, this script depends on the app_timezone.json config file.
* _livestats.py_:
    This script imports the crittercism livestats into graphite. This API is currently (november 2015) still in
    beta. All data is updated every 10 seconds, requiring this script to use a Thread pool to handle requests in
    parallel.
* _groupedby.py_:
    This script imports totals for each app grouped by version string and by carrier. Because it is a running
    total you need a graphite function like nonNegativeDerivative() or perSecond() to convert the graph to a rate.
* _fillbacklog.py_:
    Do not run this without editing it first. It is used to backfill data from daily stats.
* _servicestats.py_:
    This script imports performance data of web services used by the apps from Crittercism. Please keep the
    services.whitelist file up to date. A whitelist is required because Crittercism regards things like WIFI
    hotspots as services.
