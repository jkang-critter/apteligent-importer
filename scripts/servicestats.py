#!/usr/bin/env python
'''
Import the web service performance stats from apteligent REST API
into graphite.
'''

from libecgnoc import (logger,
                       schedule,
                       jsonstore,
                       textstore)

import apteligent
import tographite


import time
from argparse import ArgumentParser

services_whitelist = None


def import_servicestats(metric_root, at, gp):
    """
    Stats on web services including ecg api services.
    """
    failures = list()

    # These are the available parameters of the apteligent REST_API
    # performanceManagementPie
    metrics = ['dataIn', 'dataOut', 'latency', 'volume', 'errors']
    # filterKeys = ['appVersion', 'carrier', 'device', 'os', 'service']
    # groupBy = ['appId', 'appVersion', 'carrier', 'device', 'os', 'service']

    apps = at.get_apps()
    for appId in apps:
        appName = apps[appId]['appName']
        prefix = [metric_root, appName, 'services']
        for metric in metrics:
            try:
                data = at.performanceManagementPie(appids=[appId],
                                                   metric=metric,
                                                   groupby='service')
            except:
                log.exception('Failed to get %s for %s.', metric, appId)
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


def retryfailures(at, gp, failures):
    """
    Failed requests are retried one time
    """
    log.info('Retrying %s failed apteligent requests.', len(failures))
    for prefix, appId, metric in failures:
        try:
            data = at.performanceManagementPie(appids=[appId],
                                               metric=metric,
                                               groupby='service')
        except RequestException:
            log.exception('Abandoning current run. Flushing current buffer.'
                          'Retry at next run.')
        processdata(prefix, metric, data, gp)


def main(project):

    config = jsonstore.config(project)

    apteligentconf = config('apteligent')
    graphiteconf = config('graphite')

    global services_whitelist
    services_whitelist = textstore.whitelist(project, 'services')

    try:
        metric_root = apteligentconf.data.pop('metric_root')
        at = apteligent.restapi.Client(project, **apteligentconf.data)
        gp = tographite.CarbonSink(**graphiteconf.data)
    except TypeError:
        log.exception('The json configuration files contain an improper key.')
        raise

    sched = schedule.EveryXMinutes(15)

    while True:
        services_whitelist.refresh()
        sched.sleep_until_next_run()
        failures = import_servicestats(metric_root, at, gp)
        if failures:
            time.sleep(120)
            retryfailures(at, gp, failures)
        gp.flush_buffer()

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
