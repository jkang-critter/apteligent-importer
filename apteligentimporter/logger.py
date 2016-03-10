'''
Setup logging for the all nocgraphite-scripts in a consistent way using the
dramatically overly complex python logging library.
'''
import os
import logging
import logging.handlers
from resolvepaths import LOG_DIR

def setuplogger(scriptfile, debug=False):
    '''
    Return root logger configured to log to log_dir using the __file__
    global variable to determine basename of the log file.
    supports a debug keyword variable to set logging level to DEBUG.
    '''

    # First configure urllib3 verbosity separately as INFO level is worthless:
    l = logging.getLogger("requests.packages.urllib3")
    if debug:
        l.setLevel(logging.DEBUG)
    else:
        l.setLevel(logging.WARNING)

    name, ext = os.path.splitext(os.path.basename(scriptfile))
    assert ext == '.py', ('setuplogger should be called with the __file__'
                          'of the main python script')

    filename = os.path.join(LOG_DIR, name + '.log')

    # Acquire root logger.
    log = logging.getLogger()
    if debug:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)

    # Setting the loglevels of the handler does not change the loglevel of the
    # loggers. It sets the lowest loglevel the handler accepts.
    fh = logging.handlers.WatchedFileHandler(filename)
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.ERROR)

    fullformatter = logging.Formatter('%(asctime)s - %(levelname)s -'
                                      '%(name)s:%(funcName)s:%(lineno)d'
                                      '- %(message)s')
    simpleformatter = logging.Formatter('%(message)s')
    fh.setFormatter(fullformatter)
    ch.setFormatter(simpleformatter)
    log.addHandler(fh)
    log.addHandler(ch)

    return log
