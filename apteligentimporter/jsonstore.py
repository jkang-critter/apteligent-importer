import time
import json
import os
import logging
from apteligentimporter.resolvepaths import CONFIG_DIR, CACHE_DIR

log = logging.getLogger(__name__)


class JSONstore(object):

    def __init__(self, name, path):
        self.path = path
        self.name = name
        self.data = dict()
        self.last_update = None
        if self.exists():
            self.load()

    def exists(self):
        return os.path.isfile(self.path)

    def refresh(self):
        if self.last_update < self.last_modified():
            self.load()

    def load(self):
        try:
            with open(self.path, 'r') as store:
                self.data = json.load(store)
                log.info('Loaded %s from json cache.', self.path)
                self.last_update = time.time()
                return self.data
        except IOError, e:
            log.exception("Script failed to open or write %s\n %(e)s",
                          self.path, e)
            raise
        except json.JSONDecodeError, e:
            log.exception("Simplejson was unable to parse %s:\n %(e)s",
                          self.path, e)
            raise

    def last_modified(self):
        return os.path.getmtime(self.path)

    def store(self):
        lockfile = self.path + '.lock'
        if os.path.isfile(lockfile):
            log.warning('Could not acquire lock file %s', lockfile)
            return False
        try:
            lock = open(lockfile, 'w')
            with open(self.path, 'w') as store:
                json.dump(self.data, store, indent=4)
                log.info('Stored %s in json cache.', self.path)
                self.last_update = time.time()
        except IOError as e:
            log.exception("Script failed to open or write %s\n %(e)s",
                          self.path, e)
            raise
        except json.JSONDecodeError as e:
            log.exception("Simplejson was unable to parse %s:\n %(e)s",
                          self.path, e)
            raise
        finally:
            lock.close()
            os.remove(lockfile)


class Cache(JSONstore):

    def __init__(self, name):
        path = os.path.join(CACHE_DIR, name + '.json')
        super(Cache, self).__init__(name, path)


class Config(JSONstore):

    def __init__(self, name):
        path = os.path.join(CONFIG_DIR, name + '.json')
        super(Config, self).__init__(name, path)

    def store(self):
        raise RuntimeError("Config should not use store() method")
