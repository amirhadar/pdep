from dataclasses import dataclass, field
from typing import Dict, Any
import botocore.exceptions
from dataclasses_json import dataclass_json
from pdep import zstr
from pdep.plan import SimplifiedResource
from pdep.utils import log_func, _dict_to_aws_tags


@dataclass_json
@dataclass
class EventBusInput:
    name: zstr = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass_json
@dataclass
class EventBusOutput:
    name: zstr = None
    arn: zstr = None


class EventBus(SimplifiedResource[EventBusInput, EventBusOutput]):

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self.output.arn = "event-bus-dummy-arn"
            return

        response = None
        events = provider.create_client('events')
        try:
            response = events.create_event_bus(
                Name=self.input.name,
                Tags=_dict_to_aws_tags(self.input.tags)
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        if response is None and dry:
            response = {
                'EventBusArn': f'arn:this-is-a-dummy-bus{self.input.name}',
            }

        self._output.name = self.input.name
        self._output.arn = response['EventBusArn']

    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        events = provider.create_client('events')
        try:
            events.delete_event_bus(Name=self.input.name)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

    @log_func()
    def is_drifted(self, provider, dry):
        events = provider.create_client('events')
        try:
            res = events.describe_event_bus(Name=self.input.name)
            return res['Name'] != self.input.name
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        return True
