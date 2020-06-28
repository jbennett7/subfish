import logging
LOGLEVEL = logging.INFO

class Logger():
    def __init__(self, name):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(LOGLEVEL)
        handler = logging.StreamHandler()
        formatter='%(levelname)s::%(name)s::%(message)s'
        handler.setFormatter(logging.Formatter(formatter))
        self.logger.addHandler(handler)

    def set_level(self, level):
        if level == 'debug':
            self.logger.setLevel(logging.DEBUG)
        if level == 'info':
            self.logger.setLevel(logging.INFO)
        if level == 'warning':
            self.logger.setLevel(logging.WARNING)
        if level == 'error':
            self.logger.setLevel(logging.ERROR)

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)
