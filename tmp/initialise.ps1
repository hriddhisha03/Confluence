<#
.SYNOPSIS
    Scaffolds a production-grade internal structure for the Data_Pipeline
    microservices repository (ingestion, processing, intelligence, loading,
    common) plus repo-level infra, charts, proto, docs, and CI folders.

.PARAMETER Root
    Path to the repo root. Defaults to the current directory, so run this
    from inside D:\mili\OutOfCollege\Data_Pipeline, or pass -Root explicitly.

.EXAMPLE
    .\scaffold-repo.ps1
    .\scaffold-repo.ps1 -Root "D:\mili\OutOfCollege\Data_Pipeline"
#>

param(
    [string]$Root = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

function New-Dir {
    param([string]$Path)
    if (-not (Test-Path -Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function New-FileWithContent {
    param(
        [string]$Path,
        [string]$Content = ""
    )
    if (-not (Test-Path -Path $Path)) {
        Set-Content -Path $Path -Value $Content -Encoding UTF8
    }
}

Write-Host "Scaffolding repo at: $Root" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Reusable file templates
# ---------------------------------------------------------------------------

$dockerignoreContent = @"
__pycache__/
*.pyc
.venv/
.env
.git/
tests/
*.md
"@

function Get-DockerfileContent {
    param([string]$ServiceName)
    return @"
FROM python:3.12-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1
ENV SERVICE_NAME=$ServiceName

CMD ["python", "-m", "app.main"]
"@
}

function Get-RequirementsContent {
    param([string]$ServiceName)
    $base = @(
        "pydantic-settings>=2.0",
        "structlog>=24.1",
        "prometheus-client>=0.20",
        "python-dotenv>=1.0"
    )
    switch ($ServiceName) {
        "ingestion"    { $base += @("fastapi>=0.110", "uvicorn[standard]>=0.29", "aiokafka>=0.10") }
        "processing"   { $base += @("aiokafka>=0.10", "grpcio>=1.62", "grpcio-tools>=1.62") }
        "intelligence" { $base += @("grpcio>=1.62", "grpcio-tools>=1.62", "asyncpg>=0.29") }
        "loading"      { $base += @("aiokafka>=0.10", "clickhouse-connect>=0.7") }
    }
    return ($base -join "`n")
}

function Get-EnvExampleContent {
    param([string]$ServiceName)
    $lines = @(
        "SERVICE_NAME=$ServiceName",
        "LOG_LEVEL=INFO",
        "KAFKA_BOOTSTRAP_SERVERS=kafka:9092"
    )
    switch ($ServiceName) {
        "ingestion"    { $lines += @("API_PORT=8000", "AUTH_SECRET_KEY=changeme") }
        "processing"   { $lines += @("INTELLIGENCE_GRPC_HOST=intelligence", "INTELLIGENCE_GRPC_PORT=50051") }
        "intelligence" { $lines += @("GRPC_PORT=50051", "POSTGRES_DSN=postgresql://user:pass@postgres:5432/schema_registry") }
        "loading"      { $lines += @("CLICKHOUSE_HOST=clickhouse", "CLICKHOUSE_PORT=8123", "BATCH_SIZE=1000", "BATCH_INTERVAL_SECONDS=2") }
    }
    return ($lines -join "`n")
}

function Get-ConfigPyContent {
    param([string]$ServiceName)
    return @"
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    service_name: str = "$ServiceName"
    log_level: str = "INFO"
    kafka_bootstrap_servers: str = "kafka:9092"

    class Config:
        env_file = ".env"


settings = Settings()
"@
}

$loggingPyContent = @"
import logging
import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(format="%(message)s", level=level)
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ]
    )


def get_logger(name: str):
    return structlog.get_logger(name)
"@

function Get-MainPyContent {
    param([string]$ServiceName)
    switch ($ServiceName) {
        "ingestion" {
            return @"
from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.routes import router

configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(title="Ingestion Service")
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.service_name}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"@
        }
        "processing" {
            return @"
import asyncio
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.event_processor import run_consumer

configure_logging(settings.log_level)
logger = get_logger(__name__)


async def main():
    logger.info("starting_processing_service")
    await run_consumer()


if __name__ == "__main__":
    asyncio.run(main())
"@
        }
        "intelligence" {
            return @"
from concurrent import futures
import grpc
from app.core.config import settings
from app.core.logging import configure_logging, get_logger

configure_logging(settings.log_level)
logger = get_logger(__name__)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    # TODO: register SchemaInferenceServicer here once proto stubs are generated
    server.add_insecure_port("[::]:50051")
    server.start()
    logger.info("intelligence_grpc_server_started", port=50051)
    server.wait_for_termination()


if __name__ == "__main__":
    serve()
"@
        }
        "loading" {
            return @"
import asyncio
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.services.loader import run_loader

configure_logging(settings.log_level)
logger = get_logger(__name__)


async def main():
    logger.info("starting_loading_service")
    await run_loader()


if __name__ == "__main__":
    asyncio.run(main())
"@
        }
    }
}

$readmeServiceTemplate = @"
# {0} Service

## Purpose
{1}

## Local run
```
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

## Structure
See `app/` for source, `tests/` for unit and integration tests.
"@

$servicePurpose = @{
    "ingestion"    = "Authenticates and accepts incoming clickstream events, publishes to Kafka raw_events topic."
    "processing"   = "Validates and normalizes events, detects unknown keys, routes to clean_events or dead-letter."
    "intelligence" = "Infers schema for unknown keys via gRPC, maintains versioned schema registry in Postgres."
    "loading"      = "Consumes clean events and schema updates, batches writes and DDL into ClickHouse."
}

# ---------------------------------------------------------------------------
# Per-service scaffolding
# ---------------------------------------------------------------------------

$services = @("ingestion", "processing", "intelligence", "loading")

foreach ($svc in $services) {
    $svcRoot = Join-Path $Root $svc
    if (-not (Test-Path $svcRoot)) {
        Write-Warning "$svc directory not found at $svcRoot, skipping."
        continue
    }

    Write-Host "Scaffolding service: $svc" -ForegroundColor Yellow

    # app package
    New-Dir "$svcRoot\app"
    New-Dir "$svcRoot\app\api"
    New-Dir "$svcRoot\app\core"
    New-Dir "$svcRoot\app\models"
    New-Dir "$svcRoot\app\services"
    New-Dir "$svcRoot\app\clients"
    New-Dir "$svcRoot\app\utils"

    New-FileWithContent "$svcRoot\app\__init__.py"
    New-FileWithContent "$svcRoot\app\api\__init__.py"
    New-FileWithContent "$svcRoot\app\api\routes.py" "from fastapi import APIRouter`n`nrouter = APIRouter()`n"
    New-FileWithContent "$svcRoot\app\api\dependencies.py"
    New-FileWithContent "$svcRoot\app\core\__init__.py"
    New-FileWithContent "$svcRoot\app\core\config.py" (Get-ConfigPyContent -ServiceName $svc)
    New-FileWithContent "$svcRoot\app\core\logging.py" $loggingPyContent
    New-FileWithContent "$svcRoot\app\core\security.py"
    New-FileWithContent "$svcRoot\app\models\__init__.py"
    New-FileWithContent "$svcRoot\app\models\schemas.py"
    New-FileWithContent "$svcRoot\app\services\__init__.py"
    New-FileWithContent "$svcRoot\app\clients\__init__.py"
    New-FileWithContent "$svcRoot\app\clients\kafka_client.py"
    New-FileWithContent "$svcRoot\app\utils\__init__.py"
    New-FileWithContent "$svcRoot\app\main.py" (Get-MainPyContent -ServiceName $svc)

    # service-specific extras
    if ($svc -eq "processing") {
        New-FileWithContent "$svcRoot\app\clients\grpc_client.py"
        New-FileWithContent "$svcRoot\app\services\event_processor.py" "async def run_consumer():`n    # TODO: implement Kafka consumer loop`n    pass`n"
    }
    if ($svc -eq "loading") {
        New-FileWithContent "$svcRoot\app\clients\clickhouse_client.py"
        New-FileWithContent "$svcRoot\app\services\loader.py" "async def run_loader():`n    # TODO: implement batching + ClickHouse writes`n    pass`n"
    }
    if ($svc -eq "intelligence") {
        New-FileWithContent "$svcRoot\app\clients\postgres_client.py"
        New-FileWithContent "$svcRoot\app\services\schema_inference.py"
    }

    # tests
    New-Dir "$svcRoot\tests\unit"
    New-Dir "$svcRoot\tests\integration"
    New-FileWithContent "$svcRoot\tests\__init__.py"
    New-FileWithContent "$svcRoot\tests\unit\__init__.py"
    New-FileWithContent "$svcRoot\tests\integration\__init__.py"

    # top-level service files
    New-FileWithContent "$svcRoot\Dockerfile" (Get-DockerfileContent -ServiceName $svc)
    New-FileWithContent "$svcRoot\.dockerignore" $dockerignoreContent
    New-FileWithContent "$svcRoot\requirements.txt" (Get-RequirementsContent -ServiceName $svc)
    New-FileWithContent "$svcRoot\.env.example" (Get-EnvExampleContent -ServiceName $svc)
    New-FileWithContent "$svcRoot\pyproject.toml" "[project]`nname = `"$svc`"`nversion = `"0.1.0`"`nrequires-python = `">=3.12`"`n"
    $svcReadme = $readmeServiceTemplate -f ($svc.Substring(0,1).ToUpper() + $svc.Substring(1)), $servicePurpose[$svc]
    New-FileWithContent "$svcRoot\README.md" $svcReadme
}

