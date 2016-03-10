#!/usr/bin/env python
'''
Script to retreive grouped mobile app data from the Crittercism REST API and
store it into graphite.
'''
import time
from argparse import ArgumentParser

from apteligentimporter import (setuplogger,
                                Config,
                                apteligent,
                                graphite,
                                schedule,
                                groupmap)

metric_root = None
quit = False

app_countries = None
carriers_per_country = None


def groupedby_carrier(cc, gp):
    """
    For all the tracked apps get the Crittercism metrics per version of the app
    """

    metrics = ['crashes', 'crashPercent', 'appLoads']

    global metric_root  # Use the global variable metric_root
    global quit  # Only way to catch a KeyboardInterrupt in a threaded app.
    if quit:
        raise KeyboardInterrupt
    apps = cc.get_apps()
    appids = apps.keys()
    # If we want to stop tracking a certain metric remove it below.
    for metric in metrics:
        for appid in appids:
            if quit:
                raise KeyboardInterrupt
            appName = apps[appid]['appName']
            try:
                country = app_countries[appid][2]
            except LookupError:
                log.exception('No timezone or country configuration for app.'
                              'appName: %s appid: %s', appName, appid)
                continue

            timestamp = time.time()
            prefix = [metric_root, appName, 'groupedby', 'carrier']
            stats = cc.errorMonitoringPie(appid=appid, metric=metric,
                                          groupby='carrier')
            try:
                slices = stats['data']['slices']
                aggregator = dict()
                for sl in slices:
                    blurb = sl['label']
                    group = carriers_per_country[country].findgroup(blurb)
                    value = sl['value']
                    aggregator[group] = aggregator.get(group, 0) + value

                for group, value in aggregator.iteritems():
                    path = prefix + [group, metric]
                    gp.submit(path, value, timestamp)

            except LookupError:
                log.error('No data for metric: %s app: %s',
                          metric, appName, exc_info=True)

    gp.flush_buffer()


def groupedby_appversion(cc, gp):
    """
    For all the tracked apps get the Crittercism metrics per version of the app
    """

    metrics = ['dau', 'appLoads', 'crashes', 'crashPercent',
               'affectedUsers', 'affectedUserPercent']

    global metric_root  # Use the global variable metric_root
    global quit  # Only way to catch a KeyboardInterrupt in a threaded app.
    if quit:
        raise KeyboardInterrupt
    apps = cc.get_apps()
    appids = apps.keys()
    # If we want to stop tracking a certain metric remove it below.
    for metric in metrics:
        for appid in appids:
            if quit:
                raise KeyboardInterrupt
            appName = apps[appid]['appName']
            timestamp = time.time()
            prefix = [metric_root, appName, 'groupedby', 'appversion']
            stats = cc.errorMonitoringPie(appid=appid, metric=metric,
                                          groupby='appVersion')
            try:
                slices = stats['data']['slices']
                for sl in slices:
                    group = sl['label']
                    value = sl['value']
                    path = prefix + [group, metric]
                    gp.submit(path, value, timestamp)

            except LookupError:
                log.error('No data for metric: %s app: %s',
                          metric, appName, exc_info=True)

    gp.flush_buffer()


def main():

    apteligentconf = Config('apteligent')
    graphiteconf = Config('graphite')

    global metric_root
    global app_countries
    global carriers_per_country

    app_countries = Config('app_timezones').data
    carriers_per_country = groupmap.Groupmap('carrier')

    try:
        metric_root = apteligentconf.data.pop('metric_root')
        cc = apteligent.REST_API(**apteligentconf.data)
        gp = graphite.CarbonSink(**graphiteconf.data)
    except TypeError:
        log.exception('The json configuration files contains an improper key.')
        raise

    # Important: the ClockBasedScheduler spawns threads, so Events can
    # run in parallel
    sched = schedule.ClockBasedScheduler()
    event = schedule.Event

    # Pull in stats grouped by app version every 10 minutes
    sched.addevent(event('*',  0, groupedby_appversion, cc, gp))
    sched.addevent(event('*', 10, groupedby_appversion, cc, gp))
    sched.addevent(event('*', 20, groupedby_appversion, cc, gp))
    sched.addevent(event('*', 30, groupedby_appversion, cc, gp))
    sched.addevent(event('*', 40, groupedby_appversion, cc, gp))
    sched.addevent(event('*', 50, groupedby_appversion, cc, gp))

    # Pull in stats grouped by carrier every 10 minutes starting from 2
    # past the whole hour
    sched.addevent(event('*',  2, groupedby_carrier, cc, gp))
    sched.addevent(event('*', 12, groupedby_carrier, cc, gp))
    sched.addevent(event('*', 22, groupedby_carrier, cc, gp))
    sched.addevent(event('*', 32, groupedby_carrier, cc, gp))
    sched.addevent(event('*', 42, groupedby_carrier, cc, gp))
    sched.addevent(event('*', 52, groupedby_carrier, cc, gp))

    sched.run()


if __name__ == "__main__":

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-q", "--quiet", action="store_false",
                        dest="verbose", default=True,
                        help="Suppress debug level log messages")
    args = parser.parse_args()

    log = setuplogger(__file__, debug=args.verbose)

    try:
        main()
    except KeyboardInterrupt:
        quit = True
        raise
