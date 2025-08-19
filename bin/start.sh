#!/bin/bash

set -e

echo "Starting the application..."
echo "Environment: ${ENV:-development}"

# Add your application startup commands here


source .venv/bin/activate
pip install -r requirements.txt

echo "Application started successfully!" 