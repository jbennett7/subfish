from botocore.exceptions import ClientError
import botocore.session
from time import sleep
import yaml, re
from subfish.logger import Logger
logger = Logger(__name__)


PATH='./.aws_dict.yml'

class AwsBase(dict):
    def __init__(self, path):
        logger.info("__init__::Executing")
        self.session = botocore.session.get_session()
        self.path = path
        logger.info("__init__::path::{}".format(self.path))
        self.load()

    def list_append(self, k, v):
        logger.debug("list_append: Executing")
        if k not in self:
            self[k] = []
        self[k].append(v)

    def load(self):
        logger.debug("load: Executing")
        try:
            data = yaml.load(open(self.path).read())
            for key in data.keys(): self[key] = data[key]
        except ( FileNotFoundError, AttributeError):
            self = {}

    def save(self):
        logger.debug("save: Executing")
        f = open(self.path, 'w')
        logger.debug("saving: {}".format(self))
        yaml.safe_dump(dict(self), f, default_flow_style=False)

    def sleep(self, s=1):
        logger.debug("sleep: Executing")
        i = .1*s
        sleep(i)
