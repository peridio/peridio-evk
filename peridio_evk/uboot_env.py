import uboot


def create_uboot_env(env_vars, env_file_path, env_size):
    """
    Create a U-Boot environment file with a valid CRC using the uboot Python module and specify the environment size.

    Parameters:
    env_vars (dict): A dictionary of environment variables.
    env_file_path (str): The path where the environment file will be saved.
    env_size (int): The desired size of the environment file in bytes.
    """
    # Create an instance of the U-Boot environment
    env = uboot.EnvBlob(size=env_size)

    # Set the environment variables
    for key, value in env_vars.items():
        env.set(key, value)

    # Export the environment data
    env_data = env.export()

    # Check if the environment data is smaller than the specified size
    if len(env_data) > env_size:
        raise ValueError("Environment data exceeds the specified size.")

    # Pad the environment data to the desired size
    padded_env_data = env_data.ljust(env_size, b"\x00")

    # Write the padded environment data to a file
    with open(env_file_path, "wb") as f:
        f.write(padded_env_data)
