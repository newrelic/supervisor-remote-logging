#!/usr/bin/env python

from __future__ import print_function

import logging
import logging.handlers
import os
import os.path
import re
import socket
import sys
import json
import time
import datetime
import docker

# http://docs.python.org/library/logging.html#logrecord-attributes
RESERVED_ATTRS = (
    'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
    'funcName', 'levelname', 'levelno', 'lineno', 'module',
    'msecs', 'message', 'msg', 'name', 'pathname', 'process',
    'processName', 'relativeCreated', 'thread', 'threadName'
)

RESERVED_ATTR_HASH = dict(zip(RESERVED_ATTRS, RESERVED_ATTRS))


class FormatterMixin(object):
    HOSTNAME = re.sub(r':\d+$', '', os.environ.get('SITE_DOMAIN', socket.gethostname()))
    DEFAULT_DATE_FORMAT = '%Y-%m-%dT%H:%M:%S%z'
    DEFAULT_MESSAGE_FORMAT = '%(asctime)s %(hostname)s %(name)s[%(process)d]: %(message)s'


    def message_format(self):
        """
        Use user defined message format via
        os.environ['MESSAGE_FORMAT'] or
        DEFAULT_MESSAGE_FORMAT as default.
        """
        fmt = os.environ.get('MESSAGE_FORMAT', self.DEFAULT_MESSAGE_FORMAT)

        return fmt.replace('%(hostname)s', self.HOSTNAME)  # Accepts hostname in the form of %(hostname)s


    def date_format(self):
        """
        Use user defined message format via
        os.environ['DATE_FORMAT'] or
        DEFAULT_DATE_FORMAT as default.
        """
        return os.environ.get('DATE_FORMAT', self.DEFAULT_DATE_FORMAT)


class DockerJsonFormatter(logging.Formatter, FormatterMixin):
    CONTAINER_ID   = ""
    CONTAINER_JSON = {}
    IMAGE_ID       = ""
    IMAGE_TAG      = ""

    def __init__(self, *args, **kwargs):
        """
        :param json_default: a function for encoding non-standard objects
            as outlined in http://docs.python.org/2/library/json.html
        :param json_encoder: optional custom encoder
        """
        self.json_default = kwargs.pop("json_default", None)
        self.json_encoder = kwargs.pop("json_encoder", None)

        kwargs['fmt'] = self.message_format()
        kwargs['datefmt'] = self.date_format()

        super(DockerJsonFormatter, self).__init__(*args, **kwargs)

        if not self.json_encoder and not self.json_default:
            def _default_json_handler(obj):
                '''Prints dates in ISO format'''
                if isinstance(obj, datetime.datetime):
                    return obj.strftime(self.datefmt or '%Y-%m-%dT%H:%M')
                elif isinstance(obj, datetime.date):
                    return obj.strftime('%Y-%m-%d')
                elif isinstance(obj, datetime.time):
                    return obj.strftime('%H:%M')
                return str(obj)
            self.json_default = _default_json_handler

        self._required_fields = self.parse()
        self._skip_fields = dict(zip(self._required_fields, self._required_fields))
        self._skip_fields.update(RESERVED_ATTR_HASH)


    def parse(self):
        """Parses format string looking for substitutions"""
        standard_formatters = re.compile(r'\((.+?)\)', re.IGNORECASE)
        return standard_formatters.findall(self._fmt)


    def format(self, record):
        # Log Format
        # {
        #     "hostname":"localhost",
        #     "time": "2014-12-11T03:02:45.2112+00:00",
        #     "log":"ERROR: unable to connect to localhost:3306",
        #     "pid": 123,
        #     "container_id": "6b7ec98af6d7",
        #     "stream": "stdout",
        #     "image_tag": "heka/latest",
        #     "service_env": "staging",
        #     "service_name": "be_site",
        # }

        record.message = record.getMessage()

        log_record = {}
        log_record['hostname']     = self.HOSTNAME
        log_record['stream']       = 'stdout'
        log_record['pid']          = record.process

        if record.processName:
            log_record['programname'] = record.processName

        if self.CONTAINER_ID:
            log_record['container_id'] = self.CONTAINER_ID

        if self.IMAGE_ID:
            log_record['image_id'] = self.IMAGE_ID

        if self.IMAGE_TAG:
            log_record['image_tag'] = self.IMAGE_TAG

        if 'asctime' in self._required_fields:
            log_record['time'] = self.formatTime(record, self.datefmt)

        if record.message:
            log_record['log'] = record.message

        service_env = os.environ.get('SERVICE_ENV', None)
        if service_env:
            log_record['service_env'] = service_env

        service_name = os.environ.get('SERVICE_NAME', None)
        if service_name:
            log_record['service_name'] = service_name

        return json.dumps(log_record, default=self.json_default, cls=self.json_encoder) + '\n'


class SyslogDockerJsonFormatter(logging.Formatter, FormatterMixin):
    def __init__(self):
        super(SyslogDockerJsonFormatter, self).__init__(fmt=self.message_format(), datefmt=self.date_format())

    def format(self, record):
        json_message = DockerJsonFormatter().format(record)
        json_data    = json.loads(json_message)

        syslog_message = self.message_format()
        syslog_message = syslog_message.replace('%(asctime)s', json_data['time'])
        syslog_message = syslog_message.replace('%(name)s', record.name)
        syslog_message = syslog_message.replace('%(process)d', str(record.process))
        syslog_message = syslog_message.replace('%(message)s', json_message)

        if record.processName:
            syslog_message = syslog_message.replace('%(processName)s', str(record.processName))

        return syslog_message + '\n'


