# AGENTS.md

## Setup commands

- if the virtualenv path `venv` does not exist, create it with: `python3 -m venv venv`
- install requirements with: `pip3 install -r requirements.txt -r requirements-test.txt`
- before running commands activate virtualenv with: `source venv/bin/activate`
- Start app: `./main.py --config miio-wohnzimmer.cfg --verbose`
- Run tests: `PYTHONPATH=. pytest --cov-report term-missing`

## Code style

- test files must be placed in the `tests` folder
- test files must be named: `*_test.py`
- use single quotes
- multiline lists must have a trailing comma
- used python version is at least 3.12
- max line length is 160 charaters
- there must be no mypy errors
