''' tester test'''

import unittest
import tempfile
import shutil
import os
# import json
import random
import string
from mock import patch
# from knack.util import CLIError
from azext_cdf.parser import ConfigParser

# pylint: disable=C0111

class BasicParser(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.config = {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
        self.config['tmp_dir'] = self.dirpath
        self.state_file = f"{self.dirpath}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"

    def tearDown(self):
        shutil.rmtree(self.dirpath)

# class SimpleParser(BasicParser):
#     @patch.object(ConfigParser, '_read_config')
#     def test_min_default(self, mock_read_config):
#         self.config.pop('tmp_dir', None)# use default generated
#         # default_state_file = f"{os.getcwd()}/.cdf_tmp/state.json"
#         # default_tmp_dir = f"{os.getcwd()}/.cdf_tmp"
#         mock_read_config.return_value = self.config
#         # parser = ConfigParser(f"{os.getcwd()}/config.yml")

if __name__ == '__main__':
    unittest.main()

# def run_test(cmd, cobj, config, cwd, exit_on_error, test_args, working_dir, state_file, down_strategy):
# _run_provision
# _run_expect_tests
# _run_hook
# _run_de_provision
