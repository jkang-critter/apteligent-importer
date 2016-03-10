#!/usr/bin/env python
'''
Script to import the apteligent livestats out of the current beta API.
'''

from apteligentimporter import (setuplogger,
                                REST_API,
                                CarbonSink,
                                schedule,
                                Config,
                                RequestException)

import time
import concurrent.futures
from argparse import ArgumentParser

metric_root = None


def import_livestats(cc, gp, appids):
    global metric_root
    failures = list()

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        future_to_app_id = {executor.submit(cc.livestats_periodic,
                            app_id, 'total', False):
                                app_id for app_id in appids}

        for future in concurrent.futures.as_completed(future_to_app_id):
            app_id = future_to_app_id[future]
            app_name = cc.appname(app_id)
            prefix = [metric_root, app_name, 'live']

            try:
                stats = future.result()
            except RequestException:
                failures.append(app_id, prefix)
                log.exception('Request failed for %s with app ID: %s.',
                              app_name, app_id)
            else:
                log.info('Received live stats (periodic)'
                         'for %s with app ID: %s', app_name, app_id)

            for stat in stats['periodic_data']:
                # The Crittercism API returns milliseconds since epoch instead
                # of seconds.
                # To add insult to injury, the smallest interval returned by
                # the api is 10 seconds
                timestamp = int(stat['time']/1000)
                gp.submit(prefix + ['appLoads'], stat['app_loads'], timestamp)
                gp.submit(prefix + ['crashes'], stat['app_errors'], timestamp)
                gp.submit(prefix + ['exceptions'], stat['app_exceptions'],
                          timestamp)
    return failures


def main():

    apteligentconf = Config('apteligent')
    graphiteconf = Config('graphite')

    global metric_root
    try:
        metric_root = apteligentconf.data.pop('metric_root')
        cc = REST_API(**apteligentconf.data)
        gp = CarbonSink(**graphiteconf.data)
    except (KeyError, TypeError):
        log.exception('The json configuration files contains'
                      'an improper key.')
        raise

    sched = schedule.EveryXSeconds(10)

    while True:
        sched.sleep_until_next_run()
        start = time.time()
        appids = cc.get_apps().keys()
        failures = import_livestats(cc, gp, appids)
        if failures:
            log.info('Retrying %s failed requests', len(failures))
            failures = import_livestats(cc, gp, failures)
            if failures:
                log.info('Giving up.... %s failed requests', len(failures))
            else:
                log.info('Retry successful')

        gp.flush_buffer()

        duration = time.time() - start
        if duration > 10:
            log.error('It took longer to retrieve the livestats than'
                      'the 10 second bucket. Duration: %s seconds.', duration)
        else:
            log.debug('End of run. Duration: %s seconds', duration)


if __name__ == "__main__":

    parser = ArgumentParser(description=__doc__)
    parser.add_argument("-q", "--quiet", action="store_false",
                        dest="verbose", default=True,
                        help="Suppress debug level log messages")
    args = parser.parse_args()

    log = setuplogger(__file__, debug=args.verbose)
    main()
