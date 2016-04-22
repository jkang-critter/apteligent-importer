import time
import os
import logging
from collections import Sequence
from libecgnoc.resolvepaths import Resolve

log = logging.getLogger(__name__)


class Textstore(Sequence):

    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.data = list()
        self.last_update = None
        if self.exists():
            self.load()
        log.debug('%s at %s', name, path)

    def __getitem__(self, key):
        return self.data[key]

    def __len__(self):
        return len(self.data)

    def exists(self):
        return os.path.isfile(self.path)

    def load(self):
        try:
            with open(self.path, 'r') as store:
                for line in store:
                    line = line.strip()
                    if line.startswith('#'):
                        continue
                    elif line:
                        self.data.append(line)

                log.info('Read text file: %s.', self.path)
                self.last_update = time.time()
                self.as_set()
                return self.data
        except IOError as e:
            log.exception("Script failed to open %s\n %(e)s", self.path, e)
            raise

    def last_modified(self):
        return os.path.getmtime(self.path)

    def refresh(self):
        if self.last_modified() > self.last_update:
            self.data = list()
            self.load()
            self.as_set()

    def as_set(self):
        raise RuntimeError('The Textstore class should not be used by itself')


class Blacklist(Textstore):
    Extension = '.blacklist'

    def __init__(self, storagedir, name):
        path = os.path.join(storagedir, name + self.Extension)
        super(Blacklist, self).__init__(name, path)

    def as_set(self):
        self.blacklist = set(self.data)
        return self.blacklist

    def __contains__(self, item):
        reject = item in self.blacklist
        if reject:
            log.debug('REJECT: %s in blacklist: %s', item, self.path)
        else:
            log.debug('ALLOWED: %s', item)

        return reject


def blacklist(project, name=None):
    resolve = Resolve(project)
    path = resolve.config()

    def creator(_name):
        return Blacklist(path, _name)

    if name:
        return creator(name)
    else:
        return creator


class Whitelist(Textstore):
    Extension = '.whitelist'

    def __init__(self, storagedir, name):
        path = os.path.join(storagedir, name + self.Extension)
        super(Whitelist, self).__init__(name, path)

    def as_set(self):
        self.whitelist = set(self.data)
        return self.whitelist

    def __contains__(self, item):
        allow = item in self.whitelist
        if allow:
            log.debug('ALLOWED: %s', item)
        else:
            log.debug('REJECT: %s not in whitelist: %s', item, self.path)

        return allow


def whitelist(project, name=None):
    resolve = Resolve(project)
    path = resolve.config()

    def creator(_name):
        return Whitelist(path, _name)

    if name:
        return creator(name)
    else:
        return creator
