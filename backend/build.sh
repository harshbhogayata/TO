#!/usr/bin/env bash
# Render build script — runs on every deploy
set -o errexit

# Verify Python version (Django 6.0 requires 3.10+)
python --version
python -c "import sys; assert sys.version_info >= (3, 10), f'Python 3.10+ required, got {sys.version}'"

pip install --upgrade pip
pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate
