import os

CONFIG_DIRS = [os.getenv('CONFIG_DIR', False),
               os.path.join(os.path.expanduser('~'), '.nocgraphite-scripts'),
               os.path.join(os.getcwd(), 'config'),
               '/etc/nocgraphite-scripts']

CACHE_DIRS = [os.getenv('CACHE_DIR', False),
              os.path.join(os.getcwd(), 'cache'),
              '/var/cache/nocgraphite-scripts',
              '/tmp']

LOG_DIRS = [os.getenv('LOG_DIR', False),
            os.path.join(os.getcwd(), 'log'),
            '/var/log/nocgraphite-scripts',
            '/tmp']


def resolve(dirs):
    for candidate in dirs:
        if candidate and os.path.isdir(candidate):
            return candidate
    raise RuntimeError('No storage directory found in: %s' % dirs)

CONFIG_DIR = resolve(CONFIG_DIRS)
CACHE_DIR = resolve(CACHE_DIRS)
LOG_DIR = resolve(LOG_DIRS)
