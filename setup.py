from setuptools import setup, find_packages

setup(
    name='peridio_evk',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click',
    ],
    entry_points={
        'console_scripts': [
            'peridio-evk = peridio_evk.cli:cli',
        ],
    },
)
