import struct
import crc32c

def pack_env(env_dict, size):
    """
    Pack the environment dictionary into a binary format with padding.
    """
    # Join the environment variables into a single byte string
    env_data = '\0'.join(f'{k}={v}' for k, v in env_dict.items()).encode('ascii') + b'\0\0'
    
    # Check if the packed environment is too large
    if len(env_data) > size:
        raise ValueError("Environment data is too large")
    
    # Pad the environment data to the specified size
    return env_data.ljust(size, b'\0')

def create_env_file(env_dict, size, file_path):
    """
    Create a U-Boot environment and write it to a file.
    """
    # Pack the environment dictionary into a byte string
    env_data = pack_env(env_dict, size - 4)  # 4 bytes for the CRC
    
    # Calculate the CRC32C checksum of the environment data
    crc = crc32c.crc32c(env_data)
    
    # Pack the CRC and environment data together
    packed_env = struct.pack('<I', crc) + env_data

    # Write the packed environment to the specified file
    with open(file_path, 'wb') as f:
        f.write(packed_env)
