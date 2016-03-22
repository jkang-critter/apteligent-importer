from setuptools import setup

AUTHOR = "Paul Frederiks"
EMAIL = "pfrederiks@ebay.com"
DESCRIPTION = "Import Apteligent data to graphite"


def readme():
    with open('README.rst') as f:
        return f.read()


setup(
    name='apteligentimporter',
    description=DESCRIPTION,
    long_description=readme(),
    author=AUTHOR,
    author_email=EMAIL,
    maintainer=AUTHOR,
    maintainer_email=EMAIL,
    version='0.4',
    classifiers=[
        'Programming Language :: Python :: 2.7'
        ],
    keywords='graphite apteligent crittercism mobile',
    packages=['apteligent', 'tographite', 'libecgnoc'],
    scripts=[
        'scripts/dailyjobs.py',
        'scripts/livestats.py',
        'scripts/servicestats.py',
        'scripts/groupedby.py',
        'scripts/pingdom.py'
        ],
    license='TBD',
    install_requires=[
        'requests>=2.7.0',
        'futures>=3.0.3'
        ]
)
