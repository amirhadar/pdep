from dataclasses import dataclass, field
from typing import List, Optional, Dict
from dataclasses_json import dataclass_json

from pdep import zstr
from pdep.aws.backbones.net.interfaces import BasicNetBBOutput
from pdep.aws.network import VpcOutput, RouteTableOutput, SubnetOutput, SecurityGroupOutput


@dataclass_json
@dataclass
class SimpleAppBBInput:
    simple_net_bb: BasicNetBBOutput = field(default_factory=BasicNetBBOutput)


@dataclass_json
@dataclass
class SimpleAppBBOutput:
    alb: str = None
    evb: str = None
    ecs_cluster: str = None


