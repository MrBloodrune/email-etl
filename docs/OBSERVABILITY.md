# Observability with Grafana Alloy

This document describes how to set up and configure observability for the Gmail ETL system using Grafana Alloy.

## Overview

The Gmail ETL system uses Grafana Alloy as a unified observability agent that can collect and forward:
- **Metrics** - Application and system metrics via Prometheus exporters
- **Logs** - Structured logs via OpenTelemetry Protocol (OTLP)
- **Traces** - Distributed traces for request tracking
- **PostgreSQL Metrics** - Database performance metrics

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   Gmail ETL     │────▶│ Grafana Alloy│────▶│ External        │
│   API Server    │OTLP │              │     │ Backends        │
└─────────────────┘     │  - Metrics   │     │ - Prometheus    │
                        │  - Logs      │     │ - Loki          │
┌─────────────────┐     │  - Traces    │     │ - Tempo         │
│   PostgreSQL    │────▶│              │     │ - Grafana Cloud │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

## Running with Observability

### 1. With Grafana Alloy (Recommended)

```bash
# Start all services including Alloy
docker-compose --profile observability up -d

# Check Alloy UI
open http://localhost:12345
```

### 2. Without Observability

```bash
# Start only core services (postgres, api)
docker-compose up -d

# Or explicitly disable observability
ENABLE_OBSERVABILITY=false docker-compose up -d
```

### 3. Using Override File

Create a `docker-compose.override.yml`:

```yaml
version: '3.8'
services:
  api:
    environment:
      ENABLE_OBSERVABILITY: "false"
```

## Configuring Alloy

### 1. Copy Example Configuration

```bash
cp alloy/config.alloy.example alloy/config.alloy
```

### 2. Configure Backends

Edit `alloy/config.alloy` and set your backend endpoints:

```hcl
// For Prometheus metrics
prometheus.remote_write "default" {
  endpoint {
    url = "https://prometheus.example.com/api/v1/write"
    basic_auth {
      username = "your-username"
      password = "your-password"
    }
  }
}

// For OTLP endpoints
otelcol.exporter.otlphttp "metrics" {
  client {
    endpoint = "https://otlp.example.com/v1/metrics"
    headers = {
      "Authorization" = "Bearer your-token",
    }
  }
}
```

### 3. Grafana Cloud Configuration

For Grafana Cloud users:

```hcl
// Metrics
prometheus.remote_write "grafana_cloud" {
  endpoint {
    url = "https://prometheus-prod-XX-prod-XX.grafana.net/api/prom/push"
    bearer_token = env("GRAFANA_CLOUD_TOKEN")
  }
}

// Logs
loki.write "grafana_cloud" {
  endpoint {
    url = "https://logs-prod-XX.grafana.net/loki/api/v1/push"
    bearer_token = env("GRAFANA_CLOUD_TOKEN")
  }
}

// Traces
otelcol.exporter.otlphttp "traces" {
  client {
    endpoint = "https://tempo-prod-XX-prod-XX.grafana.net:443"
    headers = {
      "Authorization" = "Bearer ${env("GRAFANA_CLOUD_TOKEN")}",
    }
  }
}
```

## Metrics Collected

### Application Metrics
- `gmail_etl_emails_imported` - Counter of imported emails
- `gmail_etl_embedding_generation_duration` - Histogram of embedding generation time
- `gmail_etl_search_latency` - Histogram of search request latency
- `gmail_etl_attachment_size` - Histogram of attachment sizes

### System Metrics (via node_exporter)
- CPU usage
- Memory usage
- Disk I/O
- Network statistics
- Filesystem usage

### PostgreSQL Metrics (via postgres_exporter)
- Connection statistics
- Query performance
- Database size
- Table statistics
- Replication lag (if applicable)

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ENABLE_OBSERVABILITY` | Enable/disable observability | `true` |
| `OTLP_ENDPOINT` | OTLP receiver endpoint | `alloy:4317` |
| `ENVIRONMENT` | Deployment environment | `production` |
| `OTEL_CONSOLE_EXPORT` | Enable console trace export | `false` |
| `ENABLE_PROMETHEUS_METRICS` | Enable Prometheus metrics | `true` |

## Monitoring Alloy

### Alloy UI

Access the Alloy UI at http://localhost:12345 to:
- View component status
- Check pipeline health
- Debug configuration issues
- Monitor resource usage

### Alloy Metrics

Alloy exposes its own metrics which can be scraped:
- Component health
- Data flow statistics
- Error rates
- Resource usage

## Troubleshooting

### Check Alloy Logs

```bash
docker-compose logs alloy
```

### Verify OTLP Connection

```bash
# Test OTLP endpoint
curl -v http://localhost:4318/v1/metrics
```

### Common Issues

1. **No data in backends**
   - Check Alloy logs for export errors
   - Verify backend endpoints and authentication
   - Ensure `ENABLE_OBSERVABILITY=true`

2. **High memory usage**
   - Adjust batch processor settings
   - Reduce scrape frequency
   - Check WAL size configuration

3. **Connection refused**
   - Ensure Alloy is running with correct profile
   - Check firewall rules
   - Verify port mappings

## Best Practices

1. **Resource Management**
   - Set appropriate batch sizes
   - Configure WAL limits
   - Monitor Alloy resource usage

2. **Security**
   - Use TLS for external endpoints
   - Rotate authentication tokens
   - Limit metric cardinality

3. **Data Retention**
   - Configure appropriate retention in backends
   - Use metric relabeling to reduce cardinality
   - Filter unnecessary telemetry data

## Minimal Setup

For development or testing without external backends:

```bash
# Use minimal Alloy config
cp alloy/config.alloy.minimal alloy/config.alloy

# Start with observability profile
docker-compose --profile observability up -d
```

This runs Alloy in no-op mode - it receives telemetry but doesn't forward it anywhere.