import setuptools

setuptools.setup(
     name='logpool',
     version='1.00',
     packages = setuptools.find_packages(),
     author="Gustavo Schwarz",
     author_email="gustavo.b.schwarz@gmail.com",
     description="Log and threading easy",
     url="https://github.com/schwarzam/logpool",
     install_requires = [''],
     classifiers=[
         "Programming Language :: Python :: 3",
         "License :: OSI Approved :: Apache Software License"
     ],
 )

# python3 setup.py bdist_wheel
# python3 -m twine upload dist/*