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

from ryu import cfg
from ryu.base import app_manager
from ryu.lib import hub
from ryu.services.protocols.ovsdb import client
from ryu.services.protocols.ovsdb import event
from ryu.controller import handler
import auth
import ssl


opts = [cfg.StrOpt('address', default='0.0.0.0',
                   help='OVSDB address'),
        cfg.IntOpt('port', default=6632,
                   help='OVSDB port'),
        cfg.StrOpt('mngr-privkey', default=None, help='manager private key'),
        cfg.StrOpt('mngr-cert', default=None, help='manager certificate'),
        cfg.StrOpt('mngr-ca-certs', default=None,
                   help='manager CA Certificated'),
        cfg.BoolOpt('ssl-required', default=False,
                    help='require ssl connections'),
        cfg.BoolOpt('ssl-fingerprint-verify', default=False,
                    help='enable fingerprint only verification')
        ]

cfg.CONF.register_opts(opts, 'ovsdb')


class OVSDB(app_manager.RyuApp):
    _EVENTS = [event.EventNewOVSDBConnection,
               event.EventModifyRequest,
               event.EventReadRequest]

    def __init__(self, *args, **kwargs):
        super(OVSDB, self).__init__(*args, **kwargs)
        self._address = self.CONF.ovsdb.address
        self._port = self.CONF.ovsdb.port
        self._clients = {}

        auth.add_test_cert()

    def _accept(self, server):
        while True:
            # TODO(jkoelker) Whitelist addresses
            sock, client_address = server.accept()
            self.logger.debug('New connection from %s:%s' % client_address)
            t = hub.spawn(self._start_remote, sock, client_address)
            self.threads.append(t)

    def _proxy_event(self, ev):
        system_id = ev.system_id
        client_name = client.RemoteOvsdb.instance_name(system_id)

        if client_name not in self._clients:
            self.logger.info('Unknown remote system_id %s' % system_id)
            return

        return self.send_event(client_name, ev)

    def _start_remote(self, sock, client_address):
        app = client.RemoteOvsdb.factory(sock, client_address)

        if app:
            self._clients[app.name] = app
            app.start()
            ev = event.EventNewOVSDBConnection(app.system_id)
            self.send_event_to_observers(ev)

    def start(self):
        server = hub.listen((self._address, self._port))

        if self.CONF.ovsdb.ssl_required:
            key = self.CONF.ovsdb.mngr_privkey or self.CONF.ctl_privkey
            crt = self.CONF.ovsdb.mngr_cert or self.CONF.ctl_cert

            if not all((key, crt)):
                raise RuntimeError('Key and Cert must be specified if SSL is '
                                   'required')

            if self.CONF.ssl_fingerprint_verify:
                if hub.HUB_TYPE != 'eventlet':
                    raise RuntimeError('Fingerprint Verification only '
                                       'supported with the ryu hub')

                from eventlet.green.OpenSSL import SSL
                context = SSL.Context(SSL.SSLv23_METHOD)
                context.use_certificate_file(crt)
                context.use_privatekey_file(key)

                def verify(conn, cert, errnum, depth, ok):
                    digest = cert.digest('sha256')
                    digest = digest.replace(':', '')
                    digest = digest.replace(' ', '')
                    digest = digest.upper()
                    return auth.is_authorized(digest)

                opts = (SSL.VERIFY_PEER | SSL.VERIFY_FAIL_IF_NO_PEER_CERT |
                        SSL.VERIFY_CLIENT_ONCE)

                context.set_verify(opts, verify)

                self._server = SSL.Connection(context, server)
                self._server.set_accept_state()

            else:
                ca_certs = self.CONF.ovsdb.mngr_ca_certs or self.CONF.ca_certs

                if not ca_certs:
                    raise RuntimeError('CA certificates required for full '
                                       'validation')

                self._server = ssl.wrap_socket(server,
                                               cert_reqs=ssl.CERT_REQUIRED,
                                               keyfile=key,
                                               certfile=crt,
                                               server_side=True)

        self.logger.info('Listening on %s:%s for clients' % (self._address,
                                                             self._port))
        t = hub.spawn(self._accept, self._server)
        super(OVSDB, self).start()
        return t

    def stop(self):
        clients = self._clients.values()

        for client in clients:
            client.stop()

        super(OVSDB, self).stop()

    @handler.set_ev_cls(event.EventModifyRequest)
    def modify_request_handler(self, ev):

        system_id = ev.system_id
        client_name = client.RemoteOvsdb.instance_name(system_id)
        remote = self._clients.get(client_name)

        if not remote:
            self.logger.info('Unknown remote system_id %s' % system_id)
            return

        return remote.modify_request_handler(ev)

    @handler.set_ev_cls(event.EventReadRequest)
    def read_request_handler(self, ev):
        system_id = ev.system_id
        client_name = client.RemoteOvsdb.instance_name(system_id)
        remote = self._clients.get(client_name)

        if not remote:
            self.logger.info('Unknown remote system_id %s' % system_id)
            return

        return remote.read_request_handler(ev)

    @handler.set_ev_cls(event.EventReadFuncRequest)
    def read_request_func_handler(self, ev):
        system_id = ev.system_id
        client_name = client.RemoteOvsdb.instance_name(system_id)
        remote = self._clients.get(client_name)

        if not remote:
            self.logger.info('Unknown remote system_id %s' % system_id)
            return

        return remote.read_request_func_handler(ev)

    @handler.set_ev_cls(event.EventRegisterClientCertificateRequest)
    def register_client_cert_request_handler(self, ev):
        message = auth.add_authorized_client(ev.address, ev.cert)
        rep = event.EventRegisterClientCertificateResponse(message)
        self.reply_to_request(ev, rep)
