from pprint import pprint
from uuid import UUID
from pdep import FileResourceManager, AwsLocalStackProvider
from pdep.aws.backbones.net.interfaces import BasicNetBBInput
from pdep.aws.backbones.net.simplenetbb import SimpleNetBB
from pdep.utils import setup_logging, log_func


def deploy():
    setup_logging(console_level=log_func.ABOVE_DEBUG)
    rm = FileResourceManager("state.json")
    provider = AwsLocalStackProvider(None)

    rm.folder = "/"

    bb = SimpleNetBB(BasicNetBBInput(
        vpc_cidr_block="10.212.160.0/22",
        subnets_num=2,
        region="us-east-1",
        tags={"mytag": "mytagvalue"}
    ), UUID('a81054b2-bb57-4969-b3c5-308fee049e02'))

    bb.apply(rm, provider, dry=False, check_drift=True)
    pprint(bb.output)

if __name__ == "__main__":
    deploy()
