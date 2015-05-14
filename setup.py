from setuptools import setup, find_packages

with open('requirements.txt') as requirements:
    setup(
        name='supervisor-remote-logging',
        version='0.0.3',
        description='Stream supervisord logs various remote endpoints',
        author='New Relic Site Engineering Team',
        url='https://github.com/newrelic/supervisor-remote-logging',
        license='MIT License',
        long_description=open('README.md').read(),

        packages=find_packages(exclude=['tests']),
        package_data={
            'forklift': [
                'README.md',
                'requirements.txt',
            ],
        },
        entry_points={
            'console_scripts': [
                'supervisor_remote_logging = supervisor_remote_logging:main',
            ],
        },

        install_requires=requirements.read().splitlines(),

        test_suite='tests',
    )
