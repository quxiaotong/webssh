from gevent import monkey
monkey.patch_all()

from flask import Flask, request, abort, render_template
from werkzeug.exceptions import BadRequest
import gevent
import sys
import os

sys.path.append(os.getcwd())

from paramikossh import *

app = Flask(__name__)


@app.route('/wssh/<hostname>')
def connect(hostname):
    hostip = request.url.split("/")[-1]
    print(hostip)
    bridge = WSSHBridge(request.environ['wsgi.websocket'])
    try:
        bridge.open(
            hostname=hostip,
            private_key="/root/.ssh/id_rsa")
    except Exception as e:
        print(e)
        request.environ['wsgi.websocket'].close()

    # Launch a shell on the remote server and bridge the connection
    # This won't return as long as the session is alive
    #bridge.shell()

    # Alternatively, you can run a command on the remote server
    bridge.shell()

    # We have to manually close the websocket and return an empty response,
    # otherwise flask will complain about not returning a response and will
    # throw a 500 at our websocket client
    request.environ['wsgi.websocket'].close()
    print('用户断开连接.....')

if __name__ == '__main__':
    from gevent.pywsgi import WSGIServer
    from geventwebsocket.handler import WebSocketHandler

    app.debug = True
    http_server = WSGIServer(('0.0.0.0', 33333), app,
        log=None,
        handler_class=WebSocketHandler)
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        pass
