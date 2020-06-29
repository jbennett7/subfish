from subfish.base import AwsBase

import logging
from os import listdir
import re, json
from uuid import uuid1
from jinja2 import Template

from botocore.exceptions import ClientError, WaiterError

RELATIVE_LAUNCH_TEMPLATES="launch_templates"
RELATIVE_SG_AUTHORIZATIONS="sg_authorizations"
RELATIVE_USER_DATA="user_data"

logger = logging.getLogger(__name__)

class AwsSG(AwsBase):

    def __init__(self, path, config_path):
        logger.info("__init__::Executing")
        super().__init__(path)
        self.ec2_client = self.session.create_client('ec2')
        self.sg_authorization_path = "{}/{}".format(config_path,RELATIVE_SG_AUTHORIZATIONS)
        logger.debug("__init__::sg_authorization_path::{}".format(self.sg_authorization_path))

    def create_security_group(self, sg_name):
        logger.info("create_security_group::Executing")
        vpc_id = self['Vpc']['VpcId']
        try:
            res = self.ec2_client.create_security_group(
                Description=sg_name,
                GroupName=sg_name,
                VpcId=vpc_id)
            data = res
            group_id = res
            logger.debug(
                "create_security_group::create_security_group::data::{}".format(data))
            self.refresh_security_groups()
            self.sleep()
        except ClientError as c:
            if c.response['Error']['Code'] == 'InvalidGroup.Duplicate':
                pass
            else:
                raise
        self.refresh_security_groups()

    def refresh_security_groups(self):
        logger.debug("refresh_security_group::Executing")
        vpc_id = self['Vpc']['VpcId']
        res = self.ec2_client.describe_security_groups(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}])
        meta = res['ResponseMetadata']
        data = res['SecurityGroups']
        logger.debug(
            "refresh_security_groups::describe_security_groups::meta::{}".format(meta))
        logger.debug(
            "refresh_security_groups::describe_security_groups::data::{}".format(data))
        self['SecurityGroups'] = [s for s in data if s['GroupName'] != 'default']
        self.save()

    def authorize_security_group_policies(self, sg_name, jinja2_vars={}):
        logger.debug("authorize_security_group_policies::Executing")
        sg_id = next(sg['GroupId'] for sg in self['SecurityGroups'] \
            if sg['GroupName'] == sg_name)
        if "{}_ingress.json.j2".format(sg_name) in listdir(self.sg_authorization_path):
            f = open("{}/{}_ingress.json.j2".format(self.sg_authorization_path, sg_name))
            data = f.read()
            res = self.ec2_client.authorize_security_group_ingress(
                GroupId=sg_id,
                IpPermissions=json.loads(Template(data).render(jinja2_vars)))
            meta = res['ResponseMetadata']
            logger.debug(
                "authorize_security_group_policies::authorize_security_group_ingresss::meta::{}".format(meta))
        if "{}_egress.json.j2".format(sg_name) in listdir(self.sg_authorization_path):
            f = open("{}/{}_egress.json.j2".format(self.sg_authorization_path, sg_name))
            data = f.read()
            res = self.ec2_client.authorize_security_group_egress(
                GroupId=sg_id,
                IpPermissions=json.loads(Template(data).render(jinja2_vars)))
            meta = res['ResponseMetadata']
            logger.debug(
                "authorize_security_group_policies::authorize_security_group_egresss::meta::{}".format(meta))
        self.refresh_security_groups()

    def delete_security_groups(self):
        logger.info("delete_security_group::Executing")
        try:
            for sg in [s for s in self['SecurityGroups'] if s['GroupName'] != 'default']:
                if sg['IpPermissions']:
                    res = self.ec2_client.revoke_security_group_ingress(
                        GroupId=sg['GroupId'],
                        IpPermissions=sg['IpPermissions'])
                    meta = res['ResponseMetadata']
                    logger.debug(
                        "delete_security_groups::revoke_security_group_ingresss::meta::{}".format(meta))
                if sg['IpPermissionsEgress']:
                    res = self.ec2_client.revoke_security_group_egress(
                        GroupId=sg['GroupId'],
                        IpPermissions=sg['IpPermissionsEgress'])
                    meta = res['ResponseMetadata']
                    logger.debug(
                        "delete_security_groups::revoke_security_group_egresss::meta::{}".format(meta))
                    self.ec2_client.delete_security_group(GroupId=sg['GroupId'])
            del(self['SecurityGroups'])
        except ClientError as c:
            if c.response['Error']['Code'] == 'InvalidGroup.NotFound':
                logger.debug("delete_security_group")
                pass
            else:
                raise
        except KeyError as k:
            if k.args[0] == 'SecurityGroups':
                pass
            else:
                raise
        self.save()
