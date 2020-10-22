from subfish.base import AwsBase

from os import listdir, remove
import re, json
from uuid import uuid1
from jinja2 import Template
import logging

from botocore.exceptions import ClientError, WaiterError

logger = logging.getLogger(__name__)

RELATIVE_LAUNCH_TEMPLATES="launch_templates"
RELATIVE_SG_AUTHORIZATIONS="sg_authorizations"
RELATIVE_USER_DATA="user_data"

class AwsCompute(AwsBase):

    def __init__(self, path, config_path="."):
        logger.info("__init__::Executing")
        super().__init__(path)
        self.ec2_client = self.session.create_client('ec2')
        self.launch_templates_path = "{}/{}".format(config_path,RELATIVE_LAUNCH_TEMPLATES)
        logger.debug("__init__::launch_templates_path::{}".format(self.launch_templates_path))
        self.user_data_path = "{}/{}".format(config_path,RELATIVE_USER_DATA)
        logger.debug("__init__::user_data_path::{}".format(self.user_data_path))

    def create_launch_template(self, launch_template_name, jinja2_vars={}):
        logger.info("create_launch_template::Executing")
        try:
            idemp_token = str(uuid1())
            key_name = idemp_token
            try:
                res = self.ec2_client.create_key_pair(KeyName=key_name)
                key_material = res['KeyMaterial']
                f = open("./.instance_key-{}".format(key_name), 'w')
                f.write(key_material)
                jinja2_vars['key_name'] = key_name
            except ClientError as c:
                print(c)
            regex = re.compile(r'\.json\.j2')
            f = open("{}/{}.json.j2".format(self.launch_templates_path, launch_template_name))
            data = f.read()
            res = self.ec2_client.create_launch_template(
                ClientToken = idemp_token,
                LaunchTemplateName = launch_template_name,
                VersionDescription = launch_template_name,
                LaunchTemplateData=json.loads(Template(data).render(jinja2_vars)))
            meta = res['ResponseMetadata']
            data = res['LaunchTemplate']
            logger.debug(
                "create_launch_template::create_launch_template::meta::{}".format(meta))
            logger.debug(
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
        logger.debug(
            "modify_launch_template::create_launch_template_version::meta::{}".format(meta))
        logger.debug(
            "modify_launch_template::create_launch_template_version::data::{}".format(data))
        idemp_token2 = str(uuid1())
        res = self.ec2_client.modify_launch_template(
            ClientToken = idemp_token2,
            LaunchTemplateName = launch_template_name,
            DefaultVersion = str(data['VersionNumber']))
        meta = res['ResponseMetadata']
        data = res['LaunchTemplate']
        logger.debug(
            "modify_launch_template::modify_launch_template::meta::{}".format(meta))
        logger.debug(
            "modify_launch_template::modify_launch_template::data::{}".format(data))
        self.refresh_launch_templates()

    def refresh_launch_templates(self):
        logger.debug("refresh_launch_templates::Executing")
        regex = re.compile(r'(\w+)\.json(\.j2)*')
        lts = []
        for f in listdir(self.launch_templates_path):
            r = regex.search(f)
            if r:
                lts.append(r.group(1))
        logger.debug("refresh_launch_templates::launch_templates::{}".format(lts))
        res = self.ec2_client.describe_launch_templates(Filters=[
            {'Name': 'launch-template-name', 'Values': lts}])
        meta = res['ResponseMetadata']
        data = res['LaunchTemplates']
        logger.debug(
            "refresh_launch_templates::describe_launch_templates::meta::{}".format(meta))
        logger.debug(
            "refresh_launch_templates::describe_launch_templates::data::{}".format(data))
        self['LaunchTemplates'] = data
        self.save()

    def delete_launch_templates(self):
        logger.info("delete_launch_templates::Executing")
        try:
            for lt in self['LaunchTemplates']:
                res = self.ec2_client.describe_launch_template_versions(
                        LaunchTemplateId=lt['LaunchTemplateId'], Versions=['$Latest'])
                key_name = res['LaunchTemplateVersions'][0]['LaunchTemplateData']['KeyName']
                try:
                    res = self.ec2_client.delete_key_pair(KeyName=key_name)
                    remove("./.instance_key-{}".format(key_name))
                except ClientError as c:
                    print(c)
                res = self.ec2_client.delete_launch_template(
                    LaunchTemplateId=lt['LaunchTemplateId'])
                meta = res['ResponseMetadata']
                data = res['LaunchTemplate']
                logger.info(
                    "delete_launch_templates::delete_launch_template::{}".format(meta))
                logger.info(
                    "delete_launch_templates::delete_launch_template::{}".format(data))
            del(self['LaunchTemplates'])
            self.save()
        except KeyError as k:
            logger.debug("delete_launch_templates::KeyError::%s", k.args[0])

    def run_instance(self, instance_template, affinity_group=0):
        logger.info("run_instance::Executing")
        vpc_id = self['Vpc']['VpcId']
        subnet_ids = [s['SubnetId'] for s in self['Subnets'] for t in s['Tags'] \
            if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group)]
        sg_ids = next(g['GroupId'] for g in self['SecurityGroups'] if g['GroupName'] == 'bastion')
        res = self.ec2_client.describe_instances(Filters=[
            {'Name': 'subnet-id', 'Values': subnet_ids}])
        meta = res['ResponseMetadata']
        data = res['Reservations']
        logger.debug("run_instances::describe_instances::meta::%s", meta)
        logger.debug("run_instances::describe_instances::data::%s", data)
        res = self.ec2_client.run_instances(LaunchTemplate={
            'LaunchTemplateName': instance_template},
            SecurityGroupIds=[sg_ids],
            SubnetId=subnet_ids[0],
            MinCount=1,
            MaxCount=1)
        meta = res['ResponseMetadata']
        data = res['Instances']
        logger.debug("run_instances::run_instances::meta::%s", meta)
        logger.debug("run_instances::run_instances::data::{}", data)
        inst_id = [i['InstanceId'] for i in data]
        logger.info("run_instances::waiting for instance")
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
        logger.debug("refresh_instances::run_instances::meta::%s", meta)
        logger.debug("refresh_instances::run_instances::data::%s", data)
        self['Instances'] = data['Instances']
        self.save()

    def terminate_instances(self):
        logger.info("terminate_instances::Executing")
        inst_id = [i['InstanceId'] for i in self['Instances']]
        res = self.ec2_client.terminate_instances(InstanceIds=inst_id)
        meta = res['ResponseMetadata']
        data = res['TerminatingInstances']
        logger.debug("terminate_instances::terminate_instances::meta::%s", meta)
        logger.debug("terminate_instances::terminate_instances::data::{}", data)
        waiter = self.ec2_client.get_waiter('instance_terminated')
        logger.info("terminate_instances::waiter::%s", inst_id)
        waiter.wait(InstanceIds=inst_id)
        self.save()


    def create_autoscaling_group(self, instance_template, affinity_group=0):
        logger.info("create_autoscaling_group::Executing")
        vpc_id = self['Vpc']['VpcId']
        azs = [s['AvailabilityZone'] for s in self['Subnets'] for t in s['Tags']\
            if t['Key'] == 'affinity_group' and t['Value'] == str(affinity_group)]
        res = self.ec2_client.create_auto_scaling_group(
            AutoScalingGroupName=instance_template,
            LaunchTemplate={
                'LaunchTemplateName': instance_template,
                'Version': '$Default'},
            MinSize=1,
            MaxSize=2,
            DesiredCapacity=2,
            AvailabilityZones=azs)
        meta = res
        logger.info("create_autoscaling_group::create_autoscaling_group::%s", meta)
        res = self.ec2_client.describe_auto_scaling_group(Filters=[
            {'Name': 'vpc-id', 'Values': [vpc_id]}])
        meta = res['ResponseMetadata']
        data = res['AvailabilityZones']
        logger.info("create_autoscaling_group::describe_auto_scaling_group::%s", meta)
        logger.info("create_autoscaling_group::describe_auto_scaling_group::%s", data)
        self['AvailabilityZones'] = data
        self.save()
