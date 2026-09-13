# Clickstream Ingestion Pipeline

A multi-node, microservice-based system for ingesting high-volume clickstream
data from heterogeneous sources, validating and cleaning it, automatically
detecting new event fields, evolving the destination schema, and loading
the data into an analytical store. Deployed as containerized microservices
on Kubernetes.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Data Flow](#data-flow)
- [Kubernetes Topology](#kubernetes-topology)
- [Schema Evolution Flow](#schema-evolution-flow)
- [Scale Targets](#scale-targets)
- [Repository Structure](#repository-structure)
- [Local Development](#local-development)
- [Deployment](#deployment)
- [Roadmap](#roadmap)

## Overview

| Property | Value |
|---|---|
| Design throughput | 1,000,000 requests/sec |
| Demonstrated throughput | Documented separately per load test, see `/docs/load-test.md` |
| Data volume (sample) | 5 GB |
| Orchestration | Kubernetes, multi-node cluster |
| Primary language | Python |
| Messaging | Kafka |
| Inter-service RPC | gRPC |
| Analytical store | ClickHouse |
| Metadata store | PostgreSQL |

## Architecture

```mermaid
flowchart LR
    C[Clients] --> ING[Ingestion Service]
    ING -->|produce| K1[(Kafka: raw_events)]
    K1 -->|consume| PROC[Processing Service]
    PROC -->|produce, clean| K2[(Kafka: clean_events)]
    PROC -->|gRPC, unknown key| INT[Intelligence Service]
    INT -->|read/write| PG[(PostgreSQL Schema Registry)]
    INT -->|produce| K3[(Kafka: schema_updates)]
    K2 -->|consume| LOAD[Loading Service]
    K3 -->|consume| LOAD
    LOAD -->|batch insert / DDL| CH[(ClickHouse)]
    PROC -->|produce, malformed| DLQ[(Kafka: dlq_events)]
```

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| API framework | FastAPI, Uvicorn/Gunicorn | Async HTTP ingestion layer, auth |
| Messaging | Apache Kafka (Strimzi operator on K8s) | Decoupled, replay-able event backbone |
| Inter-service RPC | gRPC, Protocol Buffers | Low-latency schema-inference calls |
| Metadata store | PostgreSQL | Schema registry, auth, service config |
| Analytical store | ClickHouse | High-volume event storage and query |
| Orchestration | Kubernetes | Multi-node deployment, scaling, self-healing |
| Kafka client | aiokafka / confluent-kafka-python | Producer/consumer implementation |
| DB clients | asyncpg, clickhouse-connect | Async Postgres and ClickHouse access |
| Containerization | Docker | Service packaging |
| Package management (K8s) | Helm | Templated manifests per environment |
| CI/CD | GitHub Actions | Build, test, push image, deploy |
| Observability | Prometheus, Grafana | Metrics, dashboards |
| Logging | structlog, Fluent Bit | Structured logs, cluster-wide aggregation |
| Load testing | Locust or k6 | Throughput and latency validation |
| Autoscaling | Kubernetes HPA | Scale Ingestion/Processing/Loading on load |

## Data Flow

```mermaid
sequenceDiagram
    participant Client
    participant Ingestion
    participant Kafka as Kafka (raw_events)
    participant Processing
    participant Intelligence
    participant Postgres
    participant Loading
    participant ClickHouse

    Client->>Ingestion: POST /events (auth token, payload)
    Ingestion->>Kafka: publish raw event
    Kafka->>Processing: consume raw event
    Processing->>Processing: validate, normalize format
    alt known schema
        Processing->>Kafka: publish to clean_events
    else unknown key detected
        Processing->>Intelligence: gRPC InferSchema(event sample)
        Intelligence->>Postgres: read/write schema registry
        Intelligence-->>Processing: schema delta
        Processing->>Kafka: publish schema_updates
        Processing->>Kafka: publish to clean_events
    end
    Kafka->>Loading: consume clean_events / schema_updates
    Loading->>ClickHouse: ALTER TABLE if new column
    Loading->>ClickHouse: batch INSERT
```

## Kubernetes Topology

```mermaid
flowchart TB
    subgraph Cluster[Kubernetes Cluster - Multi Node]
        subgraph NS1[Namespace: ingestion]
            IngPod1[Ingestion Pod]
            IngPod2[Ingestion Pod]
            IngSvc[Service + Ingress]
        end

        subgraph NS2[Namespace: processing]
            ProcPod1[Processing Pod]
            ProcPod2[Processing Pod]
            ProcPod3[Processing Pod]
        end

        subgraph NS3[Namespace: intelligence]
            IntPod1[Intelligence Pod]
            IntPod2[Intelligence Pod]
        end

        subgraph NS4[Namespace: loading]
            LoadPod1[Loading Pod]
            LoadPod2[Loading Pod]
        end

        subgraph NS5[Namespace: kafka]
            KBroker1[Kafka Broker 1]
            KBroker2[Kafka Broker 2]
            KBroker3[Kafka Broker 3]
        end

        subgraph NS6[Namespace: data]
            PGNode[(PostgreSQL StatefulSet)]
            CHNode1[(ClickHouse Shard 1)]
            CHNode2[(ClickHouse Shard 2)]
        end

        subgraph NS7[Namespace: observability]
            Prom[Prometheus]
            Graf[Grafana]
        end
    end

    IngSvc --> IngPod1
    IngSvc --> IngPod2
    IngPod1 --> KBroker1
    IngPod2 --> KBroker2
    KBroker1 --> ProcPod1
    KBroker2 --> ProcPod2
    KBroker3 --> ProcPod3
    ProcPod1 -.gRPC.-> IntPod1
    ProcPod2 -.gRPC.-> IntPod2
    IntPod1 --> PGNode
    IntPod2 --> PGNode
    ProcPod1 --> KBroker1
    KBroker1 --> LoadPod1
    KBroker2 --> LoadPod2
    LoadPod1 --> CHNode1
    LoadPod2 --> CHNode2
    Prom --> IngPod1
    Prom --> ProcPod1
    Prom --> IntPod1
    Prom --> LoadPod1
    Graf --> Prom
```

Each service namespace ships with a `Deployment`, a `HorizontalPodAutoscaler`
keyed on CPU and Kafka consumer lag, and a `Service` for internal routing.
Kafka runs via the Strimzi operator as a `Kafka` custom resource with a
configurable number of broker pods and partitions per topic. PostgreSQL and
ClickHouse run as `StatefulSet`s with persistent volume claims; ClickHouse
uses the `ReplicatedMergeTree` engine across shards for horizontal scale.

## Schema Evolution Flow

```mermaid
flowchart TD
    A[Event arrives in Processing] --> B{Keys match known schema?}
    B -->|Yes| C[Route to clean_events]
    B -->|No| D[Send sample to Intelligence via gRPC]
    D --> E[Intelligence infers type]
    E --> F[Write new schema version to Postgres registry]
    F --> G[Publish schema_updates to Kafka]
    G --> H[Loading service consumes schema_updates]
    H --> I[ALTER TABLE ADD COLUMN on ClickHouse]
    I --> J[Subsequent events with new key insert cleanly]
    C --> K[Loading batches and inserts into ClickHouse]
```

## Scale Targets

| Metric | Design target | Notes |
|---|---|---|
| Ingest rate | 1,000,000 req/sec | Achieved via horizontal pod scaling and Kafka partition count, not a single-node number |
| Kafka partitions | Sized per topic based on target consumer parallelism | Partition count should be greater than or equal to max consumer replicas |
| ClickHouse | Sharded, replicated cluster | Writes batched by Loading service, never row-by-row |
| Postgres | Single primary with read replicas | Low write volume, schema registry only |
| Pod autoscaling | HPA on CPU and Kafka consumer lag | Prevents over-provisioning at idle |

Any throughput number reported for this project should be backed by a load
test (see `/docs/load-test.md`) with cluster size, partition count, and
replica count documented alongside the result.

## Repository Structure

```
.
├── services/
│   ├── ingestion/
│   ├── processing/
│   ├── intelligence/
│   └── loading/
├── proto/
│   └── schema_inference.proto
├── charts/
│   ├── ingestion/
│   ├── processing/
│   ├── intelligence/
│   ├── loading/
│   └── kafka/
├── infra/
│   ├── k8s-manifests/
│   └── terraform/ (optional, for cluster provisioning)
├── docs/
│   ├── architecture.md
│   └── load-test.md
└── README.md
```

## Local Development

Local development uses `kind` or `minikube` to approximate the multi-node
cluster, or Docker Compose for a lighter single-node loop during early
service development.

```bash
# spin up a local multi-node cluster
kind create cluster --config infra/k8s-manifests/kind-multi-node.yaml

# install Kafka via Strimzi
kubectl apply -f infra/k8s-manifests/strimzi-operator.yaml

# deploy all services via Helm
helm install ingestion charts/ingestion
helm install processing charts/processing
helm install intelligence charts/intelligence
helm install loading charts/loading
```

## Deployment

Deployment to a multi-node cluster (cloud-managed or self-hosted) follows
the same Helm charts with environment-specific `values.yaml` overrides for
replica counts, resource requests/limits, and storage class. CI/CD builds
and pushes container images on merge to main, then applies Helm upgrades to
the target cluster.

## Roadmap

| Phase | Focus | Output |
|---|---|---|
| 0 | Local K8s cluster and Kafka via Strimzi | Working multi-node cluster locally |
| 1 | Ingestion service | Deployed, authenticated, publishing to Kafka |
| 2 | Processing service | Validating, normalizing, routing known/unknown keys |
| 3 | Intelligence service | gRPC schema inference, Postgres registry |
| 4 | Loading service | Batched ClickHouse writes, dynamic ALTER TABLE |
| 5 | Autoscaling and observability | HPA tuned, Prometheus/Grafana dashboards live |
| 6 | Load testing | Throughput report with cluster configuration documented |
| 7 | CI/CD and documentation | Automated deploys, complete docs |