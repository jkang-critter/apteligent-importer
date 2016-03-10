#!/usr/bin/env python
'''
Import the web service performance stats from apteligent REST API
into graphite.
'''
from apteligentimporter import (setuplogger,
                                apteligent,
                                graphite,
                                schedule,
                                Config,
                                Whitelist,
                                RequestException)

import time
# import concurrent.futures
from argparse import ArgumentParser

metric_root = None

services_whitelist = Whitelist('services')


def import_servicestats(cc, gp):
    """
    Stats on web services including ecg api services.
    """
    global metric_root
    failures = list()

    # These are the available parameters of the apteligent REST_API
    # performanceManagementPie
    metrics = ['dataIn', 'dataOut', 'latency', 'volume', 'errors']
    # filterKeys = ['appVersion', 'carrier', 'device', 'os', 'service']
    # groupBy = ['appId', 'appVersion', 'carrier', 'device', 'os', 'service']

    apps = cc.get_apps()
    for appId in apps:
        appName = apps[appId]['appName']
        prefix = [metric_root, appName, 'services']
        for metric in metrics:
            try:
                data = cc.performanceManagementPie(appids=[appId],
                                                   metric=metric,
                                                   groupby='service')
            except RequestException:
                log.error('Failed to get %s for %s.', metric, appId)
                failures.append((prefix, appId, metric))
                continue
            processdata(prefix, metric, data, gp)

    return failures


def processdata(prefix, metric, data, gp):
    """
    Before the results from a performanceManagementPie API call can be send to
    graphite it needs to be sliced and diced.
    """
    timestamp = time.mktime(time.strptime(data['data']['end'],
                                          '%Y-%m-%dT%H:%M:%S'))
    for dataslice in data['data']['slices']:
        service = dataslice['label']
        if service in services_whitelist:
            gp.submit(prefix + [dataslice['label'], metric],
                      dataslice['value'], timestamp)


def retryfailures(cc, gp, failures):
    """
    Failed requests are retried one time
    """
    log.info('Retrying %s failed apteligent requests.', len(failures))
    for prefix, appId, metric in failures:
        try:
            data = cc.performanceManagementPie(appids=[appId],
                                               metric=metric,
                                               groupby='service')
        except RequestException:
            log.exception('Abandoning current run. Flushing current buffer.'
                          'Retry at next run.')
        processdata(prefix, metric, data, gp)


def main():

    apteligentconf = Config('apteligent')
    graphiteconf = Config('graphite')

    global metric_root

    try:
        metric_root = apteligentconf.data.pop('metric_root')
        cc = apteligent.REST_API(**apteligentconf.data)
        gp = graphite.CarbonSink(**graphiteconf.data)
    except TypeError:
        log.exception('The json configuration files contain an improper key.')
        raise

    sched = schedule.EveryXMinutes(15)

    while True:
        services_whitelist.refresh()
        sched.sleep_until_next_run()
        failures = import_servicestats(cc, gp)
        if failures:
            time.sleep(120)
            retryfailures(cc, gp, failures)
        gp.flush_buffer()

if __name__ == "__main__":

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-q", "--quiet", action="store_false",
                        dest="verbose", default=True,
                        help="Suppress debug level log messages")
    args = parser.parse_args()

    log = setuplogger(__file__, debug=args.verbose)

    main()
