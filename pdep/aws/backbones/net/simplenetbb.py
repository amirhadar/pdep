import ipaddress
import math
from pprint import pprint
from uuid import UUID
from pdep import FileResourceManager, AwsLocalStackProvider
from pdep.aws.aws_info import aws_info
from pdep.aws.backbones.net.interfaces import BasicNetBBOutput, BasicNetBBInput
from pdep.aws.network import RouteTable, RouteTableInput, DefaultVpc, Subnet, SubnetInput, Vpc, VpcInput, \
    RouteTableAssociation, RouteTableAssociationInput, SecurityGroup, \
    SecurityGroupInput, SecurityGroupRuleIngress, SecurityGroupRuleIngressInput, \
    SecurityGroupRuleEgressInput, SecurityGroupRuleEgress
from pdep.plan import BaseBackbone, CalcConnector
from pdep.utils import setup_logging, log_func


class SubnetCidrCalculator(CalcConnector):
    def calc(self, cidr_block, total_subnet_num, subnet_num):
        network = ipaddress.ip_network(cidr_block)
        subnets = list(network.subnets(prefixlen_diff=int(math.log2(total_subnet_num))))
        cidr = subnets[subnet_num].with_prefixlen
        return cidr


class SimpleNetBB(BaseBackbone[BasicNetBBInput, BasicNetBBOutput]):

    def do_init_resources(self):

        if self.input.vpc_cidr_block:
            self.resources.main_vpc = Vpc(VpcInput(
                cidr_block=self.input.vpc_cidr_block
            ))
        else:
            self.resources.main_vpc = DefaultVpc()

        self.resources.rout_table = RouteTable(RouteTableInput(
            vpc_id=self.resources.main_vpc.output.vpc_id
        ))

        self.resources.subnets = [
            Subnet(SubnetInput(
                vpc_id=self.resources.main_vpc.output.vpc_id,
                cidr_block=SubnetCidrCalculator(self.resources.main_vpc.output.cidr_block, self.input.subnets_num, i),
                availability_zone=aws_info.regions[self.input.region].availability_zones[i].name
            )) for i in range(self.input.subnets_num)
        ]

        self.resources.route_table_associations = [
            RouteTableAssociation(RouteTableAssociationInput(
                route_table_id=self.resources.rout_table.output.rout_table_id,
                subnet_id=subnet.output.subnet_id
            ))
            for subnet in self.resources.subnets
        ]

        self.resources.security_group = SecurityGroup(SecurityGroupInput(
            vpc_id=self.resources.main_vpc.output.vpc_id,
            name="simple-def",
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

        subnets = [subnet.output for subnet in self.resources.subnets]
        self._output = BasicNetBBOutput(
            vpc=self.resources.main_vpc.output,
            route_table=self.resources.rout_table.output,
            security_group=self.resources.security_group.output,
            subnets=subnets,
            public_subnets=subnets,
            private_subnets=subnets,
            db_subnets=subnets,
        )


if __name__ == "__main__":
    setup_logging(console_level=log_func.ABOVE_DEBUG)
    rm = FileResourceManager("state.json")
    provider = AwsLocalStackProvider(None)
    bb = SimpleNetBB(BasicNetBBInput(
        vpc_cidr_block="10.212.160.0/22",
        subnets_num=2,
        region="us-east-1",
        tags={"mytag": "mytagvalue"}
    ), UUID('a81054b2-bb57-4969-b3c5-308fee049e02'))

    rm.select("/")
    bb.apply(rm, provider, dry=False, check_drift=True)
    pprint(bb.output.to_dict())
