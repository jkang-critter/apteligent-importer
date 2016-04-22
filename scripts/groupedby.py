#!/usr/bin/env python
'''
Script to retreive grouped mobile app data from the Crittercism REST API and
store it into graphite.
'''
from __future__ import unicode_literals
from builtins import object
import time
from argparse import ArgumentParser

from libecgnoc import (logger,
                       jsonstore,
                       schedule)

from libecgnoc.groupmap import groupmap

import apteligent
import tographite

# If you want to stop tracking a certain metric remove it below.
APPVERSION_TRACKED_METRICS = [
        'dau',
        'appLoads',
        'crashes',
        'crashPercent',
        'affectedUsers',
        'affectedUserPercent'
        ]

CARRIER_TRACKED_METRICS = [
        'crashes',
        'crashPercent',
        'appLoads'
        ]


class BatchJob(object):



    def __init__(self, metric_root, at, gp, countries, carriers):
        self.metric_root = metric_root
        self.at = at
        self.gp = gp
        self.countries = countries
        self.carriers = carriers

    def carrier(self):
        """
        For all the tracked apps get the Crittercism metrics per carrier
        """


        apps = self.at.get_apps()
        appids = list(apps.keys())
        # If we want to stop tracking a certain metric remove it below.
        for metric in CARRIER_TRACKED_METRICS:
            for appid in appids:
                appName = apps[appid]['appName']
                try:
                    country = self.countries[appid][2]
                except LookupError:
                    log.exception('No timezone or country configuration.'
                                  'appName: %s appid: %s', appName, appid)
                    continue

                timestamp = time.time()
                prefix = [self.metric_root, appName, 'groupedby', 'carrier']
                stats = self.at.errorMonitoringPie(
                    appid=appid, metric=metric, groupby='carrier')
                try:
                    slices = stats['data']['slices']
                    aggregator = dict()
                    for sl in slices:
                        blurb = sl['label']
                        group = self.carriers[country].findgroup(blurb)
                        value = sl['value']
                        aggregator[group] = aggregator.get(group, 0) + value

                    for group, value in aggregator.items():
                        path = prefix + [group, metric]
                        self.gp.submit(path, value, timestamp)

                except LookupError:
                    log.error('No data for metric: %s app: %s',
                              metric, appName, exc_info=True)

        self.gp.flush()

    def appversion(self):
        """
        For all the tracked apps get the Crittercism metrics per version
        """

        apps = self.at.get_apps()
        appids = list(apps.keys())

        for metric in APPVERSION_TRACKED_METRICS:
            for appid in appids:
                appName = apps[appid]['appName']
                timestamp = time.time()
                prefix = [self.metric_root, appName, 'groupedby', 'appversion']
                stats = self.at.errorMonitoringPie(
                    appid=appid, metric=metric, groupby='appVersion')
                try:
                    slices = stats['data']['slices']
                    for sl in slices:
                        group = sl['label']
                        value = sl['value']
                        path = prefix + [group, metric]
                        self.gp.submit(path, value, timestamp)

                except LookupError:
                    log.error('No data for metric: %s app: %s',
                              metric, appName, exc_info=True)

        self.gp.flush()


def main(project):

    config = jsonstore.config(project)

    apteligentconf = config('apteligent')
    graphiteconf = config('graphite')
    countries = config('app_timezones')
    carriers = groupmap(project, 'carrier')

    try:
        metric_root = apteligentconf.data.pop('metric_root')
        at = apteligent.restapi.Client(project, **apteligentconf)
        gp = tographite.CarbonSink(**graphiteconf)
    except TypeError:
        log.exception('The json configuration files contains an improper key.')
        raise

    batchjob = BatchJob(metric_root, at, gp, countries, carriers)

    # Important: the ClockBasedScheduler spawns threads, so Events can
    # run in parallel
    sched = schedule.ClockBasedScheduler()
    event = schedule.Event

    # Pull in stats grouped by app version every 10 minutes
    sched.addevent(event('*',  0, batchjob.appversion))
    sched.addevent(event('*', 10, batchjob.appversion))
    sched.addevent(event('*', 20, batchjob.appversion))
    sched.addevent(event('*', 30, batchjob.appversion))
    sched.addevent(event('*', 40, batchjob.appversion))
    sched.addevent(event('*', 50, batchjob.appversion))

    # Pull in stats grouped by carrier every 10 minutes starting from 2
    # past the whole hour
    sched.addevent(event('*',  2, batchjob.carrier))
    sched.addevent(event('*', 12, batchjob.carrier))
    sched.addevent(event('*', 22, batchjob.carrier))
    sched.addevent(event('*', 32, batchjob.carrier))
    sched.addevent(event('*', 42, batchjob.carrier))
    sched.addevent(event('*', 52, batchjob.carrier))

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
