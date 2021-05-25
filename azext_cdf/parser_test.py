''' Utils test'''

import unittest
import tempfile
import shutil
import os
import platform
import json
import random
import string
from mock import patch
from knack.util import CLIError
from azext_cdf.parser import ConfigParser
from azext_cdf.version import VERSION

# pylint: disable=C0111
class BasicParser(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.config = {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
        self.config['tmp_dir'] = self.dirpath
        self.state_file = f"{self.dirpath}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"
    def tearDown(self):
        shutil.rmtree(self.dirpath)

class FullParser(BasicParser):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.config = {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
        self.config['tmp_dir'] = self.dirpath
        self.state_file = f"{self.dirpath}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"
    def tearDown(self):
        shutil.rmtree(self.dirpath)

class SimpleParser(BasicParser):
    @patch.object(ConfigParser, '_read_config')
    def test_min_default(self, mock_read_config):
        self.config.pop('tmp_dir', None)# use default generated
        default_state_file = f"{os.getcwd()}/.cdf_tmp/state.json"
        default_tmp_dir = f"{os.getcwd()}/.cdf_tmp"
        mock_read_config.return_value = self.config
        parser = ConfigParser(f"{os.getcwd()}/config.yml", remove_tmp=False, override_state=None, test=None)
        self.assertEqual(parser.name, self.config["name"])
        self.assertEqual(parser.resource_group_name, self.config["resource_group"])
        self.assertEqual(parser.location, self.config["location"])
        self.assertEqual(parser.managed_resource, True)
        self.assertEqual(parser.tmp_dir, default_tmp_dir)
        self.assertEqual(parser.up_location, '')
        self.assertEqual(parser.provisioner, 'bicep')
        self.assertEqual(parser.deployment_mode, False)
        self.assertEqual(parser.config_dir, os.getcwd()) # abs path
        self.assertEqual(parser.tests, [])
        self.assertEqual(parser.hook_names, [])
        self.assertEqual(list(parser.hooks_dict), [])
        self.assertTrue(os.path.exists(default_state_file))
        with open(default_state_file) as json_file:
            data = json.load(json_file)
            self.assertEqual(data['name'], self.config["name"])

    @patch.object(ConfigParser, '_read_config')
    def test_no_default(self, mock_read_config):
        empty_config = {}
        mock_read_config.return_value = empty_config
        with self.assertRaises(CLIError) as context:
            ConfigParser("/path/config", remove_tmp=False, override_state=None, test=None)
        self.assertTrue('name' in str(context.exception))
        self.assertTrue('resource_group' in str(context.exception))
        self.assertTrue('location' in str(context.exception))

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(f"{os.getcwd()}/.cdf_tmp", ignore_errors=True)

class PathsParser(BasicParser):
    @patch.object(ConfigParser, '_read_config')
    def test_override_state(self, mock_read_config):
        mock_read_config.return_value = self.config
        parser = ConfigParser("path_a/path_b/c.yml", remove_tmp=False, override_state=f"file:///{self.state_file}", test=None)
        self.assertEqual(parser.name, self.config["name"])
        self.assertEqual(parser.config_dir, f"{os.getcwd()}/path_a/path_b") # relative path
        self.assertTrue(os.path.exists(self.state_file))

    @patch.object(ConfigParser, '_read_config')
    def test_abs_path_config(self, mock_read_config):
        self.config["name"] = "test_abs_path_config"
        mock_read_config.return_value = self.config
        parser = ConfigParser("/path_a/path_b/c.yml", remove_tmp=False, override_state=f"file:///{self.state_file}", test=None)
        self.assertEqual(parser.name, self.config["name"])
        self.assertEqual(parser.config_dir, "/path_a/path_b") # abs path
        self.assertTrue(os.path.exists(self.state_file))

class InterpolateParser(BasicParser):
    @patch.object(ConfigParser, '_read_config')
    def test_first_stage_cdf(self, mock_read_config):
        self.config["name"] = "cdf_test_first_stage"
        # self.config["vars"] = {"cdf_builtin":"{{cdf.name}}_{{cdf.resource_group}}_{{cdf.location}}"}
        mock_read_config.return_value = self.config
        parser = ConfigParser("/path_a/path_b/c.yml", remove_tmp=False, override_state=f"file:///{self.state_file}", test=None)
        # interpolate_txt = parser.interpolate(1, "{{cdf.name}}.{{cdf.resource_group}}.{{cdf.location}}", context="test", extra_vars=None, raw_undefined_error=False)
        self.assertEqual(parser.interpolate(1, "{{cdf.name}}.{{cdf.resource_group}}.{{cdf.location}}"), "cdf_test_first_stage.rg.loc")
        self.assertEqual(parser.interpolate(1, "{{cdf.config_dir}}"), "/path_a/path_b")
        self.assertEqual(parser.interpolate(1, "{{cdf.tmp_dir}}"), self.dirpath)
        self.assertEqual(parser.interpolate(1, "{{cdf.version}}"), VERSION)
        self.assertEqual(parser.interpolate(1, "{{cdf.platform}}"), platform.system().lower())

    @patch.object(ConfigParser, '_read_config')
    def test_first_stage_env(self, mock_read_config):
        self.config["name"] = "cdf_test_first_stage_env"
        mock_read_config.return_value = self.config
        os.environ["TEST_ENV_1"] = "One"
        os.environ["TEST_ENV_2"] = "Two"
        parser = ConfigParser("/path/c.yml", remove_tmp=False, override_state=f"file:///{self.state_file}", test=None)
        self.assertEqual(parser.interpolate(1, "{{env.TEST_ENV_1}}.{{env.TEST_ENV_2}}"), "One.Two")

    @patch.object(ConfigParser, '_read_config')
    def test_first_stage_vars(self, mock_read_config):
        self.config["name"] = "cdf_test_first_stage_vars"
        self.config["vars"] = {"a": 1, "b": "2", "c": {"a": 1}, "d": False, "e": [1, 2],
                               "f": "{{cdf.name}}", "g": "{{vars.a}}"}
        mock_read_config.return_value = self.config
        parser = ConfigParser("/path/c.yml", remove_tmp=False, override_state=f"file:///{self.state_file}", test=None)
        self.assertEqual(parser.interpolate(1, "{{vars.a}}.{{vars.b}}"), "1.2")
        self.assertEqual(parser.interpolate(1, "{{vars.c.a}}"), "1")
        self.assertEqual(parser.interpolate(1, "{{vars.d}}"), "False")
        self.assertEqual(parser.interpolate(1, "{{vars.e[0]}}"), "1")
        self.assertEqual(parser.interpolate(1, "{{vars.f}}"), self.config["name"])
        self.assertEqual(parser.interpolate(1, "{{vars.a}}{{vars.z}}", extra_vars={"z": 23}), "123")
        # variable not accessible in stage one
        with self.assertRaises(CLIError) as context:
            parser.interpolate(1, "{{result}}")
        self.assertIn('result', str(context.exception))
        self.assertIn('undefined variable', str(context.exception))

    @patch.object(ConfigParser, '_read_config')
    def test_vars_circle_dep(self, mock_read_config):
        self.config["name"] = "test_vars_circle_dep"
        self.config["vars"] = {"h": "{{vars.i}}", "i": "{{vars.h}}"}
        mock_read_config.return_value = self.config
        with self.assertRaises(CLIError) as context:
            ConfigParser("/path/c.yml", remove_tmp=False, override_state=f"file:///{self.state_file}", test=None)
        self.assertTrue('undefined variable' in str(context.exception))

    @patch.object(ConfigParser, '_read_config')
    def test_jinja2_filters(self, mock_read_config):
        self.config["name"] = "test_jinja2_filters"
        self.config["vars"] = {"a": 1}
        mock_read_config.return_value = self.config
        parser = ConfigParser("/path/c.yml", remove_tmp=False, override_state=f"file:///{self.state_file}", test=None)
        # write static file
        with open(f"{self.dirpath}/static.txt", "w") as static_file:
            static_file.write("helloStatic")
        include_file = "{{include_file('" + self.dirpath + "/static.txt') }}"
        self.assertEqual(parser.interpolate(1, include_file), 'helloStatic')
        # write template
        with open(f"{self.dirpath}/template.txt", "w") as jinja2_file:
            jinja2_file.write("{{cdf.name}}{{vars.a}}")
        template_file = "{{template_file('" + self.dirpath + "/template.txt') }}"
        self.assertEqual(parser.interpolate(1, template_file), f'{self.config["name"]}1')
        inter_len = parser.interpolate(1, "{{random_string(10)}}")
        self.assertEqual(len(inter_len), 10)

    # TODO phase2 tests
    # TODO results tests

if __name__ == '__main__':
    unittest.main()
