# ''' hook test'''

# import unittest
# import tempfile
# import shutil
# import os
# import platform
# import json
# import random
# import string
# from mock import patch
# from knack.util import CLIError
# from azext_cdf.parser import ConfigParser
# from azext_cdf.version import VERSION

# # pylint: disable=C0111
# class HookLifeCycle(unittest.TestCase):
#     def setUp(self):
#         self.dirpath = tempfile.mkdtemp()
#         self.config = {"name": "cdf_simple", "resource_group": "rg", "location": "loc"}
#         self.config['tmp_dir'] = self.dirpath
#         self.state_file = f"{self.dirpath}/{''.join(random.sample(string.ascii_lowercase, 25))}.json"
#     @patch.object(ConfigParser, '_read_config')
#     def test_min_default(self, mock_read_config):

#     def tearDown(self):
#         shutil.rmtree(self.dirpath)

# run_hook_lifecycle
# if __name__ == '__main__':
#     unittest.main()
