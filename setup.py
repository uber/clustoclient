from setuptools import setup

setup(name='clustoclient',
      version='0.3.3',
      py_modules=['clustohttp'],
      scripts=['clusto-template', 'clusto-get-from-pools'],
      install_requires=['jinja2', 'IPy'])
