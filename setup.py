from setuptools import setup

setup(
    name="co2wui",
    version="0.1dev",
    packages=["co2wui"],
    license="EUPL",
    long_description=open("README.md").read(),
    install_requires=["co2mpas", "Flask", "requests", "schedula", "Werkzeug"],
    extras={
        "dev": [
            "black",  # for code-formatting
            "pip",
            "pre-commit",  # for code-formatting
            "wheel",
        ]
    },
    entry_points={"console_scripts": ["co2wui=co2wui:cli"]},
)
