import click
import os
from peridio_evk.utils import *
from peridio_evk.crypto import create_root_ca
from peridio_evk.log import log_task, log_modify_file, log_info, log_skip_task
from peridio_evk.product import do_create_product
from peridio_evk.releases import do_create_artifacts
from peridio_evk.commands.devices import (
    do_create_device_environments,
    do_create_device_certificates,
    do_register_devices,
    devices,
)


@click.command()
@click.option(
    "--organization-name",
    required=True,
    type=str,
    help="Name of the organization",
)
@click.option(
    "--organization-prn",
    required=True,
    type=str,
    help="PRN of the organization",
)
@click.option(
    "--api-key", required=True, type=str, help="API key for authentication"
)
@click.option(
    "--product-name",
    required=False,
    type=str,
    default="edge-inference",
    help="Product Name (Optional)",
)
def initialize(organization_name, organization_prn, api_key, product_name):
    log_task("Initializing EVK")
    log_info(f"Organization Name: {organization_name}")
    log_info(f"Organization PRN: {organization_prn}")
    log_info(f"Product Name: {product_name}")
    log_info(f"API key: {api_key}")

    if click.confirm(
        "Running this task may take several minutes to complete.\nYou may run this task over again in the case of errors as it will not duplicate data\n\nProceed?",
        default=False,
    ):
        do_initialize(organization_name, organization_prn, api_key)
        cohort_prns = do_create_product(product_name)
        release_cohort = find_dict_by_name(cohort_prns, "release")
        release_cohort_prn = release_cohort["prn"]
        release, artifacts = do_create_artifacts(organization_prn, release_cohort_prn)
        do_create_device_environments(devices, release, artifacts, cohort_prns)
        updated_devices = do_create_device_certificates(
            devices, release_cohort["ca"]
        )
        filtered_devices = filter_dicts(updated_devices, "tags", ["canary"])
        do_register_devices(filtered_devices, product_name, release_cohort_prn)


def do_initialize(organization_name, organization_prn, api_key):
    log_task("Updating CLI and EVK configuration")
    config_path = get_config_path()
    check_default_cli_config(config_path)
    config_file = os.path.join(config_path, "config.json")
    config = read_json_file(config_file)
    update_config(config, organization_name)
    write_json_file(config_file, config)

    credentials_file = os.path.join(config_path, "credentials.json")
    credentials = read_json_file(credentials_file)
    update_credentials(credentials, organization_name, api_key)
    write_json_file(credentials_file, credentials)

    evk_config = read_evk_config()
    evk_config_file = get_evk_config_path()
    update_evk_config(evk_config, organization_name, organization_prn)
    write_json_file(evk_config_file, evk_config)

    root_ca_path = os.path.join(config_path, "evk-data", "ca")
    root_ca_key = os.path.join(root_ca_path, "root-private-key.pem")
    root_ca_cert = os.path.join(root_ca_path, "root-certificate.pem")

    if not os.path.exists(root_ca_path):
        log_task(f"Creating Root CA")
        os.makedirs(root_ca_path)
        create_root_ca(
            f"Root CA {organization_name}", root_ca_key, root_ca_cert
        )
        log_modify_file(root_ca_key)
        log_modify_file(root_ca_cert)
    else:
        log_skip_task("Root CA already exists")
        log_info(f"Root CA Certificate: {root_ca_cert}")
        log_info(f"Root CA Private-Key: {root_ca_key}")

    # Test that the 'peridio' executable is configured by calling the system
    log_task(f"Verifying CLI configuration")
    profile_name = organization_name
    peridio_cli(["peridio", "--profile", profile_name, "users", "me"])


def update_config(config, organization_name):
    if "profiles" not in config:
        config["profiles"] = {}
    config["profiles"][organization_name] = {
        "organization_name": organization_name
    }


def update_credentials(credentials, organization_name, api_key):
    credentials[organization_name] = {"api_key": api_key}


def update_evk_config(evk_config, organization_name, organization_prn):
    evk_config["profile"] = organization_name
    evk_config["organization_name"] = organization_name
    evk_config["organization_prn"] = organization_prn


def check_default_cli_config(config_path):
    default_cli_config = {"version": 1, "profiles": {}, "signing_key_pairs": {}}

    default_credentials = {}
    config_file_path = os.path.join(config_path, "config.json")
    credentials_file_path = os.path.join(config_path, "credentials.json")
    if not os.path.exists(config_path):
        log_task(f"Creating CLI Config")
        os.makedirs(config_path)
    if not os.path.exists(config_file_path):
        log_modify_file(config_file_path)
        write_json_file(config_file_path, default_cli_config)
    if not os.path.exists(credentials_file_path):
        log_modify_file(credentials_file_path)
        write_json_file(credentials_file_path, default_credentials)
