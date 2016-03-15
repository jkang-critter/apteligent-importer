#!/usr/bin/env python
'''
Script to retreive grouped mobile app data from the Crittercism REST API and
store it into graphite.
'''
import time
from argparse import ArgumentParser

from libecgnoc import (logger,
                       jsonstore,
                       schedule)

from libecgnoc.groupmap import groupmap

import apteligent
import tographite


def groupedby_carrier(app_countries, carriers_per_country,
                      metric_root, at, gp):
    """
    For all the tracked apps get the Crittercism metrics per version of the app
    """

    metrics = ['crashes', 'crashPercent', 'appLoads']

    apps = at.get_apps()
    appids = apps.keys()
    # If we want to stop tracking a certain metric remove it below.
    for metric in metrics:
        for appid in appids:
            appName = apps[appid]['appName']
            try:
                country = app_countries[appid][2]
            except LookupError:
                log.exception('No timezone or country configuration for app.'
                              'appName: %s appid: %s', appName, appid)
                continue

            timestamp = time.time()
            prefix = [metric_root, appName, 'groupedby', 'carrier']
            stats = at.errorMonitoringPie(appid=appid, metric=metric,
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


def groupedby_appversion(metric_root, at, gp):
    """
    For all the tracked apps get the Crittercism metrics per version of the app
    """

    # If we want to stop tracking a certain metric remove it below.
    metrics = ['dau', 'appLoads', 'crashes', 'crashPercent',
               'affectedUsers', 'affectedUserPercent']

    apps = at.get_apps()
    appids = apps.keys()

    for metric in metrics:
        for appid in appids:
            appName = apps[appid]['appName']
            timestamp = time.time()
            prefix = [metric_root, appName, 'groupedby', 'appversion']
            stats = at.errorMonitoringPie(appid=appid, metric=metric,
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


def main(project):

    config = jsonstore.config(project)

    apteligentconf = config('apteligent')
    graphiteconf = config('graphite')
    app_countries = config('app_timezones').data
    carriers_per_country = groupmap(project, 'carrier')

    try:
        metric_root = apteligentconf.data.pop('metric_root')
        at = apteligent.restapi.Client(project, **apteligentconf.data)
        gp = tographite.CarbonSink(**graphiteconf.data)
    except TypeError:
        log.exception('The json configuration files contains an improper key.')
        raise

    # Important: the ClockBasedScheduler spawns threads, so Events can
    # run in parallel
    sched = schedule.ClockBasedScheduler()
    event = schedule.Event

    # Pull in stats grouped by app version every 10 minutes
    vargs = [metric_root, at, gp]
    sched.addevent(event('*',  0, groupedby_appversion, *vargs))
    sched.addevent(event('*', 10, groupedby_appversion, *vargs))
    sched.addevent(event('*', 20, groupedby_appversion, *vargs))
    sched.addevent(event('*', 30, groupedby_appversion, *vargs))
    sched.addevent(event('*', 40, groupedby_appversion, *vargs))
    sched.addevent(event('*', 50, groupedby_appversion, *vargs))

    # Pull in stats grouped by carrier every 10 minutes starting from 2
    # past the whole hour
    cargs = [app_countries, carriers_per_country, metric_root, at, gp]
    sched.addevent(event('*',  2, groupedby_carrier, *cargs))
    sched.addevent(event('*', 12, groupedby_carrier, *cargs))
    sched.addevent(event('*', 22, groupedby_carrier, *cargs))
    sched.addevent(event('*', 32, groupedby_carrier, *cargs))
    sched.addevent(event('*', 42, groupedby_carrier, *cargs))
    sched.addevent(event('*', 52, groupedby_carrier, *cargs))

    sched.run()


if __name__ == "__main__":

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-p", "--project", dest="project",
                        default="apteligent-importer",
                        help="Project name")
    parser.add_argument("-q", "--quiet", action="store_false",
                        dest="verbose", default=True,
                        help="Suppress debug level log messages")
    args = parser.parse_args()

    log = logger.setup(args.project, __file__, debug=args.verbose)

    main(args.project)
