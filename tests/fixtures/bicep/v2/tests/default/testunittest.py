#!/usr/bin/env python3
from azspec.az import Resource, Resources
import unittest
import os

class TestStringMethods(unittest.TestCase):
    name = f"{os.environ['CDF_NAME']}_key"
    resource_group = os.environ['CDF_RESOURCE_GROUP']
    location = os.environ['CDF_LOCATION']

    def test_sshkey(self):
        # print("CDF_NAME", self.name)
        # print("CDF_RESOURCE_GROUP", self.resource_group)
        # print("CDF_LOCATION", self.location)
        # print("PYTHONPATH", os.environ['PYTHONPATH'])

        sshkey = Resource(args="sshkey", name=self.name, resource_group=self.resource_group, cache=True, cache_ttl=200)        
        self.assertTrue(sshkey.exists)
        self.assertEqual(sshkey.content['location'], self.location)

    def test_rg(self):
        self.assertEqual(self.resource_group, "cdf_terraform_ssh_t_rmkoc")

    def test_location(self):
        self.assertEqual(self.location, "eastus2")
