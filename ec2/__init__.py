from subfish import AwsBase
from ipaddress import ip_network

class AwsEc2(AwsBase):

    def __init__(self, path):
        super().__init__(path)
        self.client = self.session.create_client('ec2')

    def get_available_cidr_block(self):
        cidr_block = self['Vpc']['CidrBlock']
        try:
            used_cidrs = [s['CidrBlock'] for s in self['Subnets']]
        except KeyError:
            used_cidrs = []
        cidr = list(set([str(c) for c in \
            list(ip_network(cidr_block).subnets(new_prefix=24))]) - set(used_cidrs))
        cidr.sort()
        return cidr[0]

    def get_next_az(self, affinity_group=0):
        vpc_id = self['Vpc']['VpcId']
        az_dict = {a['ZoneName']: 0 for a in \
            self.client.describe_availability_zones()['AvailabilityZones']}
        for az in [a['AvailabilityZone'] for a in self.client.describe_subnets(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]} ])['Subnets']]:
                az_dict[az] = az_dict[az] + 1
        min_value = min(az_dict.values())
        return next(k for k, v in az_dict.items() if v == min_value)

    def get_af_subnets(self, affinity_group=0):
        return [s['SubnetId'] for s in self['Subnets'] for t in s['Tags'] \
            if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group)]

    def get_af_rt(self, affinity_group=0):
        return next(rt['RouteTableId'] for rt in self['RouteTables'] for t in rt['Tags'] \
            if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group))

    def get_af_ngw(self, affinity_group=0):
        return next(ngw['NatGatewayId'] for ngw in self['NatGateways'] for t in ngw['Tags'] \
            if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group))


    def create_vpc(self, cidr_block='10.0.0.0/16'):
        if 'Vpc' in self:
            self.refresh_vpc()
            return 0
        vpc_id = self.client.create_vpc(
            CidrBlock = cidr_block)\
                ['Vpc']['VpcId']
        waiter = self.client.get_waiter('vpc_exists')
        waiter.wait(VpcIds=[vpc_id])
        waiter = self.client.get_waiter('vpc_available')
        waiter.wait(VpcIds=[vpc_id])
        self['Vpc'] = next(vpc for vpc in self.client.describe_vpcs(VpcIds=[vpc_id])['Vpcs'])
        self.save()

    def refresh_vpc(self):
        vpc_id = self['Vpc']['VpcId']
        self['Vpc'] = next(vpc for vpc in self.client.describe_vpcs(VpcIds=[vpc_id])['Vpcs'])
        self.save()

    def delete_vpc(self):
        vpc_id = self['Vpc']['VpcId']
        res = self.client.delete_vpc(VpcId=vpc_id)
        del(self['Vpc'])
        self.save()


    def create_route_table(self, affinity_group=0):
        vpc_id = self['Vpc']['VpcId']
        rt_id = self.client.create_route_table(VpcId=vpc_id)['RouteTable']['RouteTableId']
