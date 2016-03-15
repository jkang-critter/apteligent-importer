from setuptools import setup

DESCRIPTION = "Import Apteligent data to graphite"


def readme():
    with open('README.rst') as f:
            return f.read()


setup(
    name='apteligentimporter',
    description=DESCRIPTION,
    long_description=readme(),
    author="Paul Frederiks",
    author_email="pfrederiks@ebay.com",
    version='0.1.1',
    classifiers=[
        'Programming Language :: Python :: 2.7'
        ],
    keywords='graphite apteligent crittercism mobile',
    packages=['apteligent', 'tographite', 'libecgnoc'],
    scripts=[
        'scripts/dailyjobs.py',
        'scripts/livestats.py',
        'scripts/servicestats.py',
        'scripts/groupedby.py'
        ],
    license='TBD',
    install_requires=[
        'requests>=2.7.0',
        'futures>=3.0.3'
        ]
)
