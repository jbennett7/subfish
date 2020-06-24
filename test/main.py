from os import getcwd, remove
from sys import path
path.append('/'.join(getcwd().split('/')[:-2]))

from subfish.ec2 import AwsEc2
PATH = './.aws_load.yml'

aws = AwsEc2(PATH)
#aws.create_vpc()

#aws.create_route_table()
#aws.create_subnet()
#aws.associate_rt_subnet()
#aws.create_internet_gateway()
#aws.create_nat_gateway()
#
#aws.create_route_table(affinity_group=1)
#aws.create_subnet(affinity_group=1)
#aws.associate_rt_subnet(affinity_group=1)
#aws.create_nat_default_route(rt_affinity_group=1)
#print(aws)
#aws.delete_nat_gateway()
#aws.delete_route_tables()
#aws.delete_subnets()
#aws.delete_internet_gateway()
#aws.delete_vpc()
