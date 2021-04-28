""" Commands handler """

import sys
from collections import OrderedDict
from knack.util import CLIError
from knack.log import get_logger
import azure.cli.core.commands.progress as progress
from azure.cli.command_modules.resource.custom import deploy_arm_template_at_resource_group, get_deployment_at_resource_group, delete_resource
from azure.cli.command_modules.resource.custom import run_bicep_command
from azure.cli.core.util import user_confirmation
from azure.cli.core import __version__ as azure_cli_core_version
from azure.cli.core.commands.client_factory import get_subscription_id

# from azure.cli.core.commands.parameters import resource_group_name_type
from azext_cdf.parser import ConfigParser, CONFIG_PARAMS
from azext_cdf.parser import LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN #  LIFECYCLE_PRE_TEST, LIFECYCLE_POST_TEST, LIFECYCLE_ALL
from azext_cdf.version import version
from azext_cdf.utils import json_write_to_file, find_the_right_file, dir_change_working, json_load, file_read_content, file_exits
from azext_cdf.hooks import run_hook, run_hook_lifecycle
from azext_cdf.state import STATE_PHASE_GOING_UP, STATE_PHASE_UP, STATE_PHASE_DOWN, STATE_PHASE_GOING_DOWN # STATE_PHASE_TESTED, STATE_PHASE_TESTING,
from azext_cdf.state import STATE_STATUS_SUCCESS, STATE_STATUS_ERROR #, STATE_STATUS_FAILED
from azext_cdf.provisioner import run_bicep, run_arm_deployment

_logger = get_logger(__name__)

CONFIG_DEFAULT = ".cdf.yml"


def _init_config(config, remove_tmp=False, working_dir=None, state_file=None):
    if working_dir:
        dir_change_working(working_dir)
    cobj = ConfigParser(config, remove_tmp, state_file)
    return cobj


def test_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    # pylint: disable=unused-argument
    # TODO
    # p = progress.ProgressReporter(message="Hello")
    import time
    v = progress.get_progress_view()
    controller = progress.ProgressHook()
    controller.init_progress(v)
    controller.begin(message="Starting hook")
    time.sleep(4)
    controller.end(message="Fished hook")
    time.sleep(1)

def init_handler(cmd, config=CONFIG_DEFAULT, force=False, example=False, working_dir=None, state_file=None):
    # pylint: disable=unused-argument
    # cobj = _init_config(config, False, working_dir)
    # TODO
    pass


