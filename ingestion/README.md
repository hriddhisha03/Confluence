# Ingestion Service

## Purpose
Authenticates and accepts incoming clickstream events, publishes to Kafka raw_events topic.

## Local run
`
pip install -r requirements.txt
cp .env.example .env
python -m app.main
`

## Structure
See pp/ for source, 	ests/ for unit and integration tests.
