from dataclasses import dataclass
from typing import List, Dict

from dataclasses_json import dataclass_json


@dataclass_json
@dataclass
class RegionAvailabilityZone:
    name: str


@dataclass_json
@dataclass
class Region:
    name: str
    availability_zones: List[RegionAvailabilityZone]


@dataclass_json
@dataclass
class AwsInfo:
    regions: Dict[str, Region]


aws_info = AwsInfo(
    regions={
        "us-east-1":
            Region(
                name="us-east-1",
                availability_zones=[
                    RegionAvailabilityZone(name="us-east-1" + letter)
                    for letter in "abcdef"
                ]
            )
    }
)


def get_aws_info() -> AwsInfo:
    return aws_info
