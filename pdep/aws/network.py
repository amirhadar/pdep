from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import botocore.exceptions
from dataclasses_json import dataclass_json
from pdep import zstr
from pdep.plan import SimplifiedResource, BaseResource, InputT, OutputT
from pdep.utils import log_func, _aws_tags_to_dict, _dict_to_aws_tags, do_with_timeout


def ec2_set_tags(ec2, tags, dry, id_):
    try:
        ec2.create_tags(
            DryRun=dry,
            Resources=[
                id_,
            ],
            Tags=_dict_to_aws_tags(tags)
        )
    except botocore.exceptions.ClientError as e:
        if 'DryRunOperation' in e.response['Error']['Code'] and dry:
            pass
        else:
            raise


@dataclass_json
@dataclass
class VpcInput:
    cidr_block: zstr = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass_json
@dataclass
class VpcOutput:
    vpc_id: zstr = None
    cidr_block: zstr = None


class Vpc(SimplifiedResource[VpcInput, VpcOutput]):

    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        ec2 = provider.create_resource('ec2')
        try:
            vpc = ec2.Vpc(self.output.vpc_id)
            vpc.delete(DryRun=dry)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self.output.vpc_id = "vpc-dummy"
            return

        self.output.cidr_block = self.input.cidr_block
        ec2 = provider.create_resource('ec2')
        try:
            vpc = ec2.create_vpc(
                DryRun=dry,
                CidrBlock=self.input.cidr_block
            )
            vpc.wait_until_available()
            self._output.vpc_id = vpc.vpc_id
            self._output.cidr_block = self.input.cidr_block
            self.logger.info(f"vpc_id:{vpc.vpc_id}")
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

        ec2_set_tags(ec2, self.input.tags, dry, vpc.vpc_id)

    @log_func()
    def is_drifted(self, provider, dry):
        if dry:
            return False
        ec2 = provider.create_resource('ec2')
        try:
            vpc = ec2.Vpc(self._output.vpc_id)
            device_tags = _aws_tags_to_dict(vpc.tags)
            if 'apply_uuid' in device_tags:
                del device_tags['apply_uuid']

            ret = vpc.state != 'available' or \
                  vpc.cidr_block != self.input.cidr_block or \
                  device_tags != self.input.tags

            return ret
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                # Vpc was deleted on aws
                return True
            raise


@dataclass_json
@dataclass
class ExistingVpcInput:
    vpc_id: zstr = None
    cidr_block: zstr = None


@dataclass_json
@dataclass
class VpcOutput:
    vpc_id: zstr = None
    cidr_block: zstr = None


class ExistingVpc(SimplifiedResource[ExistingVpcInput, VpcOutput]):

    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        return

    @log_func()
    def create(self, provider, apply_uuid, dry):
        self._output.vpc_id = self.input.vpc_id
        self.output.cidr_block = self.input.cidr_block

    @log_func()
    def is_drifted(self, provider, dry):
        ec2 = provider.create_resource('ec2')
        try:
            vpc = ec2.Vpc(self._output.vpc_id)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                # Vpc was deleted on aws
                return True
            raise


class DefaultVpc(SimplifiedResource[None, VpcOutput]):

    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        return

    @log_func()
    def create(self, provider, apply_uuid, dry):
        client = provider.create_client('ec2')
        response = client.describe_vpcs()
        for vpc_desc in response['Vpcs']:
            if vpc_desc['IsDefault']:
                self._output.vpc_id = vpc_desc['VpcId']
                self._output.cidr_block = vpc_desc['CidrBlock']
                break
        else:
            raise Exception('Default Vpc not found')

    @log_func()
    def is_drifted(self, provider, dry):
        ec2 = provider.create_resource('ec2')
        try:
            vpc = ec2.Vpc(self._output.vpc_id)
            if not vpc.is_default:
                raise Exception(f"Vpc id:{vpc.vpc_id} is not default")
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                # Vpc was deleted on aws
                return True
            raise


@dataclass_json
@dataclass
class SubnetInput:
    vpc_id: zstr = None
    cidr_block: zstr = None
    availability_zone: Optional[zstr] = None
    tags: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass_json
