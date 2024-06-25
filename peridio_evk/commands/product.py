import click
import json
import os
import base64
from .utils import *
from .log import *
from .crypto import *

@click.command()
@click.option('--name', required=True, type=str, help='Name of the product')
def create_product(name):
    log_task('Creating product')
    log_info(f'Product Name: {name}')

    evk_config = read_evk_config()
    result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'products-v2', 'create', '--name', name, '--organization-prn', evk_config['organization_prn']])
    if result.returncode != 0:
        response = json.loads(result.stderr.strip())
        if "has already been taken" in response['data']['params']['name']:
            log_skip_task('Product already exists')
        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'products-v2', 'list', '--search', f'organization_prn:\'{evk_config['organization_prn']}\' and name:\'{name}\''])
        if result.returncode == 0:
            response = json.loads(result.stdout)
            product_prn = response['products'][0]['prn']
        else:
            log_error(result.stderr.strip())
    else:
        response = json.loads(result.stdout)
        product_prn = response['data']['product']['prn']
    log_info(f'Product PRN: {product_prn}')
    create_product_cohorts(product_prn, name)

def create_product_cohorts(product_prn, product_name):
    evk_config = read_evk_config()
    log_task(f'Creating Product Cohorts')
    cohorts = [
        ('release', 'This cohort is for devices running stable, production-ready firmware releases that are suitable for end-users or wider deployment.'), 
        ('release-debug', 'Devices in this cohort run release candidate builds with debugging features enabled, allowing for more in-depth testing and issue diagnosis in a near-production environment.'), 
        ('daily-release', 'This cohort is for devices running daily release builds, which are more stable than debug builds but still updated frequently for testing and validation purposes.'), 
        ('daily-debug', 'This cohort is used for devices that run daily debug builds, typically used by developers for active development and testing.')
    ]
    for cohort, desc in cohorts:
        log_info(f'Cohort: {cohort}')
        
    for cohort, desc in cohorts:
        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'cohorts', 'create', '--name', cohort, '--description', desc, '--organization-prn', evk_config['organization_prn'], '--product-prn', product_prn])
        if result.returncode != 0:
            log_skip_task('Cohort already exists')
            result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'cohorts', 'list', '--search', f'organization_prn:\'{evk_config['organization_prn']}\' and name:\'{cohort}\''])
            if result.returncode == 0:
                response = json.loads(result.stdout)
                cohort_prn = response['cohorts'][0]['prn']
            else:
                log_error(result.stderr.strip())
        else:
            response = json.loads(result.stdout)
            cohort_prn = response['data']['cohort']['prn']
        create_product_cohort_ca(product_name, cohort, cohort_prn)
        create_cohort_signing_key(cohort, cohort_prn)
    
def create_product_cohort_ca(product_name, cohort_name, cohort_prn):
    config_path = get_config_path()
    evk_config = read_evk_config()
    root_ca_path = os.path.join(config_path, 'evk-data', 'ca')
    root_ca_key = os.path.join(root_ca_path, 'root-private-key.pem')
    root_ca_cert = os.path.join(root_ca_path, 'root-certificate.pem')

    intermediate_ca_path = os.path.join(root_ca_path, product_name, cohort_name)
    intermediate_ca_key = os.path.join(intermediate_ca_path, f'intermediate-private-key.pem')
    intermediate_ca_csr = os.path.join(intermediate_ca_path, f'intermediate-signing-request.pem')
    intermediate_ca_cert = os.path.join(intermediate_ca_path, f'intermediate-certificate.pem')
    if not os.path.exists(intermediate_ca_cert):
        log_task(f'Creating Intermediate CA')
        os.makedirs(intermediate_ca_path)
        create_intermediate_ca_csr(f'Intermediate CA {product_name} {cohort_name}', intermediate_ca_key, intermediate_ca_csr)
        log_modify_file(intermediate_ca_key)
        log_modify_file(intermediate_ca_csr)
        sign_intermediate_ca_csr(root_ca_key, root_ca_cert, intermediate_ca_csr, intermediate_ca_cert)
        log_modify_file(intermediate_ca_cert)
    else:
        log_skip_task('Intermediate CA already exists')
        log_info(f'Intermediate CA Certificate: {intermediate_ca_cert}')
        log_info(f'Intermediate CA Private-Key: {intermediate_ca_key}')

    log_task(f'Registering Intermediate CA')
    ca_certificate_serial = str(read_ca_serial_number(intermediate_ca_cert))
    result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'ca-certificates', 'get', '--ca-certificate-serial', ca_certificate_serial])
    if result.returncode != 0:
        log_task(f'Generating CA Certificate Verification Code')
        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'ca-certificates', 'create-verification-code'])
        if result.returncode == 0:
            response = json.loads(result.stdout)
            verification_code = response['data']['verification_code']
            log_info(f'Verification Code: {verification_code}')
        
        log_task(f'Signing Verification Certificate')
        verification_ca_key = os.path.join(intermediate_ca_path, 'verification-private-key.pem')
        verification_ca_csr = os.path.join(intermediate_ca_path, 'verification-signing-request.pem')
        verification_ca_cert = os.path.join(intermediate_ca_path, 'verification-certificate.pem')
        create_end_entity_csr(verification_code, verification_ca_key, verification_ca_csr)
        log_modify_file(verification_ca_key)
        log_modify_file(verification_ca_csr)
        sign_end_entity_csr(intermediate_ca_key, intermediate_ca_cert, verification_ca_csr, verification_ca_cert)
        log_modify_file(verification_ca_cert)

        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'ca-certificates', 'create', '--certificate-path', intermediate_ca_cert, '--verification-certificate-path', verification_ca_cert, '--description', f'Intermediate CA: {product_name}:{cohort_name}', '--jitp-cohort-prn', cohort_prn, '--jitp-product-name', product_name, '--jitp-tags', 'JITP', '--jitp-description', 'JITP'])
        if result.returncode != 0:
            log_error(result.stderr)
    else:
        log_skip_task(f'Intermediate CA Already Registered')

