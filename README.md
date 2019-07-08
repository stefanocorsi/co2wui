
# Co2mpas Web UI

A flask UI for running co2mpas.

## Development instructions
<!--move them to CONTRIBUTING.md -->

1. create a virtual env, eg. in this folder called `.venv` with:

       pythonX.Y -m venv .venv

   and **activate it** afterwards,

2. clone the following repositories:

	 - git clone https://github.com/vinci1it2000/co2mpas.git (branch dev)
	 - git clone https://github.com/vinci1it2000/syncing.git
	 - git clone https://github.com/JRCSTU/DICE.git

3. Install the above packages in development mode:

       pip install -e <some-folder>

   for each of the packages

4. (optional) Install all pinned versions in `requirements.txt` with::

       pip install -r ./requirements.txt

   assuming you want to reproduce the exact environment, OR just...

6. install this project in *develop mode* along with all its development-dependencies
   with:

       pip install .[dev]

7. enable [*pre-commit* hooks][1] for [black-formatting][2] python code with::

       pre-commit install

## Launch WebUI

```shell
co2wui
```
or
```shell
python co2wui/app.py
```

[1]: https://ljvmiranda921.github.io/notebook/2018/06/21/precommits-using-black-and-flake8/
[2]: https://black.readthedocs.io/

