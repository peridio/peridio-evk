from setuptools import setup, find_packages

setup(
    name="peridio_evk",
    version="0.1.8",
    author="Peridio Developers",
    author_email="support@peridio.com",
    description="The Peridio Evaluation Kit",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/peridio/peridio-evk",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    include_package_data=True,
    install_requires=["click", "cryptography", "uboot", "docker"],
    entry_points={
        "console_scripts": [
            "peridio-evk = peridio_evk.cli:cli",
        ],
    },
)
