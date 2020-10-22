from os import getcwd, remove, listdir
from sys import path
path.append('/'.join(getcwd().split('/')[:-2]))
print(path)
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

aws = Ec2(PATH, config_path='.')
#aws.create_launch_template('HelloWorld')
#aws.delete_launch_templates()
#create_env(aws)
#destroy_env(aws)
