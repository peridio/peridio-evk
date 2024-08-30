from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from datetime import datetime, timedelta


def create_root_ca(common_name, key_path, cert_path):
    # Generate private key
    private_key = ec.generate_private_key(ec.SECP256R1())

    # Write private key to file
    with open(key_path, "wb") as key_file:
        key_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Generate public certificate
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    )
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(days=1))
        .not_valid_after(
            # Certificate is valid for 31 years
            datetime.utcnow()
            + timedelta(days=31 * 365)
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(
                private_key.public_key()
            ),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write public certificate to file
    with open(cert_path, "wb") as cert_file:
        cert_file.write(certificate.public_bytes(serialization.Encoding.PEM))


def create_intermediate_ca_csr(common_name, key_path, csr_path):
    # Generate private key for Intermediate CA
    private_key = ec.generate_private_key(ec.SECP256R1())

    # Write private key to file
    with open(key_path, "wb") as key_file:
        key_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Generate CSR
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write CSR to file
    with open(csr_path, "wb") as csr_file:
        csr_file.write(csr.public_bytes(serialization.Encoding.PEM))


def sign_intermediate_ca_csr(
    root_key_path, root_cert_path, intermediate_csr_path, intermediate_cert_path
):
    # Load Root CA's private key
    with open(root_key_path, "rb") as key_file:
        root_private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
        )

    # Load Root CA's certificate
    with open(root_cert_path, "rb") as cert_file:
        root_cert = x509.load_pem_x509_certificate(cert_file.read())

    # Load Intermediate CA's CSR
    with open(intermediate_csr_path, "rb") as csr_file:
        intermediate_csr = x509.load_pem_x509_csr(csr_file.read())

    # Generate Intermediate CA's certificate
    intermediate_cert = (
        x509.CertificateBuilder()
        .subject_name(intermediate_csr.subject)
        .issuer_name(root_cert.subject)
        .public_key(intermediate_csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(days=1))
        .not_valid_after(
            # Certificate is valid for 10 years
            datetime.utcnow()
            + timedelta(days=3650)
        )
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(
                root_private_key.public_key()
            ),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(
                intermediate_csr.public_key()
            ),
            critical=False,
        )
        .sign(root_private_key, hashes.SHA256())
    )

    # Write Intermediate CA's certificate to file
    with open(intermediate_cert_path, "wb") as cert_file:
        cert_file.write(
            intermediate_cert.public_bytes(serialization.Encoding.PEM)
        )


def create_end_entity_csr(common_name, key_path, csr_path):
    # Generate private key for End-Entity
    private_key = ec.generate_private_key(ec.SECP256R1())

    # Write private key to file
    with open(key_path, "wb") as key_file:
        key_file.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Generate CSR
    csr = (
        x509.CertificateSigningRequestBuilder()
        .subject_name(
            x509.Name(
                [
                    x509.NameAttribute(NameOID.COMMON_NAME, common_name),
                ]
            )
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write CSR to file
    with open(csr_path, "wb") as csr_file:
        csr_file.write(csr.public_bytes(serialization.Encoding.PEM))


def sign_end_entity_csr(
    intermediate_key_path,
    intermediate_cert_path,
    end_entity_csr_path,
    end_entity_cert_path,
):
    # Load Intermediate CA's private key
    with open(intermediate_key_path, "rb") as key_file:
        intermediate_private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
        )

    # Load Intermediate CA's certificate
    with open(intermediate_cert_path, "rb") as cert_file:
        intermediate_cert = x509.load_pem_x509_certificate(cert_file.read())

    # Load End-Entity CSR
    with open(end_entity_csr_path, "rb") as csr_file:
        end_entity_csr = x509.load_pem_x509_csr(csr_file.read())

    # Generate End-Entity certificate
    end_entity_cert = (
        x509.CertificateBuilder()
        .subject_name(end_entity_csr.subject)
        .issuer_name(intermediate_cert.subject)
        .public_key(end_entity_csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(days=1))
        .not_valid_after(
            # Certificate is valid for 1 year
            datetime.utcnow()
            + timedelta(days=365)
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(
                intermediate_private_key.public_key()
            ),
            critical=False,
        )
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(
                end_entity_csr.public_key()
            ),
            critical=False,
        )
        .sign(intermediate_private_key, hashes.SHA256())
    )

    # Write End-Entity certificate to file
    with open(end_entity_cert_path, "wb") as cert_file:
        cert_file.write(
            end_entity_cert.public_bytes(serialization.Encoding.PEM)
        )


def read_ca_serial_number(cert_path):
    with open(cert_path, "rb") as cert_file:
        ca_cert = x509.load_pem_x509_certificate(cert_file.read())

    serial_number = ca_cert.serial_number
    return serial_number


def create_ed25519_keys(private_key_path, public_key_path):
    private_key = ed25519.Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    with open(private_key_path, "wb") as private_key_file:
        private_key_file.write(private_pem)

    with open(public_key_path, "wb") as public_key_file:
        public_key_file.write(public_pem)


def convert_ed25519_private_pem_to_raw(pem_path):
    # Read the PEM file
    with open(pem_path, "rb") as pem_file:
        pem_data = pem_file.read()

    # Load the private key from the PEM data
    private_key = serialization.load_pem_private_key(pem_data, password=None)

    # Ensure the key is an Ed25519 private key
    if not isinstance(private_key, ed25519.Ed25519PrivateKey):
        raise ValueError("The provided key is not an Ed25519 private key.")

    # Convert the private key to raw bytes
    raw_private_key = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return raw_private_key


def convert_ed25519_public_pem_to_raw(pem_path):
    # Read the PEM file
    with open(pem_path, "rb") as pem_file:
        pem_data = pem_file.read()

    # Load the public key from the PEM data
    public_key = serialization.load_pem_public_key(pem_data)

    # Ensure the key is an Ed25519 public key
    if not isinstance(public_key, ed25519.Ed25519PublicKey):
        raise ValueError("The provided key is not an Ed25519 public key.")

    # Convert the public key to raw bytes
    raw_public_key = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    return raw_public_key
