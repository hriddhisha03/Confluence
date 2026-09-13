# Problem Statement
To ingest clickstream data from various different sources, in different format using microservice architecture, and auto detecting new key to alter the schema.
## Database 
- Clickhouse
- Postgres

## Metrics 
Ingestion rate = 1 million request per second
Data size - 5 GB 

## Architecture
Ingestion -> Processing -> loading -> clickhouse 
                |
                V
             Intelligence

### Ingestion 
API layer which handles authentication 

### Processing 
Cleans data format, it validates and cleans

### Intelligence
Auto detects new keys, and returns the new schema

### Loading 
Data dumping and schema update

## Data movement
Ingesting processing loading = Kafka
Processing to intelligence = GRPC (Google remote procedure call)

## Language 
Python

