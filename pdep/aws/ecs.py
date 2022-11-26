from dataclasses import dataclass, field
from typing import Dict, Any
import botocore.exceptions
from dataclasses_json import dataclass_json
from pdep import zstr
from pdep.plan import SimplifiedResource
from pdep.utils import log_func, do_with_timeout, _dict_to_aws_tags


def ecs_set_tags(ecs, tags, dry, arn):
    try:
        ecs.tag_resource(
            resourceArn=arn,
            tags=_dict_to_aws_tags(tags)
        )
    except botocore.exceptions.ClientError as e:
        if 'DryRunOperation' in e.response['Error']['Code'] and dry:
            pass
        else:
            raise


@dataclass_json
@dataclass
class EcsClusterInput:
    name: zstr = None
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass_json
@dataclass
class EcsClusterOutput:
    name: zstr = None
    arn: zstr = None
    state: zstr = None


class EcsCluster(SimplifiedResource[EcsClusterInput, EcsClusterOutput]):

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self.output.arn = "cluster-dummy-arn"
            return

        response = None
        ecs = provider.create_client('ecs')
        try:
            response = ecs.create_cluster(
                clusterName=self.input.name
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        if response is None and dry:
            response = {
                'clusterArn': f'arn:this-is-a-dummy-cluster{self.input.name}',
                'clusterName': self.input.name
            }

        self._output.name = response['cluster']['clusterName']
        self._output.arn = response['cluster']['clusterArn']

        ecs_set_tags(ecs, self.input.tags, dry, self._output.arn)

        def check_cluster_status():
            res = ecs.describe_clusters(clusters=[self._output.arn])
            status = res['clusters'][0]['status']
            self._output.state = status
            return status != 'ACTIVE'

        do_with_timeout(check_cluster_status, 30)


    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        ecs = provider.create_client('ecs')
        try:
            ecs.delete_cluster(cluster=self._output.arn)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

    @log_func()
    def is_drifted(self, provider, dry):
        ecs = provider.create_client('ecs')
        try:
            res = ecs.describe_clusters(clusters=[self._output.arn])
            status = res['clusters'][0]['status']
            return status != 'ACTIVE'
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        return True