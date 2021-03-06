"""Wheel setup file"""

try:
    from azure_bdist_wheel import cmdclass
except ImportError:
    from distutils import log as logger
    logger.warn("Wheel is not available, disabling bdist_wheel hook")

# Get version from version file
import sys
import os

from setuptools import setup, find_packages
azext = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'azext_cdf/')
sys.path.append(azext)
from version import VERSION

sys.path.pop()

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Intended Audience :: System Administrators',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'License :: OSI Approved :: MIT License',
]

DEPENDENCIES = [
    "schema",
    "pyYaml",
    "Jinja2",
    "semver"
]

setup(
    name='cdf',
    version=VERSION,
    description='CDF tools',
    author='Adham Abdelwahab',
    author_email='',
    url='https://github.com/ahelal/cdf',
    long_description='CDF is an Azure CLI plugin that will make your life easier to develop, test, maintain, share units, and run IaC code in Azure',
    license='MIT',
    classifiers=CLASSIFIERS,
    packages=find_packages(),
    install_requires=DEPENDENCIES,
    package_data={'azext_cdf': ['azext_metadata.json']},
)
