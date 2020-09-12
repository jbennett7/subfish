from os import getcwd, remove, listdir
from sys import path
path.append('/'.join(getcwd().split('/')[:-1]))

from subfish.ec2 import Ec2
#from subfish.iam import AwsIam
#from subfish.eks import AwsEks
PATH = './.aws_load.yml'
import logging
logging.basicConfig(level=logging.DEBUG)
botocore_logger = logging.getLogger('botocore')
urllib3_logger = logging.getLogger('urllib3')
botocore_logger.setLevel(logging.CRITICAL)
urllib3_logger.setLevel(logging.CRITICAL)

def create_env(aws):
    aws.create_vpc()
    aws.create_subnet()
    aws.create_subnet()
    aws.create_subnet()
    aws.create_route_table()
    aws.associate_rt_subnet()
    aws.create_internet_gateway()
    

def destroy_env(aws):
    aws.delete_internet_gateway()
    aws.delete_route_tables()
    aws.delete_subnets()
    aws.delete_vpc()

def cycle(aws):
    for i in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]:
        for j in [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]:
            print("Try: {}{}".format(i, j))
            create_env(aws)
            destroy_env(aws)

aws = Ec2(PATH, config_path='.')
create_env(aws)
#destroy_env(aws)
