#!/usr/bin/env python
from setuptools import setup

from pip.req import parse_requirements

install_reqs = parse_requirements('requirements.txt', session=False)

setup(name="mypanda-mt-remote",
      version="0.0.1",
      description="MetaTrader remote interface",
      author="Ricky Cook",
      author_email="mt_remote@auto.thatpanda.com",
      url="https://github.com/RickyCook/mt_remote",
      packages=['mt_remote'],
      install_requires=[str(ir.req) for ir in install_reqs],
)
