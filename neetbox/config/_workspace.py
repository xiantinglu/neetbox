# -*- coding: utf-8 -*-
#
# Author: GavinGong aka VisualDust
# Github: github.com/visualDust
# Date:   20230413


import inspect
import os
import sys
import types
import uuid
from importlib.metadata import version
from threading import Thread
from typing import Union
from uuid import uuid4

import toml

from neetbox.utils.framing import get_frame_module_traceback
from neetbox.utils.massive import check_read_toml, update_dict_recursively

CONFIG_FILE_NAME = f"neetbox.toml"
NEETBOX_VERSION = version("neetbox")

_DEFAULT_WORKSPACE_CONFIG = {
    "name": os.path.basename(os.path.normpath(os.getcwd())),
    "version": NEETBOX_VERSION,
    "projectid": str(uuid4()),  # later will be overwrite by workspace config file
    "logging": {"level": "INFO", "logdir": "logs"},
    "extension": {
        "autoload": True,
    },
    "client": {
        "enable": True,
        "host": "127.0.0.1",
        "port": 20202,
        "allowIpython": False,
        "mute": True,
        "mode": "detached",
        "uploadInterval": 1,
    },
}


def _obtain_new_run_id():
    """put a new run id into config. do not run before workspace loaded as a project.

    Returns:
        str: new run id
    """
    global _DEFAULT_WORKSPACE_CONFIG
    _DEFAULT_WORKSPACE_CONFIG["runid"] = str(uuid4())
    return _DEFAULT_WORKSPACE_CONFIG["runid"]


_QUERY_ADD_EXTENSION_DEFAULT_CONFIG = []

_IS_WORKSPACE_LOADED = False
_QUERY_AFTER_CONFIG_LOAD = []


def on_config_loaded(func):
    if _IS_WORKSPACE_LOADED:  # if workspace already loaded
        Thread(target=func, daemon=True).start()  # run target
    else:  # not loaded yet, append to query
        global _QUERY_AFTER_CONFIG_LOAD
        _QUERY_AFTER_CONFIG_LOAD.append(func)
    return func


def export_default_config(func):
    global _QUERY_ADD_EXTENSION_DEFAULT_CONFIG
    if _IS_WORKSPACE_LOADED:
        raise RuntimeError("should not add default config after workspace loaded")
    _QUERY_ADD_EXTENSION_DEFAULT_CONFIG.append(func)
    return func


def _build_global_config_dict_for_module(module, local_config):
    """build a global config from a local config of a module. for example:
    - local config in neetbox/moduleA/some.py: { { "a" : 1 } }
    - the returned global config: {
        moduleA: {
            some: {
                "a" : 1
            }
        }
    }

    Args:
        module (_type_): _description_
        local_config (_type_): _description_
    """

    def _form_global_config_dict_from_module_name_list(
        pass_in_a_empty_dict_to_operate, module_name_list, local_config
    ):
        """turn a local config to a global config.
        Args:
            pass_in_a_empty_dict_to_operate (dict): pass in a empty dict, this function directly write into the dict, no value is returned.
            module_name_list (list): list of splited module names, for example, should be ["neetbox", "moduleA", "some"] for module neetbox.moduleA.some.
            local_config (dict): the local config of the sub module
        """
        for module_name in module_name_list:
            pass_in_a_empty_dict_to_operate[module_name] = {}
            pass_in_a_empty_dict_to_operate = pass_in_a_empty_dict_to_operate[module_name]
        for _k, _v in local_config.items():
            pass_in_a_empty_dict_to_operate[_k] = _v

    try:
        config = {}
        module_names = module.__name__.split(".")
        if module_names[0] == "neetbox":
            module_names.pop(0)
        _form_global_config_dict_from_module_name_list(config, module_names, local_config)
        return config
    except Exception as e:
        raise e


def _update_default_config_from_config_register():
    """iterate through config register to read their default config and write the result into global config. DO NOT run after workspace loaded.

    Raises:
        e: any possible exception
    """
    global _DEFAULT_WORKSPACE_CONFIG
    for fun in _QUERY_ADD_EXTENSION_DEFAULT_CONFIG:
        try:
            local_config = fun()
            parsed_local_config = _build_global_config_dict_for_module(
                inspect.getmodule(fun), local_config
            )
            update_dict_recursively(_DEFAULT_WORKSPACE_CONFIG, parsed_local_config)
        except Exception as e:
            raise e


