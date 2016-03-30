from builtins import range
from builtins import object
import logging
import pickle
import struct
import socket
import pprint
from collections import deque

log = logging.getLogger(__name__)

# Special characters are not supported for use in graphite expressions.
# delchars contains all the characters to remove from a metric path
delchars = '(){}[]!"#$%&\'*+/<=>?@\\^`|~\t\n\r\x0b\x0c'
# Dots create a new directory in whisperdb. They are replaced with a dash.
# Spaces, commas, parentheses are problematic, we replace them with underscores
inchars = '. ,/:;'
ouchars = '-_____'


transtable = {ord(a): ord(b) for a, b in zip(inchars, ouchars)}
deltable = {ord(d): None for d in delchars}
transtable.update(deltable)


def sanitize(metric):

    if type(metric) == list:
            l = list()
            for m in metric:
                try:
                    l.append(m.translate(transtable))
                except TypeError:
                    l.append(m.decode().translate(transtable))
            metric = '.'.join(l)
    else:
        try:
            metric = metric.translate(deltable)
        except TypeError:
            metric = metric.decode().translate(deltable)

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
        for i in range(self.max_buffer):
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

        if self.protocol == 'pickle':
            # Use pickle protocol 2 as carbon is python2 only (march 2016)
            payload = pickle.dumps(lst, 2)
            header = struct.pack("!L", len(payload))
            message = header + payload
        elif self.protocol == 'plain' or self.protocol == 'dummy':
            message = '\n'.join(
                ('{0[0]} {0[1][1]} {0[1][0]}'.format(metric)
                    for metric in lst))
            if self.protocol == 'dummy':
                log.info(message)
                return
        else:
            log.warning('Graphite protocol unknown: %s', self.protocol)
            raise ValueError('Graphite protocol unknown')
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(self.connection)
            s.sendall(message)
        except socket.error:
            log.exception('Failed to send data to graphite.')
        else:
            log.info('%s metrics succesfully sent to graphite.', len(lst))
        finally:
            s.close()
