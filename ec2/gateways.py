from subfish.base import AwsBase
from subfish.logger import Logger

from ipaddress import ip_network
import re, json
from jinja2 import Template
from botocore.exceptions import ClientError, WaiterError

#RELATIVE_SG_AUTHORIZATIONS="sg_authorizations"
#RELATIVE_LAUNCH_TEMPLATES="launch_templates"
LOGLEVEL='info'
#LOGLEVEL2='debug'
# General logger
logger = Logger(__name__)
logger.set_level(LOGLEVEL)

# Logger for AWS API Response metadata
logger_meta = Logger("{}::AWS_API_META".format(__name__))
logger_meta.set_level(LOGLEVEL)

# Logger for AWS API returns
logger_data = Logger("{}::AWS_API".format(__name__))
logger_data.set_level(LOGLEVEL)

class AwsVpc(AwsBase):

    def __init__(self, path, ec2_path=".", **kwargs):
        super().__init__(path=path)
        logger.debug("__init__::Executing")
        self.ec2_client = self.session.create_client('ec2')

    def get_available_cidr_block(self):
        logger.debug("get_available_cidr_block::Executing")
        try:
            cidr_block = self['Vpc']['CidrBlock']
            used_cidrs = [s['CidrBlock'] for s in self['Subnets']]
        except KeyError as k:
            logger.debug("get_available_cidr_block::KeyError::{}".format(k.args[0]))
            if k.args[0] == 'Vpc':
                return 0
            if k.args[0] in ('CidrBlock', 'Subnets'):
                used_cidrs = []
        all_cidrs = [str(c) for c in list(ip_network(cidr_block).subnets(new_prefix=24))]
        cidrs = list(set(all_cidrs) - set(used_cidrs))
        cidrs.sort()
        logger.debug("get_available_cidr_block::Returning::{}".format(cidrs[0]))
        return cidrs[0]

    def get_next_az(self, affinity_group=0):
        logger.debug("get_next_az::Executing")
        try:
            vpc_id = self['Vpc']['VpcId']
            az_zones = self.ec2_client.describe_availability_zones()
            meta = az_zones['ResponseMetadata']
            azs = az_zones['AvailabilityZones']
            logger_meta.debug(
                "get_next_az::describe_availability_zones::meta::{}".format(meta))
            logger_data.debug(
                "get_next_az::describe_availability_zones::data::{}".format(azs))
            az_dict = {a['ZoneName']: 0 for a in azs}
            subnets = self.ec2_client.describe_subnets(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
            meta = subnets['ResponseMetadata']
            logger_meta.debug(
                "get_next_az::describe_subnets::meta::{}".format(meta))
            logger_data.debug(
                "get_next_az::describe_subnets::data::{}".format(subnets['Subnets']))
            for az in [s['AvailabilityZone'] for s in subnets['Subnets']]:
                    az_dict[az] = az_dict[az] + 1
            min_value = min(az_dict.values())
            az = next(k for k, v in az_dict.items() if v == min_value)
            logger.debug("get_next_az::Returning::{}".format(az))
            return az
        except KeyError as k:
            if k.args[0] == 'Vpc':
                logger.error("get_available_cidr_block::Exception::{}".format(k.args[0]))

    def get_af_subnets(self, affinity_group=0):
        logger.debug("get_af_subnets::Executing")
        try:
            subnets = [s['SubnetId'] for s in self['Subnets'] for t in s['Tags'] \
                if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group)]
            logger.debug("get_af_subnets::Returning::{}".format(subnets))
            return subnets
        except KeyError as k:
            logger.error("get_af_subnets::KeyError::{}".format(k.args[0]))

    def get_af_rt(self, affinity_group=0):
        logger.debug("get_af_rt::Executing")
        try:
            rts = next(rt['RouteTableId'] for rt in self['RouteTables'] for t in rt['Tags'] \
                if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group))
            logger.debug("get_af_rt::Returning::{}".format(rts))
        except KeyError as k:
            logger.debug("get_af_rt::NoKey::{}".format(k.args[0]))
            return 0
        return rts

    def get_af_ngw(self, affinity_group=0):
        logger.debug("get_af_ngw::Executing")
        try:
            ngw = next(ngw['NatGatewayId'] for ngw in self['NatGateways'] for t in ngw['Tags'] \
                if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group))
            logger.debug("get_af_ngw: Returning <{}>".format(ngw))
        except KeyError as k:
            logger.debug("get_af_ngw::NoKey::{}".format(k.args[0]))
            return 0
        return ngw


    def create_vpc(self, cidr_block='10.0.0.0/16'):
        logger.info("create_vpc::Executing")
        if 'Vpc' in self:
            self.refresh_vpc()
            return 0
        res = self.ec2_client.create_vpc(CidrBlock = cidr_block)
        meta = res['ResponseMetadata']
        data = res['Vpc']
        self['Vpc'] = data
        logger_meta.debug("create_vpc::create_vpc::meta::{}".format(meta))
        logger_data.debug("create_vpc::create_vpc::data::{}".format(data))
        vpc_id = res['Vpc']['VpcId']
        waiter = self.ec2_client.get_waiter('vpc_exists')
        waiter.wait(VpcIds=[vpc_id])
        waiter = self.ec2_client.get_waiter('vpc_available')
        waiter.wait(VpcIds=[vpc_id])
        res = self.ec2_client.modify_vpc_attribute(
            EnableDnsHostnames={'Value': True}, VpcId=vpc_id)
        meta = res
        logger_data.debug("create_vpc::modify_vpc_attribute::meta::{}".format(meta))
        res = self.ec2_client.modify_vpc_attribute(
            EnableDnsSupport={'Value': True}, VpcId=vpc_id)
        meta = res
        logger_data.debug("create_vpc::modify_vpc_attribute::meta::{}".format(meta))
        self.save()

    def refresh_vpc(self):
        logger.debug("refresh_vpc::Executing")
        vpc_id = self['Vpc']['VpcId']
        res = self.ec2_client.describe_vpcs(VpcIds=[vpc_id])
        meta = res['ResponseMetadata']
        data = res['Vpcs']
        self['Vpc'] = data[0]
        logger_meta.debug("refresh_vpc::describe_vpcs::meta::{}".format(meta))
        logger_data.debug("refresh_vpc::describe_vpcs::data::{}".format(data))
        self.save()

    def delete_vpc(self):
        logger.info("delete_vpc::Executing")
        try:
            vpc_id = self['Vpc']['VpcId']
            logger.debug("delete_vpc::Deleting::{}".format(vpc_id))
            res = self.ec2_client.delete_vpc(VpcId=vpc_id)
            meta = res['ResponseMetadata']
            logger_data.debug("delete_vpc::describe_vpcs::meta::{}".format(meta))
            del(self['Vpc'])
            self.save()
        except KeyError as k:
            logger.debug("delete_vpc::KeyError::{}".format(k.args[0]))


    def create_route_table(self, affinity_group=0):
        logger.info("create_route_table::Executing")
        vpc_id = self['Vpc']['VpcId']
        res = self.ec2_client.create_route_table(VpcId=vpc_id)
        meta = res['ResponseMetadata']
        data = res['RouteTable']
        logger_meta.debug("create_route_table::create_route_table::meta::{}".format(meta))
        logger_data.debug("create_route_table::create_route_table::data::{}".format(data))
        rt_id = data['RouteTableId']
