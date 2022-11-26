from pprint import pprint
from uuid import UUID
from pdep import FileResourceManager, AwsLocalStackProvider
from pdep.aws.backbones.app.interfaces import SimpleAppBBInput
from pdep.aws.backbones.app.simpleappbb import SimpleAppBB
from pdep.aws.backbones.net.interfaces import BasicNetBBOutput
from pdep.utils import setup_logging, log_func


def deploy():
    setup_logging(console_level=log_func.ABOVE_DEBUG)
    rm = FileResourceManager("state.json")
    provider = AwsLocalStackProvider(None)

    rm.folder = "/myenv"

    bb = SimpleAppBB(
        SimpleAppBBInput(
            name=rm.folder.replace('/', '_'),
            simple_net_bb=rm.get_output(BasicNetBBOutput)
        ),
        UUID('a4a8393f-aead-4396-9e29-038f4b346104')
    )
    bb.apply(rm, provider, dry=False, check_drift=True)
    pprint(bb.output)


if __name__ == "__main__":
    deploy()
