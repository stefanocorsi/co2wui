#!/bin/bash
rm -rf *egg-info build dist/* && python setup.py sdist bdist_wheel