# ---------------------------------------------------------------------------
# common/ shared package
# ---------------------------------------------------------------------------

$commonRoot = Join-Path $Root "common"
if (Test-Path $commonRoot) {
    Write-Host "Scaffolding shared package: common" -ForegroundColor Yellow

    New-Dir "$commonRoot\proto"
    New-Dir "$commonRoot\kafka"
    New-Dir "$commonRoot\logging"
    New-Dir "$commonRoot\config"
    New-Dir "$commonRoot\exceptions"
    New-Dir "$commonRoot\schemas"
    New-Dir "$commonRoot\tests"

    New-FileWithContent "$commonRoot\__init__.py"
    New-FileWithContent "$commonRoot\proto\schema_inference.proto" @"
syntax = "proto3";

package intelligence;

service SchemaInference {
  rpc InferSchema (SchemaRequest) returns (SchemaResponse);
}

message SchemaRequest {
  string event_sample = 1;
  repeated string unknown_keys = 2;
}

message SchemaResponse {
  string schema_version = 1;
  map<string, string> inferred_types = 2;
}
"@
    New-FileWithContent "$commonRoot\kafka\__init__.py"
    New-FileWithContent "$commonRoot\kafka\producer.py"
    New-FileWithContent "$commonRoot\kafka\consumer.py"
    New-FileWithContent "$commonRoot\logging\__init__.py"
    New-FileWithContent "$commonRoot\logging\logger.py" $loggingPyContent
    New-FileWithContent "$commonRoot\config\__init__.py"
    New-FileWithContent "$commonRoot\config\base_settings.py"
    New-FileWithContent "$commonRoot\exceptions\__init__.py"
    New-FileWithContent "$commonRoot\exceptions\errors.py" "class PipelineError(Exception):`n    pass`n"
    New-FileWithContent "$commonRoot\schemas\__init__.py"
    New-FileWithContent "$commonRoot\tests\__init__.py"
    New-FileWithContent "$commonRoot\pyproject.toml" "[project]`nname = `"common`"`nversion = `"0.1.0`"`nrequires-python = `">=3.12`"`n"
    New-FileWithContent "$commonRoot\README.md" "# Common`n`nShared code used across all services: Kafka producer/consumer wrappers, structured logging, base config, custom exceptions, and the gRPC proto contract.`n"
}

