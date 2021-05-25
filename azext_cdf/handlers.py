""" Commands handler """

import sys
import os
from collections import OrderedDict
from knack.util import CLIError
from knack.log import get_logger
from azure.cli.command_modules.resource.custom import run_bicep_command
from azure.cli.core.util import user_confirmation
from azure.cli.core import __version__ as azure_cli_core_version
from azext_cdf.parser import LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN #  LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL
from azext_cdf.version import VERSION
from azext_cdf.utils import dir_change_working, json_load, file_read_content, file_exists
from azext_cdf.utils import Progress, init_config
from azext_cdf.hooks import run_hook, run_hook_lifecycle
from azext_cdf.state import STATE_PHASE_GOING_UP, STATE_PHASE_UP, STATE_PHASE_DOWN, STATE_PHASE_GOING_DOWN # STATE_PHASE_TESTED, STATE_PHASE_TESTING,
from azext_cdf.state import STATE_STATUS_SUCCESS, STATE_STATUS_ERROR #, STATE_STATUS_FAILED
from azext_cdf.provisioner import de_provision, provision, check_deployment_error
from azext_cdf.tester import run_test
from azext_cdf.parser import ConfigParser

_LOGGER = get_logger(__name__)

CONFIG_DEFAULT = ".cdf.yml"

# pylint: disable=unused-argument
def test_handler(cmd, config=CONFIG_DEFAULT, exit_on_first_error=False, test_args=None, working_dir=None, state_file=None, always_clean_up=False, always_keep=False):
    """ test handler function. Run all tests or specific ones """

    if always_clean_up and always_keep:
        raise CLIError("You can only use one of flags 'alway-clean' or 'always-keep'.")
    working_dir = os.path.realpath(working_dir)
    cobj, cwd = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    Progress(cmd, pseudo=True) # hacky way to disable default progress animation
    dir_change_working(cwd)
    if test_args:
        for test in test_args:
            if not test in cobj.tests:
                raise CLIError(f"unknown test name '{test}', Supported hooks '{cobj.tests}")
    else:
        test_args = cobj.tests

    results = run_test(cmd, cobj, config, cwd, exit_on_first_error, test_args, working_dir, state_file, always_clean_up, always_keep)
    # print status to screen
    # gen = (x for x in xyz if x not in a)
    one_test_failed = False
    for test in results:
        if results[test]["failed"]:
            one_test_failed = True
            _LOGGER.warning(results[test])
    if one_test_failed:
        raise CLIError("At-least on test failed")
    return results

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
        for key, value in cobj.hooks_dict:
            lifecycle = value["lifecycle"]
            if isinstance(lifecycle, str):
                lifecycle = [lifecycle]
            output_hooks.append({"name": key, "description": value["description"], "lifecycle": lifecycle})
        return output_hooks

    hook_name = hook_args[0]  # hook is the first arg
    hooks_names = cobj.hook_names
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

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    output_status = {}
    if events:
        output_status["events"] = cobj.state.events
    else:
        output_status = cobj.state.status
    return output_status


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


def debug_config_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None, validate=False):
    ''' debug config handler, dump the configuration file'''

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    if validate:
        return None
    return cobj.config


def debug_state_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    ''' debug state handler, return state content '''

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    return cobj.state.state


def debug_result_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    ''' debug result handler, return results after up'''

    cobj, _ = init_config(config, False, working_dir, state_file=state_file)
    return cobj.state.result_up


def debug_deployment_error_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    ''' debug deployment error handler, return results last known deployment error '''

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    if cobj.provisioner == "bicep" or cobj.provisioner == "arm":
        if not file_exists(f"{cobj.tmp_dir}/targetfile.json"):
            raise CLIError(f"{cobj.tmp_dir}/targetfile.json does not exists please run up first")
        arm_deployment = json_load(file_read_content(f"{cobj.tmp_dir}/targetfile.json"))
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

    cobj, _ = init_config(config, ConfigParser, remove_tmp=False, working_dir=working_dir, state_file=state_file)
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

def down_handler(cmd, config=CONFIG_DEFAULT, remove_tmp=False, working_dir=None, state_file=None):
    ''' down handler, Destroy a provisioned environment '''

    Progress(cmd, pseudo=True) # hacky way to disable default progress animation
    cobj, _ = init_config(config, ConfigParser, remove_tmp=remove_tmp, working_dir=working_dir, state_file=state_file)
    cobj.state.transition_to_phase(STATE_PHASE_GOING_DOWN)
    run_hook_lifecycle(cobj, LIFECYCLE_PRE_DOWN)
    try:
        de_provision(cmd, cobj)
    except CLIError as error:
        cobj.state.add_event(f"Errored during down phase: {str(error)}", STATE_STATUS_ERROR)
        raise CLIError(error) from error
    except Exception as error:
        cobj.state.add_event(f"General error during down phase: {str(error)}", STATE_STATUS_ERROR)
        raise

    cobj.state.completed_phase(STATE_PHASE_DOWN, STATE_STATUS_SUCCESS, msg="")
    run_hook_lifecycle(cobj, LIFECYCLE_POST_DOWN)

def up_handler(cmd, config=CONFIG_DEFAULT, remove_tmp=False, prompt=False, working_dir=None, state_file=None, destroy=False):
    ''' up handler, Provision an environment '''

    Progress(cmd, pseudo=True) # hacky way to disable default progress animation
    if destroy:
        cwd = os.getcwd()
        down_handler(cmd, config=config, remove_tmp=remove_tmp, working_dir=working_dir, state_file=state_file)
        dir_change_working(cwd)

    cobj, _ = init_config(config, ConfigParser, remove_tmp=remove_tmp, working_dir=working_dir, state_file=state_file)
    cobj.state.transition_to_phase(STATE_PHASE_GOING_UP)
    # Run pre up life cycle
    run_hook_lifecycle(cobj, LIFECYCLE_PRE_UP)
    # p = Progress()
    try:
        provision(cmd, cobj)
    except CLIError as error:
        cobj.state.add_event(f"Errored during up phase: {str(error)}", STATE_STATUS_ERROR)
        raise
    except Exception as error:
        cobj.state.add_event(f"General error during up phase: {str(error)}", STATE_STATUS_ERROR)
        raise
    cobj.state.completed_phase(STATE_PHASE_UP, STATE_STATUS_SUCCESS, msg="")
    run_hook_lifecycle(cobj, LIFECYCLE_POST_UP)
