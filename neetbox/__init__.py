import os
import sys

import neetbox.daemon as daemon
import neetbox.extension as extension  # DO NOT remove this import
from neetbox.client import action, add_image
from neetbox.config import get_module_level_config


def _load_workspace(connect_daemon=True):
    get_module_level_config()  # run things after init workspace
    extension._init_extensions()
    if connect_daemon:
        daemon.connect()


is_in_daemon_process = (
    "NEETBOX_DAEMON_PROCESS" in os.environ and os.environ["NEETBOX_DAEMON_PROCESS"] == "1"
)

if len(sys.argv) > 0 and sys.argv[0].endswith("neet") or is_in_daemon_process:
    # running in cli or daemon process, do not load workspace
    pass
else:
    _load_workspace(connect_daemon=True)


__all__ = ["add_image", "action", "logger"]
