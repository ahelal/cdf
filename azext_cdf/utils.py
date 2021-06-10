""" utils """

import os
from os import access, R_OK
import glob
import json
from json import JSONDecodeError
import random
import string
import shutil
import subprocess
import shlex
import requests
import yaml
from knack.log import get_logger
from knack.util import CLIError
import azure.cli.core.commands.progress as progress
from azext_cdf._def import CONFIG_STATE_FILEPATH
# from azext_cdf.parser import ConfigParser

_LOGGER = get_logger(__name__)


# pylint: disable=no-self-use
class Progress():
    ''' Progress message'''
    def __init__(self, cmd, pseudo=True):
        self.pseudo = pseudo
        if self.pseudo:
            cmd.cli_ctx.only_show_errors = True
            cmd.cli_ctx.progress_controller = self
            return
        self.controller = progress.ProgressHook()
        self.controller.init_progress(progress.get_progress_view())

    def init_progress(self, _):
        ''' NoOps '''
        return

    def begin(self, msg=None):
        ''' begin message '''
        if self.pseudo:
            return
        self.controller.begin(message=msg)
        self.controller.update()

    def end(self, msg=None):
        ''' end message '''
        if self.pseudo:
            return
        self.controller.end(message=msg)
        self.stop()

    def stop(self):
        ''' stop progress '''
        if self.pseudo:
            return
        self.controller.stop()

    def update_progress(self):
        ''' NoOps '''
        return


# TODO should be refactored into parser code
def init_config(config, config_parser, remove_tmp=False, working_dir=None, state_file=None, state_locking=True):
    ''' return config obj and cwd'''
    cwd = os.getcwd()
    override_config = {}
    if state_file:
        override_config = {
            CONFIG_STATE_FILEPATH: f"file://{state_file}",
        }
    return config_parser(config_filepath=config, remove_tmp=remove_tmp, test=None, working_dir=working_dir, override_config=override_config, state_locking=state_locking), cwd


def real_dirname(dir_path):
    ''' return real dir name '''

    realpath = os.path.realpath(dir_path)
    return os.path.dirname(os.path.abspath(realpath))


def dir_exists(filepath):
    ''' test if a directory exists '''

    if not os.path.exists(filepath):
        return False
    # if it exists it should be a dir or a link
    return os.path.isdir(filepath)


def dir_create(filepath):
    ''' Create a directory '''

    if dir_exists(filepath):
        return
    try:
        os.mkdir(filepath)
    except OSError as error:
        raise CLIError(f"Failed to create directory {filepath}. Error: {str(error)}") from error


def dir_remove(filepath):
    ''' Remove a directory '''

    if not dir_exists(filepath):
        return
    try:
        shutil.rmtree(filepath)
    except OSError as error:
        raise CLIError(f"Failed to remove directory {filepath}. Error: {str(error)}") from error


def dir_change_working(dirpath):
    ''' Change working directory '''

    if dirpath is None:
        dirpath = os.getcwd()
    abs_path = os.path.realpath(dirpath)
    if not abs_path:
        raise CLIError(f"Invalid working directory supplied {abs_path}")
    try:
        os.chdir(abs_path)
    except FileNotFoundError as error:
        raise CLIError(f"Change working dir failed. {str(error)}") from error


def file_exists(filepath):
    ''' test if a file exists '''

    if not os.path.exists(filepath):
        return False
    if not os.path.isfile(filepath) and access(filepath, R_OK):
        return False
    return True


def file_read_content(filepath):
    ''' Return content of file '''

    try:
        with open(filepath, "r") as in_fh:
            return in_fh.read()
    except OSError as error:
        raise CLIError(f"Failed to read file '{filepath}'. Error: {str(error)}") from error


def file_http_read_json_content(urlpath):
    ''' get http content'''
    try:
        resp = requests.get(urlpath)
        return resp.json()
    except Exception as error:
        raise CLIError(f"Failed to read file '{urlpath}'. Error: {str(error)}") from error


def file_write_content(filepath, content):
    ''' write content to a file '''
    try:
        with open(filepath, "w") as file_in:
            file_in.write(content)
    except OSError as error:
        raise CLIError(f"Failed to write file '{filepath}'. Error: {str(error)}") from error


def file_http_write_json_content(filepath, content):
    ''' write content do dapr endpoint'''
    raise CLIError("http write WIP")
    # try:
    #     r = requests.get(filepath, json=[content])
    # except Exception as error:
    #     raise CLIError(f"Failed to read file '{filepath}'. Error: {str(error)}") from error


def json_write_to_file(filepath, data):
    ''' serialize data into file '''

    try:
        with open(filepath, "w") as outfile:
            json.dump(data, outfile)
    except OSError as error:
        raise CLIError(f"Failed to write json file '{filepath}'. Error: {str(error)}") from error


def json_load(content):
    ''' de serialize string content '''
    try:
        return json.loads(content)
    except JSONDecodeError as error:
        raise CLIError(f"Failed to parse JSON content. Error: {str(error)}") from error


