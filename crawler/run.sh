#!/bin/bash
export PYTHONPATH=.
# Try to load env from backend if available for local dev
if [ -f ../backend/.env ]; then
  export $(grep -v '^#' ../backend/.env | xargs)
fi

# Override specific vars for Crawler
export PROJECT_NAME="Crawler Service"

echo "Starting Crawler Service on port 8000..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000
