import os

CONFIG = 0
CACHE = 1
LOG = 2


def resolve(function, project):
    """Return the directory where either config, cache or log files belong.
    Function should be one of resolvepaths.CONFIG, resolvepaths.CACHE
    or resolvepaths.LOG. The project argument should be string."""

    if function == CONFIG:
        dirs = [os.getenv('CONFIG_DIR', False),
                os.path.join(os.path.expanduser('~'), '.' + project),
                os.path.join(os.path.expanduser('~/Library'), project),
                os.path.join(os.getcwd(), 'config'),
                os.path.join('/etc', project)]
    elif function == CACHE:
        dirs = [os.getenv('CACHE_DIR', False),
                os.path.join(os.getcwd(), 'cache'),
                os.path.join('/var/cache/', project),
                '/tmp']
    elif function == LOG:
        dirs = [os.getenv('LOG_DIR', False),
                os.path.join(os.getcwd(), 'log'),
                os.path.join('/var/log', project),
                '/tmp']
    else:
        raise RuntimeError('function should be resolve.paths.CONFIG,'
                           'resolvepaths.CACHE or resolvepaths.LOG')

    for candidate in dirs:
        if candidate and os.path.isdir(candidate):
            return candidate
    raise RuntimeError('None of the following are available: %s' % dirs)