#       waiter = get_waiter('router_exists')
        self.sleep()
        self.client.create_tags(
            Resources=[rt_id],
            Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
        self.refresh_route_tables()

    def refresh_route_tables(self):
        vpc_id = self['Vpc']['VpcId']
        self['RouteTables'] = self.client.describe_route_tables(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]},
            {'Name': 'tag-key', 'Values': ['affinity_group']}])['RouteTables']
        self.save()

    def associate_rt_subnet(self, affinity_group=0):
        rt_id = next(rt['RouteTableId'] for rt in self['RouteTables'] \
            for t in rt['Tags'] if t['Key'] == 'affinity_group' \
            and t['Value'] == str(affinity_group))
        for s in self.get_af_subnets(affinity_group):
            self.client.associate_route_table(RouteTableId=rt_id, SubnetId=s)
        self.sleep()
        self.refresh_route_tables()

    def delete_route_tables(self, affinity_group=0):
        self.refresh_route_tables()
        try:
            for rt in self['RouteTables']:
                for association in rt['Associations']:
                    self.client.disassociate_route_table(
                        AssociationId=association['RouteTableAssociationId'])
                self.client.delete_route_table(RouteTableId=rt['RouteTableId'])
            del(self['RouteTables'])
            self.save()
        except KeyError:
            return 0
        

    def create_subnet(self, affinity_group=0):
        vpc_id = self['Vpc']['VpcId']
        az = self.get_next_az(affinity_group)
        cidr = self.get_available_cidr_block()
        subnet_id = self.client.create_subnet(
            VpcId=vpc_id,
            AvailabilityZone=az,
            CidrBlock=cidr)['Subnet']['SubnetId']
        waiter = self.client.get_waiter('subnet_available')
        waiter.wait(SubnetIds=[subnet_id])
        self.client.create_tags(
            Resources=[subnet_id],
            Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
        self.refresh_subnets()

    def refresh_subnets(self):
        vpc_id = self['Vpc']['VpcId']
        self['Subnets'] = self.client.describe_subnets(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]}])['Subnets']
        self.save()

    def delete_subnets(self):
        try:
            [self.client.delete_subnet(SubnetId=s['SubnetId']) for s in self['Subnets']]
            del(self['Subnets'])
            self.save()
        except KeyError:
            return 0
        

    def create_internet_gateway(self, affinity_group=0):
        if 'InternetGateway' in self:
            return 0
        vpc_id = self['Vpc']['VpcId']
        igw_id = self.client.create_internet_gateway()['InternetGateway']['InternetGatewayId']
        self.sleep()
        self.client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
        rt_id = self.get_af_rt(affinity_group)
        self.client.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=igw_id,
            RouteTableId=rt_id)
        self.sleep()
        self.client.create_tags(
            Resources=[igw_id],
            Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
        self.refresh_route_tables()
        self.refresh_internet_gateway()

    def refresh_internet_gateway(self):
        vpc_id = self['Vpc']['VpcId']
        self['InternetGateway'] = next(igw for igw in \
            self.client.describe_internet_gateways(Filters=[
                {'Name': 'attachment.vpc-id', 'Values': [vpc_id]}])['InternetGateways'])
        self.save()

    def delete_internet_gateway(self):
        vpc_id = self['Vpc']['VpcId']
        try:
            igw_id = self['InternetGateway']['InternetGatewayId']
            self.client.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
            self.sleep()
            self.client.delete_internet_gateway(InternetGatewayId=igw_id)
            del(self['InternetGateway'])
            self.save()
        except KeyError:
            return 0


    def create_nat_gateway(self, affinity_group=0):
        eipalloc_id = self.client.allocate_address(Domain='vpc')['AllocationId']
        subnet_id = self.get_af_subnets(affinity_group)[0]
        ngw_id = self.client.create_nat_gateway(AllocationId=eipalloc_id, SubnetId=subnet_id)\
            ['NatGateway']['NatGatewayId']
        self.sleep()
        waiter = self.client.get_waiter('nat_gateway_available')
        waiter.wait(NatGatewayIds=[ngw_id])
        self.client.create_tags(
            Resources=[ngw_id],
            Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
        self.refresh_nat_gateways()

    def create_nat_default_route(self, rt_affinity_group, nat_affinity_group=0):
        ngw_id = self.get_af_ngw(nat_affinity_group)
        rt_id = self.get_af_rt(rt_affinity_group)
        self.client.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            NatGatewayId=ngw_id,
            RouteTableId=rt_id)
        self.sleep

    def refresh_nat_gateways(self):
        vpc_id = self['Vpc']['VpcId']
        self['NatGateways'] = self.client.describe_nat_gateways(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]}])['NatGateways']
        self.save()

    def delete_nat_gateway(self):
        try:
            eipalloc_ids = []
            for n in self['NatGateways']:
                for a in n['NatGatewayAddresses']:
                    eipalloc_ids.append(a['AllocationId'])
                self.client.delete_nat_gateway(NatGatewayId=n['NatGatewayId'])
                #Create a waiter
                while self.client.describe_nat_gateways(NatGatewayIds=[n['NatGatewayId']])\
                    ['NatGateways'][0]['State'] != 'deleted': self.sleep(5)
            for a in eipalloc_ids:
                self.client.release_address(AllocationId=a)
            del(self['NatGateways'])
            self.save()
        except KeyError:
            return 0
