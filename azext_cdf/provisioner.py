''' Provisioner file '''

import subprocess
from knack.util import CLIError
from knack.log import get_logger
from azure.cli.command_modules.resource.custom import build_bicep_file
from azure.cli.command_modules.resource.custom import deploy_arm_template_at_resource_group, create_resource_group

logger = get_logger(__name__)

def run_command(bin_path, args=[], interactive=False):
    try:
        cmd_args = [rf"{bin_path}"] + args
        if interactive:
            subprocess.check_call(cmd_args)
            return "", ""

        process = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.check_returncode()
        return process.stdout.decode("utf-8"), process.stderr.decode("utf-8")
    except subprocess.CalledProcessError as error:
        context = f'Run command error. {str(error)}'
        if 'process' in locals():
            context = f"{context}\n{process.stderr.decode('utf-8')}"
        raise CLIError(context) from error

def run_bicep(cmd, deployment_name, bicep_file, tmp_dir, resource_group, location, params=None, manage_resource_group=True, no_prompt=False, complete_deployment=False):
    arm_template_file = f"{tmp_dir}/targetfile.json"
    logger.debug(f' Building bicep file in tmp dir {arm_template_file}')
    build_bicep_file(cmd, [f"{bicep_file}", "--outfile", f"{arm_template_file}"])
    return run_arm_deployment(cmd,
                              deployment_name=deployment_name,
                              arm_template_file=arm_template_file,
                              resource_group=resource_group,
                              location=location,
                              params=params,
                              manage_resource_group=manage_resource_group,
                              no_prompt=no_prompt,
                              complete_deployment=complete_deployment)

def run_arm_deployment(cmd, deployment_name, arm_template_file, resource_group, location, params=None, manage_resource_group=True, no_prompt=False, complete_deployment=False):
    """
    Deploy an ARM template

    Args:

    Returns:
        output_resources
        output
    """

    if manage_resource_group:
        create_resource_group(cmd, rg_name=resource_group, location=location)
    parameters = []
    for key, value in params.items():
        params_obj = [f"{key}={value}"]
        parameters.append(params_obj)

    if complete_deployment:
        mode = "Complete"
    else:
        mode = "Incremental"

    deployment = deploy_arm_template_at_resource_group(cmd,
                                                       resource_group_name=resource_group,
                                                       template_file=arm_template_file,
                                                       deployment_name=deployment_name,
                                                       mode=mode,
                                                       no_prompt=no_prompt,
                                                       parameters=parameters,
                                                       no_wait=False)

    output_resources = deployment.result().as_dict().get("properties", {}).get("output_resources", {})
    output = deployment.result().as_dict().get("properties", {}).get("outputs", {})
    return output_resources, output
