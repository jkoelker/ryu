# Copyright (c) 2014 Rackspace Hosting
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from Crypto.PublicKey import RSA
import hashlib

_authorized_certificates = {}


def is_authorized(digest):
    return digest in _authorized_certificates
        digest = hashlib.sha256(cert).hexdigest()
        return digest in _authorized_certificates

    return False


def add_authorized_client(address, cert):
    key = RSA.importKey(cert)
    der = key.publickey().exportKey('DER')
    digest = hashlib.sha256(der).hexdigest()
    _authorized_certificates[digest] = (address, cert)
    return 'Added certificate to allowed clients'


def convert_pem_to_der(cert):
    key = RSA.importKey(open('privatekey.pem').read())
    der = key.publickey().exportKey('DER')


def add_test_cert():
    cert = open('/etc/openvswitch/sc-privkey.pem').read()
    add_authorized_client('127.0.0.1', cert)
