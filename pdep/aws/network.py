import copy
from dataclasses import dataclass, field
from typing import Dict, Any

import botocore.exceptions
from dataclasses_json import dataclass_json
from pdep import Connector, resource, BaseResource, zstr, output_property
from pdep.utils import log_func


@dataclass_json
@dataclass
class VpcState:
    vpc_id: zstr = None


@resource()
class Vpc(BaseResource[VpcState,None,None]):
    def __init__(self, logger, cidr_block: str | Connector, tags: Dict[str, str] = {}):
        super().__init__(logger)

    @property
    @output_property
    def vpc_id(self) -> str | Connector:
        return self.state.vpc_id

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self.state.vpc_id = "vpc-dummy"
            return

        tags = self.tags
        tags['apply_uuid'] = apply_uuid
        ec2 = provider.create_resource('ec2')
        try:
            vpc = ec2.create_vpc(
                DryRun=dry,
                CidrBlock=self.inputs['cidr_block']
            )
            vpc.wait_until_available()
            self.logger.info(f"vpc_id:{vpc.vpc_id}")
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' not in e.response['Error']['Code']:
                raise
        self.state.vpc_id = vpc.vpc_id

        try:
            ec2.create_tags(
                DryRun=dry,
                Resources=[
                    vpc.vpc_id,
                ],
                Tags=self._dict_to_aws_tags(self.tags, {"apply_uuid": str(apply_uuid)})
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' not in e.response['Error']['Code']:
                raise

    @log_func()
    def is_drifted(self, provider, dry):
        if dry:
            return False
        ec2 = provider.create_resource('ec2')
        try:
            vpc = ec2.Vpc(self.state.vpc_id)
            device_tags = self._aws_tags_to_dict(vpc.tags)
            del device_tags['apply_uuid']

            ret = vpc.state != 'available' or \
                  vpc.cidr_block != self.inputs['cidr_block'] or \
                  device_tags != self.tags

            return ret
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidVpcID.NotFound':
                # Vpc was deleted on aws
                return True
            raise

    @log_func()
    def do_apply(self, env_inputs, resource_manager, provider, apply_uuid, dry):
        if env_inputs is None:
            self.create(provider, apply_uuid, dry)
            return
        if env_inputs != self.inputs or self.is_drifted(provider, dry):
            self.mark_destroy(resource_manager, env_inputs, apply_uuid)
            self.create(provider, apply_uuid, dry)
        else:
            self.logger.info("nothing to do")

    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        ec2 = provider.create_resource('ec2')
        try:
            vpc = ec2.Vpc(self.state.vpc_id)
            vpc.delete(DryRun=dry)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidVpcID.NotFound':
                pass
            elif 'DryRunOperation' in e.response['Error']['Code']:
                pass
            else:
                raise


@dataclass_json
@dataclass
class VpcInputV2:
    cidr_block: zstr = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass_json
@dataclass
class VpcOutputV2:
    vpc_id: zstr = None


@dataclass_json
@dataclass
class VpcStateV2:
    vpc_id: zstr = None


@resource()
class VpcV2(BaseResource[VpcStateV2, VpcInputV2, VpcOutputV2]):

    @log_func()
    def do_apply(self, env_inputs, resource_manager, provider, apply_uuid, dry):
        self.state.vpc_id = "vpc-hello"
        self.output.vpc_id = self.state.vpc_id

    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        pass


@dataclass_json
@dataclass
class RouteTableState:
    arn: zstr = None


@resource()
class RouteTable(BaseResource[RouteTableState,None,None]):
    def __init__(self, logger, vpc_id: str | Connector):
        super().__init__(logger, None)

    @property
    @output_property
    def arn(self):
        return self.state.arn

    @log_func()
    def do_apply(self, env_inputs, resource_manager, provider, apply_uuid, dry):
        self.state.arn = "arn:rt:somthing"
