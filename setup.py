from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# get version from __version__ variable in shg/__init__.py
from shg import __version__ as version

setup(
    name="shg",
    version=version,
    description="Self Help Group Management System for ERPNext",
    author="SHG Solutions",
    author_email="support@shgsolutions.co.ke",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Office/Business :: Financial",
        "Framework :: ERPNext",
    ],
    keywords="erpnext shg kenya finance microfinance",
    project_urls={
        "Bug Reports": "https://github.com/your-username/shg-erpnext/issues",
        "Source": "https://github.com/your-username/shg-erpnext",
        "Documentation": "https://github.com/your-username/shg-erpnext/wiki",
    },
)