@dataclass
class SubnetOutput:
    arn: zstr = None
    subnet_id: zstr = None
    cidr_block: zstr = None
    availability_zone: zstr = None
    state: zstr = None


class Subnet(SimplifiedResource[SubnetInput, SubnetOutput]):
    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        if dry:
            return

        try:
            ec2 = provider.create_resource('ec2')
            ec2.delete_subnet(SubnetId=self._output.subnet_id, DryRun=dry)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self._output.arn = "arn:dry-subnet"
            return

        response = None
        ec2_client = provider.create_client('ec2')
        try:
            response = ec2_client.create_subnet(
                AvailabilityZone=self.input.availability_zone,
                CidrBlock=self.input.cidr_block,
                VpcId=self.input.vpc_id,
                DryRun=dry,
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

        if response is None and dry:
            response = {'AssignIpv6AddressOnCreation': False,
                        'AvailabilityZone': 'us-east-1a',
                        'AvailabilityZoneId': 'use1-az6',
                        'AvailableIpAddressCount': 507,
                        'CidrBlock': '10.212.160.0/23',
                        'DefaultForAz': False,
                        'Ipv6CidrBlockAssociationSet': [],
                        'Ipv6Native': False,
                        'MapPublicIpOnLaunch': False,
                        'OwnerId': '000000000000',
                        'State': 'available',
                        'SubnetArn': 'arn:aws:ec2:us-east-1:000000000000:subnet/subnet-c9e486b8',
                        'SubnetId': 'subnet-c9e486b8',
                        'Tags': [],
                        'VpcId': 'vpc-e8885bf0'}

        self._output.arn = response['Subnet']['SubnetArn']
        self._output.cidr_block = response['Subnet']['CidrBlock']
        self._output.availability_zone = response['Subnet']['AvailabilityZone']
        self._output.subnet_id = self._output.arn.rsplit("/", 1)[1]
        self._output.state = response['Subnet']['State']

        ec2_set_tags(ec2_client, self.input.tags, dry, self._output.subnet_id)

        if not dry:
            ec2 = provider.create_resource('ec2')
            subnet = ec2.Subnet(self._output.subnet_id)

            do_with_timeout(lambda: (subnet.reload(), subnet.state != 'available')[-1], 30)
            self._output.state = subnet.state

    @log_func()
    def is_drifted(self, provider, dry):
        if dry:
            return False
        drifted = False
        ec2 = provider.create_resource('ec2')
        try:
            subnet = ec2.Subnet(self._output.subnet_id)
            drifted = drifted or self._output.cidr_block != subnet.cidr_block
            drifted = drifted or self._output.availability_zone != subnet.availability_zone
            drifted = drifted or self._output.state != subnet.state
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                # Subnet was deleted on aws
                return True
            raise
        return drifted


@dataclass_json
@dataclass
class RouteTableInput:
    vpc_id: zstr = None
    tags: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass_json
@dataclass
class RouteTableOutput:
    rout_table_id: zstr = None


class RouteTable(SimplifiedResource[RouteTableInput, RouteTableOutput]):

    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        try:
            ec2 = provider.create_resource('ec2')
            ec2.delete_route_table(RouteTableId=self._output.rout_table_id, DryRun=dry)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self._output.rout_table_id = "arn:rout-table"
            return
        response = None
        ec2_client = provider.create_client('ec2')
        try:
            response = ec2_client.create_route_table(
                VpcId=self.input.vpc_id,
                DryRun=dry,
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        if not response and dry:
            response = {'Associations': [],
                        'OwnerId': '000000000000',
                        'RouteTableId': 'rtb-f01f74b1',
                        'Routes': [{'DestinationCidrBlock': '10.212.160.0/22',
                                    'GatewayId': 'local',
                                    'State': 'active'}],
                        'Tags': [],
                        'VpcId': 'vpc-9aa0c0f8'}
        self._output.rout_table_id = response['RouteTable']['RouteTableId']

        ec2_set_tags(ec2_client, self.input.tags, dry, self._output.rout_table_id)

    @log_func()
    def is_drifted(self, provider, dry):
        if dry:
            return False
        drifted = False
        ec2 = provider.create_resource('ec2')
        try:
            route_table = ec2.RouteTable(self._output.rout_table_id)
            drifted = drifted or route_table.vpc_id != self.input.vpc_id
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                # Subnet was deleted on aws
                return True
            raise
        return drifted


@dataclass_json
@dataclass
class RouteTableAssociationInput:
    route_table_id: zstr = None
    subnet_id: zstr = None
    gateway_id: Optional[zstr] = None
    tags: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass_json
@dataclass
class RouteTableAssociationOutput:
    association_id: zstr = None
    state: zstr = None


class RouteTableAssociation(SimplifiedResource[RouteTableAssociationInput, RouteTableAssociationOutput]):
    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        try:
            ec2 = provider.create_resource('ec2')
            ec2.disassociate_route_table(RouteTableId=self._output.association_id, DryRun=dry)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self._output.association_id = "arn:rout-table-asso"
            return
        response = None
        ec2_client = provider.create_client('ec2')
        try:
            kwargs = dict(RouteTableId=self.input.route_table_id,
                          SubnetId=self.input.subnet_id,
                          DryRun=dry)
            if self.input.gateway_id is not None:
                kwargs += dict(GatewayId=self.input.gateway_id)

            response = ec2_client.associate_route_table(**kwargs)

        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        if not response and dry:
            response = {
                'AssociationId': 'rtbassoc-dd5e301e',
                'AssociationState': {
                    'State': 'associated',
                    'StatusMessage': ''
                }
            }

            self._output.association_id = response['AssociationId']
            self._output.state = response['AssociationState']['State']
            ec2_set_tags(ec2_client, self.input.tags, dry, self._output.association_id)

    @log_func()
    def is_drifted(self, provider, dry):
        return False


@dataclass_json
@dataclass
class SecurityGroupInput:
    vpc_id: zstr = None
    name: zstr = None
    description: zstr = ""
    tags: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass_json
@dataclass
class SecurityGroupOutput:
    security_group_id: zstr = None


class SecurityGroup(SimplifiedResource[SecurityGroupInput, SecurityGroupOutput]):
    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        try:
            ec2 = provider.create_resource('ec2')
            ec2.delete_security_group(GroupId=self._output.security_group_id, DryRun=dry)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self._output.security_group_id = "arn:security-group-id"
            return
        response = None
        ec2_client = provider.create_client('ec2')
        try:
            response = ec2_client.create_security_group(
                VpcId=self.input.vpc_id,
                GroupName=self.input.name,
                Description=self.input.description
            )

        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        if not response and dry:
            response = {'GroupId': 'string'}

        self._output.security_group_id = response['GroupId']
        ec2_set_tags(ec2_client, self.input.tags, dry, self._output.security_group_id)

    @log_func()
    def is_drifted(self, provider, dry):
        return False


@dataclass_json
@dataclass
class SecurityGroupRuleIngressInput:
    security_group_id: zstr = None
    from_port: int = -1
    to_port: int = -1
    protocol: zstr = None
    cidr_blocks: List[str] = field(default_factory=list)
    tags: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass_json
@dataclass
class SecurityGroupRuleIngressOutput:
    security_group_rule_id: zstr = None


class SecurityGroupRuleIngress(SimplifiedResource[SecurityGroupRuleIngressInput, SecurityGroupRuleIngressOutput]):

    @property
    def create_before_destroy(self):
        return False

    @log_func()
    def update(self, env_inputs: SecurityGroupRuleIngressInput, resource_manager, provider, apply_uuid, dry):
        if dry:
            return True
        response = None
        ec2_client = provider.create_client('ec2')
        try:
            response = ec2_client.modify_security_group_rules(
                DryRun=dry,
                GroupId=self.input.security_group_id,
                SecurityGroupRules=[
                    {
                        'SecurityGroupRuleId': self._output.security_group_rule_id,
                        'SecurityGroupRule': {
                            'IpProtocol': self.input.protocol,
                            'FromPort': self.input.from_port,
                            'ToPort': self.input.to_port,
                            'CidrIpv4': cidr_block,
                        }
                    } for cidr_block in self.input.cidr_blocks
                ],
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            elif 'InternalFailure' in e.response['Error']['Code']:
                # localstack not implemented
                return False
            else:
                raise
        if not response and dry:
            response = {'Return': True}

        if response['Return']:
            return True
        return False

    @log_func()
    def do_destroy(self, env_inputs: SecurityGroupRuleIngressInput, resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        try:
            ec2_res = provider.create_resource('ec2')
            sg = ec2_res.SecurityGroup(env_inputs.security_group_id)
            response = sg.revoke_ingress(IpPermissions=sg.ip_permissions)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        if not response and dry:
            response = {'Return': True,
                        'ResponseMetadata': {'RequestId': 'TJBBIL75FBHQ2HOG25FLERR6G4ZX0VYTU1WP2MII0SSZD9ZOYDDL',
                                             'HTTPStatusCode': 200,
                                             'HTTPHeaders': {'content-type': 'text/xml', 'content-length': '254',
                                                             'connection': 'close', 'access-control-allow-origin': '*',
                                                             'access-control-expose-headers': 'etag,x-amz-version-id',
                                                             'date': 'Fri, 04 Nov 2022 11:50:57 GMT',
                                                             'server': 'hypercorn-h11'}, 'RetryAttempts': 0}}
        if not response['Return']:
            raise Exception(f"destroy security group rule {self._output.security_group_rule_id} failed")

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self._output.security_group_rule_id = "arn:security-group-rule-id"
            return
        response = None
        ec2_client = provider.create_client('ec2')
        try:
            response = ec2_client.authorize_security_group_ingress(
                DryRun=dry,
                GroupId=self.input.security_group_id,
                IpPermissions=[
                    dict(
                        FromPort=self.input.from_port,
                        ToPort=self.input.to_port,
                        IpProtocol=self.input.protocol,
                        IpRanges=[
                            dict(
                                CidrIp=cidr_block
                            ) for cidr_block in self.input.cidr_blocks
                        ],
                    ),
                ]
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        if not response and dry:
            response = {'Return': True, 'SecurityGroupRules': [
                {'SecurityGroupRuleId': 'sgr-bc885d0346c67e7be', 'GroupId': 'sg-708dcae523c56ae0d',
                 'GroupOwnerId': '000000000000', 'IsEgress': False, 'IpProtocol': '-1', 'CidrIpv4': '0.0.0.0/0',
                 'Description': ''}],
                        'ResponseMetadata': {'RequestId': 'PTVZ1S6TC9UBJXTK2LRRAKX9D8F6MY5XHR1JJ2LIHE4CAWILB1J4',
                                             'HTTPStatusCode': 200,
                                             'HTTPHeaders': {'content-type': 'text/xml', 'content-length': '562',
                                                             'connection': 'close', 'access-control-allow-origin': '*',
                                                             'access-control-expose-headers': 'etag,x-amz-version-id',
                                                             'date': 'Fri, 04 Nov 2022 11:03:51 GMT',
                                                             'server': 'hypercorn-h11'}, 'RetryAttempts': 0}}

        self._output.security_group_rule_id = response['SecurityGroupRules'][0]['SecurityGroupRuleId']
        ec2_set_tags(ec2_client, self.input.tags, dry, self._output.security_group_rule_id)

    @log_func()
    def is_drifted(self, provider, dry):
        return False


@dataclass_json
@dataclass
class SecurityGroupRuleEgressInput:
    security_group_id: zstr = None
    from_port: int = -1
    to_port: int = -1
    protocol: zstr = None
    cidr_blocks: List[str] = field(default_factory=list)
    tags: Optional[Dict[str, str]] = field(default_factory=dict)


@dataclass_json
@dataclass
class SecurityGroupRuleEgressOutput:
    security_group_rule_id: zstr = None


class SecurityGroupRuleEgress(SimplifiedResource[SecurityGroupRuleEgressInput, SecurityGroupRuleEgressOutput]):

    @property
    def create_before_destroy(self):
        return False

    @log_func()
    def update(self, env_inputs: SecurityGroupRuleEgressInput, resource_manager, provider, apply_uuid, dry):
        if dry:
            return True
        response = None
        ec2_client = provider.create_client('ec2')
        try:
            response = ec2_client.modify_security_group_rules(
                DryRun=dry,
                GroupId=self.input.security_group_id,
                SecurityGroupRules=[
                    {
                        'SecurityGroupRuleId': self._output.security_group_rule_id,
                        'SecurityGroupRule': {
                            'IpProtocol': self.input.protocol,
                            'FromPort': self.input.from_port,
                            'ToPort': self.input.to_port,
                            'CidrIpv4': cidr_block,
                        }
                    } for cidr_block in self.input.cidr_blocks
                ],
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            elif 'InternalFailure' in e.response['Error']['Code']:
                # localstack not implemented
                return False
            else:
                raise
        if not response and dry:
            response = {'Return': True}

        if response['Return']:
            return True
        return False

    @log_func()
    def do_destroy(self, env_inputs: SecurityGroupRuleIngressInput, resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        try:
            ec2_res = provider.create_resource('ec2')
            sg = ec2_res.SecurityGroup(env_inputs.security_group_id)
            response = sg.revoke_egress(IpPermissions=sg.ip_permissions)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        if not response and dry:
            response = {'Return': True,
                        'ResponseMetadata': {'RequestId': 'TJBBIL75FBHQ2HOG25FLERR6G4ZX0VYTU1WP2MII0SSZD9ZOYDDL',
                                             'HTTPStatusCode': 200,
                                             'HTTPHeaders': {'content-type': 'text/xml', 'content-length': '254',
                                                             'connection': 'close', 'access-control-allow-origin': '*',
                                                             'access-control-expose-headers': 'etag,x-amz-version-id',
                                                             'date': 'Fri, 04 Nov 2022 11:50:57 GMT',
                                                             'server': 'hypercorn-h11'}, 'RetryAttempts': 0}}
        if not response['Return']:
            raise Exception(f"destroy security group rule {self._output.security_group_rule_id} failed")

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self._output.security_group_rule_id = "arn:security-group-rule-id"
            return
        response = None
        ec2_client = provider.create_client('ec2')
        try:
            response = ec2_client.authorize_security_group_egress(
                DryRun=dry,
                GroupId=self.input.security_group_id,
                IpPermissions=[
                    dict(
                        FromPort=self.input.from_port,
                        ToPort=self.input.to_port,
                        IpProtocol=self.input.protocol,
                        IpRanges=[
                            dict(
                                CidrIp=cidr_block
                            ) for cidr_block in self.input.cidr_blocks
                        ],
                    ),
                ]
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            elif 'InvalidPermission.Duplicate' in e.response['Error']['Code']:
                return False
            else:
                raise
        if not response and dry:
            response = {'Return': True, 'SecurityGroupRules': [
                {'SecurityGroupRuleId': 'sgr-bc885d0346c67e7be', 'GroupId': 'sg-708dcae523c56ae0d',
                 'GroupOwnerId': '000000000000', 'IsEgress': False, 'IpProtocol': '-1', 'CidrIpv4': '0.0.0.0/0',
                 'Description': ''}],
                        'ResponseMetadata': {'RequestId': 'PTVZ1S6TC9UBJXTK2LRRAKX9D8F6MY5XHR1JJ2LIHE4CAWILB1J4',
                                             'HTTPStatusCode': 200,
                                             'HTTPHeaders': {'content-type': 'text/xml', 'content-length': '562',
                                                             'connection': 'close', 'access-control-allow-origin': '*',
                                                             'access-control-expose-headers': 'etag,x-amz-version-id',
                                                             'date': 'Fri, 04 Nov 2022 11:03:51 GMT',
                                                             'server': 'hypercorn-h11'}, 'RetryAttempts': 0}}

        self._output.security_group_rule_id = response['SecurityGroupRules'][0]['SecurityGroupRuleId']
        ec2_set_tags(ec2_client, self.input.tags, dry, self._output.security_group_rule_id)

    @log_func()
    def is_drifted(self, provider, dry):
        return False
