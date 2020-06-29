from subfish.ec2.vpc import AwsVpc
from subfish.ec2.secgroup import AwsSG
from subfish.ec2.compute import AwsCompute

class Ec2(AwsVpc, AwsSG, AwsCompute): pass
