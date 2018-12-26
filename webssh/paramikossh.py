import gevent
from gevent.socket import wait_read, wait_write
from gevent.select import select
from gevent.event import Event

import paramiko
from paramiko import PasswordRequiredException
from paramiko.dsskey import DSSKey
from paramiko.rsakey import RSAKey
from paramiko.ssh_exception import SSHException
import socket
import json

class WSSHBridge(object):
    def __init__(self, websocket):
        self._websocket = websocket
        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(
            paramiko.AutoAddPolicy())
        self._tasks = []

    def _load_private_key(self, private_key):
        try:
            key = paramiko.RSAKey.from_private_key_file(private_key)
        except PasswordRequiredException as e:
           print(e)
        return key
    def open(self, hostname, port=22, username=None, password=None,
                    private_key=None, key_passphrase=None,
                    allow_agent=False, timeout=None):
        try:
            pkey = None
            if private_key:
                pkey = self._load_private_key(private_key)
                print(pkey)
            self._ssh.connect(
                hostname=hostname,
                port=port,
                username=username,
                password=password,
                pkey=pkey,
                timeout=timeout,
                allow_agent=allow_agent,
                look_for_keys=False)
        except socket.gaierror as e:
            self._websocket.send(json.dumps({'error':
                'Could not resolve hostname {0}: {1}'.format(
                    hostname, e.args[1])}))
            raise
        except Exception as e:
            self._websocket.send(json.dumps({'error': e.message or str(e)}))
            raise

    def _forward_inbound(self, channel):
        """ Forward inbound traffic (websockets -> ssh) """
        try:
            while True:
                data = self._websocket.receive()
                try:
                    if 'resize' in data:
                        channel.resize_pty(
                            data['resize'].get('width', 80),
                            data['resize'].get('height', 24))
                    if 'data' in data:
                        channel.send(data['data'])
                    channel.send(data)
                except Exception as e:
                    print(e)
        except Exception as e:
            print(e)
    def _forward_outbound(self, channel):
        """ Forward outbound traffic (ssh -> websockets) """
        try:
            while True:
                wait_read(channel.fileno())
                data = channel.recv(1024)
                self._websocket.send(data)
        except Exception as e:
            print(e)
    def _bridge(self, channel):
        """ Full-duplex bridge between a websocket and a SSH channel """
        channel.setblocking(False)
        channel.settimeout(0.0)
        self._tasks = [
            gevent.spawn(self._forward_inbound, channel),
            gevent.spawn(self._forward_outbound, channel)
        ]
        gevent.joinall(self._tasks)

    def close(self):
        """ Terminate a bridge session """
        gevent.killall(self._tasks, block=True)
        self._tasks = []
        self._ssh.close()

    def execute(self, command, term='xterm'):
        transport = self._ssh.get_transport()
        channel = transport.open_session()
        channel.get_pty(term)
        channel.exec_command(command)
        self._bridge(channel)
        channel.close()

    def shell(self, term='xterm'):
        channel = self._ssh.invoke_shell(term)
        self._bridge(channel)
        channel.close()