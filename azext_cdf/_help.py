''' Help commands '''

from knack.help_files import helps  # pylint: disable=unused-import

helps['cdf'] = """
type: group
short-summary: Commands to manage CDF https://github.com/ahelal/cdf
"""

helps['cdf up'] = """
type: command
short-summary: Bring up an environment.
"""

helps['cdf down'] = """
type: command
short-summary: Destroy an environment.
"""

helps['cdf hooks'] = """
type: command
short-summary: Run a specific hook.
"""

helps['cdf status'] = """
type: command
short-summary: Show status.
"""

helps['cdf test'] = """
type: command
short-summary: test and environment
"""

helps['cdf init'] = """
type: command
short-summary: Create the cdf directory structure.
"""
