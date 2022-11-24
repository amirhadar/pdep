from dataclasses import dataclass, field
from typing import List, Optional, Dict
from dataclasses_json import dataclass_json

from pdep import zstr
from pdep.aws.network import VpcOutput, RouteTableOutput, SubnetOutput, SecurityGroupOutput


@dataclass_json
@dataclass
class BasicNetBBInput:
    vpc_cidr_block: Optional[zstr] = None
    subnets_num: int = 2
    region: zstr = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass_json
@dataclass
class BasicNetBBOutput:
    vpc: VpcOutput = field(default_factory=VpcOutput)
    route_table: RouteTableOutput = field(default_factory=RouteTableOutput)
    security_group: SecurityGroupOutput = field(default_factory=SecurityGroupOutput)
    subnets: List[SubnetOutput] = field(default_factory=list)
    public_subnets: List[SubnetOutput] = field(default_factory=list)
    private_subnets: List[SubnetOutput] = field(default_factory=list)
    db_subnets: List[SubnetOutput] = field(default_factory=list)
