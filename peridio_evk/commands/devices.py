import click
import sys
import select
import termios
import tty
import uuid
import json
import hashlib
import base64
from peridio_evk.log import *
from peridio_evk.utils import *
from peridio_evk.uboot_env import *
from peridio_evk.crypto import *

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
  "cache_dir": "/etc/peridiod/cache",
  "release_poll_enabled": True,
  "release_poll_interval": 5000,
  "remote_shell": True,
  "targets": ["arm64-v8", "arm-ethos-u65"],
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

custom_entrypoint = """#!/usr/bin/env bash
ssh-keygen -A
addgroup "peridio"
adduser --disabled-password --ingroup "peridio" "peridio"
echo "peridio:peridio" | chpasswd
exec "$@"
"""

fw_env = "/etc/peridiod/uboot.env 0x0000 0x20000"

@click.command(name='devices-start')
@click.option(
    "--tag",
    required=False,
    type=str,
    default="latest",
    help="peridiod image tag (Optional)",
)
def devices_start(tag):
    container_client = get_container_client()
    log_task('Starting Virtual Devices')
    image_tag = f'docker.io/peridio/peridiod:{tag}'
    log_info(f"Pulling image: {image_tag}")
    image = container_client.images.pull(image_tag)

    if not bool(image.id):
        log_error("Invalid Image Tag")
        return

    config_path = get_config_path()
    devices_path = os.path.join(config_path, 'evk-data', 'devices')

    for device in devices:
        container_name = f'peridio-{device["identifier"]}'
        try:
            container_client.containers.get(container_name)
            log_info(f'Device {device["identifier"]} container already started')
            continue
        except Exception as e:
            log_info(f'Starting Device {device["identifier"]}')
        try:
            device_path = os.path.join(devices_path, device['identifier'])
            volumes = [
                {'type': 'bind', 'source': device_path, 'target': '/etc/peridiod'},
            ]
            env_vars = {
                "PERIDIO_LOG_LEVEL": "debug"
            }
            entrypoint = ['/etc/peridiod/entrypoint.sh']
            cmd = ["/opt/peridiod/bin/peridiod", "start_iex"]
            container_client.containers.run(
                image_tag,
                stdin_open=True,
                tty=True,
                detach=True,
                mounts=volumes,
                name=container_name,
                auto_remove=True,
                environment=env_vars,
                entrypoint=entrypoint,
                cap_add=["NET_ADMIN"],
                security_opt=["disable"],
                command=cmd
            )
        except Exception as e:
          log_error(f'error {e}')

@click.command(name='devices-stop')
def devices_stop():
    container_client = get_container_client()
    log_task('Stopping Virtual Devices')
    for device in devices:
        container_name = f'peridio-{device["identifier"]}'
        try:
            container = container_client.containers.get(container_name)
            log_info(f'Stopping {device["identifier"]}')
            container.stop()
        except:
            log_info(f'Device {device["identifier"]} container already stopped')

@click.argument('device_identifier')
@click.command(name='device-attach')
def device_attach(device_identifier):
    container_client = get_container_client()
    try:
        container = container_client.containers.get(f'peridio-{device_identifier}')
        log_task(f'Attaching To Container {device_identifier}')
        exec_instance = container.exec_run('/bin/bash', tty=True, stream=True, socket=True, detach=False, stdin=True)
        old_tty_settings = termios.tcgetattr(sys.stdin)
        sock = exec_instance.output
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



def do_create_device_environments(devices, release, artifacts, cohorts):
    config_path = get_config_path()
    devices_path = os.path.join(config_path, 'evk-data', 'devices')

    device_targets = ['arm64-v8', 'arm-ethos-u65']
    peridio_bin_installed = ''

    cohort = [cohort for cohort in cohorts if cohort.get('name') == 'release'][0]
    public_key_pem = cohort['signing_keys']['public_key_pem']
    public_key_raw = convert_ed25519_public_pem_to_raw(public_key_pem)
    public_key_raw_encoded = base64.b64encode(public_key_raw).decode('utf-8')

    for artifact in artifacts:
        sorted_custom_metadata = sort_dict_keys(artifact['custom_metadata'])
        custom_metadata = json.dumps(sorted_custom_metadata, separators=(',', ':'))
        log_info(f'Sorted: {custom_metadata}')
        custom_metadata_bytes = custom_metadata.encode('utf-8')
        hash_object = hashlib.new('sha256')
        hash_object.update(custom_metadata_bytes)
        custom_metadata_hash = hash_object.digest()
        installed_targets = [target for target in artifact['targets'] if target['target'] in device_targets]
        for target in installed_targets:
            binary_uuid = target['binary_prn'].split(':')[-1]
            log_info(f'binary id: {binary_uuid}')
            id = uuid.UUID(binary_uuid).bytes
            peridio_bin_installed = peridio_bin_installed + base64.b16encode(id).lower().decode('utf-8')
            log_info(f'id: {base64.b16encode(id).lower().decode("utf-8")}')
            peridio_bin_installed = peridio_bin_installed + base64.b16encode(custom_metadata_hash).lower().decode('utf-8')
            log_info(f'custom_metadata_hash: {base64.b16encode(custom_metadata_hash).lower().decode("utf-8")}')

    if not os.path.exists(devices_path):
        log_task(f'Creating Device Environments')
        os.makedirs(devices_path)

    for device in devices:
        device_path = os.path.join(devices_path, device['identifier'])
        if not os.path.exists(device_path):
            os.makedirs(device_path)

        device_env = {
            'peridio_rel_current': release['prn'],
            'peridio_vsn_current': release['version'],
            'peridio_bin_current': peridio_bin_installed
        }

        device_env_path = os.path.join(device_path, 'uboot.env')
        env_size_hex = int('0x20000', 16)
        create_uboot_env(device_env, device_env_path, env_size_hex)

        device_fw_env_config = os.path.join(device_path, 'fw_env.config')
        with open(device_fw_env_config, "w") as fw_env_config:
            fw_env_config.write(
                fw_env
            )

        entrypoint_file = os.path.join(device_path, 'entrypoint.sh')
        write_file_x(entrypoint_file, custom_entrypoint)

        peridio_json = peridio_json_template
        peridio_json['trusted_signing_keys'] = [public_key_raw_encoded]
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
        log_info(f'Device Identifier: {device["identifier"]}')
        log_info(f'Device Certificate: {device["certificate"]}')
        log_info(f'Device Private Key: {device["private_key"]}')

        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'devices',
                              'create', '--identifier', device['identifier'],
                              '--product-name', product_name, '--cohort-prn',
                              cohort_prn, '--tags', f'{",".join(device["tags"])}', '--target', device["target"]])
        if result.returncode != 0:
            log_skip_task('Device already exists')

        result = peridio_cli(['peridio', '--profile', evk_config['profile'], 'device-certificates', 'create', '--device-identifier', device['identifier'], '--product-name', product_name, '--certificate-path', device['certificate']])
        if result.returncode != 0:
            log_skip_task('Device certificate already exists')
