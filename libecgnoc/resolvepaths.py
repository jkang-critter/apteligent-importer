from os import getenv, path, getcwd
import platform


ERRORMSG = (
    "Failed to find a {} directory. "
    "Please set environment variable {}, "
    "provide a --project at the commandline "
    "or create any of the following directories:\n{}")


class Resolve(object):

    _config = None
    _cache = None
    _log = None
    system = platform.system()
    project = None

    def __init__(self, project=None):
        if project:
            self.project = project
        elif self.project:
            pass
        else:
            raise RuntimeError('The project is undefined')

    def config(self):
        if self._config:
            return self._config

        dirs = [getenv('CONFIG_DIR', False)]

        if self.system == 'Darwin':
            dirs.append(
                path.join(path.expanduser('~/Library'), self.project))

        dirs.extend([
            path.expanduser('~/.{}'.format(self.project)),
            path.join(getcwd(), 'config'),
            path.join('/etc', self.project)])

        directory = select(dirs)

        if directory:
            self._config = directory
            return directory
        else:
            failed = '\n'.join(d for d in dirs if d)
            raise RuntimeError(ERRORMSG.format('CONFIG', 'CONFIG_DIR', failed))

    def cache(self):
        if self._cache:
            return self._cache

        dirs = [getenv('CACHE_DIR', False),
                path.join(getcwd(), 'cache')]

        if self.system == 'Linux':
            dirs.append(path.join('/var/cache/', self.project))
        elif self.system == 'Darwin':
            dirs.append(
                path.join(path.expanduser('~/Library/Caches'), self.project))

        # dirs.append('/tmp')

        directory = select(dirs)
        if directory:
            self._cache = directory
            return directory
        else:
            failed = '\n'.join(d for d in dirs if d)
            raise RuntimeError(ERRORMSG.format('CACHE', 'CACHE_DIR', failed))

    def log(self):
        if self._log:
            return self._log

        dirs = [getenv('LOG_DIR', False),
                path.join(getcwd(), 'log')]

        if self.system == 'Linux':
            dirs.append(path.join('/var/log', self.project))
        if self.system == 'Darwin':
            dirs.append(
                path.join(path.expanduser('~/Library/Logs'), self.project))

        # dirs.append('/tmp')

        directory = select(dirs)
        if directory:
            self._log = directory
            return directory
        else:
            failed = '\n'.join(d for d in dirs if d)
            raise RuntimeError(ERRORMSG.format('LOG', 'LOG_DIR', failed))


def select(dirs):
    for candidate in dirs:
        if candidate and path.isdir(candidate):
            return candidate
    return False
