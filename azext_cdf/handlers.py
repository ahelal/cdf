""" Commands handler """

import sys
import os
from collections import OrderedDict
from knack.util import CLIError
from knack.log import get_logger
from azure.cli.command_modules.resource.custom import run_bicep_command
from azure.cli.core.util import user_confirmation
from azure.cli.core import __version__ as azure_cli_core_version
from azext_cdf.version import VERSION
from azext_cdf.utils import dir_change_working, json_load, file_read_content, file_exists, convert_to_list_if_need
from azext_cdf.utils import Progress, init_config
from azext_cdf.hooks import run_hook
from azext_cdf._def import STATE_PHASE_UP, STATE_STATUS_SUCCESS
from azext_cdf.provisioner import de_provision, provision, check_deployment_error
from azext_cdf.tester import run_test
from azext_cdf.parser import ConfigParser

_LOGGER = get_logger(__name__)
CONFIG_DEFAULT = ".cdf.yml"
# pylint: disable=unused-argument


def debug_version_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    """ debug version function, return versions """

    return OrderedDict(
        [
            ("CDF", VERSION),
            ("bicep", run_bicep_command(["--version"], auto_install=False).strip("\n")),
            ("az-cli", azure_cli_core_version),
            ("python", sys.version.strip("\n")),
        ]
    )


def debug_config_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    ''' debug config handler, dump the configuration file'''

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file, state_locking=False)
    return cobj.config


def debug_state_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    ''' debug state handler, return state content '''

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file, state_locking=False)
    return cobj.state.state


def debug_result_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    ''' debug result handler, return results after up'''

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file, state_locking=False)
    return cobj.state.result_up


def debug_deployment_error_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    ''' debug deployment error handler, return results last known deployment error '''

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file, state_locking=False)
    if cobj.provisioner == "bicep" or cobj.provisioner == "arm":
        if not file_exists(f"{cobj.tmp_dir}/{cobj.name}_deployment.json"):
            raise CLIError(f"{cobj.tmp_dir}/{cobj.name}_deployment.json does not exists please run up first")
        arm_deployment = json_load(file_read_content(f"{cobj.tmp_dir}/{cobj.name}_deployment.json"))
        deployments_status = []
        deployment = check_deployment_error(cmd, resource_group_name=cobj.resource_group_name, deployment_name=cobj.name, deployment_type="Microsoft.Resources/deployments")
        if deployment:
            deployments_status.append(deployment)

        for nested_deployment in arm_deployment["resources"]:
            deployment = check_deployment_error(cmd, resource_group_name=cobj.resource_group_name, deployment_name=nested_deployment["name"], deployment_type=nested_deployment["type"])
            if deployment:
                deployments_status.append(deployment)
        return deployments_status
    if cobj.provisioner == "terraform":
        raise CLIError('terraform errors not yet supported')
        # TODO add terraform errors
    return None


def debug_interpolate_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, phase=2, state_file=None):
    ''' debug interpolate handler, start an interactive jinja2 interpolation shell like '''

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file, state_locking=False)
    line = ""
    print("Type your jinja2 expression.")
    print("to exit type 'quit' or 'exit' or 'ctrl+c'.")
    while line.lower() not in ("quit", "exit"):
        print("> ", end="")
        try:
            line = input()
            if line == "":
                break
            print(cobj.interpolate(phase=phase, template=line))
        except EOFError:
            return
        except CLIError as error:
            print(f"Error : {str(error)}")


def init_handler(cmd, config=CONFIG_DEFAULT, force=False, example=False, working_dir=None, state_file=None):
    ''' init handler '''

    # cobj, _ = init_config(config, False, working_dir)
    # TODO create an initial environment
    _LOGGER.info("Init")


def hook_handler(cmd, config=CONFIG_DEFAULT, hook_args=None, working_dir=None, confirm=False, state_file=None):
    """ hook handler function. list or run specific handler """

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    if not hook_args:
        output_hooks = []
        for key, value in cobj.get_hooks(format_list=False):
            lifecycle = convert_to_list_if_need(value["lifecycle"])
            output_hooks.append({"name": key, "description": value["description"], "lifecycle": lifecycle})
        return output_hooks

    hook_name = hook_args[0]  # hook is the first arg
    hooks_names = cobj.get_hooks(format_list=True)
    if hook_name not in hooks_names:
        raise CLIError(f"unknown hook name '{hook_name}', Supported hooks '{hooks_names}")
    status = cobj.state.status
    if confirm:
        pass
    elif not status["Phase"] == STATE_PHASE_UP:
        user_confirmation(f"You want to run a hook when the phase is not up '{status['Phase']}'. Are you sure ?")
    elif not status["Status"] == STATE_STATUS_SUCCESS:
        user_confirmation(f"You want to run a hook when the last status is not success '{status['Phase']}'. Are you sure ?")
    run_hook(cobj, hook_args)
    return None


def status_handler(cmd, config=CONFIG_DEFAULT, events=False, working_dir=None, state_file=None):
    """ status handler function, return status """

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file, state_locking=False)
    output_status = {}
    if events:
        output_status["events"] = cobj.state.events
    else:
        output_status = cobj.state.status
    return output_status


def down_handler(cmd, config=CONFIG_DEFAULT, remove_tmp=False, working_dir=None, state_file=None):
    ''' down handler, Destroy a provisioned environment '''

    Progress(cmd, pseudo=True)  # hacky way to disable default progress animation
    cobj, _ = init_config(config, ConfigParser, remove_tmp=remove_tmp, working_dir=working_dir, state_file=state_file)
    de_provision(cmd, cobj)


def up_handler(cmd, config=CONFIG_DEFAULT, remove_tmp=False, prompt=False, working_dir=None, state_file=None, destroy=False):
    ''' up handler, Provision an environment '''

    Progress(cmd, pseudo=True)  # hacky way to disable default progress animation
    if destroy:
        cwd = os.getcwd()
        down_handler(cmd, config=config, remove_tmp=remove_tmp, working_dir=working_dir, state_file=state_file)
        dir_change_working(cwd)

    cobj, _ = init_config(config, ConfigParser, remove_tmp=remove_tmp, working_dir=working_dir, state_file=state_file)
    provision(cmd, cobj)


def test_handler(cmd, config=CONFIG_DEFAULT, test_args=None, working_dir=None, state_file=None, exit_on_error=False, down_strategy="success", upgrade_strategy="all"):
    """ test handler function. Run all tests or specific ones """

    if working_dir is not None:
        working_dir = os.path.realpath(working_dir)

    cobj = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file)[0]
    Progress(cmd, pseudo=True)  # hacky way to disable default progress animation
    dir_change_working(working_dir)
    if not test_args:
        test_args = cobj.tests
    for test in test_args:
        if test not in cobj.tests:
            raise CLIError(f"unknown test name '{test}', Supported tests '{cobj.tests}")

    results = run_test(cmd, cobj, config, exit_on_error, test_args, working_dir, down_strategy, upgrade_strategy)
    # print status to screen
    one_test_failed = False
    upgrade_failed = []
    for upgrade in results:
        for test_name in results[upgrade]:
            test = results[upgrade][test_name]
            if test["failed"]:
                upgrade_failed.append(upgrade)
                one_test_failed = True
                _LOGGER.warning(test)
    if one_test_failed:
        raise CLIError(f"At-least on test failed in the following upgrades paths: {set(upgrade_failed)}")
