from subfish.ec2.vpc import AwsVpc
from subfish.ec2.secgroup import AwsSG
from subfish.ec2.compute import AwsCompute
from subfish.ec2.gateways import AwsGW

class Ec2(AwsVpc, AwsSG, AwsCompute, AwsGW): pass
