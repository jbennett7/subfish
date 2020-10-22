from subfish.base import AwsBase

import re, json
import logging
from ipaddress import ip_network
from jinja2 import Template
from botocore.exceptions import ClientError, WaiterError

logger = logging.getLogger(__name__)

class AwsVpc(AwsBase):
    """
    AwsVpc object represents the methods used to build out an AWS VPC environment.

    Methods:
    __init__ - initialize
    get_available_cidr_block - INTERNAL; returns an available cidr block to use for a subnet.
    get_next_az - INTERNAL; returns next unused availability zone.
    get_af_subnets - INTERNAL; returns the subnets associated with an affinity group.
    get_at_rt - INTERNAL; returns the route tables associated with an affinity group.
    get_af_ngw - INTERNAL; returns the NAT gateways associated with an affinity group.
    create_vpc - USER; Creates a VPC with a cidr block.
    refresh_vpc - INTERNAL; refreshes the dictionary with the VPC ID.
    delete_vpc - USER; Deletes the VPC in the dictionary.
    create_route_table - USER; creates a route table for an affinity group.
    refresh_route_tables - INTERNAL; refreshes the dictionary with route tables associated with
                                     the VPC.
    associate_rt_subnet - INTERNAL; associate the route table with the subnet.
    delete_route_tables - USER; delete all route tables in the dictionary.
    create_subnet - USER; create a subnet for an affinity group.
    refresh_subnets - INTERNAL; updates the dictionary with the subnets associated with the VPC.
    delte_subnets - USER; deletes all subnets in the dictionary.
    """

    def __init__(self, path, **kwargs):
        logger.debug("__init__::Executing")
        super().__init__(path, **kwargs)
        self.ec2_client = self.session.create_client('ec2')

    def get_available_cidr_block(self):
        logger.debug("get_available_cidr_block::Executing")
        try:
            cidr_block = self['Vpc']['CidrBlock']
            used_cidrs = [s['CidrBlock'] for s in self['Subnets']]
        except KeyError as k:
            logger.debug("get_available_cidr_block::KeyError::%s", k.args[0])
            if k.args[0] == 'Vpc':
                return 0
            if k.args[0] in ('CidrBlock', 'Subnets'):
                used_cidrs = []
        all_cidrs = [str(c) for c in list(ip_network(cidr_block).subnets(new_prefix=24))]
        cidrs = list(set(all_cidrs) - set(used_cidrs))
        cidrs.sort()
        logger.debug("get_available_cidr_block::Returning::%s", cidrs[0])
        return cidrs[0]

    def get_next_az(self, affinity_group=0):
        logger.debug("get_next_az::Executing")
        try:
            vpc_id = self['Vpc']['VpcId']
            az_zones = self.ec2_client.describe_availability_zones()
            meta = az_zones['ResponseMetadata']
            azs = az_zones['AvailabilityZones']
            logger.debug(
                "get_next_az::describe_availability_zones::meta::%s", meta)
            logger.debug(
                "get_next_az::describe_availability_zones::data::%s", azs)
            az_dict = {a['ZoneName']: 0 for a in azs}
            subnets = self.ec2_client.describe_subnets(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
            meta = subnets['ResponseMetadata']
            logger.debug(
                "get_next_az::describe_subnets::meta::%s", meta)
            logger.debug(
                "get_next_az::describe_subnets::data::%s", subnets['Subnets'])
            for az in [s['AvailabilityZone'] for s in subnets['Subnets']]:
                    az_dict[az] = az_dict[az] + 1
            min_value = min(az_dict.values())
            az = next(k for k, v in az_dict.items() if v == min_value)
            logger.debug("get_next_az::Returning::%s", az)
            return az
        except KeyError as k:
            if k.args[0] == 'Vpc':
                logger.error("get_available_cidr_block::Exception::%s", k.args[0])

    def get_af_subnets(self, affinity_group=0):
        logger.debug("get_af_subnets::Executing")
        try:
            subnets = [s['SubnetId'] for s in self['Subnets'] for t in s['Tags'] \
                if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group)]
            logger.debug("get_af_subnets::Returning::%s", subnets)
            return subnets
        except KeyError as k:
            logger.error("get_af_subnets::KeyError::%s", k.args[0])

    def get_af_rt(self, affinity_group=0):
        logger.debug("get_af_rt::Executing")
        try:
            rts = next(rt['RouteTableId'] for rt in self['RouteTables'] for t in rt['Tags'] \
                if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group))
            logger.debug("get_af_rt::Returning::%s", rts)
        except KeyError as k:
            logger.debug("get_af_rt::NoKey::%s", k.args[0])
            return 0
        return rts

    def get_af_ngw(self, affinity_group=0):
        logger.debug("get_af_ngw::Executing")
        try:
            ngw = next(ngw['NatGatewayId'] for ngw in self['NatGateways'] for t in ngw['Tags'] \
                if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group))
            logger.debug("get_af_ngw: Returning <{}>".format(ngw))
        except KeyError as k:
            logger.debug("get_af_ngw::NoKey::%s", k.args[0])
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
        logger.debug("create_vpc::create_vpc::meta::%s", meta)
        logger.debug("create_vpc::create_vpc::data::%s", data)
        vpc_id = res['Vpc']['VpcId']
        waiter = self.ec2_client.get_waiter('vpc_exists')
        waiter.wait(VpcIds=[vpc_id])
        waiter = self.ec2_client.get_waiter('vpc_available')
        waiter.wait(VpcIds=[vpc_id])
        res = self.ec2_client.modify_vpc_attribute(
            EnableDnsHostnames={'Value': True}, VpcId=vpc_id)
        meta = res
        logger.debug("create_vpc::modify_vpc_attribute::meta::%s", meta)
        res = self.ec2_client.modify_vpc_attribute(
            EnableDnsSupport={'Value': True}, VpcId=vpc_id)
        meta = res
        logger.debug("create_vpc::modify_vpc_attribute::meta::%s", meta)
        self.save()

    def refresh_vpc(self):
        logger.debug("refresh_vpc::Executing")
        vpc_id = self['Vpc']['VpcId']
        res = self.ec2_client.describe_vpcs(VpcIds=[vpc_id])
        meta = res['ResponseMetadata']
        data = res['Vpcs']
        self['Vpc'] = data[0]
        logger.debug("refresh_vpc::describe_vpcs::meta::%s", meta)
        logger.debug("refresh_vpc::describe_vpcs::data::%s", data)
        self.save()

    def delete_vpc(self):
        logger.info("delete_vpc::Executing")
        try:
            vpc_id = self['Vpc']['VpcId']
            logger.debug("delete_vpc::Deleting::%s", vpc_id)
            res = self.ec2_client.delete_vpc(VpcId=vpc_id)
            meta = res['ResponseMetadata']
            logger.debug("delete_vpc::describe_vpcs::meta::%s", meta)
            del(self['Vpc'])
            self.save()
        except KeyError as k:
            logger.debug("delete_vpc::KeyError::%s", k.args[0])


    def create_route_table(self, affinity_group=0):
        logger.info("create_route_table::Executing")
        vpc_id = self['Vpc']['VpcId']
        res = self.ec2_client.create_route_table(VpcId=vpc_id)
        meta = res['ResponseMetadata']
        data = res['RouteTable']
        logger.debug("create_route_table::create_route_table::meta::%s", meta)
        logger.debug("create_route_table::create_route_table::data::%s", data)
        rt_id = data['RouteTableId']
