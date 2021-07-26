from setuptools import setup
import ast
import sys

setup_requires = ['setuptools >= 30.3.0']

if {'pytest', 'test', 'ptr'}.intersection(sys.argv):
    setup_requires.append('pytest-runner')


setup(description="oda-experiments",
      version='0.1.0',
      include_package_data=True,
      setup_requires=setup_requires)