def _update_default_workspace_config_with(cfg: dict):
    global _DEFAULT_WORKSPACE_CONFIG
    update_dict_recursively(_DEFAULT_WORKSPACE_CONFIG, cfg)
    return _DEFAULT_WORKSPACE_CONFIG


def _init_workspace(path=None, **kwargs) -> bool:
    if path:
        os.chdir(path=path)
    current_path = os.getcwd()
    config_file_path = os.path.join(current_path, CONFIG_FILE_NAME)
    if not os.path.exists(config_file_path):  # config file not exist
        try:  # creating config file using default config
            with open(config_file_path, "w+") as config_file:
                import neetbox.extension as extension

                extension._scan_sub_modules()
                _update_default_config_from_config_register()  # load custom config into default config
                _config = _DEFAULT_WORKSPACE_CONFIG
                if "name" in kwargs and kwargs["name"]:  # using given name
                    _config["name"] = kwargs["name"]
                else:  # using the folder name
                    _config["name"] = os.path.basename(os.path.normpath(os.getcwd()))
                _config["projectid"] = str(uuid.uuid4())
                toml.dump(_config, config_file)
            return True
        except Exception as e:
            raise e
    else:  # config file exist:
        raise RuntimeError(f"{config_file_path} already exist")


def _check_if_workspace_config_valid(path=None) -> bool:
    path = path or "."
    config_file_path = os.path.join(path, CONFIG_FILE_NAME)
    if not os.path.isfile(config_file_path):  # but config file not exist
        return False
    try:
        toml.load(config_file_path)  # try load as toml
        return config_file_path
    except Exception as e:
        return False


def _load_workspace_config(folder="."):
    global _IS_WORKSPACE_LOADED
    config_file_path = _check_if_workspace_config_valid(
        path=folder
    )  # check if config file is valid
    if not config_file_path:  # failed to load workspace config, exiting
        raise RuntimeError(f"Config file not exists in '{folder}'")
    import neetbox.extension as extension

    extension._scan_sub_modules()
    _update_default_config_from_config_register()  # load custom config into default config
    _obtain_new_run_id()  # obtain new run id
    config_from_file = toml.load(config_file_path)
    if "version" not in config_from_file or config_from_file["version"] != NEETBOX_VERSION:
        raise RuntimeError(
            f"config file version not match: using neetbox version {NEETBOX_VERSION} but got config from version {config_from_file['version']}"
        )
    _update_default_workspace_config_with(config_from_file)  # load config file in

    if (
        len(sys.argv) > 0
        and sys.argv[0].endswith("neet")
        or ("NEETBOX_DAEMON_PROCESS" in os.environ and os.environ["NEETBOX_DAEMON_PROCESS"] == "1")
    ):
        pass
    else:  # on workspace loaded
        _IS_WORKSPACE_LOADED = True
        for func in _QUERY_AFTER_CONFIG_LOAD:
            Thread(target=func, daemon=True).start()


def _create_load_workspace(folder="."):
    is_workspace = check_read_toml(path=os.path.join(folder, CONFIG_FILE_NAME))
    if not is_workspace:
        _init_workspace(folder)
    _load_workspace_config()


def _get_module_level_config(module: Union[str, types.ModuleType] = None, **kwargs):
    """get a module level config from global config

    Args:
        module (str or module, optional): which module's config to get. Defaults to None(which means neetbox will automatically find the module in which this function is called). if you want to get all the global config, pass "@" for module.

    Returns:
        dict: the config you want.
    """
    try:
        traceback = 2 if "traceback" not in kwargs else kwargs["traceback"]
        module = (
            module or get_frame_module_traceback(traceback=traceback).__name__  # type: ignore
        )  # try to trace if module not given
        if type(module) is not str:  # try to trace the belonging module of the given object
            module = inspect.getmodule(module).__name__  # type: ignore
    except Exception:
        module = "@"  # faild to trace, returning all configs
    the_config = _DEFAULT_WORKSPACE_CONFIG
    sub_module_names = module.split(".")
    if len(sub_module_names):
        if sub_module_names[0] == "neetbox":
            # skip 'neetbox'
            sub_module_names.pop(0)
        for sub_module in sub_module_names:
            sub_module = sub_module.removeprefix("_").removesuffix("_")
            if sub_module not in the_config:
                return the_config
            the_config = the_config[sub_module]
    return the_config
