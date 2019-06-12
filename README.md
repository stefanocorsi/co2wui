# Co2mpas Web UI

## Development instructions

- create a vrtual env, e. in this folder with `pythonX.Y -m venv venv`,
- install recent co2mpas from sources in *develop mode* with `git clone ...` and `pip install -e <co2mpas-folder>`,
- (optional) Install all pinned versions in `requirements.txt` to reproduce the exact environment, OR skip directly to...
- install this project in *develop mode* with `pip install .[dev]`, and finally
- enable *pre-commit* hooks for black-formatting python code with `pre-commit install`.

## Running

```shell
co2wui
```
