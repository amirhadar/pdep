from dataclasses import field
from typing import Dict, TypeVar, Generic
from pdep import output_property
from pdep.plan import StateT, plan_output_property, InputT, OutputT
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from uuid import UUID
from pdep import Connector, resource, BasePlan, FileResourceManager, zstr, AwsLocalStackProvider
from pdep.aws.network import Vpc, RouteTable
from pdep.utils import setup_logging, log_func


@dataclass_json
@dataclass
class SubSimpleOutput:
    vpc_id: zstr = None


@dataclass_json
@dataclass
class SimpleOutput:
    vpc: SubSimpleOutput = field(default_factory=SubSimpleOutput)


@dataclass_json
@dataclass
class SimpleInput:
    vpc_cidr_block: str = None
    tags: Dict[str, str] = field(default_factory=dict)


class BaseBackbone(BasePlan[StateT, InputT, OutputT]):
    def __init__(self, logger, uuid: UUID):
        super().__init__(logger, uuid)
        self.__output = None

    @property
    @plan_output_property
    def output(self) -> OutputT:
        return self.__output

    def _set_output(self, value: OutputT):
        self.__output = value

    @property
    def input(self) -> InputT:
        return self.inputs['input']


@resource()
class Simple(BaseBackbone[None, SimpleInput, SimpleOutput]):

    def __init__(self, logger, input: SimpleInput | Connector):
        super().__init__(logger, UUID('a81054b2-bb57-4969-b3c5-308fee049e01'))

        self.resources.main_vpc = Vpc(
            logger,
            cidr_block=input.vpc_cidr_block,
            tags=input.tags
        )

        self._set_output(SimpleOutput(
            vpc=SubSimpleOutput(
                vpc_id=self.resources.main_vpc.vpc_id
            )
        ))


@dataclass_json
@dataclass
class MainOutput:
    vpc_id: zstr = None


@dataclass_json
@dataclass
class MainInput:
    vpc_cidr_block: str = None
    tags: Dict[str, str] = field(default_factory=dict)


@resource()
class Main(BaseBackbone[None, MainInput, MainOutput]):

    def __init__(self, logger, input: MainInput | Connector):
        super().__init__(logger, UUID('a81054b2-bb57-4969-b3c5-308fee049e02'))

        self.resources.simple = Simple(
            logger,
            input=SimpleInput(
                vpc_cidr_block=input.vpc_cidr_block,
                tags=input.tags
            )
        )
        self.resources.main_rt = RouteTable(logger, vpc_id=self.resources.simple.output.vpc.vpc_id)

        self._set_output(
            MainOutput(
                vpc_id=self.resources.simple.output.vpc.vpc_id
            )
        )


if __name__ == "__main__":
    setup_logging(console_level=log_func.ABOVE_DEBUG)
    rm = FileResourceManager(None, "state.json")
    provider = AwsLocalStackProvider(None)
    bb = Main(None, input=MainInput(
        vpc_cidr_block="10.212.160.0/22",
        tags={"mytag": "mytagvalue"}
    ))
    bb.apply(rm, provider, False)
