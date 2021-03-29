''' Utils test'''

import unittest
import tempfile
import shutil
from azext_cdf.utils import file_exits

class TestFileExits(unittest.TestCase):
    def setUp(self):
        self.dirpath = tempfile.mkdtemp()
        self.file = f'{self.dirpath}/example.txt'
        with open(self.file, 'w') as the_file:
            the_file.write('Hello')
    def test_fileExitsTrue(self):
        self.assertTrue(file_exits(self.file))
    def test_fileExitsFalse(self):
        self.assertFalse(file_exits(f'{self.file}aa'))
    def test_dirExitsFalse(self):
        self.assertFalse(file_exits(self.dirpath))
        # with self.assertRaises(TypeError):
        #     s.split(2)
        # self.assertEqual('foo'.upper(), 'FOO')
        # self.assertFalse('Foo'.isupper())

    def tearDown(self):
        shutil.rmtree(self.dirpath)

if __name__ == '__main__':
    unittest.main()
