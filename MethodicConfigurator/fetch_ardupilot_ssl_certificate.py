#!/usr/bin/env python3

'''
This file is part of Ardupilot methodic configurator. https://github.com/ArduPilot/MethodicConfigurator

This script is designed to fetch, validate, and save SSL certificates for a specified host.
It utilizes the Python standard libraries ssl and socket to establish a secure connection
and retrieve the certificate, which is then saved in PEM format.
Additional functionality is provided to validate the certificate using OpenSSL to ensure
its authenticity and integrity.

SPDX-FileCopyrightText: 2024 Amilcar do Carmo Lucas <amilcar.lucas@iav.de>

SPDX-License-Identifier: GPL-3.0-or-later
'''

import ssl
import socket
import logging
import os
import sys
from datetime import datetime

try:
    from OpenSSL import crypto
except ImportError:
    print("Error: OpenSSL library not found. Please execute 'pip install pyOpenSSL'")
    sys.exit(1)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_ssl_certificate(host: str, port: int=443, timeout: float=10.0) -> str:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                # Get the certificate in DER format and decode it to PEM
                der_cert = ssock.getpeercert(binary_form=True)
                pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)
                return pem_cert
    except socket.gaierror as e:
        logging.error("Address-related error connecting to server: %s", e)
        raise
    except socket.error as e:
        logging.error("Connection error: %s", e)
        raise

def save_certificate(certificate: str, filename: str) -> None:
    # Save the certificate to a file
    with open(filename, 'w', encoding='utf-8') as cert_file:
        cert_file.write(certificate)
    logging.info("Certificate saved to %s", filename)

def validate_certificate(pem_cert: str, filename: str) -> bool:
    """
    Validate the SSL certificate using OpenSSL.

    Args:
    pem_cert (str): PEM formatted SSL certificate
    filename (str): Output file for validation results

    Returns:
    bool: True if validation successful, False otherwise
    """
    try:
        # Load the certificate
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, pem_cert)

        # Check if the certificate has expired
        if cert.has_expired():
            logging.error("Certificate has expired")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Certificate has expired")
            return False

        # Check if the certificate is still valid based on its not-before and not-after dates
        not_before = cert.get_notBefore().decode('utf-8')
        not_after = cert.get_notAfter().decode('utf-8')

        now = datetime.now()

        # Parse the date string correctly
        not_before_date = datetime.strptime(not_before, "%Y%m%d%H%M%SZ")
        not_after_date = datetime.strptime(not_after, "%Y%m%d%H%M%SZ")

        if now < not_before_date:
            logging.error("Certificate is not yet valid")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Certificate is not yet valid")
            return False

        if now > not_after_date:
            logging.error("Certificate is no longer valid")
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Certificate is no longer valid")
            return False

        # Save the validation result
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("Certificate validated successfully")

        return True

    except ssl.SSLError as e:
        logging.error("Certificate validation failed due to SSLError: %s", str(e))
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"SSLError occurred during validation: {e}")
        return False

def main():
    host = 'autotest.ardupilot.org'
    filename = 'autotest_ardupilot_org.crt'
    http_proxy = os.environ.get('HTTP_PROXY', '')
    https_proxy = os.environ.get('HTTPS_PROXY', '')
    logging.info("HTTP_PROXY: %s", http_proxy)
    logging.info("HTTPS_PROXY: %s", https_proxy)
    try:
        certificate = fetch_ssl_certificate(host)
        save_certificate(certificate, filename)
        # Perform certificate validation
        validation_filename = f"{filename}.validation.txt"
        if validate_certificate(certificate, validation_filename):
            logging.info("Certificate validated successfully. Results saved to %s", validation_filename)
        else:
            logging.error("Certificate validation failed. See %s for details", validation_filename)
    except socket.gaierror as e:
        logging.error("Address-related error connecting to server: %s", e)
        raise
    except socket.error as e:
        logging.error("Connection error: %s", e)
        raise

if __name__ == "__main__":
    main()
