import click
from log import *
from utils import *
from uboot_env import *
from crypto import *

devices = [
    {'identifier': 'EI-ML-0001', 'target': 'arm64-v8', 'tags': ['canary']},
    {'identifier': 'EI-ML-0002', 'target': 'arm64-v8', 'tags': ['canary']},
    {'identifier': 'EI-ML-0003', 'target': 'arm64-v8', 'tags': []},
    {'identifier': 'EI-ML-0004', 'target': 'arm64-v8', 'tags': []},
    {'identifier': 'EI-ML-0005', 'target': 'arm64-v8', 'tags': []},
    {'identifier': 'EI-ML-0006', 'target': 'arm64-v8', 'tags': []}
]

fw_env_config_template = """
{uboot_env_path} {uboot_env_offset} {uboot_env_size}
"""

fw_env_default = {
    'uboot_env_path': '/etc/peridiod/uboot.env',
    'uboot_env_offset': '0x0000',
    'uboot_env_size': '0x20000'
}

peridio_json_template = {
  "version": 1,
  "fwup": {
    "devpath": "/etc/peridiod/peridio.fwup.img",
  },
  "remote_shell": True,
  "remote_access_tunnels": {
    "enabled": True,
    "service_ports": [22],
    "hooks": {
      "pre_up": "/etc/peridiod/hooks/pre-up.sh",
      "pre_down": "/etc/peridiod/hooks/pre-down.sh"
    }
  },
  "node": {
    "key_pair_source": "env",
    "key_pair_config": {
      "private_key": "PERIDIO_PRIVATE_KEY",
      "certificate": "PERIDIO_CERTIFICATE"
    }
  }
}

peridio_rat_pre_up = """
#!/usr/bin/env bash
#
# Args
# 1: Wireguard Network Interface Name
# 2: Destination service port number

set -e

IFNAME=$1
DPORT=$2

COUNTER_FILE="/tmp/peridio_counter_${DPORT}"

if [[ ! -f "$COUNTER_FILE" ]]; then
  echo 0 > "$COUNTER_FILE"
fi

# Read the current counter value
COUNTER=$(cat "$COUNTER_FILE")

# If its the first connection, start the ssh service
if [ "$COUNTER" -le 0 ]; then
  case $DPORT in
    22)
      exec /usr/sbin/sshd
      ;;
    *)
      ;;
  esac
fi

# Increment the counter
COUNTER=$((COUNTER + 1))

# Write the updated counter back to the file
echo "$COUNTER" > "$COUNTER_FILE"
"""

peridio_rat_pre_down = """
#!/usr/bin/env bash
#
# Args
# 1: Wireguard Network Interface Name
# 2: Destination service port number

set -e

IFNAME=$1
DPORT=$2

COUNTER_FILE="/tmp/peridio_counter_${DPORT}"

if [[ ! -f "$COUNTER_FILE" ]]; then
  COUNTER=1
fi

# Read the current counter value
COUNTER=$(cat "$COUNTER_FILE")

# Decrement the counter
COUNTER=$((COUNTER + -1))

# Write the updated counter back to the file
echo "$COUNTER" > "$COUNTER_FILE"

echo "Current counter value: $COUNTER"

# If its the last connection, stop the ssh service
if [ "$COUNTER" -le 0 ]; then
  case $DPORT in
    22)
      killall sshd
      ;;
    *)
      ;;
  esac
fi
"""

@click.command()
def virtual_devices_start():
    log_task('Starting Virtual Devices')

@click.command()
def virtual_devices_stop():
    log_task('Stopping Virtual Devices')

@click.command()
def virtual_devices_destroy():
    log_task('Destroying Virtual Devices')

def do_create_device_environments(devices):
    config_path = get_config_path()
    devices_path = os.path.join(config_path, 'evk-data', 'devices')
    if not os.path.exists(devices_path):
        log_task(f'Creating Device Environments')
        os.makedirs(devices_path)
    
    for device in devices:
        device_path = os.path.join(devices_path, device['identifier'])
        if not os.path.exists(device_path):
            os.makedirs(device_path)

        device_env = {
            'peridio_release_prn': '1234',
            'peridio_release_version': '5678'
        }

        device_env_path = os.path.join(device_path, 'uboot.env')

        create_env_file(device_env, 2048, device_env_path)
        fw_env_config = fw_env_config_template.format(**fw_env_default)
        fw_env_path = os.path.join(device_path, 'fw_env.config')
        with open(fw_env_path, 'w') as file:
            file.write(fw_env_config)

        rat_hooks_path = os.path.join(device_path, 'hooks')
        if not os.path.exists(rat_hooks_path):
            os.makedirs(rat_hooks_path)
        
        pre_up_path = os.path.join(rat_hooks_path, 'pre-up.sh')
        write_file_x(pre_up_path, peridio_rat_pre_up)

        pre_down_path = os.path.join(rat_hooks_path, 'pre-down.sh')
        write_file_x(pre_down_path, peridio_rat_pre_down)

def do_create_device_certificates(devices, signer_ca):
    config_path = get_config_path()
    devices_path = os.path.join(config_path, 'evk-data', 'devices')
    if not os.path.exists(devices_path):
        log_task(f'Creating Device Environments')
        os.makedirs(devices_path)
     
    for device in devices:
        device_path = os.path.join(devices_path, device['identifier'])
        device_key = os.path.join(device_path, 'device-private-key.pem')
        device_csr = os.path.join(device_path, 'device-signing-request.pem')
        device_cert = os.path.join(device_path, 'device-certificate.pem')
        if not os.path.exists(device_cert):
            create_end_entity_csr(device['identifier'], device_key, device_csr)
            log_modify_file(device_key)
            log_modify_file(device_csr)
            sign_end_entity_csr(signer_ca['private_key'], signer_ca['certificate'], device_csr, device_cert)
            log_modify_file(device_cert)
        device['certificate'] = device_cert
        device['private_key'] = device_key
    
    return devices

def do_register_devices(devices, product_name, cohort_prn):
    evk_config = read_evk_config()
    for device in devices:
        log_task(f'Registering Device')
        log_info(f'Device Identifier: {device['identifier']}')
        log_info(f'Device Certificate: {device['certificate']}')
        log_info(f'Device Private Key: {device['private_key']}')

        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'devices', 'create', '--identifier', device['identifier'], '--product-name', product_name, '--cohort-prn', cohort_prn, '--tags', f'{' '.join(device['tags'])}', '--target', device['target']])
        if result.returncode != 0:
            log_skip_task('Device already exists')
        
        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'device-certificates', 'create', '--device-identifier', device['identifier'], '--product-name', product_name, '--certificate-path', device['certificate']])
        if result.returncode != 0:
            log_skip_task('Device certificate already exists')
