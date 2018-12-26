import gevent
from kubernetes import client, config
from kubernetes.stream import stream


class PodWsshBridge(object):
    def __init__(self, websocket, namespace, pod_name):
        self._websocket = websocket
        self.cv1 = client.CoreV1Api()
        self._ssh = stream(self.cv1.connect_get_namespaced_pod_exec, pod_name, namespace,
                     command="sh",
                     stderr=True, stdin=True,
                     stdout=True, tty=True,
                     _preload_content=False)
        self._tasks = []

    def _forward_inbound(self, channel):
        """ Forward inbound traffic (websockets -> ssh) """
        try:
            while True:
                data = self._websocket.receive()
                try:
                    channel.write_stdin(data)
                except Exception as e:
                    print(e)
        except Exception as e:
            print(e)

    def _forward_outbound(self, channel):
        """ Forward outbound traffic (ssh -> websockets) """
        try:
            while True:
                data = channel.read_stdout()
                self._websocket.send(data)
        except Exception as e:
            print(e)

    def _bridge(self, channel):
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

    def shell(self):
        channel = self._ssh
        self._bridge(channel)
        channel.close()