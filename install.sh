#!/bin/bash

python3 -m pip install -r requirements.txt

playwright install-deps
playwright install chromium

# cd proxy && python3 make_config.py
# test -e config.yaml && nohup ./clash-linux-amd64-v3 -d . &
# cd ..
