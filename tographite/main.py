from builtins import range
from builtins import object
import logging
import pickle
import struct
import socket
from collections import deque

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
# for unicode a transtable is just a map of ordinals.
transtable = {ord(a): ord(b) for a, b in zip(inchars, ouchars)}
deltable = {ord(d): None for d in delchars}
transtable.update(deltable)


def sanitize(metric):
    """
    Sanitize the input metric paths and accepts lists or dot seperated strings.
    Returns a dot separated string in unicode/ python 3 string. Bytes or python2
    strings are decoded to unicode.
    """

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


def plainmessage(metrics):
    """
    Return message conforming to the graphite line protocol
    """
    def processtuple(tpl):
        metric, (timestamp, value) = tpl
        return '{metric} {value:g} {timestamp:.3f}'.format(**locals())

    return '\n'.join([processtuple(tpl) for tpl in metrics])


def picklemessage(metrics):
    """
    Return message conforming to the graphite pickle protocol
    """
    def processtuple(tpl):
        metric, (timestamp, value) = tpl
        return metric.encode('utf-8'), (float(timestamp), float(value))

    lst = [processtuple(tpl) for tpl in metrics]

    # Use pickle protocol 2 as carbon is python2 only (march 2016)
    payload = pickle.dumps(lst, 2)
    header = struct.pack("!L", len(payload))
    return header + payload


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
        # All metrics are buffered in a deque. This is a thread safe and more
        # performant datastructure than using a plain list.
        self.buff = deque()

    def submit(self, metric, value, timestamp):
        """
        Add a tuple in the form (metric, (timestamp, value)) to the deque
        self.buff
        When max_buffer is reached, flush the buffer to graphite.
        Arguments:
        - metric is either a dotted string or a list representing the metric.
        - value is a number representing the value. Will be cast to float.
        - timestamp is a unix timestamps in seconds since epoch. Will be cast
        to float.
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
            message = picklemessage(lst)
        elif self.protocol == 'plain':
            message = plainmessage(lst).encode('utf-8')
        elif self.protocol == 'dummy':
            message = plainmessage(lst)
            log.info('Dummy protocol:\nSTARTDATA\n%s\nENDDATA', message)
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
