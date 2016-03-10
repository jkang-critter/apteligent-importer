#!/usr/bin/env python
import time
from datetime import datetime
from argparse import ArgumentParser

from apteligentimporter import (setuplogger,
                                Config,
                                Blacklist,
                                REST_API,
                                CarbonSink)

from apteligentimporter.schedule import Event, ClockBasedScheduler

metric_root = None


def dailystats(appid, cc, gp):
    """
    Retreive daily stats of an app based on appid. Only the data of a complete
    day, in other words
    yesterday, will be stored
    """
    global metric_root
    # Calculating 'yesterday' turned out to be a challenge.
    # I settled on using the ordinal value of the date. The python
    # documentation is not clear on what this is,
    # but it basically is the number of days since January 1st of the year 1.
    # I am still not sure if this is the best approach considering all the
    # different timezones.
    yesterday = datetime.today().toordinal() - 1
    timestamp = time.mktime(datetime.fromordinal(yesterday).timetuple())
    apps = cc.get_apps()

    # If we want to stop tracking a metric remove it below.
    metrics = ['crashPercent', 'mau', 'dau', 'rating', 'appLoads', 'crashes',
               'affectedUsers', 'affectedUserPercent']

    for metric in metrics:
        appName = apps[appid]['appName']
        path = [metric_root, appName, 'daily', metric]
        # the errorMonitoring/graph API call returns an incomplete value for
        # the running day.
        # Request the data for two days and only use yesterdays value to track
        # the completed days.
        stat = cc.errorMonitoringGraph(appid=appid, metric=metric,
                                       duration=2880)
        try:
            value = stat['data']['series'][0]['points'][0]
        except LookupError:
            log.exception('No data for metric: %s app: %s', metric, appName)
        else:
            gp.submit(path, value, timestamp)

    gp.flush_buffer()


def main():

    apteligentconf = Config('apteligent')
    graphiteconf = Config('graphite')
    app_timezones = Config('app_timezones')
    app_blacklist = Blacklist('app')

    global metric_root
    try:
        metric_root = apteligentconf.data.pop('metric_root')
        cc = REST_API(**apteligentconf.data)
        gp = CarbonSink(**graphiteconf.data)
    except TypeError:
        log.exception('The json configuration files contains an improper key.')
        raise
    log.info('Scheduling jobs')
    scheduler = ClockBasedScheduler()

    # Because the configured timezone determines the time the Crittercism
    # counters are reset,
    # we need to schedule the retreival of the data  based on this.
    for appid, (appname, timezone, country) in app_timezones.data.iteritems():
        # skip apps in the blacklist
        if appid in app_blacklist:
            continue
        log.debug('App %s with appid %s, countrycode: %s, has GMT offset: %s',
                  appname, appid, country, timezone)
        if timezone < 0:
            event = Event(0-timezone, 5, dailystats, appid, cc, gp)
        elif timezone > 0:
            event = Event(24-timezone, 5, dailystats, appid, cc, gp)
        elif timezone == 0:
            event = Event(0, 5, dailystats, appid, cc, gp)
        else:
            log.error('App %s with appid: %s,'
                      'has no timezone configured as GMT offset.',
                      appname, appid)
            raise ValueError('Improper GMT offset')

        scheduler.addevent(event)

    scheduler.addevent(Event(1, 0, cc.new_token))
    scheduler.addevent(Event(6, 0, cc.new_apps))
    scheduler.run()


if __name__ == "__main__":

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-q", "--quiet", action="store_false",
                        dest="verbose", default=True,
                        help="Suppress debug level log messages")
    args = parser.parse_args()

    log = setuplogger(__file__, debug=args.verbose)

    main()