#       waiter = get_waiter('router_exists')
        i=.1
        while True:
            try:
                logger.debug("create_route_table::Tagging::{}".format(rt_id))
                res = self.ec2_client.create_tags(
                    Resources=[rt_id],
                    Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
                logger_meta.debug("create_route_table::create_tags::meta::{}".format(meta))
            except ClientError as c:
                if c.response['Error']['Code'] == 'InvalidRouteTableID.NotFound':
                    logger.debug(
                        "create_route_table::InvalidRouteTableID.NotFound::Trying Again...")
                    self.sleep(i)
                    i=i+.1
                    continue
            break
        self.refresh_route_tables()

    def refresh_route_tables(self):
        logger.debug("refresh_route_tables::Executing")
        try:
            vpc_id = self['Vpc']['VpcId']
            res = self.ec2_client.describe_route_tables(Filters=[
                {'Name': 'vpc-id', 'Values': [vpc_id]},
                {'Name': 'tag-key', 'Values': ['affinity_group']}])
            meta = res['ResponseMetadata']
            data = res['RouteTables']
            logger_meta.debug(
                "refresh_route_tables::describe_route_tables::meta::{}".format(meta))
            logger_data.debug(
                "refresh_route_tables::describe_route_tables::data::{}".format(data))
            self['RouteTables'] = data
            self.save()
        except KeyError as k:
            logger.debug("refresh_route_tables::KeyError::{}".format(k.args[0]))

    def associate_rt_subnet(self, affinity_group=0):
        logger.debug("associate_rt_subnet::Executing")
        rt_id = next(rt['RouteTableId'] for rt in self['RouteTables'] \
            for t in rt['Tags'] if t['Key'] == 'affinity_group' \
            and t['Value'] == str(affinity_group))
        for s in self.get_af_subnets(affinity_group):
            data = self.ec2_client.associate_route_table(RouteTableId=rt_id, SubnetId=s)
            logger_data.debug(
                "associate_rt_subnet::associate_route_table::data::{}".format(data))
        self.sleep()
        self.refresh_route_tables()

    def delete_route_tables(self, affinity_group=0):
        logger.info("delete_route_tables::Executing")
        self.refresh_route_tables()
        try:
            for rt in self['RouteTables']:
                for association in rt['Associations']:
                    meta = self.ec2_client.disassociate_route_table(
                        AssociationId=association['RouteTableAssociationId'])
                    logger_meta.debug(
                        "delete_route_tables::disassociate_route_table::meta::{}".format(meta))
                meta = self.ec2_client.delete_route_table(RouteTableId=rt['RouteTableId'])
                logger_meta.debug(
                    "delete_route_tables::delete_route_tables::meta::{}".format(meta))
            del(self['RouteTables'])
            self.save()
        except KeyError as k:
            logger.debug("delete_route_tables::KeyError::{}".format(k.args[0]))
            return 0
        

    def create_subnet(self, affinity_group=0):
        logger.info("create_subnet::Executing")
        vpc_id = self['Vpc']['VpcId']
        az = self.get_next_az(affinity_group)
        cidr = self.get_available_cidr_block()
        res = self.ec2_client.create_subnet(
            VpcId=vpc_id,
            AvailabilityZone=az,
            CidrBlock=cidr)
        meta = res['ResponseMetadata']
        data = res['Subnet']
        subnet_id = data['SubnetId']
        logger_meta.debug("create_subnet::create_subnet::meta::{}".format(meta))
        logger_data.debug("create_subnet::create_subnet::data::{}".format(data))
        waiter = self.ec2_client.get_waiter('subnet_available')
        i=.1
        while True:
            try:
                waiter.wait(SubnetIds=[subnet_id])
            except WaiterError as w:
                logger.debug(
                    "create_subnet::{}::waiter failed trying again...".format(w.message))
                self.sleep(i)
                i=i+.1
                continue
            break
        res = self.ec2_client.create_tags(
            Resources=[subnet_id],
            Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
        meta = res['ResponseMetadata']
        logger_meta.debug("create_subnet::create_subnet::meta::{}".format(meta))
        self.refresh_subnets()

    def refresh_subnets(self):
        logger.debug("refresh_subnets::Executing")
        vpc_id = self['Vpc']['VpcId']
        res = self.ec2_client.describe_subnets(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]}])
        meta = res['ResponseMetadata']
        data = res['Subnets']
        self['Subnets'] = data
        logger_meta.debug("refresh_subnets::describe_subnets::meta::{}".format(meta))
        logger_data.debug("refresh_subnets::describe_subnets::data::{}".format(data))
        self.save()

    def delete_subnets(self):
        logger.info("delete_subnets::Executing")
        try:
            for s in self['Subnets']:
                res = self.ec2_client.delete_subnet(SubnetId=s['SubnetId'])
                meta = res['ResponseMetadata']
                logger_meta.debug("delete_subnets::describe_subnets::meta::{}".format(meta))
            del(self['Subnets'])
            self.save()
        except KeyError as k:
            logger.debug("delete_subnets::KeyError::{}".format(k.args[0]))
            return 0


    def create_internet_gateway(self, affinity_group=0):
        logger.info("create_internet_gateway::Executing")
        try:
            vpc_id = self['Vpc']['VpcId']
            res = self.ec2_client.create_internet_gateway()
            meta = res['ResponseMetadata']
            data = res['InternetGateway']
            igw_id = data['InternetGatewayId']
            logger_meta.debug(
                "create_internet_gateway::create_internet_gateway::meta::{}".format(meta))
            logger_data.debug(
                "create_internet_gateway::create_internet_gateway::data::{}".format(data))
            rt_id = self.get_af_rt(affinity_group)
            res = self.ec2_client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
            meta = res['ResponseMetadata']
            logger_meta.debug(
                "create_internet_gateway::attach_internet_gateway::meta::{}".format(meta))
            meta = self.ec2_client.create_route(
                DestinationCidrBlock='0.0.0.0/0',
                GatewayId=igw_id,
                RouteTableId=rt_id)
            logger_meta.debug("create_internet_gateway::create_route::meta::{}".format(meta))
            for s in self['Subnets']:
                for t in s['Tags']:
                    if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group):
                        res = self.ec2_client.modify_subnet_attribute(
                            MapPublicIpOnLaunch={'Value': True},
                            SubnetId=s['SubnetId'])
                        meta = res['ResponseMetadata']
                        logger_meta.debug(
                            "create_internet_gateway::attach_internet_gateway::meta::{}".format(meta))
            res = self.ec2_client.create_tags(
                Resources=[igw_id],
                Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
            meta = res['ResponseMetadata']
            logger_meta.debug("create_internet_gateway::create_tags::meta::{}".format(meta))
            self.refresh_route_tables()
            self.refresh_internet_gateway()
        except KeyError as k:
            if k.args[0] == 'Vpc':
                logger.error("create_internet_gateway::KeyError::{}".format(k.args[0]))
            else:
                raise
        except ClientError as c:
            if c.response['Error']['Code'] == 'InvalidParameterValue':
                logger.error("create_internet_gateway::ClientError::{}".format(c.message))
            else:
                raise

    def refresh_internet_gateway(self):
        try:
            logger.debug("refresh_internet_gateway::Executing")
            vpc_id = self['Vpc']['VpcId']
            res = self.ec2_client.describe_internet_gateways(Filters=[
                {'Name': 'attachment.vpc-id', 'Values': [vpc_id]}])
            meta = res['ResponseMetadata']
            data = res['InternetGateways']
            logger_meta.debug(
                "refresh_internet_gateway::describe_internet_gateways::meta::{}".format(meta))
            logger_data.debug(
                "refresh_internet_gateway::describe_internet_gateways::data::{}".format(data))
            self['InternetGateway'] = data[0]
            self.save()
        except KeyError as k:
            logger.error("refresh_internet_gateway::KeyError:{}".format(k.args[0]))
        except IndexError:
            logger.warning("refresh_internet_gateway::IndexError")

    def delete_internet_gateway(self):
        logger.info("delete_internet_gateway::Executing")
        try:
            vpc_id = self['Vpc']['VpcId']
            igw_id = self['InternetGateway']['InternetGatewayId']
            res = self.ec2_client.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
            meta = res['ResponseMetadata']
            logger_meta.debug(
                "delete_internet_gateway::delete_internet_gateways::meta::{}".format(meta))
            self.sleep()
            res = self.ec2_client.delete_internet_gateway(InternetGatewayId=igw_id)
            meta = res['ResponseMetadata']
            logger_meta.debug(
                "delete_internet_gateway::delete_internet_gateways::meta::{}".format(meta))
            del(self['InternetGateway'])
            self.save()
        except KeyError as k:
            logger.debug("delete_internet_gateways::KeyError::{}".format(k.args[0]))
            return 0


    def create_nat_gateway(self, affinity_group=0):
        logger.info("create_nat_gateway::Executing")
        self.refresh_internet_gateway()
        if 'InternetGateway' not in self:
            raise Exception("No Internet Gateway")
        data = self.ec2_client.allocate_address(Domain='vpc')
        eipalloc_id = data['AllocationId']
        logger_data.debug("create_nat_gateway::create_nat_gateway::data::{}".format(data))
        subnet_id = self.get_af_subnets(affinity_group)[0]
        res = self.ec2_client.create_nat_gateway(
            AllocationId=eipalloc_id,
            SubnetId=subnet_id)
        meta = res['ResponseMetadata']
        data = res['NatGateway']
        logger_meta.debug("create_nat_gateway::create_nat_gateway::meta::{}".format(meta))
        logger_data.debug("create_nat_gateway::create_nat_gateway::data::{}".format(data))
        ngw_id = data['NatGatewayId']
        self.sleep()
        logger.debug("create_nat_gateway::waiter::{}".format(ngw_id))
        waiter = self.ec2_client.get_waiter('nat_gateway_available')
        waiter.wait(NatGatewayIds=[ngw_id])
        res = self.ec2_client.create_tags(
            Resources=[ngw_id],
            Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
        meta = res['ResponseMetadata']
        logger_meta.debug("create_nat_gateway::create_tags::meta::{}".format(meta))
        self.refresh_nat_gateways()

    def create_nat_default_route(self, rt_affinity_group, nat_affinity_group=0):
        logger.debug("create_nat_default_route::Executing")
        ngw_id = self.get_af_ngw(nat_affinity_group)
        rt_id = self.get_af_rt(rt_affinity_group)
        while True:
            try:
                res = self.ec2_client.create_route(
                    DestinationCidrBlock='0.0.0.0/0',
                    NatGatewayId=ngw_id,
                    RouteTableId=rt_id)
                meta = res['ResponseMetadata']
                logger_meta.debug(
                   "create_nat_default_route::create_route::meta::{}".format(meta))
                break
            except ClientError as c:
                logger.warning(
                    "create_nat_default_route::ClientError::{}".format(
                        c.response['Error']['Message']))
                if c.response['Error']['Code'] == 'RouteAlreadyExists':
                    res = self.ec2_client.delete_route(
                        DestinationCidrBlock='0.0.0.0/0',
                        RouteTableId=rt_id)
                    meta = res['ResponseMetadata']
                    logger_meta.debug(
                        "create_nat_default_route::delete_route::meta::{}".format(meta))
                    continue
        self.refresh_route_tables()
        self.sleep()

    def refresh_nat_gateways(self):
        logger.debug("refresh_nat_gateways::Executing")
        vpc_id = self['Vpc']['VpcId']
        res = self.ec2_client.describe_nat_gateways(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]},
            {'Name': 'state', 'Values': ['pending', 'available']}])
        meta = res['ResponseMetadata']
        data = res['NatGateways']
        logger_meta.debug("refresh_nat_gateway::describe_nat_gateways::meta::{}".format(meta))
        logger_data.debug("refresh_nat_gateway::describe_nat_gateways::data::{}".format(data))
        self['NatGateways'] = data
        self.save()

    def delete_nat_gateways(self):
        logger.info("delete_nat_gateway::Executing")
        try:
            eipalloc_ids = []
            for n in self['NatGateways']:
                ngw_id = n['NatGatewayId']
                for a in n['NatGatewayAddresses']:
                    eipalloc_ids.append(a['AllocationId'])
                res = self.ec2_client.delete_nat_gateway(NatGatewayId=ngw_id)
                meta = res['ResponseMetadata']
                logger_meta.debug(
                    "delete_nat_gateway::delete_nat_gateway::meta::{}".format(meta))
                logger.debug("delete_nat_gateway::waiter::{}".format(ngw_id))
                #Create a waiter
                while self.ec2_client.describe_nat_gateways(NatGatewayIds=[ngw_id])\
                    ['NatGateways'][0]['State'] != 'deleted': self.sleep(5)
                for rt in self['RouteTables']:
                    for r in rt['Routes']:
                        try:
                            logger.debug("Route: {}".format(r))
                            if r['NatGatewayId'] == ngw_id:
                                res = self.ec2_client.delete_route(
                                    DestinationCidrBlock='0.0.0.0/0',
                                    RouteTableId=rt['RouteTableId'])
                                meta = res['ResponseMetadata']
                                logger_meta.debug(
                                    "delete_nat_gateway::delete_route::meta::{}".format(meta))
                                break
                        except KeyError as k:
                            logger.debug("delete_nat_gateway::KeyError::{}".format(k.args[0]))
                            continue
            for a in eipalloc_ids:
                res = self.ec2_client.release_address(AllocationId=a)
                meta = res['ResponseMetadata']
                logger_meta.debug("delete_nat_gateway::release_address::meta::{}".format(meta))
            del(self['NatGateways'])
            self.save()
        except KeyError as k:
            logger.debug("delete_nat_gateway::KeyError::{}".format(k.args[0]))
