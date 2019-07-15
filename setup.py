from setuptools import setup, find_packages


def read(fpath):
    with open(fpath) as fp:
        return fp.read()


test_deps = ["pytest", "selenium"]
setup(
    name="co2wui",
    version="0.0.1.dev2",
    packages=find_packages(exclude=["test"]),
    license="European Union Public Licence 1.1 or later (EUPL 1.1+)",
    description="WebUI for co2mpas",
    long_description=read("README.md"),
    keywords=["automotive", "vehicles", "simulator", "WLTP", "web-app"],
    project_urls={
        "Documentation": "https://co2mpas.io/",
        "Sources": "https://github.com/JRCSTU/co2wui",
    },
    python_requires=">=3.5",
    install_requires=[
        "co2mpas",
        "Flask",
        "Flask-Babel",
        "requests",
        "schedula",
        "Werkzeug",
        "click",
        "ruamel.yaml",
        "syncing",
    ],
    extras_require={
        "test": test_deps,
        "dev": test_deps
        + [
            "black",  # for code-formatting
            "pip",
            "pre-commit",  # for code-formatting
            "wheel",
        ],
    },
    entry_points={"console_scripts": ["co2wui=co2wui.app:cli"]},
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "Development Status :: 3 - Alpha",
        "Natural Language :: English",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Manufacturing",
        "Environment :: Console",
        "License :: OSI Approved :: European Union Public Licence 1.1 " "(EUPL 1.1)",
        "Natural Language :: English",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
)
