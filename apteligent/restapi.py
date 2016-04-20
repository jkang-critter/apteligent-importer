from builtins import object
import json
import time
import requests
import logging
from libecgnoc import jsonstore
from libecgnoc import textstore

log = logging.getLogger(__name__)


def check_http_interaction(response):
    """
    All API calls need to check their status codes.
    403 is returned in case of a authentication error.
    429 is returned when the api rate limit is reached.
    """
    log.debug(">REQUEST -------------->\nHEADERS:\n%s\nBODY:\n%s\n",
              response.request.headers, response.request.body)
    log.debug("<RESPONSE <-------------\nURL: %s\nHEADERS:\n%s\nBODY:\n%s\n",
              response.url, response.headers, response.text)
    if response.status_code < 300:
        limit = response.headers.get('Rate-Limit-Limit', False)
        if limit:
            remaining = response.headers.get('Rate-Limit-Remaining', '')
            reset = response.headers.get('Rate-Limit-Reset', '')
            log.info('Rate limit: %s; Remaining requests: %s;'
                     'Reset in %s seconds', limit, remaining, reset)
            return
    elif response.status_code < 400:
        log.critical('Received redirect. HTTP status code: %s',
                     response.status_code)
    elif response.status_code == 400:
        log.critical('Request parameters were invalid/malformed')
    elif response.status_code == 403:
        log.critical('OAuth authentication failed')
    elif response.status_code == 429:
        failure = response.json
        message = failure.get('message', 'API rate limit exceeded')
        actual = failure.get('actual', 'unknown')
        limit = failure.get('limit', 'unknown')
        reset = failure.get('reset', 'unknown')
        log.critical('%s: Number of requests was %s, but limit is %s.'
                     'Limit will reset in %s seconds.',
                     message, actual, limit, reset)
    elif response.status_code > 499:
        log.error('Server error. HTTP status code: %s', response.status_code)
    response.raise_for_status()


