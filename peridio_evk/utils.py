import click
import os
import json
import platform
import shutil
import subprocess
import queue
import threading
import stat
import sys
from datetime import datetime
from peridio_evk.log import (
    log_cli_command,
    log_cli_response,
    log_modify_file,
    log_error,
    log_info,
)


class SubprocessResult:
    def __init__(self, stdout, stderr, returncode):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def read_json_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    else:
        return {}


def write_json_file(file_path, content):
    with open(file_path, "w") as f:
        json.dump(content, f, indent=4)
        log_modify_file(file_path)


def get_config_path():
    config_dir = os.getenv("PERIDIO_CONFIG_DIRECTORY")

    if config_dir is None:
        system = platform.system()
        if system == "Linux":
            config_dir = os.path.join(
                os.path.expanduser("~"), ".config", "peridio"
            )
        elif system == "Windows":
            from ctypes import windll, create_unicode_buffer

            CSIDL_APPDATA = 0x001A
            buf = create_unicode_buffer(1024)
            windll.shell32.SHGetFolderPathW(None, CSIDL_APPDATA, None, 0, buf)
            config_dir = os.path.join(buf.value, "peridio")
        elif system == "Darwin":
            config_dir = os.path.join(
                os.path.expanduser("~"),
                "Library",
                "Application Support",
                "peridio",
            )
        else:
            raise RuntimeError(f"Unsupported platform: {system}")

    if not os.path.exists(config_dir):
        os.makedirs(config_dir)

    return config_dir


def get_evk_config_path():
    config_path = get_config_path()
    return os.path.join(config_path, "evk.json")


def read_evk_config():
    evk_config_path = get_evk_config_path()
    return read_json_file(evk_config_path)


def peridio_cli(command):
    if shutil.which("peridio") is None:
        log_error('"peridio" CLI executable not found in the system PATH.')
        raise click.ClickException(
            "Please install the peridio CLI and ensure it is available in the system PATH."
        )
    log_cli_command(command)

    try:
        # Start the subprocess
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # Ensures the output is in text mode
        )

        # Queues to collect stdout and stderr output
        stdout_queue = queue.Queue()
        stderr_queue = queue.Queue()

        # Start threads to stream stdout and stderr
        stdout_thread = threading.Thread(
            target=stream_stdout, args=(process.stdout, stdout_queue)
        )
        stderr_thread = threading.Thread(
            target=stream_stderr, args=(process.stderr, stderr_queue)
        )
        stdout_thread.start()
        stderr_thread.start()

        # Wait for the process to finish
        process.wait()

        # Wait for the threads to finish
        stdout_thread.join()
        stderr_thread.join()

        # Collect stdout output from the queue
        stdout_output = ""
        while not stdout_queue.empty():
            stdout_output += stdout_queue.get()

        # Collect stderr output from the queue
        stderr_output = ""
        while not stderr_queue.empty():
            stderr_output += stderr_queue.get()

        return_code = process.returncode
        pretty_print_result = str(stdout_output)

        if return_code == 0 and pretty_print_result != "":
            formatted_result = json.loads(pretty_print_result)
            log_cli_response(json.dumps(formatted_result, indent=2))

        result = SubprocessResult(
            str(stdout_output), str(stderr_output), return_code
        )
        return result

    except Exception as e:
        log_error(e.with_traceback)
        return SubprocessResult(None, None, None)


def generate_random_bytes_file(file_path, length):
    # Generate random bytes
    random_bytes = os.urandom(length)

    # Write the bytes to a file
    with open(file_path, "wb") as file:
        file.write(random_bytes)


def stream_stdout(pipe, output_queue):
    for line in iter(pipe.readline, ""):
        if line:
            output_queue.put(line)
    pipe.close()


def stream_stderr(pipe, output_queue):
    for line in iter(pipe.readline, ""):
        if line:
            click.secho(f"     CLI: {line.strip()}", fg="bright_black")
            output_queue.put(line)
    pipe.close()


def find_dict_by_name(list_of_dicts, name_value):
    return next((d for d in list_of_dicts if d.get("name") == name_value), None)


def get_current_time_iso8601():
    # Get the current UTC time
    now = datetime.utcnow()

    # Format the time to ISO 8601 format with a 'Z' at the end to denote UTC time
    formatted_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    return formatted_time


def boolean_to_string_lower(value):
    if isinstance(value, bool):
        return str(value).lower()
    else:
        raise ValueError("Input is not a boolean value.")


def write_file_x(file_path, content):
    with open(file_path, "w") as file:
        file.write(content)
    st = os.stat(file_path)
    os.chmod(file_path, st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def filter_dicts(dict_list, key, value):
    return [
        dictionary for dictionary in dict_list if dictionary.get(key) == value
    ]


def get_docker_client():
    try:
        import docker

        client = docker.from_env()
        # Test the connection to Docker service
        client.ping()
        log_info("Using Docker client")
        return client
    except:
        return None


def get_container_client():
    # Check if Docker is installed
    try:
        subprocess.run(
            ["docker", "--version"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        client = get_docker_client()
        if client:
            return client
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    log_error("Docker needs to be running to start device containers")
    sys.exit()

def sort_dict_keys(d):
    if isinstance(d, dict):
        # Recursively sort the dictionary
        return {k: sort_dict_keys(v) for k, v in sorted(d.items())}
    elif isinstance(d, list):
        # Recursively sort each element in the list
        return [sort_dict_keys(item) for item in d]
    else:
        return d
