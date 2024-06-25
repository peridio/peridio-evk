import click
import os
from .utils import read_json_file, write_json_file, get_config_path, read_evk_config, get_evk_config_path, peridio_cli
from .crypto import create_root_ca
from .log import log_task, log_modify_file, log_info, log_success, log_skip_task

@click.command()
@click.option('--organization-name', required=True, type=str, help='Name of the organization')
@click.option('--organization-prn', required=True, type=str, help='PRN of the organization')
@click.option('--api-key', required=True, type=str, help='API key for authentication')
def configure(organization_name, organization_prn, api_key):
    log_task('Configuring EVK')
    log_info(f'Organization Name: {organization_name}')
    log_info(f'Organization PRN: {organization_prn}')
    log_info(f'API key: {api_key}')

    log_task('Updating CLI and EVK configuration')
    config_path = get_config_path()
    config_file = os.path.join(config_path, 'config.json')
    config = read_json_file(config_file)
    update_config(config, organization_name)
    write_json_file(config_file, config)

    credentials_file = os.path.join(config_path, 'credentials.json')
    credentials = read_json_file(credentials_file)
    update_credentials(credentials, organization_name, api_key)
    write_json_file(credentials_file, credentials)

    evk_config = read_evk_config()
    evk_config_file = get_evk_config_path()
    update_evk_config(evk_config, organization_name, organization_prn)
    write_json_file(evk_config_file, evk_config)

    root_ca_path = os.path.join(config_path, 'evk-data', 'ca')
    root_ca_key = os.path.join(root_ca_path, 'root-private-key.pem')
    root_ca_cert = os.path.join(root_ca_path, 'root-certificate.pem')

    if not os.path.exists(root_ca_path):
        log_task(f'Creating Root CA')
        os.makedirs(root_ca_path)
        create_root_ca(f'Root CA {organization_name}', root_ca_key, root_ca_cert)
        log_modify_file(root_ca_key)
        log_modify_file(root_ca_cert)
    else:
        log_skip_task('Root CA already exists')
        log_info(f'Root CA Certificate: {root_ca_cert}')
        log_info(f'Root CA Private-Key: {root_ca_key}')

    # Test that the 'peridio' executable is configured by calling the system
    log_task(f'Verifying CLI configuration')
    profile_name = organization_name
    peridio_cli(['peridio', '--profile', profile_name, 'users', 'me'])
    log_success('EVK configured successfully')

def update_config(config, organization_name):
    if 'profiles' not in config:
        config['profiles'] = {}
    config['profiles'][organization_name] = {'organization_name': organization_name}

def update_credentials(credentials, organization_name, api_key):
    credentials[organization_name] = {'api_key': api_key}

def update_evk_config(evk_config, organization_name, organization_prn):
    evk_config['profile'] = organization_name
    evk_config['organization_name'] = organization_name
    evk_config['organization_prn'] = organization_prn

