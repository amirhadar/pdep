from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Literal, List
import botocore.exceptions
from dataclasses_json import dataclass_json
from dateutil.tz import tzutc

from pdep import zstr
from pdep.plan import SimplifiedResource
from pdep.utils import log_func, _dict_to_aws_tags


@dataclass_json
@dataclass
class AlbInput:
    name: zstr = None
    scheme: Literal['internet-facing', 'internal'] = 'internal'
    security_group_id: zstr = None
    subnet_ids: List[str] = field(default_factory=list)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass_json
@dataclass
class AlbOutput:
    name: zstr = None
    arn: zstr = None
    dns_name: zstr = None


class Alb(SimplifiedResource[AlbInput, AlbOutput]):

    @log_func()
    def create(self, provider, apply_uuid, dry):
        if dry:
            self.output.arn = "event-bus-dummy-arn"
            return

        tags = {"pdep_apply_uuid": str(apply_uuid)}
        tags.update(self.input.tags)

        response = None
        elbv2 = provider.create_client('elbv2')
        try:
            response = elbv2.create_load_balancer(
                Name=self.input.name,
                Type='application',
                SecurityGroups=[self.input.security_group_id],
                Subnets=self.input.subnet_ids,
                IpAddressType='ipv4',
                Scheme=self.input.scheme,
                Tags=_dict_to_aws_tags(tags)
            )
        except botocore.exceptions.ClientError as e:
            if 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        if response is None and dry:
            response = {'LoadBalancers': [{
                                              'LoadBalancerArn': 'arn:aws:elasticloadbalancing:us-east-1:000000000000:loadbalancer/app/_myenv-main/d1988681',
                                              'DNSName': '_myenv-main.elb.localhost.localstack.cloud',
                                              'CanonicalHostedZoneId': 'Z2P70J7EXAMPLE',
                                              'CreatedTime': datetime(2022, 11, 26, 14, 38, 57, 328000,
                                                                               tzinfo=tzutc()),
                                              'LoadBalancerName': '_myenv-main', 'Scheme': 'None',
                                              'VpcId': 'vpc-bd60a052', 'State': {'Code': 'provisioning'},
                                              'Type': 'application', 'AvailabilityZones': [
                    {'ZoneName': 'us-east-1a', 'SubnetId': 'subnet-57738e43'},
                    {'ZoneName': 'us-east-1b', 'SubnetId': 'subnet-60980b8b'}],
                                              'SecurityGroups': ['sg-0dec83bfda8ad8840']}],
                        'ResponseMetadata': {'RequestId': 'G2PRNEF8N9FW8MKBB3J7M3B9PC6G7LKKCCTZ4SFVMV7CQ2CC2PVF',
                                             'HTTPStatusCode': 200,
                                             'HTTPHeaders': {'content-type': 'text/xml', 'content-length': '1112',
                                                             'connection': 'close', 'access-control-allow-origin': '*',
                                                             'access-control-allow-methods': 'HEAD,GET,PUT,POST,DELETE,OPTIONS,PATCH',
                                                             'access-control-allow-headers': 'authorization,cache-control,content-length,content-md5,content-type,etag,location,x-amz-acl,x-amz-content-sha256,x-amz-date,x-amz-request-id,x-amz-security-token,x-amz-tagging,x-amz-target,x-amz-user-agent,x-amz-version-id,x-amzn-requestid,x-localstack-target,amz-sdk-invocation-id,amz-sdk-request',
                                                             'access-control-expose-headers': 'etag,x-amz-version-id',
                                                             'date': 'Sat, 26 Nov 2022 14:38:57 GMT',
                                                             'server': 'hypercorn-h11'}, 'RetryAttempts': 0}}

        self._output.name = self.input.name
        self._output.arn = response['LoadBalancers'][0]['LoadBalancerArn']
        self._output.dns_name = response['LoadBalancers'][0]['DNSName']
        waiter = elbv2.get_waiter('load_balancer_available')
        waiter.wait(LoadBalancerArns=[self._output.arn])

    @log_func()
    def do_destroy(self, env_inputs: Dict[str, Any], resource_manager, provider, apply_uuid, dry):
        if dry:
            return
        elbv2 = provider.create_client('elbv2')
        try:
            elbv2.delete_load_balancer(LoadBalancerArn=self._output.arn)
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise

    @log_func()
    def is_drifted(self, provider, dry):
        elbv2 = provider.create_client('elbv2')
        try:
            res = elbv2.describe_load_balancers(LoadBalancerArns=[self._output.arn])
            return res['LoadBalancers'][0]['State']['Code'] != 'active'
        except botocore.exceptions.ClientError as e:
            if ".NotFound" in e.response['Error']['Code']:
                pass
            elif 'DryRunOperation' in e.response['Error']['Code'] and dry:
                pass
            else:
                raise
        return True
