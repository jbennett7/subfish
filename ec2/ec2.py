from subfish.logger import Logger
from subfish.ec2.vpc import AwsVpc

from os import listdir
import re, json
from uuid import uuid1
from jinja2 import Template

from botocore.exceptions import ClientError, WaiterError

LOGLEVEL='info'
logger = Logger(__name__)
logger.set_level(LOGLEVEL)

# Logger for AWS API Response metadata
logger_meta = Logger("{}::AWS_API_META".format(__name__))
logger_meta.set_level(LOGLEVEL)

# Logger for AWS API returns
logger_data = Logger("{}::AWS_API".format(__name__))
logger_data.set_level(LOGLEVEL)

RELATIVE_LAUNCH_TEMPLATES="launch_templates"
RELATIVE_SG_AUTHORIZATIONS="sg_authorizations"
RELATIVE_USER_DATA="user_data"

class AwsEc2(AwsVpc):

    def __init__(self, path, ec2_path="."):
        super().__init__(path=path)
        self.ec2_client = self.session.create_client('ec2')
        self.sg_authorization_path = "{}/{}".format(ec2_path,RELATIVE_SG_AUTHORIZATIONS)
        logger.debug("__init__::sg_authorization_path::{}".format(self.sg_authorization_path))
        self.launch_templates = "{}/{}".format(ec2_path,RELATIVE_LAUNCH_TEMPLATES)
        self.user_data = "{}/{}".format(ec2_path,RELATIVE_USER_DATA)

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
            logger_data.debug(
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
        logger_meta.debug(
            "refresh_security_groups::describe_security_groups::meta::{}".format(meta))
        logger_data.debug(
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
            logger_meta.debug(
                "authorize_security_group_policies::authorize_security_group_ingresss::meta::{}".format(meta))
        if "{}_egress.json.j2".format(sg_name) in listdir(self.sg_authorization_path):
            f = open("{}/{}_egress.json.j2".format(self.sg_authorization_path, sg_name))
            data = f.read()
            res = self.ec2_client.authorize_security_group_egress(
                GroupId=sg_id,
                IpPermissions=json.loads(Template(data).render(jinja2_vars)))
            meta = res['ResponseMetadata']
            logger_meta.debug(
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
                    logger_meta.debug(
                        "delete_security_groups::revoke_security_group_ingresss::meta::{}".format(meta))
                if sg['IpPermissionsEgress']:
                    res = self.ec2_client.revoke_security_group_egress(
                        GroupId=sg['GroupId'],
                        IpPermissions=sg['IpPermissionsEgress'])
                    meta = res['ResponseMetadata']
                    logger_meta.debug(
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

    def create_launch_template(self, launch_template_name, jinja2_vars={}):
        logger.info("create_launch_template::Executing")
        try:
            idemp_token = str(uuid1())
            regex = re.compile(r'\.json\.j2')
            f = open("{}/{}.json.j2".format(self.launch_templates, launch_template_name))
            data = f.read()
            res = self.ec2_client.create_launch_template(
                ClientToken = idemp_token,
                LaunchTemplateName = launch_template_name,
                VersionDescription = launch_template_name,
                LaunchTemplateData=json.loads(Template(data).render(jinja2_vars)))
            meta = res['ResponseMetadata']
            data = res['LaunchTemplate']
            logger_meta.debug(
                "create_launch_template::create_launch_template::meta::{}".format(meta))
            logger_data.debug(
                "create_launch_template::create_launch_template::data::{}".format(data))
            self.refresh_launch_templates()
        except ClientError as c:
            if c.response['Error']['Code'] == 'InvalidLaunchTemplateName.AlreadyExistsException':
                logger.warning(
                    "create_launch_template::ClientError::{}".format(
                        c.response['Error']['Message']))

    def modify_launch_template(self, launch_template_name, jinja2_vars={}):
        logger.debug("create_launch_template::Executing")
        idemp_token = str(uuid1())
        regex = re.compile(r'\.json\.j2')
        f = open("{}/{}.json.j2".format(self.launch_templates, launch_template_name))
        data = f.read()
        res = self.ec2_client.create_launch_template_version(
            ClientToken = idemp_token,
            LaunchTemplateName = launch_template_name,
            VersionDescription = launch_template_name,
            LaunchTemplateData=json.loads(Template(data).render(jinja2_vars)))
        meta = res['ResponseMetadata']
        data = res['LaunchTemplateVersion']
        logger_meta.debug(
            "modify_launch_template::create_launch_template_version::meta::{}".format(meta))
        logger_data.debug(
            "modify_launch_template::create_launch_template_version::data::{}".format(data))
        idemp_token2 = str(uuid1())
        res = self.ec2_client.modify_launch_template(
            ClientToken = idemp_token2,
            LaunchTemplateName = launch_template_name,
            DefaultVersion = str(data['VersionNumber']))
        meta = res['ResponseMetadata']
        data = res['LaunchTemplate']
        logger_meta.debug(
            "modify_launch_template::modify_launch_template::meta::{}".format(meta))
        logger_data.debug(
            "modify_launch_template::modify_launch_template::data::{}".format(data))
        self.refresh_launch_templates()

    def refresh_launch_templates(self):
        logger.debug("refresh_launch_templates::Executing")
        regex = re.compile(r'(\w+)\.json(\.j2)*')
        lts = []
        for f in listdir(self.launch_templates):
            r = regex.search(f)
            if r:
                lts.append(r.group(1))
        logger.debug("refresh_launch_templates::launch_templates::{}".format(lts))
        res = self.ec2_client.describe_launch_templates(Filters=[
            {'Name': 'launch-template-name', 'Values': lts}])
        meta = res['ResponseMetadata']
        data = res['LaunchTemplates']
        logger_meta.debug(
            "refresh_launch_templates::describe_launch_templates::meta::{}".format(meta))
        logger_data.debug(
            "refresh_launch_templates::describe_launch_templates::data::{}".format(data))
        self['LaunchTemplates'] = data
        self.save()

    def delete_launch_templates(self):
        logger.info("delete_launch_templates::Executing")
        for lt in self['LaunchTemplates']:
            res = self.ec2_client.delete_launch_template(
                LaunchTemplateId=lt['LaunchTemplateId'])
            meta = res['ResponseMetadata']
            data = res['LaunchTemplate']
            logger_meta.debug(
                "delete_launch_templates::delete_launch_template::{}".format(meta))
            logger_data.debug(
                "delete_launch_templates::delete_launch_template::{}".format(data))
        del(self['LaunchTemplates'])
        self.save()


    def run_instance(self, instance_template, affinity_group=0):
        logger.debug("run_instance::Executing")
        vpc_id = self['Vpc']['VpcId']
        subnet_ids = [s['SubnetId'] for s in self['Subnets'] for t in s['Tags'] \
            if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group)]
        sg_ids = next(g['GroupId'] for g in self['SecurityGroups'] if g['GroupName'] == 'bastion')
        res = self.ec2_client.describe_instances(Filters=[
            {'Name': 'subnet-id', 'Values': subnet_ids}])
        meta = res['ResponseMetadata']
        data = res['Reservations']
        logger_meta.debug(
            "run_instances::describe_instances::meta::{}".format(meta))
        logger_data.debug(
            "run_instances::describe_instances::data::{}".format(data))
        res = self.ec2_client.run_instances(LaunchTemplate={
            'LaunchTemplateName': instance_template},
            SecurityGroupIds=[sg_ids],
            SubnetId=subnet_ids[0],
            MinCount=1,
            MaxCount=1)
        meta = res['ResponseMetadata']
        data = res['Instances']
        logger_meta.debug(
            "run_instances::run_instances::meta::{}".format(meta))
        logger_data.debug(
            "run_instances::run_instances::data::{}".format(data))
        inst_id = [i['InstanceId'] for i in data]
        waiter = self.ec2_client.get_waiter('instance_exists')
        waiter.wait(InstanceIds=inst_id)
        waiter = self.ec2_client.get_waiter('instance_running')
        waiter.wait(InstanceIds=inst_id)
        self.refresh_instances()

    def refresh_instances(self):
        logger.debug("refresh_instances::Executing")
        vpc_id = self['Vpc']['VpcId']
        res = self.ec2_client.describe_instances(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]}])
        meta = res['ResponseMetadata']
        data = res['Reservations'][0]
        logger_meta.debug(
            "refresh_instances::run_instances::meta::{}".format(meta))
        logger_data.debug(
            "refresh_instances::run_instances::data::{}".format(data))
        self['Instances'] = data['Instances']
        self.save()

    def terminate_instances(self):
        logger.debug("terminate_instances::Executing")
        inst_id = [i['InstanceId'] for i in self['Instances']]
        res = self.ec2_client.terminate_instances(InstanceIds=inst_id)
        meta = res['ResponseMetadata']
        data = res['TerminatingInstances']
        logger_meta.debug(
            "terminate_instances::terminate_instances::meta::{}".format(meta))
        logger_data.debug(
            "terminate_instances::terminate_instances::data::{}".format(data))
        waiter = self.ec2_client.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=inst_id)
        self.save()
