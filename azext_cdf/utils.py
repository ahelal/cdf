import stat
import os
import glob
import json
import shutil
from knack.util import CLIError
from os import access, R_OK
from knack.log import get_logger
from json import JSONDecodeError

logger = get_logger(__name__)

def real_dirname(p):
    realpath = os.path.realpath(p)
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
    except OSError as e:
        raise CLIError(f"Failed to create directory {filepath}. Error: {str(e)}")

def dir_remove(filepath):
    if not dir_exists(filepath):
        return 
    try:
        shutil.rmtree(filepath)
    except OSError as e:
        raise CLIError(f"Failed to remove directory {filepath}. Error: {str(e)}")

def dir_change_working(dirpath):
    abs_path = os.path.realpath(dirpath)
    if not abs_path:
        raise CLIError(f"Invalid working directory supplied {abs_path}")
    os.chdir(abs_path) 

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
    except OSError as e:
        raise CLIError(f"Failed to read file '{filepath}'. Error: {str(e)}")

def json_write_to_file(filepath, data):
    try:
        with open(filepath, 'w') as outfile:
            json.dump(data, outfile)
    except OSError as e:
        raise CLIError(f"Failed to write json file '{filepath}'. Error: {str(e)}")

def json_load(content):
    try:
        return json.loads(content)
    except JSONDecodeError as e:
        raise CLIError(f"Failed to parse JSON content. Error: {str(e)}")

def read_param_file(filepath):
    if not file_exits(filepath):
        raise CLIError(f"Failed to read parameter file '{filepath}'. Error: {str(e)}")

    data = file_read_content(filepath)
    # try JSON
    try:
        param_dict = json.loads(data)
        if ("$schema" in param_dict) or ("parameters" in param_dict):
            return False, True
        else:
            return param_dict, False
    except:
        pass
    
    # try yaml
    try:
        config_dict = yaml.safe_load(data)
        return param_dict, False
    except:
        pass
    
    # try key_value
    try:
        config_dict = {}
        for line in data:
            key, ops, value = line.partition("=")
            if not ops == "=":
                raise CLIError(f"Failed to read parameter file '{filepath}'. Error: Parameter file is not 'json', 'yaml' or key value")
            config_dict[key.strip()] = value.strip()
        return param_dict, False
    except:
        raise CLIError(f"Failed to read parameter file '{filepath}'. Error: Parameter file is not 'json', 'yaml' or key value")

def is_part_of(item, valid_list):
    if isinstance(item, list):
        return set(item) <= set(valid_list)
    elif isinstance(item, str):
        return item in valid_list

def find_the_right_file(config_up_file, provisioner_name, file_extension, config_dir):
    up_file = ""
    if config_up_file:
        up_file = config_up_file
        logger.debug(f'Using {provisioner_name} file from up argument {up_file}.')
    else:
        for filename in glob.glob(f"{config_dir}/*{file_extension}" ) :
            if len(up_file) > 0:
                raise CLIError(f"Found more then one {file_extension} file. Please configure 'up' option.")
            up_file = filename
            logger.debug(f'Using {provisioner_name} file from globing {up_file}.')

    if len(up_file) == 0:
        raise CLIError(f"Can't find {file_extension} file. Please configure 'up' option.")

    return up_file