#!/usr/bin/env python
'''
Script to import the apteligent livestats out of the current beta API every few
minutes. Results are returned in 10 second buckets.
'''
from __future__ import unicode_literals
from __future__ import print_function
from argparse import ArgumentParser
from libecgnoc import logger, schedule, jsonstore
import tographite
import apteligent
import concurrent.futures


class BatchJob(object):

    def __init__(self, metric_root, at, gp):
        self.metric_root = metric_root
        self.at = at
        self.gp = gp
        self.lastsuccess = dict()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=16)

    def run(self, appids):
        failures = list()

        future_to_appid = dict()
        for appid in appids:
            future = self.executor.submit(self.at.livestats_periodic, appid)
            future_to_appid[future] = appid

        for future in concurrent.futures.as_completed(future_to_appid):
            appid = future_to_appid[future]
            appname = self.at.appname(appid)
            prefix = [self.metric_root, appname, 'live']
            apploads = tographite.main.sanitize(prefix + ['appLoads'])
            crashes = tographite.main.sanitize(prefix + ['crashes'])
            exceptions = tographite.main.sanitize(prefix + ['exceptions'])

            try:
                result = future.result()
            except apteligent.RequestException:
                failures.append(appid, prefix)
                log.exception('Request failed for %s with app ID: %s.',
                              appname, appid)
                continue

            if result['success'] == 1:
                stats = result['periodic_data']
            else:
                log.error('Retrieval of livestats unsuccessful.'
                          'appid: %s, appname: %s', appid, appname)
                continue

            log.info('Received live stats (periodic)'
                     'for %s with app ID: %s', appname, appid)
            lastsuccess = self.lastsuccess.get(appid, 0)

            for stat in stats:
                # The Crittercism API returns milliseconds since epoch
                # instead of seconds.
                # To add insult to injury, the smallest interval returned
                # by the api is 10 seconds
                timestamp = stat['time']//1000
                if timestamp > lastsuccess:
                    self.gp.submit(apploads, stat['app_loads'], timestamp)
                    self.gp.submit(crashes, stat['app_errors'], timestamp)
                    self.gp.submit(exceptions, stat['app_exceptions'],
                                   timestamp)

            self.lastsuccess[appid] = stats[-1]['time']//1000

        return failures


def main(project, interval):

    config = jsonstore.config(project)
    apteligentconf = config('apteligent')
    graphiteconf = config('graphite')

    try:
        metric_root = apteligentconf.data.pop('metric_root')
        at = apteligent.restapi.Client(project, **apteligentconf.data)
        gp = tographite.CarbonSink(**graphiteconf.data)
    except (KeyError, TypeError):
        log.exception('The json configuration files contains'
                      'an improper key.')
        raise

    sched = schedule.EveryXMinutes(interval)
    batchjob = BatchJob(metric_root, at, gp)

    while True:
        sched.sleep_until_next_run()
        appids = list(at.get_apps().keys())
        failures = batchjob.run(appids)
        if failures:
            log.info('Retrying %s failed requests', len(failures))
            failures = batchjob.run(failures)
            if failures:
                log.info('Giving up... %s failed requests', len(failures))
            else:
                log.info('Retry successful')
        gp.flush()


if __name__ == "__main__":

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-p", "--project", dest="project",
                        default="apteligent-importer",
                        help="Project name")
    parser.add_argument("-q", "--quiet", action="store_false",
                        dest="verbose", default=True,
                        help="Suppress debug level log messages")
    parser.add_argument("-i", "--interval", dest="interval", default=2,
                        help="Polling interval in minutes from 1 upto 5.")
    args = parser.parse_args()

    interval = int(args.interval)
    assert 0 < interval < 6, "Interval not in valid range."

    log = logger.setup(args.project, __file__, debug=args.verbose)

    main(args.project, interval)
