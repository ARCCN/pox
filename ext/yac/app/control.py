__author__ = 'Eugene Chemeritskiy'


import multiprocessing
import BaseHTTPServer
import urlparse
import json
import os


class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.path = self.path.split('?')[0][1:]
        if not self.path:
            self.path = 'index.html'
        base = self.server.web_gui.base
        filename = os.path.join(base, self.path)
        if not os.path.exists(filename):
            filename = os.path.join(base, 'dummy.html')
        with open(filename, "r") as f:
            content = f.read()
            self.wfile.write(content)

    def do_POST(self):
        query_string = self.rfile.read(int(self.headers['Content-Length']))
        query = json.loads(query_string)
        print("sending query", str(query))

        web_gui = self.server.web_gui
        web_gui.ctl_conn[1].send(query)
        reply = web_gui.srv_conn[0].recv()

        print("got reply", str(reply))
        r_data = json.dumps(reply)

        self.send_response(200)
        self.send_header("Content-type", "text")
        self.send_header("Content-length", str(len(r_data)))
        self.end_headers()
        self.wfile.write(r_data)


def start_server(web_gui):
    httpd = BaseHTTPServer.HTTPServer((web_gui.host, web_gui.port), Handler)
    httpd.web_gui = web_gui
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()


class WebGUI(object):
    def __init__(self, host, port, base):
        self.base = os.path.abspath(base)
        self.host = host
        self.port = port

    def start(self):
        self.ctl_conn = multiprocessing.Pipe(False)
        self.srv_conn = multiprocessing.Pipe(False)
        subprocess = multiprocessing.Process(target=start_server, args=(self,))
        subprocess.start()


if __name__ == "__main__":

    HOST = '127.0.0.1'
    PORT = 8080
    BASE = './html'

    # start WebGUI inside of the parent process
    # HTTP server should answer GET requests
    web_gui = WebGUI(HOST, PORT, BASE)
    start_server(web_gui)