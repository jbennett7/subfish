from os import getcwd, remove, listdir
from sys import path
path.append('/'.join(getcwd().split('/')[:-2]))

from subfish.ec2 import Ec2
#from subfish.iam import AwsIam
#from subfish.eks import AwsEks
PATH = './.aws_load.yml'
import logging
logging.basicConfig(level=logging.INFO)

def create_env(aws):
    aws.create_vpc()
    aws.create_subnet()
    aws.create_route_table()
    aws.associate_rt_subnet()
    aws.create_internet_gateway()
    
    aws.create_subnet(affinity_group=1)
    aws.create_route_table(affinity_group=1)
    aws.associate_rt_subnet(affinity_group=1)
#   aws.create_nat_gateway()
#   aws.create_nat_default_route(rt_affinity_group=1)
    aws.create_launch_template('HelloWorld')
    aws.create_security_group("bastion")
    aws.authorize_security_group_policies("bastion")

    aws.run_instance("HelloWorld")



def destroy_env(aws):
    aws.terminate_instances()
#   aws.delete_nat_gateways()
    aws.delete_security_groups()
    aws.delete_launch_templates()

    aws.delete_internet_gateway()
    aws.delete_route_tables()
    aws.delete_subnets()
    aws.delete_vpc()

aws = Ec2(PATH, config_path='.')
create_env(aws)
destroy_env(aws)
