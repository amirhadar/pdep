import logging
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from uuid import UUID
from pdep import Connector, resource, BasePlan, FileResourceManager, zstr, AwsLocalStackProvider
from pdep.aws.network import Vpc, RouteTable, VpcInputV2, VpcV2
from pdep.utils import setup_logging, log_func


@dataclass_json
@dataclass
class BackboneNetState:
    cidr_block: zstr = None


@resource()
class BackboneNet(BasePlan):

    def __init__(self, logger, cidr_block: str | Connector, tags={}):
        super().__init__(logger, UUID('a81054b2-bb57-4969-b3c5-308fee049e01'))

        self.resources.main_vpc = VpcV2(
            logger,
            input=VpcInputV2(
                cidr_block=cidr_block,
                tags=tags
            )
        )
        self.resources.main_rt = RouteTable(logger, vpc_id=self.resources.main_vpc.output.vpc_id)


if __name__ == "__main__":
    setup_logging(console_level=log_func.ABOVE_DEBUG)
    rm = FileResourceManager(None, "state.json")
    provider = AwsLocalStackProvider(None)
    bb = BackboneNet(None, cidr_block="10.212.160.0/22", tags={"hello": "amir"})
    bb.apply(rm, provider, False)
