"""Connect only to an address verified as loopback, without a DNS re-resolution."""
import http.client
import ipaddress
import socket
from urllib.request import HTTPHandler


class LoopbackConnection(http.client.HTTPConnection):
    def connect(self):
        last_error = None
        for family, kind, proto, _, address in socket.getaddrinfo(self.host, self.port, type=socket.SOCK_STREAM):
            try:
                if not ipaddress.ip_address(address[0]).is_loopback: continue
                sock = socket.socket(family, kind, proto)
                try:
                    sock.settimeout(self.timeout)
                    sock.connect(address)
                except OSError:
                    sock.close()
                    raise
                self.sock = sock
                return
            except (OSError, ValueError) as exc:
                last_error = exc
        raise OSError('No reachable loopback address') from last_error


class LoopbackHTTPHandler(HTTPHandler):
    def http_open(self, request):
        return self.do_open(LoopbackConnection, request)
