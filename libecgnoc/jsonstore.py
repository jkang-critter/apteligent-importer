import time
import json
import os
import logging
from collections import MutableMapping
from libecgnoc.resolvepaths import Resolve

log = logging.getLogger(__name__)


class JSONstore(MutableMapping):
    Extension = '.json'

    def __init__(self, storagedir, name, readonly=True):
        self.path = os.path.join(storagedir, name + self.Extension)
        self.name = name
        self.data = dict()
        self.last_update = None
        log.debug('%s at %s', name, self.path)
        if self.exists():
            self.load()
        if readonly:
            self.store = self._disabled

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, val):
        self.data[key] = val

    def __delitem__(self, key):
        del self.data[key]

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __repr__(self):
        return json.dumps(self.data, indent=4, sort_keys=True)

    def _disabled(self):
        raise RuntimeError('Method is disabled')

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
        except IOError as e:
            log.exception("Script failed to open or write %s\n %(e)s",
                          self.path, e)
            raise
        except json.JSONDecodeError as e:
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


def config(project, name=None):
    resolve = Resolve(project)
    storagedir = resolve.config()

    def creator(_name):
        return JSONstore(storagedir, _name, readonly=True)

    if name:
        return creator(name)
    else:
        return creator


def cache(project, name=None):
    resolve = Resolve(project)
    storagedir = resolve.cache()

    def creator(_name):
        return JSONstore(storagedir, _name, readonly=False)

    if name:
        return creator(name)
    else:
        return creator
