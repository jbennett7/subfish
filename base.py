from botocore.exceptions import ClientError
import botocore.session
from time import sleep
import yaml, re

PATH='./.aws_dict.yml'

class AwsBase(dict):
    def __init__(self, path, **kwargs):
        self.session = botocore.session.get_session()
        self.path = path
        self.load()
        super().__init__(**kwargs)

    def list_append(self, k, v):
        if k not in self:
            self[k] = []
        self[k].append(v)

    def load(self):
        try:
            data = yaml.load(open(self.path).read())
            for key in data.keys(): self[key] = data[key]
        except ( FileNotFoundError, AttributeError):
            self = {}

    def save(self):
        with open(self.path, 'w') as f:
            yaml.safe_dump(dict(self), f, default_flow_style=False)

    def sleep(self, s=1):
        i = .1*s
        sleep(i)
