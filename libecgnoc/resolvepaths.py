import os


class Resolve(object):

    def __init__(self, project):
        self.project = project

    def config(self):
        dirs = [os.getenv('CONFIG_DIR', False),
                os.path.join(os.path.expanduser('~'), '.' + self.project),
                os.path.join(os.path.expanduser('~/Library'), self.project),
                os.path.join(os.getcwd(), 'config'),
                os.path.join('/etc', self.project)]
        return select(dirs)

    def cache(self):
        dirs = [os.getenv('CACHE_DIR', False),
                os.path.join(os.getcwd(), 'cache'),
                os.path.join('/var/cache/', self.project),
                '/tmp']
        return select(dirs)

    def log(self):
        dirs = [os.getenv('LOG_DIR', False),
                os.path.join(os.getcwd(), 'log'),
                os.path.join('/var/log', self.project),
                '/tmp']
        return select(dirs)


def select(dirs):
    for candidate in dirs:
        if candidate and os.path.isdir(candidate):
            return candidate
    raise RuntimeError('None of the following are available: %s' % dirs)
