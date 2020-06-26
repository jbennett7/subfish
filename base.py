from botocore.exceptions import ClientError
import botocore.session
from time import sleep
import yaml, re
from subfish.logger import Logger

PATH='./.aws_dict.yml'

class AwsBase(dict):
    def __init__(self, path, **kwargs):
        self.logger = Logger(__name__)
        self.logger.debug("Executing AwsBase Constructor")
        self.session = botocore.session.get_session()
        self.path = path
        self.load()
        super().__init__(**kwargs)

    def list_append(self, k, v):
        self.logger.debug("list_append: Executing")
        if k not in self:
            self[k] = []
        self[k].append(v)

    def load(self):
        self.logger.debug("load: Executing")
        try:
            data = yaml.load(open(self.path).read())
            for key in data.keys(): self[key] = data[key]
        except ( FileNotFoundError, AttributeError):
            self = {}

    def save(self):
        self.logger.debug("save: Executing")
        with open(self.path, 'w') as f:
            yaml.safe_dump(dict(self), f, default_flow_style=False)

    def sleep(self, s=1):
        self.logger.debug("sleep: Executing")
        i = .1*s
        sleep(i)
