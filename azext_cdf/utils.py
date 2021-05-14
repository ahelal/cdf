""" utils """

import os
import glob
import json
import random
import string
import shutil
import requests
from os import access, R_OK
from json import JSONDecodeError
import yaml
from knack.log import get_logger
from knack.util import CLIError

logger = get_logger(__name__)


def real_dirname(dir_path):
    realpath = os.path.realpath(dir_path)
    return os.path.dirname(os.path.abspath(realpath))


def dir_exists(filepath):
    if not os.path.exists(filepath):
        return False
    # if it exists it should be a dir or a link
    return os.path.isdir(filepath)


def dir_create(filepath):
    if dir_exists(filepath):
        return
    try:
        os.mkdir(filepath)
    except OSError as error:
        raise CLIError(f"Failed to create directory {filepath}. Error: {str(error)}") from error


def dir_remove(filepath):
    if not dir_exists(filepath):
        return
    try:
        shutil.rmtree(filepath)
    except OSError as error:
        raise CLIError(f"Failed to remove directory {filepath}. Error: {str(error)}") from error


def dir_change_working(dirpath):
    abs_path = os.path.realpath(dirpath)
    if not abs_path:
        raise CLIError(f"Invalid working directory supplied {abs_path}")
    try:
        os.chdir(abs_path)
    except FileNotFoundError as error:
        raise CLIError(f"Change working dir failed. {str(error)}") from error


def file_exits(filepath):
    if not os.path.exists(filepath):
        return False
    if not os.path.isfile(filepath) and access(filepath, R_OK):
        return False
    return True


def file_read_content(filepath):
    try:
        with open(filepath, "r") as in_fh:
            return in_fh.read()
    except OSError as error:
        raise CLIError(f"Failed to read file '{filepath}'. Error: {str(error)}") from error

def file_http_read_json_content(filepath):
    try:
        r = requests.get(filepath)
        return r.json()
    except Exception as error:
        raise CLIError(f"Failed to read file '{filepath}'. Error: {str(error)}") from error


def file_write_content(filepath, content):
    try:
        with open(filepath, "w") as file_in:
            file_in.write(content)
    except OSError as error:
        raise CLIError(f"Failed to write file '{filepath}'. Error: {str(error)}") from error

def file_http_write_json_content(filepath, content):
    try:
        r = requests.get(filepath, json=[content])
    except Exception as error:
        raise CLIError(f"Failed to read file '{filepath}'. Error: {str(error)}") from error


def json_write_to_file(filepath, data):
    try:
        with open(filepath, "w") as outfile:
            json.dump(data, outfile)
    except OSError as error:
        raise CLIError(f"Failed to write json file '{filepath}'. Error: {str(error)}") from error


def json_load(content):
    try:
        return json.loads(content)
    except JSONDecodeError as error:
        raise CLIError(f"Failed to parse JSON content. Error: {str(error)}") from error


def read_param_file(filepath):
    if not file_exits(filepath):
        raise CLIError(f"Failed to read parameter file '{filepath}'.")

    data = file_read_content(filepath)
    try:  # try JSON
        param_dict = json.loads(data)
        if ("$schema" in param_dict) or ("parameters" in param_dict):
            return False, True
        return param_dict, False
    except Exception:
        pass

    try:  # try yaml
        config_dict = yaml.safe_load(data)
        return param_dict, False
    except Exception:
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
    elif isinstance(value2, str):
        return value1 == value2

    raise CLIError(f"unsupported date type '{type(value2)}', {value2}")


def is_part_of(item, valid_list):
    if isinstance(item, list):
        return set(item) <= set(valid_list)
    elif isinstance(item, str):
        return item in valid_list
    else:
        raise CLIError(f"unsupported date type '{type(item)}', {item}")


def find_the_right_dir(config_up_dir, config_dir):
    if config_up_dir:
        return config_up_dir
    return config_dir

def find_the_right_file(config_up_file, provisioner_name, file_extension, config_dir):
    if config_up_file:
        logger.debug("Using %s file from up argument %s.", provisioner_name, config_up_file)
        return config_up_file

    up_file = ""
    for filename in glob.glob(f"{config_dir}/*{file_extension}"):
        if len(up_file) > 0:
            raise CLIError(f"Found more then one {file_extension} file. Please configure 'up' option.")
        up_file = filename
        logger.debug("Using %s file from globing %s.", provisioner_name, up_file)

    if not up_file:
        raise CLIError(f"Can't find {file_extension} file. Please configure 'up' option.")
    return up_file

def random_string(length, option=['lower','upper']):
    ''' Create a random string of a given length '''

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
