from subfish.ec2 import AwsEc2
from subfish.iam import AwsIam

class AwsEks(AwsEc2, AwsIam):

    def __init__(self, path, config_path="."):
        super().__init__(path=path,
                ec2_path=config_path,
                iam_path=config_path)
        self.logger.debug("Executing AwsEks Constructor")
        self.eks_client = self.session.create_client('eks')

    def create_vpc_environment(self, num_affinity_groups=2):
        self.logger.debug("Executing AwsEks create_vpc_environment")
        self.create_vpc()
        self.create_affinity_group(zones=num_affinity_groups)

    def create_affinity_group(self, type='private', zones=2):
        self.logger.debug("Executing AwsEks create_affinity_group")
        try:
            next_af_group_number = int(max([t['Value'] \
                for s in self['Subnets'] for t in s['Tags'] \
                if t['Key'] == 'affinity_group']))+1
            self.logger.debug(
                "Generated next_af_group_number: <{}>".format(next_af_group_number))
        except KeyError as k:
            if k.args[0] == 'Subnets':
                self.logger.debug("Generating first subnet")
                next_af_group_number = 0
            else:
                raise
        if type == 'public' or type == 'public-private-access' and 'InternetGateway' in self:
            self.logger.error("Cannot have two public affinity groups.")
            return -1
        self.logger.debug("Generating subnets for {} availability zones.".format(zones))
        for i in range(zones):
            self.logger.debug("Creating subnet <{}>.".format(i))
            self.create_subnet(affinity_group=next_af_group_number)
        self.create_route_table(affinity_group=next_af_group_number)
        self.associate_rt_subnet(affinity_group=next_af_group_number)
        if type == 'public':
            self.create_internet_gateway(affinity_group=next_af_group_number)
        if type == 'public-private-access':
            self.create_internet_gateway(affinity_group=next_af_group_number)
            self.create_nat_gateway(affinity_group=next_af_group_number)
        if type == 'private-access-public':
            if 'InternetGateway' not in self:
                return -1
            nat_af_group = next(t['Value'] for t in self['NatGateway']['Tags'] \
                if t['Key'] == 'affinitiy_group')
            self.create_nat_default_route(
                rt_affinity_group=next_af_group_number,
                nat_affinity_group=nat_af_group)

    def destroy_vpc_environment(self):
#       self.delete_nat_gateway()
#       self.delete_internet_gateway()
#       self.delete_iam_roles()
#       self.refresh_route_tables()
#       self.refresh_subnets()
#       self.delete_route_tables()
#       self.delete_subnets()
#       self.delete_security_groups()
        self.delete_vpc()
