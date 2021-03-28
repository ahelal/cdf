# import os
# import platform
import subprocess
from knack.util import CLIError
from knack.log import get_logger
from azure.cli.command_modules.resource.custom import build_bicep_file, run_bicep_command
from azure.cli.command_modules.resource.custom import deploy_arm_template_at_resource_group, create_resource_group

logger = get_logger(__name__)

def run_command(bin_path, args=[], interactive=False):
    try:
        cmd_args = [rf"{bin_path}"] + args
        if interactive:
            subprocess.check_call(cmd_args)
            return "", ""
        else:
            process = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            process.check_returncode()
            return process.stdout.decode("utf-8"), process.stderr.decode("utf-8")
    except subprocess.CalledProcessError as e:
        context = f'Run command error. {str(e)}'
        if 'process' in locals():
            ccontext = f"{context}\n{process.stderr.decode('utf-8')}"
        raise CLIError(context)

def run_bicep(cmd, deployment_name, bicep_file, tmp_dir, resource_group, location, params={} , manage_resource_group=True, no_prompt=False, complete_deployment=False):
    arm_template_file = f"{tmp_dir}/targetfile.json"
    logger.debug(f' Building bicep file in tmp dir {arm_template_file}')
    build_bicep_file(cmd, [f"{bicep_file}", "--outfile", f"{arm_template_file}"])
    return run_arm_deployment(cmd, 
                            deployment_name=deployment_name,
                            arm_template_file=arm_template_file, 
                            tmp_dir=tmp_dir,
                            resource_group=resource_group, 
                            location=location, 
                            params=params, 
                            manage_resource_group=manage_resource_group, 
                            no_prompt=no_prompt,
                            complete_deployment=complete_deployment)

def run_arm_deployment(cmd, deployment_name, arm_template_file, tmp_dir, resource_group, location, params={} , manage_resource_group=True, no_prompt=False, complete_deployment=False):
    if manage_resource_group:
        create_resource_group(cmd, rg_name=resource_group, location=location)
    parameters = []
    for k,v in params.items():
        p=[f"{k}={v}"]
        parameters.append(p)

    if complete_deployment:
        mode="Complete"
    else:
        mode="Incremental"

    deployment = deploy_arm_template_at_resource_group(cmd, 
                                              resource_group_name=resource_group,
                                              template_file=arm_template_file,
                                              deployment_name=deployment_name,
                                              mode=mode,
                                              no_prompt=no_prompt,
                                              parameters=parameters,
                                              no_wait=False
                                            )
    output_resources = deployment.result().as_dict().get("properties", {}).get("output_resources",{})
    output = deployment.result().as_dict().get("properties", {}).get("outputs",{})
    return output_resources, output
