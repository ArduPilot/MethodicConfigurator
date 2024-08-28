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

#import OpenSSL
import ssl
import socket
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_ssl_certificate(host, port=443, timeout=10):
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                # Get the certificate in DER format and decode it to PEM
                der_cert = ssock.getpeercert(binary_form=True)
                pem_cert = ssl.DER_cert_to_PEM_cert(der_cert)
                return pem_cert
    except socket.gaierror as e:
        logging.error(f"Address-related error connecting to server: {e}")
        raise
    except socket.error as e:
        logging.error(f"Connection error: {e}")
        raise

def save_certificate(certificate, filename):
    # Save the certificate to a file
    with open(filename, 'w') as cert_file:
        cert_file.write(certificate)
    logging.info(f"Certificate saved to {filename}")

def main():
    host = 'autotest.ardupilot.org'
    filename = 'autotest_ardupilot_org.crt'
    logging.info(os.environ['HTTP_PROXY'])
    logging.info(os.environ['HTTPS_PROXY'])
    try:
        certificate = fetch_ssl_certificate(host)
        save_certificate(certificate, filename)
    except Exception as e:
        logging.error(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
