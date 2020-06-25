from subfish.base import AwsBase
from jinja2 import Template
from os import path
from botocore.exceptions import ClientError

RELATIVE_ASSUME_ROLE_POLICIES="assume_policies"
RELATIVE_ROLE_POLICIES="role_policies"

class AwsIam(AwsBase):

    def __init__(self, path, iam_path="."):
        super().__init__(path)
        self.client = self.session.create_client('iam')
        self.assume_policy_path = "/".join([iam_path, RELATIVE_ASSUME_ROLE_POLICIES])
        self.role_policy_path = "/".join([iam_path, RELATIVE_ROLE_POLICIES])

    def get_iam_role_policy_arn(self, policy_name):
        try:
            return next(p['Arn'] for p in self.client.list_policies()['Policies'] \
                if p['PolicyName'] == policy_name)
        except StopIteration:
            return 0

    def create_iam_role(self, role_name, policy_attachments):
        try:
            role = next(r for r in self['Roles'] if r['RoleName'] == role_name)
            try:
                arole = next(r['RoleName'] for r in \
                    self.client.list_roles()['Roles'] \
                    if r['RoleName'] == role_name)
            except StopIteration:
                self['Roles'].remove(role)
                raise StopIteration
        except StopIteration:
            pfile = open("{}/{}.json".format(self.assume_policy_path, role_name))
            assume_policy = pfile.read().replace("\n", " ")
            pfile.close()
            try:
                self.client.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=assume_policy)
            except ClientError as c:
                if c.response['Error']['Code'] == 'EntityAlreadyExists':
                    self['Roles'].append(self.client.get_role(RoleName=role_name)['Role'])
                else:
                    raise
        for policy in policy_attachments:
            self.client.attach_role_policy(RoleName=role_name, PolicyArn=policy)
        self.save()

    def delete_iam_roles(self):
        roles = [r['RoleName'] for r in self['Roles']]
        for role_name in roles:
            policy_list = [p['PolicyArn'] for p in \
                self.client.list_attached_role_policies(
                    RoleName=role_name)['AttachedPolicies']]
            for policy in policy_list:
                self.client.detach_role_policy(RoleName=role_name, PolicyArn=policy)
            self.client.delete_role(RoleName=role_name)
        del(self['Roles'])
