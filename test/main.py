from os import getcwd, remove, listdir
from sys import path
path.append('/'.join(getcwd().split('/')[:-2]))

from subfish.ec2 import AwsEc2
from subfish.iam import AwsIam
from subfish.eks import AwsEks
PATH = './.aws_load.yml'

aws = AwsEc2(PATH)
aws.create_launch_template('HelloWorld')
aws.refresh_launch_templates()
aws.modify_launch_template('HelloWorld')
aws.refresh_launch_templates()
aws.delete_launch_templates()
#aws.create_vpc()
#aws.create_subnet()
#aws.create_route_table()
#aws.associate_rt_subnet()
#aws.create_internet_gateway()
#aws.create_subnet(affinity_group=1)
#aws.create_route_table(affinity_group=1)
#aws.associate_rt_subnet(affinity_group=1)
#aws.create_nat_gateway()
#aws.create_nat_default_route(rt_affinity_group=1)
#aws.create_security_group("bastion")
#aws.refresh_security_groups()
#aws.authorize_security_group_policies("bastion")








#aws.delete_nat_gateways()
#aws.delete_internet_gateway()
#aws.delete_route_tables()
#aws.delete_subnets()
#aws.delete_vpc()












#aws = AwsIam(PATH)
#aws = AwsEks(path=PATH)
#print(dir(aws))
#aws.create_vpc_environment()
#aws.create_affinity_group(type='public-private-access')
#aws.create_affinity_group(type='private-public-access')
#print("\n\n")
#print(aws)
#print("\n\n")
#aws.destroy_vpc_environment()

#pattachments = [aws.get_iam_role_policy_arn("AmazonEKSClusterPolicy")]
#aws.create_iam_role(role_name="EKSClusterRole", policy_attachments=pattachments)
#aws.delete_iam_roles()




#aws.create_vpc()
#aws.create_subnet()
#aws.create_route_table()
#aws.delete_route_tables()
#aws.get_af_ngw()
#aws.delete_subnets()
#aws.get_available_cidr_block()
#aws.get_next_az()
#aws.create_security_group('bastion')
#print(aws)
#aws.delete_security_groups()
#aws.delete_vpc()

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
