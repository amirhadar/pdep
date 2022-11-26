from dataclasses import dataclass, field
from typing import List, Optional, Dict
from dataclasses_json import dataclass_json

from pdep import zstr
from pdep.aws.backbones.net.interfaces import BasicNetBBOutput
from pdep.aws.ecs import EcsClusterOutput
from pdep.aws.eventbridge import EventBusOutput
from pdep.aws.elb import AlbOutput
from pdep.aws.network import VpcOutput, RouteTableOutput, SubnetOutput, SecurityGroupOutput


@dataclass_json
@dataclass
class SimpleAppBBInput:
    name: zstr = None
    simple_net_bb: BasicNetBBOutput = field(default_factory=BasicNetBBOutput)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass_json
@dataclass
class SimpleAppBBOutput:
    name: zstr = None
    ecs_cluster: EcsClusterOutput = None
    event_bus: EventBusOutput = None
    alb: AlbOutput = None
