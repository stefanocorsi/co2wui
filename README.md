# Co2mpas Web UI

A flask UI for running co2mpas.

## Development instructions
<!--move them to CONTRIBUTING.md -->

1. create a virtual env, eg. in this folder called `.venv` with:

       pythonX.Y -m venv .venv

   and **activate it** afterwards,

2. install recent co2mpas from sources in *develop mode* with:

       git clone ... <some-folder>
       pip install -e <some-folder>

3. (optional) Install all pinned versions in `requirements.txt` with::

       pip install -r ./requirements.txt

   assuming you want to reproduce the exact environment, OR just...

4. install this project in *develop mode* along with all its development-dependencies
   with:

       pip install .[dev]

5. enable [*pre-commit* hooks][1] for [black-formatting][2] python code with::

       pre-commit install

## Launch WebUI

```shell
co2wui
```

[1]: https://ljvmiranda921.github.io/notebook/2018/06/21/precommits-using-black-and-flake8/
[2]: https://black.readthedocs.io/
