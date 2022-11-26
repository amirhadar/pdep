from pdep.aws.backbones.app.interfaces import SimpleAppBBInput, SimpleAppBBOutput
from pdep.aws.ecs import EcsCluster, EcsClusterInput
from pdep.aws.eventbridge import EventBusInput, EventBus
from pdep.aws.elb import AlbInput, Alb
from pdep.plan import BaseBackbone


class SimpleAppBB(BaseBackbone[SimpleAppBBInput, SimpleAppBBOutput]):

    def do_init_resources(self):
        self.resources.cluster = EcsCluster(EcsClusterInput(
            name=f"{self.input.name}-main",
            tags=self.input.tags
        ))

        self.resources.event_bus = EventBus(EventBusInput(
            name=f"{self.input.name}-main",
            tags=self.input.tags
        ))

        self.resources.alb = Alb(AlbInput(
            name=f"{self.input.name}-main",
            security_group_id=self.input.simple_net_bb.security_group.security_group_id,
            subnet_ids=[subnet.subnet_id for subnet in self.input.simple_net_bb.private_subnets],
            scheme="internal",
            tags=self.input.tags
        ))

        self._output = SimpleAppBBOutput(
            name=self.input.name,
            ecs_cluster=self.resources.cluster.output,
            event_bus=self.resources.event_bus.output,
            alb=self.resources.alb.output
        )