class SyslogFormatter(logging.Formatter, FormatterMixin):
    def __init__(self):
        super(SyslogFormatter, self).__init__(fmt=self.message_format(), datefmt=self.date_format())


    def format(self, record):
        message = super(SyslogFormatter, self).format(record)
        return message.replace('\n', ' ') + '\n'


class TcpJsonHandler(object):
    def __init__(self, address):
        self.retry_interval = 0
        self.address        = address
        self.server         = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            self.server.connect(self.address)
        except socket.error:
            self.reconnect_after_backing_off()
        except socket.gaierror:
            self.reconnect_after_backing_off()

    def reconnect(self):
        self.server.close()
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.connect(self.address)

    def reconnect_after_backing_off(self):
        print("WARNING: Failed to connect to {}. Reconnecting...".format(self.address), file=sys.stderr)
        time.sleep(2 ** self.backoff_interval())
        self.reconnect()

    def backoff_interval(self):
        current = self.retry_interval
        self.retry_interval += 1

        if self.retry_interval > 1800:
            self.retry_interval = 0

        return current

    def setFormatter(self, formatter):
        self.formatter = formatter

    def handle(self, record):
        try:
            self.server.sendall(self.formatter.format(record))
        except socket.error:
            self.reconnect_after_backing_off()
        except socket.gaierror:
            self.reconnect_after_backing_off()


class SysLogHandler(logging.handlers.SysLogHandler):
    """
    A SysLogHandler not appending NUL character to messages
    """
    append_nul = False


def get_headers(line):
    """
    Parse Supervisor message headers.
    """

    return dict([x.split(':') for x in line.split()])


def eventdata(payload):
    """
    Parse a Supervisor event.
    """

    headerinfo, data = payload.split('\n', 1)
    headers = get_headers(headerinfo)
    return headers, data


def supervisor_events(stdin, stdout):
    """
    An event stream from Supervisor.
    """

    while True:
        stdout.write('READY\n')
        stdout.flush()

        line = stdin.readline()
        headers = get_headers(line)

        payload = stdin.read(int(headers['len']))
        event_headers, event_data = eventdata(payload)

        yield event_headers, event_data

        stdout.write('RESULT 2\nOK')
        stdout.flush()


def new_syslog_handler():
    host     = os.environ.get('SYSLOG_SERVER', '127.0.0.1')
    port     = int(os.environ.get('SYSLOG_PORT', '514'))
    proto    = os.environ.get('SYSLOG_PROTO', 'udp')
    socktype = socket.SOCK_DGRAM if proto == 'udp' else socket.SOCK_STREAM

    return SysLogHandler(
        address=(host, port),
        socktype=socktype,
    )


def new_tcp_json_handler():
    host = os.environ.get('JSON_SERVER', '127.0.0.1')
    port = int(os.environ.get('JSON_PORT', '22552'))

    return TcpJsonHandler((host, port))


def new_handler(log_type='syslog'):
    handler = None

    if log_type == 'syslog_json' or log_type == 'syslog':
        handler = new_syslog_handler()
    elif log_type == 'tcp_json':
        handler = new_tcp_json_handler()

    if log_type == 'tcp_json':
        handler.setFormatter(DockerJsonFormatter())
    elif log_type == 'syslog_json':
        handler.setFormatter(SyslogDockerJsonFormatter())
    elif log_type == 'syslog':
        handler.setFormatter(SyslogFormatter())

    return handler


def main():
    '''
    3 different log type:
    * syslog
    * syslog_json
    * tcp_json
    '''
    log_type = os.environ.get('SUPERVISOR_LOG_TYPE', 'syslog')
    handler  = new_handler(log_type)

    if handler:
        docker_client = docker.Client(base_url="tcp://{0}:2375".format(DockerJsonFormatter.HOSTNAME), timeout=10)

        docker_cid = os.environ.get('DOCKER_CID', '')

        if docker_cid:
            DockerJsonFormatter.CONTAINER_ID   = docker_cid
            DockerJsonFormatter.CONTAINER_JSON = docker_client.inspect_container(DockerJsonFormatter.CONTAINER_ID)
            DockerJsonFormatter.IMAGE_ID       = DockerJsonFormatter.CONTAINER_JSON['Image']

            images = docker_client.images()
            for image in images:
                if image['Id'] == DockerJsonFormatter.IMAGE_ID:
                    image_repo_tags = image['RepoTags']
                    if len(image_repo_tags) > 0:
                        DockerJsonFormatter.IMAGE_TAG = image_repo_tags[0]

        for event_headers, event_data in supervisor_events(sys.stdin, sys.stdout):
            event = logging.LogRecord(
                name=event_headers['processname'],
                level=logging.INFO,
                pathname=None,
                lineno=0,
                msg=event_data,
                args=(),
                exc_info=None,
            )
            event.process = int(event_headers['pid'])
            event.processName = event_headers['processname'] or os.getenv('SUPERVISOR_PROCESS_NAME', 'unknown')

            handler.handle(event)


if __name__ == '__main__':
    main()