#       waiter = get_waiter('router_exists')
        i=.1
        while True:
            try:
                logger.debug("create_route_table::Tagging::%s", rt_id)
                res = self.ec2_client.create_tags(
                    Resources=[rt_id],
                    Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
                logger.debug("create_route_table::create_tags::meta::%s", meta)
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
            logger.debug(
                "refresh_route_tables::describe_route_tables::meta::%s", meta)
            logger.debug(
                "refresh_route_tables::describe_route_tables::data::%s", data)
            self['RouteTables'] = data
            self.save()
        except KeyError as k:
            logger.debug("refresh_route_tables::KeyError::%s", k.args[0])

    def associate_rt_subnet(self, affinity_group=0):
        logger.debug("associate_rt_subnet::Executing")
        rt_id = next(rt['RouteTableId'] for rt in self['RouteTables'] \
            for t in rt['Tags'] if t['Key'] == 'affinity_group' \
            and t['Value'] == str(affinity_group))
        for s in self.get_af_subnets(affinity_group):
            data = self.ec2_client.associate_route_table(RouteTableId=rt_id, SubnetId=s)
            logger.debug(
                "associate_rt_subnet::associate_route_table::data::%s", data)
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
                    logger.debug(
                        "delete_route_tables::disassociate_route_table::meta::%s", meta)
                meta = self.ec2_client.delete_route_table(RouteTableId=rt['RouteTableId'])
                logger.debug(
                    "delete_route_tables::delete_route_tables::meta::%s", meta)
            del(self['RouteTables'])
            self.save()
        except KeyError as k:
            logger.debug("delete_route_tables::KeyError::%s", k.args[0])
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
        logger.debug("create_subnet::create_subnet::meta::%s", meta)
        logger.debug("create_subnet::create_subnet::data::%s", data)
        waiter = self.ec2_client.get_waiter('subnet_available')
        i=.1
        while True:
            try:
                waiter.wait(SubnetIds=[subnet_id])
            except WaiterError as w:
                print(w.args)
                logger.debug(
                    "create_subnet::{}::waiter failed trying again...".format(w.args[0]))
                self.sleep(i)
                i=i+.1
                continue
            break
        res = self.ec2_client.create_tags(
            Resources=[subnet_id],
            Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
        meta = res['ResponseMetadata']
        logger.debug("create_subnet::create_subnet::meta::%s", meta)
        self.refresh_subnets()

    def refresh_subnets(self):
        logger.debug("refresh_subnets::Executing")
        vpc_id = self['Vpc']['VpcId']
        res = self.ec2_client.describe_subnets(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]}])
        meta = res['ResponseMetadata']
        data = res['Subnets']
        self['Subnets'] = data
        logger.debug("refresh_subnets::describe_subnets::meta::%s", meta)
        logger.debug("refresh_subnets::describe_subnets::data::%s", data)
        self.save()

    def delete_subnets(self):
        logger.info("delete_subnets::Executing")
        try:
            for s in self['Subnets']:
                res = self.ec2_client.delete_subnet(SubnetId=s['SubnetId'])
                meta = res['ResponseMetadata']
                logger.debug("delete_subnets::describe_subnets::meta::%s", meta)
            del(self['Subnets'])
            self.save()
        except KeyError as k:
            logger.debug("delete_subnets::KeyError::%s", k.args[0])
            return 0
