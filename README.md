[![Archived header](https://github.com/newrelic/open-source-office/raw/master/examples/categories/images/Archived.png)](https://github.com/newrelic/open-source-office/blob/master/examples/categories/index.md#archived)

![Language: Python](https://img.shields.io/badge/language-Python-brightgreen.svg)
[![License: MIT](https://img.shields.io/badge/license-MIT-red.svg)](LICENSE)


supervisor-remote-logging
=========================

This is a [supervisord](http://supervisord.org/) plugin that allows us to stream logs in various format to remote destination.


## Why should I use it?

Inside docker environment, it is best to ship your logs to a remote location because Docker does not do a good job managing its own log files.

If you use supervisord to run your process inside a Docker container, you may find this plugin handy.


## Installation

```
cd /path/to/supervisor-remote-logging
pip install -e .
```

Add the plugin as an event listener:

```
[eventlistener:logging]
command = supervisor_remote_logging
events = PROCESS_LOG
```

## Configurations

* `SUPERVISOR_LOG_TYPE` There can only be 3 options: syslog, syslog_json, tcp_json.

* `DOCKER_CID` Pass Docker container id explicitly.

* `SUPERVISOR_PROCESS_NAME` Pass processname explicitly.


## Log Formats

**1. Syslog** `SUPERVISOR_LOG_TYPE=syslog`

Syslog remote endpoint is configured with the following environment variables:

* `SYSLOG_SERVER`
* `SYSLOG_PORT`
* `SYSLOG_PROTO`


**2. Syslog JSON** `SUPERVISOR_LOG_TYPE=syslog_json`

Syslog JSON remote endpoint is configured similarly to Syslog endpoint.


**3. TCP JSON** `SUPERVISOR_LOG_TYPE=tcp_json`

TCP JSON remote endpoint is configured with the following environment variables:

* `JSON_SERVER`
* `JSON_PORT`

Example JSON payload:
```
{
    "hostname":"localhost",
    "time": "2014-12-11T03:02:45.2112+00:00",
    "log":"ERROR: unable to connect to localhost:3306",
    "pid": 123,
    "container_id": "6b7ec98af6d7",
    "stream": "stdout",
    "image_tag": "heka/latest",
    "service_env": "staging",
    "service_name": "be_site",
}
```


## Contribution Guidelines

You are welcome to send pull requests to us - however, by doing so you agree that you are granting New Relic a non-exclusive, non-revokable, no-cost license to use the code, algorithms, patents, and ideas in that code in our products if we so choose. You also agree the code is provided as-is and you provide no warranties as to its fitness or correctness for any purpose.


## Running Tests for Contributors
```
# Install nose module.
pip install nose

# Run tests.
nosetests
```
