''' jinja2 functions '''

import os
from knack.util import CLIError
from jinja2 import StrictUndefined, Template, contextfunction  # pass_context


def include_file(name):
    ''' include content of a file'''
    try:
        with open(name) as in_file:
            return in_file.read()
    except Exception as error:
        raise CLIError(f"include_file filter argument '{name}' error. {str(error)}") from error


# @pass_context
@contextfunction
def template_file(ctx, name):
    ''' include content of a file and template it '''
    try:
        data = include_file(name)
        return Template(data, undefined=StrictUndefined).render(ctx)

    except Exception as error:
        raise CLIError(f"template_file filter argument '{name}' error. {str(error)}") from error
    return data


def directory_exists(path):
    """ Tests to see if path is a valid directory.  Returns True/False. """
    return os.path.isdir(os.path.expanduser(path))


def file_exists(path):
    """ Tests to see if path is a valid file.  Returns True/False. """
    return os.path.isfile(os.path.expanduser(path))
