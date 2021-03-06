""" Provisioner file """

import json
import os
from knack.util import CLIError
from knack.log import get_logger
from azure.cli.command_modules.resource.custom import get_deployment_at_resource_group
from azure.cli.command_modules.resource.custom import build_bicep_file
from azure.cli.command_modules.resource.custom import deploy_arm_template_at_resource_group, create_resource_group, delete_resource, show_resource
from azure.cli.core.commands.client_factory import get_subscription_id
from azure.core.exceptions import ResourceNotFoundError
from msrestazure.azure_exceptions import CloudError
from azext_cdf._def import CONFIG_PARAMS, LIFECYCLE_PRE_UP, LIFECYCLE_POST_UP, LIFECYCLE_PRE_DOWN, LIFECYCLE_POST_DOWN
from azext_cdf._def import STATE_PHASE_GOING_UP, STATE_PHASE_UP, STATE_PHASE_DOWN, STATE_PHASE_GOING_DOWN
from azext_cdf.hooks import run_hook_lifecycle
from azext_cdf.utils import run_command, find_the_right_file, find_the_right_dir, json_write_to_file
from azext_cdf.state import STATE_STATUS_SUCCESS, STATE_STATUS_ERROR

_LOGGER = get_logger(__name__)


def _empty_deployment(cmd, cobj):
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


def provision_rg_if_needed(cmd, cobj):
    ''' Create resource group if needed '''

    if cobj.managed_resource and not _resource_group_exists(cmd, cobj.resource_group_name):
        resource_group_tags = cobj.first_phase_vars["vars"].get("resource_group_tags", False)
        tags = {"managed_by": "CDF", "deployment": cobj.name}
        if isinstance(resource_group_tags, dict):
            tags = resource_group_tags
        create_resource_group(cmd, rg_name=cobj.resource_group_name, location=cobj.location, tags=tags)


def _resource_group_exists(cmd, resource_group):
    try:
        show_resource(cmd, resource_ids=[f"/subscriptions/{get_subscription_id(cmd.cli_ctx)}/resourceGroups/{resource_group}"])
    except ResourceNotFoundError:
        return False
    except CloudError as error:
        if "ResourceGroupNotFound" in str(error):
            return False
        raise error
    return True


def de_provision(cmd, cobj):
    ''' main de-provision with lifecycle '''
    cobj.state.transition_to_phase(STATE_PHASE_GOING_DOWN)
    # Run template interpolate
    cobj.interpolate_pre_up()
    # Run pre down life cycle
    run_hook_lifecycle(cobj, LIFECYCLE_PRE_DOWN)
    try:
        _de_provision(cmd, cobj)
    except CLIError as error:
        cobj.state.add_event(f"Errored during down phase: {str(error)}", STATE_STATUS_ERROR)
        raise CLIError(error) from error
    except Exception as error:
        cobj.state.add_event(f"General error during down phase: {str(error)}", STATE_STATUS_ERROR)
        raise
    # Remove resource group if needed
    if cobj.managed_resource and _resource_group_exists(cmd, cobj.resource_group_name):
        delete_resource(cmd, resource_ids=[f"/subscriptions/{get_subscription_id(cmd.cli_ctx)}/resourceGroups/{cobj.resource_group_name}"])

    cobj.state.completed_phase(STATE_PHASE_DOWN, STATE_STATUS_SUCCESS, msg="")
    run_hook_lifecycle(cobj, LIFECYCLE_POST_DOWN)


def _de_provision(cmd, cobj):
    ''' de-provision'''

    if cobj.provisioner == "bicep" or cobj.provisioner == "arm":
        _empty_deployment(cmd, cobj)
    elif cobj.provisioner == "terraform":
        # Run template interpolate
        run_terraform_destroy(
            deployment_name=cobj.name,
            terraform_dir=find_the_right_dir(cobj.up_location, cobj.config_dir),
            tmp_dir=cobj.tmp_dir,
            params=cobj.data[CONFIG_PARAMS],
            no_prompt=False
        )
    cobj.state.set_result(outputs={}, resources={}, flush=True)


def provision(cmd, cobj):
    ''' main provision function that handles lifecycle '''

    cobj.state.transition_to_phase(STATE_PHASE_GOING_UP)
    # Run template interpolate
    cobj.interpolate_pre_up()
    # Create RG if needed
    provision_rg_if_needed(cmd, cobj)
    # Run pre up life cycle
    run_hook_lifecycle(cobj, LIFECYCLE_PRE_UP)
    try:
        _provision(cmd, cobj)
    except CLIError as error:
        cobj.state.add_event(f"Errored during up phase: {str(error)}", STATE_STATUS_ERROR)
        raise
    except Exception as error:
        cobj.state.add_event(f"General error during up phase: {str(error)}", STATE_STATUS_ERROR)
        raise
    cobj.state.completed_phase(STATE_PHASE_UP, STATE_STATUS_SUCCESS, msg="")
    run_hook_lifecycle(cobj, LIFECYCLE_POST_UP)


