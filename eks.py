from subfish.ec2 import AwsEc2
from subfish.iam import AwsIam

class AwsEks(AwsEc2, AwsIam):

    def __init__(self, path, config_path="."):
        AwsIam.__init__(self, path=path, iam_path=config_path)
        AwsEc2.__init__(self, path=path, ec2_path=config_path)
        self.eks_client = self.session.create_client('eks')


    def create_vpc_environment(self, num_affinity_groups=2):
        redundancy = 2
#       self.create_vpc()
#       for i in range(num_affinity_groups):
#           for j in range(redundancy):
#               self.create_subnet(affinity_group=i)
#           self.create_route_table(affinity_group=i)
#           self.associate_rt_subnet(affinity_group=i)
#       self.create_internet_gateway()
#       self.create_nat_gateway()
#       self.create_security_group('bastion')
        p = [self.get_iam_role_policy_arn("AmazonEKSClusterPolicy")]
        self.create_iam_role(role_name="EKSClusterRole", policy_attachments=p)

    def destroy_vpc_environment(self):
        self.delete_iam_roles()
#       self.delete_subnets()
#       self.delete_route_tables()
#       self.delete_nat_gateway()
#       self.delete_internet_gateway()
#       self.delete_vpc()