def read_param_file(filepath):
    ''' read a json parameters file '''

    data = file_read_content(filepath)

    try:  # try JSON
        param_dict = json.loads(data)
        if ("$schema" in param_dict) or ("parameters" in param_dict):
            return False, True
        return param_dict, False
    except JSONDecodeError:
        pass

    try:  # try yaml
        config_dict = yaml.safe_load(data)
        return param_dict, False
    except yaml.YAMLError:
        pass

    try:  # try key_value
        config_dict = {}
        for line in data:
            key, ops, value = line.partition("=")
            if not ops == "=":
                raise CLIError(f"Failed to read parameter file '{filepath}'. Error: Parameter file is not 'json', 'yaml' or key value")
            config_dict[key.strip()] = value.strip()
        return param_dict, False
    except Exception as error:
        raise CLIError(f"Failed to read parameter file '{filepath}'. Error: Parameter file is not 'json', 'yaml' or key value") from error


def is_equal_or_in(value1, value2):
    """Return a boolean. value1 is equal or in value2"""

    if isinstance(value2, list):
        return value1 in value2
    if isinstance(value2, str):
        return value1 == value2

    raise CLIError(f"unsupported date type '{type(value2)}', {value2}")


def is_part_of(item, valid_list):
    ''' returns if item is part of valid_list, valid_list can str, or list '''
    if isinstance(item, list):
        return set(item) <= set(valid_list)
    if isinstance(item, str):
        return item in valid_list
    raise CLIError(f"unsupported date type '{type(item)}', {item}")


def find_the_right_dir(config_up_dir, config_dir):
    ''' find a terraform dir '''
    if config_up_dir:
        return config_up_dir
    return config_dir


def find_the_right_file(config_up_location, provisioner_name, file_extension, config_dir):
    ''' find a bicep or arm json file in a dir'''
    # TODO need to test this function
    if config_up_location:
        _LOGGER.debug("Using %s file from up argument %s.", provisioner_name, config_up_location)
        return config_up_location

    up_location = ""
    for filename in glob.glob(f"{config_dir}/*{file_extension}"):
        if len(up_location) > 1:
            raise CLIError(f"Found more then one {file_extension} file. Please configure 'up' option.")
        up_location = filename
        _LOGGER.debug("Using %s file from globing %s.", provisioner_name, up_location)

    if not up_location:
        raise CLIError(f"Can't find {file_extension} file. Please configure 'up' option.")
    return up_location


def random_string(length, option=None):
    ''' Create a random string of a given length '''

    if option is None:
        option = ['lower', 'upper']
    letters = ""
    if "upper" in option or "all" in option:
        letters += string.ascii_uppercase
    if "lower" in option or "all" in option:
        letters += string.ascii_lowercase
    if "numbers" in option or "all" in option:
        letters += string.digits
    if "special" in option or "all" in option:
        letters += string.digits
    if not letters:
        raise CLIError("random_string function requires option supported(all, upper, lower and special)")
    return ''.join(random.choice(letters) for i in range(length))


def convert_to_shlex_arg(var):
    ''' Checks if var is a str and converts to args with shlex '''
    if isinstance(var, str):
        return shlex.split(var)
    return var


def convert_to_list_if_need(var):
    ''' Checks if var is a list if not return singe element list '''
    if isinstance(var, list):
        return var
    if var is None or var == "":
        return []
    return [var]


def dict_lookup(dictionary, keys):
    ''' Returns an object using dot notation from keys in dict d'''
    try:
        if "." in keys:
            key, rest = keys.split(".", 1)
            return dict_lookup(dictionary[key], rest)

        return dictionary[keys]
    except KeyError:
        return None


def run_command(bin_path, args=None, interactive=False, cwd=None):
    """
    Run CLI commands
    Returns: stdout, stderr  strings
    Exceptions: raise CLIError on execution error
    """

    process = None
    stdout = None
    stderr = None
    try:
        cmd_args = [rf"{bin_path}"] + args
        _LOGGER.debug(" Running a command %s", cmd_args)
        if interactive:
            subprocess.check_call(cmd_args, cwd=cwd)
            return "", ""
        process = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, check=False)
        stdout = process.stdout.decode('utf-8')
        stderr = process.stderr.decode('utf-8')
        process.check_returncode()
        return stdout, stderr
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        context = f"Run command error. {str(error)}"
        if stdout:
            context = f"{context} stdout:{stdout}"
        if stderr:
            context = f"{context} stdout:{stderr}"
        raise CLIError(context) from error

# class Colors:
#     ''' Colors '''
#     HEADER = '\033[95m'
#     OK_BLUE = '\033[94m'
#     OK_CYAN = '\033[96m'
#     OK_GREEN = '\033[92m'
#     WARNING = '\033[93m'
#     FAIL = '\033[91m'
#     END_C = '\033[0m'
#     BOLD = '\033[1m'
#     UNDERLINE = '\033[4m'

# def p_color(message, enabled=True, color=None):
#     ''' Print color message '''

#     if not enabled:
#         return
#     if not color:
#         print(message)
#         return
#     print(f"{color}{message}{Colors.END_C}")
