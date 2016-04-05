from __future__ import absolute_import
from __future__ import unicode_literals
from builtins import (object, zip)
import logging
import pickle
import struct
import socket
from collections import deque, namedtuple

log = logging.getLogger(__name__)

# Some special characters are not supported for use in graphite expressions.
# Regardless, whisper will happily create a file with names containing
# those characters.
# delchars contains all the characters to remove from a metric path
# that are problematic.
delchars = '(){}[]!"#$%&\'*+/<=>?@\\^`|~\t\n\r\x0b\x0c'
# Dots create a new directory in whisperdb. They are replaced with a dash.
# Spaces, commas, parentheses are problematic, we replace them with underscores
inchars = '. ,/:;'
ouchars = '-_____'

# Here I avoid the use of maketrans, because of python2 / python3 differences
# for unicode a transtable is just a map of ordinals to ordinals.
transtable = {ord(a): ord(b) for a, b in zip(inchars, ouchars)}
deltable = {ord(d): None for d in delchars}
transtable.update(deltable)

Metric = namedtuple('Metric', ['path', 'value', 'timestamp'])


def sanitize(path):
    """
    Sanitize the input metric paths and accepts lists or dot seperated strings.
    Returns a dot separated string in unicode/ python 3 string.
    Bytes or python2 strings are decoded to unicode.
    """

    if type(path) == list:
            l = list()
            for el in path:
                try:
                    l.append(el.translate(transtable))
                except TypeError:
                    l.append(el.decode().translate(transtable))
            path = '.'.join(l)
    else:
        try:
            path = path.translate(deltable)
        except TypeError:
            path = path.decode().translate(deltable)

    return path


def plainmessage(metrics):
    """
    Return message conforming to the graphite line protocol
    """
    def processtuple(m):
        return '{m.path} {m.value:g} {m.timestamp:.3f}'.format(**locals())

    return '\n'.join(processtuple(metric) for metric in metrics)


def picklemessage(metrics):
    """
    Return message conforming to the graphite pickle protocol
    """
    def processtuple(m):
        return m.path.encode('utf-8'), (float(m.timestamp), float(m.value))

    lst = [processtuple(metric) for metric in metrics]

    # Use pickle protocol 2 as carbon is python2 only (march 2016)
    payload = pickle.dumps(lst, 2)
    header = struct.pack("!L", len(payload))
    return header + payload


class CarbonSink(object):
    """
    Submit data to carbon.
    """

    def __init__(self, host=None, port=None, protocol='plain', max_buffer=500):
        """
        Initialize graphite object with empty buffer. Needs the following
        keyword arguments:
        host: Hostname of the graphite server
        port: Port of the carbon daemon supporting the protocol selected
        protocol: plain, pickle or dummy
        max_buffer: max size of the buffer (number of items in the list)
        """
        def connection():
            if host and port:
                log.info('Graphite connection created.\n Connection: %s:%s\n'
                         'Protocol: %s\nMax buffer: %s', host, port, protocol,
                          max_buffer)
                self.connection = (host, port)
            else:
                raise RuntimeError("Missing host and/or port arguments.Example:"
                                   "Graphite(host=localhost, port=2004,"
                                   "protocol='plain', max_buffer=100)")

        if protocol == 'pickle':
            connection()
            self._message = picklemessage
        elif protocol == 'plain':
            connection()
            self._message = plainmessage
        elif protocol == 'dummy':
            self.send = self._dummysend
            self._message = plainmessage
        else:
            raise ValueError('Unknown protocol: %s', protocol)

        self.max_buffer = max_buffer
        if max_buffer > 500:
            log.critical('max_buffer higher than 500 could hurt performance')

        # All metrics are buffered in a deque. A deque is thread safe and supports
        # fast pops and appends on both sides.
        self._buff = deque()

    def submit(self, path, value, timestamp):
        """
        Add a tuple in the form (metric, (timestamp, value)) to the deque
        self._buff
        When max_buffer is reached, flush the buffer to graphite.
        Arguments:
        - path is either a dotted string or a list representing the metric path
        - value is a number representing the value
        - timestamp is a unix timestamps in seconds since epoch
        """
        path = sanitize(path)
        metric = Metric(path, value, timestamp)

        self._buff.append(metric)
        if len(self._buff) >= self.max_buffer:
            self.flush()

    def _buffgen(self):
        """
        Return a generator which returns Metric tuples from the buffer
        until empty or max_buffer is reached. FIFO
        """
        i = 0
        while i < self.max_buffer:
            try:
                yield self._buff.popleft()
                i += 1
            except IndexError:
                log.info('Removed %s metrics from queue', i)
                break

    def flush(self):
        """
        Flush all metrics found in the buffer to graphite until max_buffer is
        reached.
        """

        buff = self._buffgen()

        message = self._message(buff)

        self.send(message)

    def _dummysend(self, message):
        """
        Record the message in the logs and discard it.
        """
        log.info('Dummy protocol:\nSTARTDATA\n%s\nENDDATA', message)

    def send(self, message):
        """
        Open a socket and send a message to graphite.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(self.connection)
            s.sendall(message)
        except socket.error:
            log.exception('Failed to send data to graphite.')
        else:
            log.info('Metrics succesfully sent to graphite.')
        finally:
            s.close()
