#! /usr/bin/env python2.7
try:
    from setuptools import setup, find_packages
except ImportError as e:
    import ez_setup
    ez_setup.use_setuptools()
finally:
    from setuptools import setup, find_packages

setup(name="ircdd",
      version="alpha",
      description="Distributed IRC Daemon",
      url="github.com/kzvezdarov/ircdd",
      license="GPL v3.0 or later",
      install_requires=["twisted", "pyyaml", "pynsq==0.6.4",
                        "tornado", "requests", "rethinkdb"],
      setup_requires=["flake8", "nose", "mock", "responses",
                        "testfixtures"],
      packages=find_packages(),
      scripts=["bin/ircdd.sh", ],
      test_suite="nosetests",
      )
