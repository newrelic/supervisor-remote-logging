import os
import json
import datetime
import logging
from unittest import TestCase
from supervisor_remote_logging import SyslogFormatter, DockerJsonFormatter, SyslogDockerJsonFormatter


class SupervisorLoggingDateFormatTestCase(TestCase):
    def test_default_date_format(self):
        """
        Test default date format.
        """
        date = datetime.datetime(2000, 1, 1, 1, 0, 0)
        date_format = SyslogFormatter().date_format()
        self.assertEqual(date.strftime(date_format), '2000-01-01T01:00:00')

    def test_custom_date_format(self):
        """
        Test custom date format.
        """
        date = datetime.datetime(2000, 1, 1, 1, 0, 0)
        os.environ['DATE_FORMAT'] = '%b %d %H:%M:%S'
        date_format = SyslogFormatter().date_format()
        self.assertEqual(date.strftime(date_format), 'Jan 01 01:00:00')
        os.environ['DATE_FORMAT'] = SyslogFormatter.DEFAULT_DATE_FORMAT


class DockerJsonFormatterTestCase(TestCase):
    def test_json_format(self):
        record = logging.LogRecord(
            name='foo',
            level=logging.INFO,
            pathname=None,
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        formatted    = DockerJsonFormatter().format(record)
        deserialized = json.loads(formatted)

        self.assertEqual(deserialized['hostname'], DockerJsonFormatter.HOSTNAME)
        self.assertEqual(deserialized['log'], record.msg)
        self.assertTrue(deserialized['time'] != None)


class SyslogDockerJsonFormatterTestCase(TestCase):
    def test_format(self):
        record = logging.LogRecord(
            name='foo',
            level=logging.INFO,
            pathname=None,
            lineno=0,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        message = SyslogDockerJsonFormatter().format(record)

        syslog_message, json_message = message.split(']: ')

        syslog_parts = message.split(' ')
        json_data    = json.loads(json_message)

        self.assertEqual(syslog_parts[0], json_data['time'])
        self.assertEqual(syslog_parts[1], json_data['hostname'])
