import ipaddress
import math
from pprint import pprint
from uuid import UUID
from pdep import FileResourceManager, AwsLocalStackProvider
from pdep.aws.aws_info import aws_info
from pdep.aws.backbones.app.interfaces import SimpleAppBBInput, SimpleAppBBOutput
from pdep.aws.backbones.net.interfaces import BasicNetBBOutput, BasicNetBBInput
from pdep.aws.backbones.net.simplenetbb import SimpleNetBB
from pdep.aws.network import RouteTable, RouteTableInput, DefaultVpc, Subnet, SubnetInput, Vpc, VpcInput, \
    RouteTableAssociation, RouteTableAssociationInput, SecurityGroup, \
    SecurityGroupInput, SecurityGroupRuleIngress, SecurityGroupRuleIngressInput, \
    SecurityGroupRuleEgressInput, SecurityGroupRuleEgress
from pdep.plan import BaseBackbone, CalcConnector
from pdep.utils import setup_logging, log_func


class SimpleAppBB(BaseBackbone[SimpleAppBBInput, SimpleAppBBOutput]):

    def do_init_resources(self):
        self.resources.security_group = SecurityGroup(SecurityGroupInput(
            vpc_id=self.resources.main_vpc.output.vpc_id,
            name="simple-app-def",
            description="simple backbone default security group"
        ))

        self.resources.security_group_ingress = SecurityGroupRuleIngress(SecurityGroupRuleIngressInput(
            security_group_id=self.resources.security_group.output.security_group_id,
            from_port=0,
            to_port=0,
            protocol="-1",
            cidr_blocks=["0.0.0.0/0"]
        ))
        self.resources.security_group_egress = SecurityGroupRuleEgress(SecurityGroupRuleEgressInput(
            security_group_id=self.resources.security_group.output.security_group_id,
            from_port=0,
            to_port=0,
            protocol="-1",
            cidr_blocks=["0.0.0.0/0"]
        ))

        self._output = SimpleAppBBOutput(
            alb="slkdfjls",
            evb="lsdfjksl",
            ecs_cluster="sldfkjsdl"
        )


if __name__ == "__main__":
    setup_logging(console_level=log_func.ABOVE_DEBUG)
    rm = FileResourceManager("state.json")
    provider = AwsLocalStackProvider(None)
    bb = SimpleAppBB(
        SimpleAppBBInput(
            simple_net_bb=rm.get_plan_output(BasicNetBBOutput)
        ),
        UUID('a4a8393f-aead-4396-9e29-038f4b346104')
    )

    # bb.apply(rm, provider, dry=False, check_drift=True)
    # pprint(bb.output.to_dict())
