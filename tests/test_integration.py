import os
import re
import json
import signal
import socket
import SocketServer as socketserver
import subprocess
import threading

from time import sleep

from unittest import TestCase
from simple_tcp_json_server import SimpleTCPJsonServer

def strip_volatile(message):
    """
    Strip volatile parts (PID, datetime) from a logging message.
    """

    volatile = (
        (socket.gethostname(), 'HOST'),
        (r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}-\d{4}', 'DATE'),
    )

    for regexp, replacement in volatile:
        message = re.sub(regexp, replacement, message)

    return message


class SyslogIntegrationTestCase(TestCase):
    def setUp(self):
        self.old_env = os.environ.copy()


    def tearDown(self):
        os.environ = self.old_env


    def test_logging(self):
        messages = []

        class SyslogHandler(socketserver.BaseRequestHandler):
            def handle(self):
                messages.append(self.request[0].strip().decode())

        server = socketserver.UDPServer(('0.0.0.0', 0), SyslogHandler)
        try:
            threading.Thread(target=server.serve_forever).start()

            os.environ['SYSLOG_SERVER'] = server.server_address[0]
            os.environ['SYSLOG_PORT'] = str(server.server_address[1])
            os.environ['SYSLOG_PROTO'] = 'udp'

            mydir = os.path.dirname(__file__)

            supervisor = subprocess.Popen(
                ['supervisord', '-c', os.path.join(mydir, 'supervisord.conf')],
                env=os.environ,
            )
            try:
                sleep(3)

                print subprocess.check_output(['supervisorctl', 'status'])

                pid = subprocess.check_output(
                    ['supervisorctl', 'pid', 'messages']
                ).strip()

                sleep(6)

                self.assertEqual(
                    list(map(strip_volatile, messages)),
                    ['<14>DATE HOST messages[{pid}]: Test {i} \n\x00'.format(pid=pid, i=i) for i in range(4)]
                )
            finally:
                os.kill(supervisor.pid, signal.SIGKILL)

        finally:
            server.shutdown()


class TCPJsonIntegrationTestCase(TestCase):
    def setUp(self):
        self.old_env = os.environ.copy()


    def tearDown(self):
        os.environ = self.old_env


    def test_logging(self):
        messages = []

        class SimpleTCPJsonServerHandler(socketserver.BaseRequestHandler):
            def handle(self):
                data = json.loads(self.request.recv(1024).strip())
                messages.append(data)


        server = SimpleTCPJsonServer(('127.0.0.1', 22552), SimpleTCPJsonServerHandler)
        try:
            threading.Thread(target=server.serve_forever).start()

            os.environ['SUPERVISOR_LOG_TYPE'] = 'tcp_json'
            os.environ['JSON_SERVER'] = server.server_address[0]
            os.environ['JSON_PORT'] = str(server.server_address[1])

            mydir = os.path.dirname(__file__)

            supervisor = subprocess.Popen(
                ['supervisord', '-c', os.path.join(mydir, 'supervisord.conf')],
                env=os.environ,
            )
            try:
                sleep(3)

                self.assertEqual(len(messages), 1, messages)
                self.assertEqual(messages[0]["hostname"], socket.gethostname(), messages)
                self.assertEqual(messages[0]["log"], "Test 0\n", messages)
            finally:
                os.kill(supervisor.pid, signal.SIGKILL)

        finally:
            server.shutdown()
