''' Config schema '''

import schema
from schema import And, Or, Use, Optional
# from knack.util import CLIError
# pylint: disable=W0401,W0614
from azext_cdf._def import *
from azext_cdf.utils import is_part_of


def _list_or_tuple_of(sub_schema):
    return schema.Or((sub_schema,), [sub_schema])


# https://github.com/keleshev/schema
HOOKS_SCHEMA = {
    str: {
        "ops": [
            {
                Optional(CONFIG_NAME): str,
                Optional(CONFIG_DESCRIPTION, default=""): str,
                Optional(CONFIG_TYPE, default="az"): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_OPS_TYPES),
                Optional("platform", default=""): Or(And(str, Use(str.lower), (And(list))), lambda s: is_part_of(s, CONFIG_SUPPORTED_PLATFORM)),
                Optional("mode", default='wait'): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_OPS_MODE),
                Optional("cwd"): str,
                CONFIG_ARGS: Or(str, list),
            }
        ],
        Optional("lifecycle", default=""): Or(And(str, Use(str.lower), (And(list))), lambda s: is_part_of(s, CONFIG_SUPPORTED_LIFECYCLE)),
        Optional(CONFIG_DESCRIPTION, default=""): str,
        Optional("run_if", default="true"): str,
    }
}

EXPECT_SCHEMA = {
    Optional(CONFIG_EXPECT_FAIL, default=False): bool,
    Optional(CONFIG_EXPECT_ASSERT): Or(str, list),
    Optional(CONFIG_EXPECT_HOOK_ARGS): Or(str, list),
    # TODO expect other plan options for ARM
    Optional(CONFIG_EXPECT_PLAN, default={}): {
        Optional(CONFIG_EXPECT_PLAN_ADD): Or(int, str),
        Optional(CONFIG_EXPECT_PLAN_CHANGE): Or(int, str),
        Optional(CONFIG_EXPECT_PLAN_DESTROY): Or(int, str),
    },
    Optional(CONFIG_EXPECT_RUNNER, default={}): {
        Optional(CONFIG_EXPECT_RUNNER_CMD, default=None): Or(str, list),
        Optional(CONFIG_EXPECT_RUNNER_FILES, default=None): Or(str, list, None),
        Optional(CONFIG_EXPECT_RUNNER_EXTENSION, default="*"): str,
    }
}

UPGRADE_SCHEMA = {
    CONFIG_NAME: And(str, Use(str.lower), lambda s: s != "fresh"),
    Optional(CONFIG_TYPE, default="local"): And(str, lambda s: s in CONFIG_SUPPORTED_UPGRADE_TYPES),
    Optional("path", default="/"): str,
    Optional("from_expect", default="default"): Or(str, list),
    Optional("git"): {
        "repo": str,
        Optional("branch"): str,
        Optional("tag"): str,
        Optional("commit"): str,
        Optional("key"): (str),
    }
}

TEST_SCHEMA = {
    str: {
        Optional(CONFIG_FILE): str,
        Optional(CONFIG_NAME): And(str, len),
        Optional(CONFIG_DESCRIPTION, default=""): str,
        Optional(CONFIG_RG): And(str, len),
        Optional(CONFIG_LOCATION): And(str, len),
        Optional(CONFIG_RG_MANAGED, default=True): bool,
        Optional(CONFIG_DEPLOYMENT_COMPLETE, default=False): bool,
        Optional(CONFIG_UP): And(str, len),
        Optional(CONFIG_PROVISIONER_BINARY_PATH, default=""): str,
        Optional("upgrade_strategy", default="all"): And(str, lambda s: s in ("all", "fresh", "upgrade")),
        Optional(CONFIG_UPGRADE, default=[]): _list_or_tuple_of(UPGRADE_SCHEMA),
        # Optional('vars_file', default=[]): Or(str,list),
        Optional(CONFIG_VARS): dict,
        Optional(CONFIG_PARAMS): dict,
        Optional(CONFIG_EXPECT): {
            Optional(Or("up", "down")): EXPECT_SCHEMA,
            Optional(CONFIG_HOOKS): _list_or_tuple_of({str: EXPECT_SCHEMA}),
        }
    }
}

MAIN_SCHEMA = {
    CONFIG_NAME: And(str, len),
    CONFIG_RG: And(str, len),
    CONFIG_LOCATION: And(str, len),
    Optional(CONFIG_SCOPE, default="resource_group"): And(str, len),
    Optional(CONFIG_RG_MANAGED, default=True): bool,
    Optional(CONFIG_PROVISIONER, default="bicep"): And(str, Use(str.lower), lambda s: s in CONFIG_SUPPORTED_PROVISIONERS),
    Optional(CONFIG_DEPLOYMENT_COMPLETE, default=False): bool,
    Optional(CONFIG_UP, default=""): str,
    Optional(CONFIG_PROVISIONER_BINARY_PATH, default=""): str,
    Optional(CONFIG_TMP, default="{{cdf.config_dir}}/.cdf_tmp"): And(str, len),
    # Optional('vars_file', default=[]): Or(str,list),
    Optional(CONFIG_VARS, default={}): dict,
    Optional(CONFIG_PARAMS, default={}): dict,
    Optional(CONFIG_HOOKS, default={}): HOOKS_SCHEMA,
    Optional(CONFIG_UPGRADE, default=[]): _list_or_tuple_of(UPGRADE_SCHEMA),
    Optional(CONFIG_TESTS, default={}): TEST_SCHEMA,
    Optional(CONFIG_STATE_FILEPATH, default=CONFIG_STATE_FILEPATH_DEFAULT): str,
}
