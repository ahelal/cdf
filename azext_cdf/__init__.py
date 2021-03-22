#!/usr/bin/env python3

from azure.cli.core import AzCommandsLoader
from azure.cli.core.profiles import ResourceType
import azext_cdf._help # pylint: disable=unused-import
from azext_cdf._formater import hooks_output_format
# from azext_cdf.parser

class BicepHelperCommandLoad(AzCommandsLoader):
    def __init__(self, cli_ctx=None):
        from azure.cli.core.commands import CliCommandType
        custom_type = CliCommandType(operations_tmpl='azext_cdf.handlers#{}')
        super(BicepHelperCommandLoad, self).__init__(cli_ctx=cli_ctx, custom_command_type=custom_type)

    def load_command_table(self, args):
        with self.command_group('cdf', resource_type=ResourceType.MGMT_RESOURCE_RESOURCES) as g:
            g.custom_command('init', 'init_handler')
            g.custom_command('up', 'up_handler')
            g.custom_command('status', 'status_handler')
            g.custom_command('down', 'down_handler', confirmation=True)
            g.custom_command('hook', 'hook_handler', table_transformer=hooks_output_format)
            g.custom_command('test', 'test_handler')
        with self.command_group('cdf debug', resource_type=ResourceType.MGMT_RESOURCE_RESOURCES) as g:
            g.custom_command('version', 'debug_version_handler')
            g.custom_command('config', 'debug_config_handler')
            g.custom_command('result', 'debug_result_handler')
            g.custom_command('state', 'debug_state_handler')
            g.custom_command('interpolate', 'debug_interpolate_handler')
            g.custom_command('deployment-errors', 'debug_deployment_error_handler')
        return self.command_table

    def load_arguments(self, command):
        from ._params import load_arguments
        load_arguments(self, command)

COMMAND_LOADER_CLS = BicepHelperCommandLoad
