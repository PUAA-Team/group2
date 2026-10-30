"""证书联调临时CONNECT转发；只允许官方ACME接口，保持端到端TLS。"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import socket
import time


ALLOWED = {"acme-v02.api.letsencrypt.org:443", "acme-staging-v02.api.letsencrypt.org:443"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_CONNECT(self):
        if self.path not in ALLOWED:
            self.send_error(403)
            return
        host, port = self.path.rsplit(":", 1)
        try:
            remote = socket.create_connection((host, int(port)), timeout=20)
        except OSError:
            self.send_error(502)
            return
        with remote:
            self.send_response(200, "Connection established")
            self.end_headers()
            self.wfile.flush()
            self.close_connection = True
            deadline = time.monotonic() + 180
            connections = (self.connection, remote)
            try:
                while time.monotonic() < deadline:
                    readable, _, _ = select.select(connections, [], [], 5)
                    for source in readable:
                        content = source.recv(65536)
                        if not content:
                            return
                        destination = remote if source is self.connection else self.connection
                        destination.sendall(content)
                        deadline = time.monotonic() + 180
            except (OSError, ConnectionError):
                return


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.root.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    (arguments.root / "process.json").write_text(json.dumps({"pid": os.getpid(), "port": server.server_port}))
    server.serve_forever()
