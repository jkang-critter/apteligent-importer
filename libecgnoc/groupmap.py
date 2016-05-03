from __future__ import absolute_import
from builtins import next
from builtins import str
from builtins import object
import logging
import re
import os
from libecgnoc.resolvepaths import Resolve
log = logging.getLogger(__name__)


class Regexgroup(object):
    def __init__(self, regexp, group):
        self.regexp = regexp
        self.group = group
        self.compiledre = re.compile(self.regexp)

    def __contains__(self, blurb):
        return self.compiledre.search(blurb) is not None

    def __str__(self):
        return self.regexp + ' ' + self.group + '\n'


class Groups(object):
    def __init__(self, name):
        self.name = name
        self.lst = list()

    def __str__(self):
        builder = ""
        builder += '[' + self.name + ']\n'
        for group in self.lst:
            builder += str(group)
        return builder

    def add(self, group):
        self.lst.append(group)

    def findgroup(self, topic):
        for candidate in self.lst:
            if topic in candidate:
                log.debug('%s: %s matches %s so belongs to %s',
                          self.name, topic, candidate.regexp, candidate.group)
                return candidate.group
        # None of the candidate groups matched.
        log.critical('No group found for %s in table: %s', topic, self.name)


class GroupmapParser(object):

    def __init__(self, filename):
        self.filename = filename
        self.groupmap = dict()
        self.lineno = 0

    def parse(self):
        try:
            store = self.store_iterator()
            return self.scannext(store)
        except:
            log.exception('Parsing failed at %s:%s', self.filename,
                          self.lineno)
            raise

    def store_iterator(self):
        with open(self.filename, 'r') as f:
            for lineno, line in enumerate(f, 1):
                yield lineno, line

    def createmap(self, line, store):
        """
        Create a map with a name based on the following syntax: [name]
        """
        name = line.strip('[]\n')
        groups = Groups(name)
        log.debug('Creating list of groups for %s', name)
        self.addregex(store, groups)
        self.closemap(store, groups)
        return

    def addregex(self, store, groups):
        try:
            self.lineno, line = next(store)
        except StopIteration:
            return
        if line.strip() == "":
            return
        regexp, group = line.split()
        groups.add(Regexgroup(regexp, group))
        log.debug('%s ->  %s', regexp, group)
        self.addregex(store, groups)

    def closemap(self, store, groups):
        self.groupmap[groups.name] = groups
        log.debug('Close groupings for %s.', groups.name)

    def scannext(self, store):
        try:
            linenumber, line = next(store)
        except StopIteration:
            return self.groupmap
        if line == "" or line.startswith('#'):
            return self.scannext(store)
        elif line.startswith('['):
            self.createmap(line, store)
            return self.scannext(store)
        else:
            log.error('Line %s in %s, not handled.\n%s', linenumber,
                      self.filename, line)
            return self.scannext(store)


class Groupmap(object):
    """
    Use a config file with a .map extension to combine groups of metrics in new
    ways.
    Each map file contains a list of regular expressions and destination groups
    """

    Extension = '.map'

    def __init__(self, storagedir, name):
        self.name = name
        self.path = os.path.join(storagedir, name + self.Extension)
        self.data = None
        self.last_update = None
        if self.exists():
            self.load()
        else:
            raise RuntimeError('File %s does not exist', self.path)

    def __getitem__(self, key):
        return self.data[key]

    def __str__(self):
        builder = ""
        for groups in self.data.values():
            builder += str(groups)
            builder += '\n'
        return builder

    def exists(self):
        return os.path.isfile(self.path)

    def load(self):
        parser = GroupmapParser(self.path)
        self.data = parser.parse()


def groupmap(project, name=None):
    path = Resolve(project).config()

    def creator(_name):
        return Groupmap(path, _name)

    if name:
        return creator(name)
    else:
        return creator
