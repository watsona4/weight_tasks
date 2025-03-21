#!/bin/sh
cd $(dirname $(realpath $0))
. venv/bin/activate
python weight_tasks.py $*