def _provision(cmd, cobj):
    ''' run the IaC logic for all provisioners '''

    output_resources, outputs = None, None
    if cobj.provisioner == "bicep":
        output_resources, outputs = run_bicep(
            cmd,
            deployment_name=cobj.name,
            bicep_file=find_the_right_file(cobj.up_location, "bicep", "*.bicep", cobj.config_dir),
            tmp_dir=cobj.tmp_dir,
            resource_group=cobj.resource_group_name,
            params=cobj.data[CONFIG_PARAMS],
            no_prompt=False,
            complete_deployment=cobj.deployment_mode,
        )
    elif cobj.provisioner == "arm":
        output_resources, outputs = run_arm_deployment(
            cmd,
            deployment_name=cobj.name,
            arm_template_file=find_the_right_file(cobj.up_location, "arm", "*.json", cobj.config_dir),
            resource_group=cobj.resource_group_name,
            params=cobj.data[CONFIG_PARAMS],
            no_prompt=False,
            complete_deployment=cobj.deployment_mode,
        )
    elif cobj.provisioner == "terraform":
        output_resources, outputs = run_terraform_apply(
            deployment_name=cobj.name,
            terraform_dir=find_the_right_dir(cobj.up_location, cobj.config_dir),
            tmp_dir=cobj.tmp_dir,
            params=cobj.data[CONFIG_PARAMS],
            no_prompt=False
        )
    cobj.state.set_result(outputs=outputs, resources=output_resources, flush=True)


def run_bicep(cmd, deployment_name, bicep_file, tmp_dir, resource_group, params=None, no_prompt=False, complete_deployment=False):
    '''
    Deploy an bicep files
    Returns:
        output_resources
        output
    '''
    arm_template_file = f"{tmp_dir}/{deployment_name}_deployment.json"
    _LOGGER.debug(" Building bicep file in tmp dir %s", arm_template_file)
    build_bicep_file(cmd, bicep_file, outfile=arm_template_file)

    return run_arm_deployment(
        cmd,
        deployment_name=deployment_name,
        arm_template_file=arm_template_file,
        resource_group=resource_group,
        params=params,
        no_prompt=no_prompt,
        complete_deployment=complete_deployment,
    )


def check_deployment_error(cmd, resource_group_name, deployment_name, deployment_type):
    ''' Check arm deployment errors '''

    deployment_status = {}
    if not deployment_type == "Microsoft.Resources/deployments":
        return deployment_status
    deployment = get_deployment_at_resource_group(cmd, resource_group_name=resource_group_name, deployment_name=deployment_name)
    properties = deployment.as_dict().get("properties")
    if properties.get("provisioning_state") == "Failed":
        error = properties.get("error")
        deployment_status.update({"error": error, "name": deployment_name})
    return deployment_status


def run_arm_deployment(cmd, deployment_name, arm_template_file, resource_group, params=None, no_prompt=False, complete_deployment=False):
    """
    Deploy an ARM template
    Returns:
        output_resources
        output
    """

    parameters = []
    for key, value in params.items():
        params_obj = [f"{key}={value}"]
        parameters.append(params_obj)

    if complete_deployment:
        mode = "Complete"
    else:
        mode = "Incremental"

    deployment = deploy_arm_template_at_resource_group(
        cmd, resource_group_name=resource_group, template_file=arm_template_file, deployment_name=deployment_name, mode=mode, no_prompt=no_prompt, parameters=parameters, no_wait=False
    )
    return deployment.result().as_dict().get("properties", {}).get("output_resources", {}), deployment.result().as_dict().get("properties", {}).get("outputs", {})


def run_terraform_apply(deployment_name, terraform_dir, tmp_dir, params=None, no_prompt=False):
    ''' Run terraform apply '''
    # TODO fix return
    _run_terraform_cmd(deployment_name, "apply", terraform_dir, tmp_dir, params=params, no_prompt=no_prompt)
    stdout, _ = run_command("terraform", args=["output", f"-state={tmp_dir}/{deployment_name}.tfstate", "-json"], interactive=False, cwd=terraform_dir)
    try:
        output = json.loads(stdout)
    # except subprocess.CalledProcessError as error:
    except json.JSONDecodeError as error:
        raise CLIError(f"Error while decoding json from terraform output. Error: {error}") from error
    return {}, output


def run_terraform_destroy(deployment_name, terraform_dir, tmp_dir, params=None, no_prompt=False):
    ''' Run terraform destroy '''
    return _run_terraform_cmd(deployment_name, "destroy", terraform_dir, tmp_dir, params=params, no_prompt=no_prompt)


def _run_terraform_cmd(deployment_name, terraform_cmd, terraform_dir, tmp_dir, params=None, no_prompt=False):
    varsfile = os.path.join(tmp_dir, "terraformvars.json")
    if params:
        json_write_to_file(varsfile, params)

    run_command("terraform", args=["init"], interactive=False, cwd=terraform_dir)
    args = [terraform_cmd, f"-input={no_prompt}", f"-state={tmp_dir}/{deployment_name}.tfstate", "-auto-approve", "-no-color"]
    if params:
        args.append("-var-file")
        args.append(varsfile)
    return run_command("terraform", args=args, interactive=False, cwd=terraform_dir)
