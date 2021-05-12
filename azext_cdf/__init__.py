#!/usr/bin/env python3
""" Entry point for the extension """

from azure.cli.core import AzCommandsLoader
from azure.cli.core.profiles import ResourceType
import azext_cdf._help
from azext_cdf._formater import hooks_output_format


class BicepHelperCommandLoad(AzCommandsLoader):
    """ Main class that glues all CDF commands and arguments """

    def __init__(self, cli_ctx=None):
        from azure.cli.core.commands import CliCommandType

        custom_type = CliCommandType(operations_tmpl="azext_cdf.handlers#{}")
        super(BicepHelperCommandLoad, self).__init__(cli_ctx=cli_ctx, custom_command_type=custom_type)

    def load_command_table(self, args):
        with self.command_group("cdf", resource_type=ResourceType.MGMT_RESOURCE_RESOURCES) as group_command:
            group_command.custom_command("init", "init_handler")
            group_command.custom_command("up", "up_handler")
            group_command.custom_command("status", "status_handler")
            group_command.custom_command("down", "down_handler", confirmation=True)
            group_command.custom_command("hook", "hook_handler", table_transformer=hooks_output_format)
            group_command.custom_command("test", "test_handler")
        with self.command_group("cdf debug", resource_type=ResourceType.MGMT_RESOURCE_RESOURCES) as group_command:
            group_command.custom_command("version", "debug_version_handler")
            group_command.custom_command("config", "debug_config_handler")
            group_command.custom_command("result", "debug_result_handler")
            group_command.custom_command("state", "debug_state_handler")
            group_command.custom_command("interpolate", "debug_interpolate_handler")
            group_command.custom_command("errors", "debug_deployment_error_handler")
        return self.command_table

    def load_arguments(self, command):
        from ._params import load_arguments

        load_arguments(self, command)


# pylint: disable=C0103
COMMAND_LOADER_CLS = BicepHelperCommandLoad