def create_cohort_signing_key(cohort_name, cohort_prn):
    config_path = get_config_path()
    evk_config = read_evk_config()
    signing_keys_path = os.path.join(config_path, 'evk-data', 'signing-keys')
    if not os.path.exists(signing_keys_path):
        os.makedirs(signing_keys_path)

    cohort_public_key_pem = os.path.join(signing_keys_path, f'{cohort_name}-public-key.pem')
    cohort_private_key_pem = os.path.join(signing_keys_path, f'{cohort_name}-private-key.pem')

    if not os.path.exists(cohort_private_key_pem):
        log_task(f'Creating Binary Signing Key')
        create_ed25519_keys(cohort_private_key_pem, cohort_public_key_pem)
        log_modify_file(cohort_private_key_pem)
        log_modify_file(cohort_public_key_pem)
    else:
        log_skip_task(f'Binary Signing Key Already Exists')
        log_info(f'Private Key PEM: {cohort_private_key_pem}')
        log_info(f'Public Key PEM: {cohort_public_key_pem}')

    public_key_raw = convert_ed25519_public_pem_to_raw(cohort_public_key_pem)
    public_key_raw_encoded = base64.b64encode(public_key_raw).decode('utf-8')
    result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'signing-keys', 'list', '--search', f'organization_prn:\'{evk_config['organization_prn']}\' and value:\'{public_key_raw_encoded}\''])
    if result.returncode == 0:
        response = json.loads(result.stdout)
        if response['signing_keys'] == []:
            log_task(f'Registering Binary Signing Key')
            response = peridio_cli(['peridio', '--profile', evk_config['profile'], 'signing-keys', 'create', '--organization-prn', evk_config['organization_prn'], '--value', public_key_raw_encoded, '--name', f'{cohort_name}-signing-key'])
            if result.returncode == 0:
                response = json.loads(result.stdout)
                signing_key_prn = response['signing_key']['prn']
        else:
            log_skip_task(f'Binary Signing Key Already Registered')
            signing_key_prn = response['signing_keys'][0]['prn']
    else:
        log_error(result.stderr)

    log_task(f'Adding Signing Key to CLI Keychain')
    config_file = os.path.join(config_path, 'config.json')
    config = read_json_file(config_file)
    update_config_signing_key_pairs(config, f'{cohort_name}-signing-key', signing_key_prn, cohort_private_key_pem)
    write_json_file(config_file, config)

def update_config_signing_key_pairs(config, signing_key_pair_name, signing_key_prn, signing_key_private_path):
    if 'signing_key_pairs' not in config:
        config['signing_key_pairs'] = {}
    config['signing_key_pairs'][signing_key_pair_name] = {'signing_key_prn': signing_key_prn, 'signing_key_private_path': signing_key_private_path}
