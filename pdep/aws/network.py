from dataclasses import dataclass
from typing import Dict, Any

from dataclasses_json import dataclass_json
from pdep import Connector, resource, BaseResource, zstr, output_property


@dataclass_json
@dataclass
class VpcState:
    vpc_id: zstr = None


@resource()
class Vpc(BaseResource[VpcState]):
    def __init__(self, cidr_block: str | Connector):
        super().__init__()

    @property
    @output_property
    def vpc_id(self) -> str | Connector:
        return self.state.vpc_id

    def create(self, provider):
        ec2 = provider.create_resource('ec2')
        vpc = ec2.create_vpc(CidrBlock=self.inputs.cidr_block)
        vpc.wait_until_available()
        self.state.vpc_id = vpc.vpc_id

    def do_destroy(self, env_state: VpcState, env_inputs: Dict[str, Any], resource_manager, provider):
        print(f"{self.__class__.__name__} destroy state:{self.state} env_state:{env_state} inputs:{self.inputs} env_inputs:{env_inputs}")

    def do_destroy_dry(self, env_state: VpcState, env_inputs: Dict[str, Any], resource_manager, provider):
        print(f"{self.__class__.__name__} destroy_dry state:{self.state} env_state:{env_state} inputs:{self.inputs} env_inputs:{env_inputs}")

    def do_apply(self, env_state: VpcState, env_inputs, resource_manager, provider):
        print(f"{self.__class__.__name__} apply state:{self.state} env_state:{env_state} inputs:{self.inputs} env_inputs:{env_inputs}")
        if env_state is None:
            self.create(provider)
            return
        if env_inputs != self.inputs:
            self.mark_destroy(resource_manager, env_state, env_inputs)
            self.create(provider)

    def do_apply_dry(self, env_state: VpcState, env_inputs, resource_manager, provider):
        print(
            f"{self.__class__.__name__} apply dry state:{self.state} env_state:{env_state} inputs:{self.inputs} env_inputs:{env_inputs}")
        self.mark_destroy(resource_manager, env_state, env_inputs)
        self.state.vpc_id = "dry_vpc"


@dataclass_json
@dataclass
class RouteTableState:
    arn: zstr = None


@resource()
class RouteTable(BaseResource[RouteTableState]):
    def __init__(self, vpc_id: str | Connector):
        super().__init__()

    @property
    @output_property
    def arn(self):
        return self.state.arn

    def do_apply(self, env_state, env_inputs, resource_manager, provider):
        print(
            f"{self.__class__.__name__} apply state:{self.state} env_state:{env_state} inputs:{self.inputs} env_inputs:{env_inputs}")

    def do_apply_dry(self, env_state, env_inputs, resource_manager, provider):
        print(
            f"{self.__class__.__name__} apply dry state:{self.state} env_state:{env_state} inputs:{self.inputs} env_inputs:{env_inputs}")
        self.state.arn = "arn:rt:somthing"
