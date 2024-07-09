import click
import sys
import select
import termios
import tty
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
    "key_pair_source": "file",
    "key_pair_config": {
      "private_key_path": "/etc/peridiod/device-private-key.pem",
      "certificate_path": "/etc/peridiod/device-certificate.pem"
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

@click.command(name='devices-start')
def devices_start():
    container_client = get_container_client()
    log_task('Starting Virtual Devices')
    image_tag = 'peridio/peridiod:latest'
    log_info(f"Pulling image: {image_tag}")
    container_client.images.pull(image_tag)

    config_path = get_config_path()
    devices_path = os.path.join(config_path, 'evk-data', 'devices')

    for device in devices:
        container_name = f'peridio-{device['identifier']}'
        try:
            container_client.containers.get(container_name)
            log_info(f'Device {device['identifier']} container already started')
        except:
            log_info(f'Starting Device {device['identifier']}')
            device_path = os.path.join(devices_path, device['identifier'])
            volumes = {
                device_path: {'bind': '/etc/peridiod', 'mode': 'rw'},
            }
            container = container_client.containers.run(
                image_tag,
                detach=True,
                volumes=volumes,
                name=container_name,
                auto_remove=True
            )
   
@click.command(name='devices-stop')
def devices_stop():
    container_client = get_container_client()
    log_task('Stopping Virtual Devices')
    for device in devices:
        container_name = f'peridio-{device['identifier']}'
        try:
            container = container_client.containers.get(container_name)
            log_info(f'Stopping {device['identifier']}')
            container.stop()
        except:
            log_info(f'Device {device['identifier']} container already stopped')

@click.argument('device_identifier')
@click.command(name='device-attach')
def device_attach(device_identifier):
    container_client = get_container_client()
    try:
        container = container_client.containers.get(f'peridio-{device_identifier}')
        log_task(f'Attaching To Container {device_identifier}')
        exec_id = container_client.api.exec_create(container.id, '/bin/bash', tty=True, stdin=True)['Id']
        old_tty_settings = termios.tcgetattr(sys.stdin)
        sock = container_client.api.exec_start(exec_id, tty=True, stream=True, detach=False, socket=True)
        try:
            # Set terminal to raw mode
            tty.setraw(sys.stdin.fileno())
            log_info("Attached to the container")
            while True:
                # Wait for either input from the user or output from the container
                readable, _, _ = select.select([sys.stdin, sock], [], [])
                
                for r in readable:
                    if r == sys.stdin:
                        # Read user input and send it to the container's stdin
                        user_input = os.read(sys.stdin.fileno(), 1024)
                        sock._sock.send(user_input)
                    else:
                        # Read logs from the container and print them
                        output = sock._sock.recv(1024)
                        if not output:
                            return
                        output_decoded = output.decode('utf-8')
                        sys.stdout.write(output_decoded)
                        sys.stdout.flush()
        finally:
            # Restore the terminal settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty_settings)
            sock.close()

    except:
        log_info(f'Device {device_identifier} not running')



def do_create_device_environments(devices, release):
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
            'peridio_release_prn': release['prn'],
            'peridio_release_version': release['version']
        }

        device_env_path = os.path.join(device_path, 'uboot.env')
        env_size_hex = int('0x20000', 16)
        create_uboot_env(device_env, device_env_path, env_size_hex)

        peridio_json = peridio_json_template
        peridio_json_path = os.path.join(device_path, 'peridio.json')
        with open(peridio_json_path, 'w') as file:
            file.write(json.dumps(peridio_json, indent=2))

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