class Client(object):
    """
    Implements a client of the Apteligent REST API.
    """

    def __init__(self, project, hostname, username, password,
                 clientID, proxies=None):
        """
        Initialize the REST API using provided Apteligent credentials.
        The following keyword arguments need to be provided:
        hostname, username, password and clientID
        Optionally a list of proxies could be given.
        """
        self.hostname = hostname
        self.username = username
        self.password = password
        self.clientID = clientID
        self.proxies = proxies

        cache = jsonstore.cache(project)
        blacklist = textstore.blacklist(project)
        self.token = cache('token')
        self.apps = cache('apps')
        self.app_blacklist = blacklist('app')

    def all_your_base(self):
        """"
        Returns the current API version as long as it is v1 and the link to the
        base path of this API version
        """
        url = 'https://' + self.hostname + '/allyourbase'
        r = requests.get(url, proxies=self.proxies)
        log.debug("All your base belongs to:\n {}".format(r.text))
        r.raise_for_status()
        version = r.json()['versions']['v1']['latest']
        href = r.json()['links'][version]['href']
        return version, href

    def get_base(self, basepath):
        """
        Returns a list of API endpoints. Pretty worthless in v1.0 as only two
        endpoints are returned. Most of the interesting endpoints are missing.
        """
        log.info('Retrieving list of API endpoints')
        url = 'https://' + self.hostname + basepath
        r = requests.get(url, proxies=self.proxies)
        log.debug(r.text)
        r.raise_for_status()
        return r.json()['links']

    def get_token(self):
        """
        Returns an existing OAuth token from cache for the Apteligent API or
        fetches a new one using current credentials.
        """
        if self.token.exists():
            self.token.refresh()
        else:
            self.new_token()

        return 'Bearer' + ' ' + self.token.data['access_token']

    def new_token(self):
        log.info('Getting a new authorization token from apteligent')

        payload = {'grant_type': 'password', 'username': self.username,
                   'password': self.password}
        path = '/v1.0/token'
        url = "https://" + self.hostname + path
        r = requests.post(url, payload, auth=(self.clientID, ''),
                          proxies=self.proxies)

        check_http_interaction(r)
        self.token.data = r.json()
        self.token.data['expiration'] = (time.time() +
                                         self.token.data['expires_in'])
        self.token.store()
        return self.token

    def appname(self, appId):
        apps = self.get_apps()
        return apps[appId]['appName']

    def get_apps(self):
        if self.apps.exists():
            self.apps.refresh()
            return self.apps.data
        else:
            return self.new_apps()

        return self.apps.data

    def new_apps(self):
        apps = self.__get_apps(['appName',
                                'linkToAppStore',
                                'appVersions',
                                'latestVersionString',
                                'iconURL'])

        self.apps.data = self.app_filter(apps)

        log.info("List of apps has been updated.")
        log.info("Tracking %s apps.", len(apps))
        self.apps.store()
        return apps

    def app_filter(self, apps):
        self.app_blacklist.refresh()
        self.app_blacklist.as_set()
        appids = list(apps.keys())
        for appid in appids:
            if appid in self.app_blacklist:
                # remove blacklisted apps from list
                del apps[appid]
            else:
                # remove useless links section from results
                del apps[appid]['links']

        return apps

    def __get_apps(self, tracked_attributes):
        tokenstr = self.get_token()
        path = '/v1.0/apps'
        url = 'https://' + self.hostname + path
        attr = ','.join(tracked_attributes)

        log.info('Retreiving the current list of apps from apteligent,'
                 'with tracked attributes %s', attr)

        r = requests.get(
            url,
            headers={
                'Content-Type': 'application/json',
                'Authorization': tokenstr
            },
            params={'attributes': attr},
            proxies=self.proxies)

        check_http_interaction(r)

        apps = r.json()
        log.info("Number of apps: %s", len(apps))
        return apps

    def get_dailystats(self):

        log.info('Retrieving daily stats')

        tracked_attributes = ['appName',
                              'crashPercent',
                              'latency',
                              'mau',
                              'dau',
                              'rating']

        apps = self.__get_apps(tracked_attributes)
        return self.app_filter(apps)

    def performanceManagementPie(self, appids=None, duration=15,
                                 metric='volume', filterkey=None,
                                 filtervalue=None, groupby=None):
        """
        PerformanceManagementPie API Call. Keyword arguments: appIds, metric,
        duration, filterkey, filtervalue and groupby.
        """
        if appids is None:
            appids = list(self.get_apps().keys())
        href = '/v1.0/performanceManagement/pie'
        url = 'https://' + self.hostname + href
        tokenstr = self.get_token()

        parameters = dict()
        parameters['params'] = {'appIds': appids, 'graph': metric,
                                'duration': duration}
        if groupby:
            parameters['params']['groupBy'] = groupby
        if filterkey:
            parameters['params']['filters'] = {filterkey: filtervalue}

        payload = json.dumps(parameters)

        r = requests.post(url,
                          data=payload,
                          headers={'Content-Type': 'application/json',
                                   'Authorization': tokenstr},
                          proxies=self.proxies)

        check_http_interaction(r)

        return r.json()

    def errorMonitoringGraph(self, **kwargs):
        if 'metric' not in kwargs:
            kwargs['metric'] = 'crashes'
        return self.errorMonitoring('/v1.0/errorMonitoring/graph', **kwargs)

    def errorMonitoringPie(self, **kwargs):
        if 'metric' not in kwargs:
            kwargs['metric'] = 'appLoads'
        if 'groupby' not in kwargs:
            kwargs['groupby'] = 'appId'
        return self.errorMonitoring('/v1.0/errorMonitoring/pie', **kwargs)

    def errorMonitoringSparklines(self, **kwargs):
        if 'metric' not in kwargs:
            kwargs['metric'] = 'appLoads'
        if 'groupby' not in kwargs:
            kwargs['groupby'] = 'appId'
        return self.errorMonitoring('/v1.0/errorMonitoring/sparklines',
                                    **kwargs)

    def errorMonitoring(self, path, appid=None, appids=None, metric='appLoads',
                        duration=1440, filterkey=None, filtervalue=None,
                        groupby=None):
        """
        ErrorMonitoring/sparklines API Call. Keyword arguments: appIds, metric,
        duration, filterkey, filtervalue and groupby.
        possible values:
        metrics = ['affectedUserPercent','affectedUsers','appLoads',
        'crashPercent','crashes','dau','mau','rating']
        filterKeys = ['appVersion', 'carrier', 'device', 'os']
        groupBy = ['appId', 'appVersion', 'carrier', 'device', 'os']
        """

        url = 'https://' + self.hostname + path

        parameters = dict()
        parameters['params'] = {'graph': metric, 'duration': duration}
        if appid is None and appids is None:
            apps = self.get_apps()
            appids = list(apps.keys())
            parameters['params']['appIds'] = appids
        elif appids is None:
            parameters['params']['appId'] = appid

        tokenstr = self.get_token()

        if groupby:
            parameters['params']['groupBy'] = groupby
        if filterkey:
            parameters['params']['filters'] = {filterkey: filtervalue}

        payload = json.dumps(parameters)

        r = requests.post(url,
                          data=payload,
                          headers={'Content-Type': 'application/json',
                                   'Authorization': tokenstr},
                          proxies=self.proxies)

        check_http_interaction(r)

        return r.json()

    def livestats_totals(self, app_id, app_version='total'):
        """
        API Call to the beta of Apteligent livestats. Returns the current
        totals of the day for the provided app_id.
        Arguments:
        - app_id: You can only retrieve data for one App at a time.
        - app_version: Version of the app you want data for. 'total' gives
        you a combined result for all appVersions.
        Metrics received: app_exceptions, app_loads, app_errors
        """
        tokenstr = self.get_token()

        url = "https://{}/v1.0/liveStats/totals/{}".format(self.hostname,
                                                           app_id)
        r = requests.post(url,
                          headers={'Authorization': tokenstr},
                          params={'app_version': app_version},
                          proxies=self.proxies)

        check_http_interaction(r)

        return r.json()

    def livestats_periodic(self, app_id, app_version='total', init=True):
        """
        API Call to the beta of Apteligent livestats. Returns metrics for the
        last 10 seconds for the provided app_id.
        Arguments:
        - app_id: You can only retrieve data for one App at a time.
        - app_version: Version of the app you want data for. 'total' gives you
        a combined result for all appVersions.
        - init: If this is True, data for the last 5 minutes is returned in 10
        second buckets. If False only the last bucket is returned.
        Metrics received: app_exceptions, app_loads, app_errors
        """

        tokenstr = self.get_token()

        url = "https://{}/v1.0/liveStats/periodic/{}".format(self.hostname,
                                                             app_id)
        parameters = dict()
        parameters['app_version'] = app_version
        if init:
            parameters['initialize'] = 1
        r = requests.post(url,
                          headers={'Authorization': tokenstr},
                          params=parameters,
                          proxies=self.proxies)

        check_http_interaction(r)

        return r.json()
