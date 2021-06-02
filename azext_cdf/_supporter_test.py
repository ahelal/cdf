''' Utils test'''

import unittest
import tempfile
import shutil
import os
import json
import random
import string
from azext_cdf._def import CONFIG_STATE_FILEPATH

# pylint: disable=C0111

def assert_state(self, state_path, content=None):
    print("XXXXXXXXX", state_path)
    self.assertTrue(os.path.exists(state_path))
    if not content:
        return
    with open(state_path) as json_file:
        data = json.load(json_file)
        for key, assert_value in content.items():
            self.assertEqual(data[key], assert_value)


class BasicParser(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.config = {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
        self.config['tmp_dir'] = self.dirpath
        self.state_file = f"{self.dirpath}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"
        self.override_config = {
            CONFIG_STATE_FILEPATH: f"file://{self.state_file}",
        }
    def tearDown(self):
        shutil.rmtree(self.dirpath)
