import sys
from setuptools import setup

AUTHOR = "Paul Frederiks"
EMAIL = "pfrederiks@ebay.com"
DESCRIPTION = "Import Apteligent data to graphite"


def readme():
    """Return the README.rst file to include as long description"""
    with open('README.rst') as f:
        return f.read()


def requirements():
    """Return different requirements depending on python version"""
    install_requires = ['requests>=2.7.0']
    v = sys.version_info
    if v.major == 2:
        # Install backport of concurrent.futures fo python 2
        install_requires.append('futures>=3.0.5')
        # Install future which is a compatibility layer for python 3 code
        # on python 2 and should not be confused with futures...
        install_requires.append('future>=0.15.2')
        if v.minor == 7 and v.micro < 9:
            # python requests regards SSL of python < 2.7.9 as insecure
            # It's optional security requirements install pyOpenSSL and
            # more as an alernative
            install_requires.append('requests[security]>=2.7.0')

    return install_requires


setup(
    name='apteligentimporter',
    description=DESCRIPTION,
    long_description=readme(),
    author=AUTHOR,
    author_email=EMAIL,
    maintainer=AUTHOR,
    maintainer_email=EMAIL,
    url='https://github.com/pfrederiks/apteligent-importer',
    version='1.0.5',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Topic :: System :: Monitoring'
        ],
    keywords='graphite apteligent crittercism mobile',
    packages=['apteligent', 'tographite', 'libecgnoc'],
    scripts=[
        'scripts/dailyjobs.py',
        'scripts/livestats.py',
        'scripts/servicestats.py',
        'scripts/groupedby.py'
        ],
    license='MIT',
    install_requires=requirements()
    )
