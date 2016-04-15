#!/usr/bin/env python
'''
Script to import the apteligent livestats out of the current beta API every 5
minutes. Aggregates data in to 1 minute buckets.
'''
from __future__ import unicode_literals
from libecgnoc import logger, schedule, jsonstore
import tographite
import apteligent
import concurrent.futures
from argparse import ArgumentParser


class Livestats(object):

    def __init__(self, metric_root, at, gp):
        self.metric_root = metric_root
        self.at = at
        self.gp = gp
        self.lastsuccess = dict()

    def periodic(self, appids):
        failures = list()

        with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
            future_to_app_id = {executor.submit(self.at.livestats_periodic,
                                app_id, 'total', True):
                                    app_id for app_id in appids}

            for future in concurrent.futures.as_completed(future_to_app_id):
                app_id = future_to_app_id[future]
                app_name = self.at.appname(app_id)
                prefix = [self.metric_root, app_name, 'live']
                apploads = tographite.main.sanitize(prefix + ['apploads'])
                crashes = tographite.main.sanitize(prefix + ['crashes'])
                exceptions = tographite.main.sanitize(prefix + ['exceptions'])

                try:
                    result = future.result()
                except:
                    failures.append(app_id, prefix)
                    log.exception('Request failed for %s with app ID: %s.',
                                  app_name, app_id)
                    continue

                if result['success'] == 1:
                    stats = result['periodic_data']
                else:
                    log.error('Retrieval of livestats unsuccessful.'
                              'appid: %s, appname: %s', app_id, app_name)
                    continue

                log.info('Received live stats (periodic)'
                         'for %s with app ID: %s', app_name, app_id)
                lastsuccess = self.lastsuccess.get(app_id, 0)

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

                self.lastsuccess[app_id] = stats[-1]['time']//1000

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
    livestats = Livestats(metric_root, at, gp)

    while True:
        sched.sleep_until_next_run()
        appids = list(at.get_apps().keys())
        failures = livestats.periodic(appids)
        if failures:
            log.info('Retrying %s failed requests', len(failures))
            failures = livestats.periodic(failures)
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
    parser.add_argument("-i", "--interval", dest="interval",
                        default=2, help="Polling interval in minutes")
    args = parser.parse_args()

    log = logger.setup(args.project, __file__, debug=args.verbose)

    main(args.project, args.interval)