def hook_handler(cmd, config=CONFIG_DEFAULT, hook_args=None, working_dir=None, confirm=False, state_file=None):
    # pylint: disable=unused-argument
    cobj = _init_config(config, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    if not hook_args:
        return cobj.hook_table

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

    cobj.delayed_variable_interpolite()
    run_hook(cobj, hook_args)
    return None


def status_handler(cmd, config=CONFIG_DEFAULT, events=False, working_dir=None, state_file=None):
    # pylint: disable=unused-argument
    cobj = _init_config(config, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    output_status = {}
    if events:
        output_status["events"] = cobj.state.events
    else:
        output_status = cobj.state.status
    return output_status


def debug_version_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    # pylint: disable=unused-argument
    return OrderedDict(
        [
            ("CDF", version),
            ("bicep", run_bicep_command(["--version"], auto_install=False).strip("\n")),
            ("az-cli", azure_cli_core_version),
            ("python", sys.version.strip("\n")),
        ]
    )


def debug_config_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    ''' Dump the configuration file '''
    # pylint: disable=unused-argument
    cobj = _init_config(config, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    return cobj.config


def debug_state_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    ''' Dump the state file '''
    # pylint: disable=unused-argument
    cobj = _init_config(config, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    return cobj.state.state


def debug_result_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    # pylint: disable=unused-argument
    cobj = _init_config(config, False, working_dir, state_file=state_file)
    return cobj.state.result_up


def debug_deployment_error_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, state_file=None):
    cobj = _init_config(config, remove_tmp=False, working_dir=working_dir, state_file=state_file)
    if cobj.provisioner == "bicep":
        if not file_exits(f"{cobj.tmp_dir}/targetfile.json"):
            raise CLIError(f"{cobj.tmp_dir}/targetfile.json does not exists please run up first")
        arm_deployment = json_load(file_read_content(f"{cobj.tmp_dir}/targetfile.json"))
        deployments_status = []
        deployment = _check_deployment_error(cmd, resource_group_name=cobj.resource_group_name, deployment_name=cobj.name, deployment_type="Microsoft.Resources/deployments")
        if deployment:
            deployments_status.append(deployment)

        for nested_deployment in arm_deployment["resources"]:
            deployment = _check_deployment_error(cmd, resource_group_name=cobj.resource_group_name, deployment_name=nested_deployment["name"], deployment_type=nested_deployment["type"])
            if deployment:
                deployments_status.append(deployment)
        return deployments_status


def debug_interpolate_handler(cmd, config=CONFIG_DEFAULT, working_dir=None, phase=2, state_file=None):
    # pylint: disable=unused-argument
    cobj = _init_config(config, remove_tmp=False, working_dir=working_dir, state_file=state_file)
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


def _check_deployment_error(cmd, resource_group_name, deployment_name, deployment_type):
    deployment_status = {}
    if not deployment_type == "Microsoft.Resources/deployments":
        return deployment_status
    deployment = get_deployment_at_resource_group(cmd, resource_group_name=resource_group_name, deployment_name=deployment_name)
    properties = deployment.as_dict().get("properties")
    if properties.get("provisioning_state") == "Failed":
        error = properties.get("error")
        deployment_status.update({"error": error, "name": deployment_name})
    return deployment_status


def down_handler(cmd, config=CONFIG_DEFAULT, remove_tmp=False, working_dir=None, state_file=None):
    cobj = _init_config(config, remove_tmp=remove_tmp, working_dir=working_dir, state_file=state_file)
    cobj.state.transition_to_phase(STATE_PHASE_GOING_DOWN)
    run_hook_lifecycle(cobj, LIFECYCLE_PRE_DOWN)
    try:
        if cobj.provisioner == "bicep" or cobj.provisioner == "arm":
            _down_bicep(cmd, cobj)
    except CLIError as error:
        cobj.state.add_event(f"Errored during down phase: {str(error)}", STATE_STATUS_ERROR)
        raise CLIError(error) from error
    except Exception as error:
        cobj.state.add_event(f"General error during down phase: {str(error)}", STATE_STATUS_ERROR)
        raise

    try:
        if cobj.managed_resource:
            delete_resource(cmd, resource_ids=[f"/subscriptions/{get_subscription_id(cmd.cli_ctx)}/resourceGroups/{cobj.resource_group_name}"])
    except Exception as error:
        if "failed to be deleted" not in str(error):
            raise error from error

    cobj.state.set_result(outputs={}, resources={}, flush=True)
    cobj.state.completed_phase(STATE_PHASE_DOWN, STATE_STATUS_SUCCESS, msg="")
    run_hook_lifecycle(cobj, LIFECYCLE_POST_DOWN)


def _down_bicep(cmd, cobj):
    # TODO check deployment exists before doing an empty deployment
    empty_deployment = {
        "$schema": "http://schema.management.azure.com/schemas/2015-01-01/deploymentTemplate.json#",
        "contentVersion": "1.0.0.0",
        "parameters": {},
        "variables": {},
        "resources": [],
        "outputs": {},
    }
    json_write_to_file(f"{cobj.tmp_dir}/empty_deployment.json", empty_deployment)
    try:
        deploy_arm_template_at_resource_group(
            cmd, resource_group_name=cobj.resource_group_name, template_file=f"{cobj.tmp_dir}/empty_deployment.json", deployment_name=cobj.name, mode="Complete", no_wait=False
        )
    except CLIError as error:
        if "ResourceGroupNotFound" in str(error):
            pass
        else:
            raise CLIError(error) from error


def up_handler(cmd, config=CONFIG_DEFAULT, remove_tmp=False, prompt=False, working_dir=None, state_file=None):
    # pylint: disable=unused-argument
    cobj = _init_config(config, remove_tmp=remove_tmp, working_dir=working_dir, state_file=state_file)
    cobj.state.transition_to_phase(STATE_PHASE_GOING_UP)
    # Run pre up life cycle
    run_hook_lifecycle(cobj, LIFECYCLE_PRE_UP)
    # Run template interpolate
    cobj.delayed_up_interpolite()
    try:
        if cobj.provisioner == "bicep":
            output_resources, outputs = run_bicep(
                cmd,
                deployment_name=cobj.name,
                bicep_file=find_the_right_file(cobj.up_file, "bicep", "*.bicep", cobj.config_dir),
                tmp_dir=cobj.tmp_dir,
                resource_group=cobj.resource_group_name,
                location=cobj.location,
                params=cobj.data[CONFIG_PARAMS],
                manage_resource_group=cobj.managed_resource,
                no_prompt=False,
                complete_deployment=cobj.deployment_mode,
            )
        elif cobj.provisioner == "arm":
            output_resources, outputs =  run_arm_deployment(
                cmd,
                deployment_name=cobj.name,
                arm_template_file=find_the_right_file(cobj.up_file, "arm", "*.json", cobj.config_dir),
                resource_group=cobj.resource_group_name,
                location=cobj.location,
                params=cobj.data[CONFIG_PARAMS],
                manage_resource_group=cobj.managed_resource,
                no_prompt=False,
                complete_deployment=cobj.deployment_mode,
            )

    except CLIError as error:
        cobj.state.add_event(f"Errored during up phase: {str(error)}", STATE_STATUS_ERROR)
        raise
    except Exception as error:
        cobj.state.add_event(f"General error during up phase: {str(error)}", STATE_STATUS_ERROR)
        raise

    cobj.state.set_result(outputs=outputs, resources=output_resources, flush=True)
    cobj.state.completed_phase(STATE_PHASE_UP, STATE_STATUS_SUCCESS, msg="")
    run_hook_lifecycle(cobj, LIFECYCLE_POST_UP)
