# Processing Service

## Purpose
Validates and normalizes events, detects unknown keys, routes to clean_events or dead-letter.

## Local run
`
pip install -r requirements.txt
cp .env.example .env
python -m app.main
`

## Structure
See pp/ for source, 	ests/ for unit and integration tests.
