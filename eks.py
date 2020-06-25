from subfish.ec2 import AwsEc2
from subfish.iam import AwsIam

class AwsEks(AwsEc2, AwsIam):

    def __init__(self, path, config_path="."):
        AwsIam.__init__(self, path=path, iam_path=config_path)
        AwsEc2.__init__(self, path=path, ec2_path=config_path)
        self.eks_client = self.session.create_client('eks')

    def create_vpc_environment(self, num_affinity_groups=2):
        self.create_vpc()
        self.create_affinity_group(zones=num_affinity_groups)
#            self.create_route_table(affinity_group=i)
#            self.associate_rt_subnet(affinity_group=i)
#        self.create_internet_gateway()
#        self.create_nat_gateway()
#        self.create_security_group('bastion')
#        p = [self.get_iam_role_policy_arn("AmazonEKSClusterPolicy")]
#        self.create_iam_role(role_name="EKSClusterRole", policy_attachments=p)

    def create_affinity_group(self, type='private', zones=2):
        try:
            next_af_group_number = int(max([t['Value'] \
                for s in self['Subnets'] for t in s['Tags'] \
                if t['Key'] == 'affinity_group']))+1
        except KeyError as k:
            if k.args[0] == 'Subnets':
                next_af_group_number = 0
            else:
                raise
        if type == 'public' and 'InternetGateway' in self:
            return -1
        for i in range(zones):
            self.create_subnet(affinity_group=next_af_group_number)
        self.create_route_table(affinity_group=next_af_group_number)
        self.associate_rt_subnet(affinity_group=next_af_group_number)
        if type == 'public':
            self.create_internet_gateway(affinity_group=next_af_group_number)

    def destroy_vpc_environment(self):
#       self.delete_nat_gateway()
#       self.delete_internet_gateway()
#       self.delete_iam_roles()
        self.delete_route_tables()
        self.delete_subnets()
#       self.delete_security_groups()
        self.delete_vpc()
