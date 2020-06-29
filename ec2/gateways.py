from subfish.base import AwsBase

import re, json
import logging
from ipaddress import ip_network
from jinja2 import Template
from botocore.exceptions import ClientError, WaiterError

logger = logging.getLogger(__name__)

class AwsGW(AwsBase):

    def __init__(self, path, **kwargs):
        super().__init__(path=path)
        logger.debug("__init__::Executing")
        self.ec2_client = self.session.create_client('ec2')

    def create_internet_gateway(self, affinity_group=0):
        logger.info("create_internet_gateway::Executing")
        try:
            vpc_id = self['Vpc']['VpcId']
            res = self.ec2_client.create_internet_gateway()
            meta = res['ResponseMetadata']
            data = res['InternetGateway']
            igw_id = data['InternetGatewayId']
            logger.debug(
                "create_internet_gateway::create_internet_gateway::meta::{}".format(meta))
            logger.debug(
                "create_internet_gateway::create_internet_gateway::data::{}".format(data))
            rt_id = self.get_af_rt(affinity_group)
            res = self.ec2_client.attach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
            meta = res['ResponseMetadata']
            logger.debug(
                "create_internet_gateway::attach_internet_gateway::meta::{}".format(meta))
            meta = self.ec2_client.create_route(
                DestinationCidrBlock='0.0.0.0/0',
                GatewayId=igw_id,
                RouteTableId=rt_id)
            logger.debug("create_internet_gateway::create_route::meta::{}".format(meta))
            for s in self['Subnets']:
                for t in s['Tags']:
                    if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group):
                        res = self.ec2_client.modify_subnet_attribute(
                            MapPublicIpOnLaunch={'Value': True},
                            SubnetId=s['SubnetId'])
                        meta = res['ResponseMetadata']
                        logger.debug(
                            "create_internet_gateway::attach_internet_gateway::meta::{}".format(meta))
            res = self.ec2_client.create_tags(
                Resources=[igw_id],
                Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
            meta = res['ResponseMetadata']
            logger.debug("create_internet_gateway::create_tags::meta::{}".format(meta))
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
            logger.debug(
                "refresh_internet_gateway::describe_internet_gateways::meta::{}".format(meta))
            logger.debug(
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
            logger.debug(
                "delete_internet_gateway::delete_internet_gateways::meta::{}".format(meta))
            self.sleep()
            res = self.ec2_client.delete_internet_gateway(InternetGatewayId=igw_id)
            meta = res['ResponseMetadata']
            logger.debug(
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
        logger.debug("create_nat_gateway::create_nat_gateway::data::{}".format(data))
        subnet_id = self.get_af_subnets(affinity_group)[0]
        res = self.ec2_client.create_nat_gateway(
            AllocationId=eipalloc_id,
            SubnetId=subnet_id)
        meta = res['ResponseMetadata']
        data = res['NatGateway']
        logger.debug("create_nat_gateway::create_nat_gateway::meta::{}".format(meta))
        logger.debug("create_nat_gateway::create_nat_gateway::data::{}".format(data))
        ngw_id = data['NatGatewayId']
        self.sleep()
        logger.info("create_nat_gateway::waiter::{}".format(ngw_id))
        waiter = self.ec2_client.get_waiter('nat_gateway_available')
        waiter.wait(NatGatewayIds=[ngw_id])
        res = self.ec2_client.create_tags(
            Resources=[ngw_id],
            Tags=[{'Key': 'affinity_group', 'Value': str(affinity_group)}])
        meta = res['ResponseMetadata']
        logger.debug("create_nat_gateway::create_tags::meta::{}".format(meta))
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
                logger.debug(
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
                    logger.debug(
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
        logger.debug("refresh_nat_gateway::describe_nat_gateways::meta::{}".format(meta))
        logger.debug("refresh_nat_gateway::describe_nat_gateways::data::{}".format(data))
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
                logger.debug(
                    "delete_nat_gateway::delete_nat_gateway::meta::{}".format(meta))
                logger.info("delete_nat_gateway::waiter::{}".format(ngw_id))
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
                                logger.debug(
                                    "delete_nat_gateway::delete_route::meta::{}".format(meta))
                                break
                        except KeyError as k:
                            logger.debug("delete_nat_gateway::KeyError::{}".format(k.args[0]))
                            continue
            for a in eipalloc_ids:
                res = self.ec2_client.release_address(AllocationId=a)
                meta = res['ResponseMetadata']
                logger.debug("delete_nat_gateway::release_address::meta::{}".format(meta))
            del(self['NatGateways'])
            self.save()
        except KeyError as k:
            logger.debug("delete_nat_gateway::KeyError::{}".format(k.args[0]))
