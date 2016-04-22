#!/usr/bin/env python
'''
Import the web service performance stats from apteligent REST API
into graphite.
'''

from __future__ import unicode_literals
from builtins import object
import time
from libecgnoc import (logger,
                       schedule,
                       jsonstore,
                       textstore)

import apteligent
from apteligent import RequestException
import tographite


from argparse import ArgumentParser


class BatchJob(object):

    def __init__(self, metric_root, at, gp):
        self.metric_root = metric_root
        self.at = at
        self.gp = gp
        self.whitelist = None

    def run(self):
        """
        Stats on web services including ecg api services.
        """
        failures = list()
        self.whitelist.refresh()

        # These are the available metrics of the apteligent REST_API
        # performanceManagementPie
        metrics = ['dataIn', 'dataOut', 'latency', 'volume', 'errors']

        apps = self.at.get_apps()
        for appId in apps:
            appName = apps[appId]['appName']
            prefix = [self.metric_root, appName, 'services']
            for metric in metrics:
                try:
                    data = self.at.performanceManagementPie(
                        appids=[appId],
                        metric=metric,
                        groupby='service')
                except:
                    log.exception('Failed to get %s for %s.', metric, appId)
                    failures.append((prefix, appId, metric))
                    continue
                self.process(prefix, metric, data)

        return failures

    def process(self, prefix, metric, data):
        """
        Before the results from a performanceManagementPie API call can be send
        to graphite it needs to be sliced and diced.
        """
        timestamp = time.mktime(time.strptime(data['data']['end'],
                                              '%Y-%m-%dT%H:%M:%S'))
        for dataslice in data['data']['slices']:
            service = dataslice['label']
            if service in self.whitelist:
                path = prefix + [service, metric]
                self.gp.submit(
                    path, dataslice['value'], timestamp)

    def retry(self, failures):
        """
        Failed requests are retried one time
        """
        log.info('Retrying %s failed apteligent requests.', len(failures))
        for prefix, appId, metric in failures:
            try:
                data = self.at.performanceManagementPie(
                    appids=[appId],
                    metric=metric,
                    groupby='service')
            except RequestException:
                log.exception('Abandoning current run.'
                              'Flushing current buffer.'
                              'Retry at next run.')
            self.processdata(prefix, metric, data)


def main(project):

    config = jsonstore.config(project)

    apteligentconf = config('apteligent')
    graphiteconf = config('graphite')

    try:
        metric_root = apteligentconf.pop('metric_root')
        at = apteligent.restapi.Client(project, **apteligentconf)
        gp = tographite.CarbonSink(**graphiteconf)
    except TypeError:
        log.exception('The json configuration files contain an improper key.')
        raise

    sched = schedule.EveryXMinutes(15)
    batchjob = BatchJob(metric_root, at, gp)
    batchjob.whitelist = textstore.whitelist(project, 'services')

    while True:
        sched.sleep_until_next_run()
        failures = batchjob.run()
        if failures:
            time.sleep(120)
            batchjob.retry(failures)
        gp.flush()

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
