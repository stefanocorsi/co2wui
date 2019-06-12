from setuptools import setup

setup(
    name='co2wui',
    version='0.1dev',
    packages=['co2wui',],
    license='EUPL',
    long_description=open('README.md').read(),
    entry_points={
        'console_scripts': [
            'co2wui=co2wui:cli'
        ],
    },
)