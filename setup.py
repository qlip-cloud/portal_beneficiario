from setuptools import setup, find_packages

with open('requirements.txt') as f:
	install_requires = f.read().strip().split('\n')

# get version from __version__ variable in portal_beneficiario/__init__.py
from portal_beneficiario import __version__ as version

setup(
	name='portal_beneficiario',
	version=version,
	description='Portal de Beneficiario',
	author='Adolfo Hernandez',
	author_email='adolfo.jgi.hernandez@gmail.com',
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