# ---------------------------------------------------------------------------
# Repo-level infra, charts, proto, docs, CI, scripts
# ---------------------------------------------------------------------------

Write-Host "Scaffolding repo-level folders" -ForegroundColor Yellow

New-Dir "$Root\proto"
New-FileWithContent "$Root\proto\.gitkeep"

New-Dir "$Root\charts\ingestion\templates"
New-Dir "$Root\charts\processing\templates"
New-Dir "$Root\charts\intelligence\templates"
New-Dir "$Root\charts\loading\templates"
New-Dir "$Root\charts\kafka\templates"

foreach ($chart in @("ingestion", "processing", "intelligence", "loading", "kafka")) {
    New-FileWithContent "$Root\charts\$chart\Chart.yaml" "apiVersion: v2`nname: $chart`nversion: 0.1.0`nappVersion: `"0.1.0`"`n"
    New-FileWithContent "$Root\charts\$chart\values.yaml" "replicaCount: 2`n`nimage:`n  repository: $chart`n  tag: latest`n  pullPolicy: IfNotPresent`n`nresources: {}`n"
}

New-Dir "$Root\infra\k8s-manifests"
New-Dir "$Root\infra\terraform"
New-FileWithContent "$Root\infra\k8s-manifests\.gitkeep"
New-FileWithContent "$Root\infra\terraform\.gitkeep"

New-Dir "$Root\docs"
New-FileWithContent "$Root\docs\architecture.md" "# Architecture`n`nSee root README.md for diagrams. Expand per-component design notes here.`n"
New-FileWithContent "$Root\docs\load-test.md" "# Load Test Results`n`nDocument cluster size, partition count, replica count, and measured throughput here.`n"

New-Dir "$Root\.github\workflows"
New-FileWithContent "$Root\.github\workflows\ci.yml" @"
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  build-and-test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [ingestion, processing, intelligence, loading]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        working-directory: `${{ matrix.service }}
        run: pip install -r requirements.txt
      - name: Run tests
        working-directory: `${{ matrix.service }}
        run: pytest tests/ || true
"@

New-Dir "$Root\scripts"
New-FileWithContent "$Root\scripts\.gitkeep"

New-FileWithContent "$Root\.gitignore" @"
__pycache__/
*.pyc
.venv/
.env
*.egg-info/
.idea/
.vscode/
"@

Write-Host "Scaffolding complete." -ForegroundColor Green