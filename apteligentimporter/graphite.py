import logging
import pickle
import struct
import socket
import uuid
from apteligentimporter.jsonstore import Cache
from collections import deque
from string import maketrans
import pprint

log = logging.getLogger(__name__)

pp = pprint.PrettyPrinter(indent=2, width=200)

# Special characters are not supported for use in graphite expressions.
# delchars contains all the characters to remove from a metric path
delchars = '(){}[]!"#$%&\'*+/<=>?@\\^`|~\t\n\r\x0b\x0c'
# Dots create a new directory in whisperdb. They are replaced with a dash.
# Spaces, commas, parentheses are problematic, we replace them with underscores
transtable = maketrans('. ,/:;',
                       '-_____')


def sanitize(metric):

    if type(metric) == list:
            l = list()
            for m in metric:
                if isinstance(m, unicode):
                    l.append(
                        m.encode('ascii', 'ignore')
                        .translate(transtable, delchars))
                elif isinstance(m, str):
                    l.append(m.translate(transtable, delchars))
            metric = '.'.join(l)
    elif isinstance(metric, str):
        metric = metric.translate(None, delchars)
    elif isinstance(metric, unicode):
        metric = metric.encode('ascii', 'ignore').translate(None, delchars)
    else:
        raise TypeError('Metric needs to be a list of path elements or a'
                        'dotted path string.')
    return metric


class CarbonSink(object):
    """
    Submit data to carbon.
    """

    def __init__(self, host=None, port=None, protocol=None, max_buffer=None):
        """
        Initialize graphite object with empty buffer. Needs the following
        keyword arguments:
        host: Hostname of the graphite server
        port: Port of the carbon daemon supporting the protocol selected
        protocol: plain, pickle or dummy
        max_buffer: max size of the buffer (number of items in the list)
        """
        if host and port and protocol and max_buffer:
            log.info('Graphite connection created.\n Connection: %s:%s\n'
                     'Protocol: %s\nMax buffer: %s', host, port, protocol,
                     max_buffer)
        else:
            raise RuntimeError("Missing arguments. Example:"
                               "Graphite(connection=(host, port),"
                               "protocol='pickle'/'plain', max_buffer=100)")

        self.host = host
        self.port = port
        self.connection = (host, port)
        self.protocol = protocol
        self.max_buffer = max_buffer
        self.buff = deque()

    def submit(self, metric, value, timestamp):
        """
        Add a tuple in the form (metric, (timestamp, value)) to the list
        self.buff
        When max_buffer is reached, flush the buffer to graphite.
        Arguments:
        - metric is either a dotted string or a list representing the metric.
        - value is a number representing the value.
        - timestamp is a unix timestamps in seconds since epoch.
        """
        metric = sanitize(metric)
        message = metric, (timestamp, value)

        self.buff.append(message)
        if len(self.buff) >= self.max_buffer:
            self.flush_buffer()

    def flush_buffer(self):
        """
        Flush all metrics found in the buffer to graphite until max_buffer is
        reached. Both the line protocol and the Pickle protocol are supported.
        """
        log.info('Flushing buffer to carbon daemon at %s:%s', self.host,
                 self.port)
        lst = list()
        for i in xrange(self.max_buffer):
            try:
                lst.append(self.buff.popleft())
            except IndexError:
                log.debug('Found %s metrics in queue', i+1)
                break
        # This else belongs to the for loop. It executes when it completes
        # without encountering a break.
        else:
            log.debug('Will flush max number of metrics in queue: %s',
                      self.max_buffer)

        if not lst:
            log.info('flush_buffer called, but nothing to send to carbon')
            return

        log.debug(pp.pformat(lst))
        if self.protocol == 'pickle':
            payload = pickle.dumps(lst, 2) # Setting protocol 2 as carbon is python2 only (march 2016).
            header = struct.pack("!L", len(payload))
            message = header + payload
        elif self.protocol == 'plain':
            message = '\n'.join(
                ['{0[0]} {0[1][1]} {0[1][0]}'.format(metric)
                    for metric in lst])
            log.debug(message)
        elif self.protocol == 'dummy':
            return
        else:
            log.warning('Graphite protocol unknown: %s', self.protocol)
            raise ValueError('Graphite protocol unknown')
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(self.connection)
            s.sendall(message)
        except socket.error as e:
            log.error('Failed to send data to graphite.\n%s', e)
            c = Cache(str(uuid.uuid1()))
            c.data = lst
            c.store()
            log.info('Buffer flushed to json cache: %s', c.path)
        else:
            log.info('%s metrics succesfully sent to graphite.', len(lst))
        finally:
            s.close()
