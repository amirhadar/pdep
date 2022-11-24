from dataclasses import dataclass
from typing import Dict, Any

from dataclasses_json import dataclass_json

from pdep.plan import SimplifiedResource, zstr, BaseResource
from pdep.utils import log_func




@dataclass_json
@dataclass
class ResExampleInput:
    vpc_id: zstr = None


@dataclass_json
@dataclass
class ResExampleOutput:
    arn: zstr = None


class ResExample(BaseResource[ResExampleInput, ResExampleOutput]):

    @log_func()
    def do_apply(self, env_inputs, resource_manager, provider, dry, check_drift, apply_uuid):
        pass
    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        pass


@dataclass_json
@dataclass
class ImmutableResExampleInput:
    vpc_id: zstr = None


@dataclass_json
@dataclass
class ImmutableResExampleOutput:
    arn: zstr = None


class SimplifiedResExample(SimplifiedResource[ImmutableResExampleInput, ImmutableResExampleOutput]):
    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        return

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            return None

    @log_func()
    def is_drifted(self, provider, dry):
        return False
