import logging
from dataclasses import dataclass, field
from typing import Dict

from dataclasses_json import dataclass_json
from uuid import UUID
from pdep import BasePlan, FileResourceManager, zstr, AwsLocalStackProvider
from pdep.aws.network import VpcV1, RouteTable, VpcInput, Vpc, RouteTableInput
from pdep.utils import setup_logging, log_func


@dataclass_json
@dataclass
class BackboneNetInput:
    cidr_block: zstr = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass_json
@dataclass
class BackboneNetOutput:
    vpc_id: zstr = None


class BackboneNet(BasePlan[BackboneNetInput, BackboneNetOutput]):

    def do_init_resources(self):
        self.resources.main_vpc = Vpc(
            input=VpcInput(
                cidr_block=self.input.cidr_block,
                tags=self.input.tags
            )
        )
        self.resources.main_rt = RouteTable(
            RouteTableInput(
                vpc_id=self.resources.main_vpc.output.vpc_id
            )
        )


if __name__ == "__main__":
    setup_logging(console_level=log_func.ABOVE_DEBUG)
    rm = FileResourceManager("state.json")
    provider = AwsLocalStackProvider(None)
    bb = BackboneNet(
        BackboneNetInput(
            cidr_block="10.212.160.0/22",
            tags={"hello": "amir"}
        ), UUID('a81054b2-bb57-4969-b3c5-308fee049e01')
    )
    bb.apply(rm, provider, False, True)
