import click
import os
import json
import platform
import shutil
import subprocess
from .log import log_cli_command, log_cli_response, log_modify_file, log_error

def read_json_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    else:
        return {}

def write_json_file(file_path, content):
    with open(file_path, 'w') as f:
        json.dump(content, f, indent=4)
        log_modify_file(file_path)

def get_config_path():
    config_dir = os.getenv('PERIDIO_CONFIG_DIRECTORY')
    
    if config_dir is None:
        system = platform.system()
        if system == 'Linux':
            config_dir = os.path.join(os.path.expanduser('~'), '.config', 'peridio')
        elif system == 'Windows':
            from ctypes import windll, create_unicode_buffer
            CSIDL_APPDATA = 0x001a
            buf = create_unicode_buffer(1024)
            windll.shell32.SHGetFolderPathW(None, CSIDL_APPDATA, None, 0, buf)
            config_dir = os.path.join(buf.value, 'peridio')
        elif system == 'Darwin':
            config_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', 'peridio')
        else:
            raise RuntimeError(f'Unsupported platform: {system}')
    
    if not os.path.exists(config_dir):
        os.makedirs(config_dir)
    
    return config_dir

def get_evk_config_path():
    config_path = get_config_path()
    return os.path.join(config_path, 'evk.json')

def read_evk_config():    
    evk_config_path = get_evk_config_path()
    return read_json_file(evk_config_path)

def peridio_cli(command):
    if shutil.which('peridio') is None:
        log_error('"peridio" CLI executable not found in the system PATH.')
        raise click.ClickException('Please install the peridio CLI and ensure it is available in the system PATH.')
    log_cli_command(command)
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode == 0:
        formatted_result = json.loads(result.stdout)
        log_cli_response(json.dumps(formatted_result, indent=2))
    return result
