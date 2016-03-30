from builtins import object
import time
import logging
import concurrent.futures

log = logging.getLogger(__name__)


class Event(object):
    def __init__(self, *args, **kwargs):
        self.hour = args[0]
        self.minute = args[1]
        self.task = args[2]
        if len(args) > 3:
            self.args = args[3:]
        else:
            self.args = None
        if kwargs:
            self.kwargs = kwargs
        else:
            self.kwargs = None
        log.debug('Event: hour: %s, minute: %s, task: %s,'
                  'args: %s, kwargs: %s', self.hour, self.minute,
                  self.task, self.args, self.kwargs)

    def trigger(self, current_hour, current_minute):
        if self.hour == '*' and self.minute == current_minute:
            return True
        elif self.hour == current_hour and self.minute == current_minute:
            return True
        else:
            return False

    def execute(self):
        if self.args and self.kwargs:
            self.task(*self.args, **self.kwargs)
        elif self.args:
            self.task(*self.args)
        elif self.kwargs:
            self.task(**self.kwargs)
        else:
            self.task()


class ClockBasedScheduler(object):
    def __init__(self):
        self.events = []

    def addevent(self, event):
        self.events.append(event)

    def run(self):
        log.info('Starting schedule with %s events', len(self.events))
        futures = dict()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=16)
        try:
            while True:
                current_time = time.localtime()
                current_hour = current_time.tm_hour
                current_minute = current_time.tm_min
                for event in self.events:
                    if event.trigger(current_hour, current_minute):
                        futures[event] = executor.submit(event.execute)
                for event in self.events:
                    if event in futures:
                        future = futures[event]
                        if future.done():
                            try:
                                future.result()
                            except Exception as e:
                                log.error(event)
                                log.error(e)
                            finally:
                                del futures[event]

                time.sleep(60 - (int(time.time()) % 60))
        finally:
            executor.shutdown(wait=True)


class EveryX(object):
    """
    Baseclass for EveryXMinutes and EveryXSeconds.
    """
    def __init__(self, X):

        self.X = X

    def sleep_until_next_run(self):
        n = self.seconds_until_next_run()
        log.debug('Sleep for %s seconds, until next run.', n)
        time.sleep(n)


class EveryXMinutes(EveryX):
    """
    To run a job every X minutes on the clock, the next time the clock strikes
    this minute mark needs to be calculated. Then the script can sleep until
    the next run.
    """

    def seconds_until_next_run(self):
        minutes = self.X
        # time.localtime returns a struct with the time split out in years,
        # days, hours, minutes and seconds. We need minutes and seconds.
        t = time.localtime()
        # The time until the clock strikes X minutes again is calculated by
        # the formula below.

        return (minutes - (t.tm_min % minutes)) * 60 - t.tm_sec


class EveryXSeconds(EveryX):
    """
    To run a job every X Seconds on the clock, the next time the clock strikes
    this second mark needs to be calculated. Then the script can sleep until
    the next run.
    """
    def seconds_until_next_run(self):
        seconds = self.X
        # time.localtime returns a struct with the time split out in years,
        # days, hours, minutes and seconds. We only seconds.
        t = time.localtime()
        # The formula below calculates how many seconds it takes before the
        # seconds on the clock are divisible by the seconds we want to run.

        return seconds - (t.tm_sec % seconds)
