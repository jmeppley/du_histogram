try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

DESCRIPTION = "Simply ASCII histogram of du output"
LONG_DESCRIPTION = open('README.md').read()
NAME = "du_histogram"
AUTHOR = "John Eppley"
AUTHOR_EMAIL = "jmeppley@gmail.com"
MAINTAINER = "John Eppley"
MAINTAINER_EMAIL = "jmeppley@gmail.com"
URL = 'http://github.com/jmeppley/du_histogram'
DOWNLOAD_URL = 'http://github.com/jmeppley/du_histogram'
LICENSE = 'Apache'
VERSION = '0.9.3'

setup(name=NAME,
      version=VERSION,
      description=DESCRIPTION,
      long_description=LONG_DESCRIPTION,
      author=AUTHOR,
      author_email=AUTHOR_EMAIL,
      maintainer=MAINTAINER,
      maintainer_email=MAINTAINER_EMAIL,
      url=URL,
      download_url=DOWNLOAD_URL,
      license=LICENSE,
      scripts=['duhist.py',],
      install_requires=('docopt'),
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: GPL License',
          'Natural Language :: English',
          'Programming Language :: Python :: 2.7'],
      )
