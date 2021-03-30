""" Help commands """

from knack.help_files import helps  # pylint: disable=unused-import

helps[
    "cdf"
] = """
type: group
short-summary: Commands to manage CDF https://github.com/ahelal/cdf
"""

helps[
    "cdf debug"
] = """
type: group
short-summary: Commands to help you debug your CDF deployment.
"""

helps[
    "cdf up"
] = """
type: command
short-summary: Bring up an environment.
"""

helps[
    "cdf down"
] = """
type: command
short-summary: Destroy an environment.
"""

helps[
    "cdf hook"
] = """
type: command
short-summary: Manage CDF hooks.
"""

helps[
    "cdf status"
] = """
type: command
short-summary: Show status.
"""

helps[
    "cdf test"
] = """
type: command
short-summary: test and environment
"""

helps[
    "cdf init"
] = """
type: command
short-summary: Create the cdf directory structure.
"""

helps[
    "cdf debug interpolate"
] = """
type: command
short-summary: Run an interactive session to test/debug your jinja2 expressions.
"""

helps[
    "cdf debug version"
] = """
type: command
short-summary: Version of CDF.
"""

helps[
    "cdf debug config"
] = """
type: command
short-summary: Dump the configuration file.
"""

helps[
    "cdf debug deployment-errors"
] = """
type: command
short-summary: Check deployment error and all nested deployments.
"""

helps[
    "cdf debug result"
] = """
type: command
short-summary: Print out results.
"""
