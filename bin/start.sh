#!/bin/bash

set -e

echo "Starting the application..."
echo "Environment: ${ENV:-development}"

# Add your application startup commands here

echo "Creating Virtual Environment" 
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements/local.txt

echo "Migrating Database" 
python manage.py makemigrations
python manage.py migrate

echo "Starting Server" 
python manage.py runserver 8080
