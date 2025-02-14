# Simple functions to do basic verification of the contents of .pem and .key files.
#

import re

# Disabling for now - in the world of crypto; the developers of the cryptography
# package are doing the right thing and pushing for modern fixed libraries

# Unfortunately that means that ARMv6l processors aren't on the supported list
# This drops support for the RPi Zero and similar devices.
# Need a better way to do cert validation without having to bring full crypto along to play

# Partial success with
# pip install cryptography==41.0.5

from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.x509 import load_pem_x509_certificate
from cryptography.exceptions import InvalidKey
from datetime import datetime, timezone


def check_private_key(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            # Check if the file contains private key format
            if re.search(b"-----BEGIN (RSA|EC) PRIVATE KEY-----", data):
                try:
                    private_key = load_pem_private_key(data, password=None)
                    return "Valid Private Key"
                except (ValueError, TypeError, InvalidKey):
                    return "Invalid Private Key"
            else:
                return "Not a Private Key"
    except Exception as e:
        return f"Error reading file: {e}"


def check_certificate(file_path):
    try:
        with open(file_path, "rb") as f:
            data = f.read()
            # Check if the file contains certificate format
            if b"-----BEGIN CERTIFICATE-----" in data:
                try:
                    cert = load_pem_x509_certificate(data)
                    # Check expiration
                    current_date = datetime.now(timezone.utc)
                    if cert.not_valid_after_utc < current_date:
                        return "Expired TLS Certificate"
                    return "Valid TLS Certificate"
                except ValueError as err:
                    return "Invalid TLS Certificate"
            else:
                return "Not a Certificate"
    except Exception as e:
        return f"Error reading file: {e}"


def verify_file(file_path):
    # First, check if it's a valid private key
    private_key_status = check_private_key(file_path)
    if private_key_status == "Valid Private Key":
        return private_key_status
    # If it's not a private key, check if it's a valid TLS certificate
    certificate_status = check_certificate(file_path)
    if certificate_status == "Valid TLS Certificate":
        return certificate_status
    elif certificate_status == "Expired TLS Certificate":
        return certificate_status
    return "File is neither a valid private key nor a valid TLS certificate"


# # Example usage:
# file_path = 'https_cert.pem'  # Replace with your file path
# status = verify_file(file_path)
# print(status)
