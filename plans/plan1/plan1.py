from dataclasses import dataclass
from dataclasses_json import dataclass_json
from uuid import UUID
from pdep import Connector, resource, BasePlan, FileResourceManager, zstr, AwsLocalStackProvider
from pdep.aws.network import Vpc, RouteTable


@dataclass_json
@dataclass
class BackboneNetState:
    cidr_block: zstr = None


@resource()
class BackboneNet(BasePlan):

    def __init__(self, cidr_block: str | Connector):
        super().__init__(UUID('a81054b2-bb57-4969-b3c5-308fee049e01'))

        self.resources.main_vpc = Vpc(cidr_block=cidr_block)
        self.resources.main_rt = RouteTable(vpc_id=self.resources.main_vpc.vpc_id)



if __name__ == "__main__":
    rm = FileResourceManager("state.json")
    provider = AwsLocalStackProvider()
    bb = BackboneNet(cidr_block="10.212.160.0/22")
    bb.destroy(rm, provider, True)
