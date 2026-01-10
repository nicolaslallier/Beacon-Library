# Observability for Beacon-Library

This directory contains configuration for collecting and exporting observability signals (metrics, logs, traces) to the external monitoring infrastructure.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Beacon-Library Stack                                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│  │ Backend  │ │ Frontend │ │  Nginx   │ │ Postgres │                        │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘                        │
│       │            │            │            │                               │
│       │ stdout/stderr          stdout/stderr │                               │
│       │            │            │            │                               │
│       ▼            ▼            ▼            ▼                               │
│  ┌─────────────────────────────────────────────┐     ┌──────────────────┐   │
│  │              Promtail                        │────▶│       Loki       │   │
│  │         (Log Collection)                     │     │ (External)       │   │
│  └─────────────────────────────────────────────┘     └──────────────────┘   │
│                                                                              │
│  ┌──────────────┐    ┌─────────────────────────┐     ┌──────────────────┐   │
│  │   cAdvisor   │───▶│      Grafana Alloy      │────▶│   Prometheus     │   │
│  │  (Metrics)   │    │   (Metrics + Traces)    │     │   (External)     │   │
│  └──────────────┘    └───────────┬─────────────┘     └──────────────────┘   │
│                                  │                                          │
│       ┌──────────────────────────┘                   ┌──────────────────┐   │
│       │ OTLP                                         │      Tempo       │   │
│       ▼                                              │   (External)     │   │
│  ┌──────────┐                                        └──────────────────┘   │
│  │ Backend  │──────────────────────────────────────────────▲                │
│  │ (Traces) │                                                               │
│  └──────────┘                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
```

## External Endpoints

| Signal  | Endpoint                                    | Protocol       |
|---------|---------------------------------------------|----------------|
| Logs    | `loki.beacon.famillallier.net:3100`         | HTTP (Loki API)|
| Metrics | `prometheus.beacon.famillallier.net:9090`   | HTTP (remote_write) |
| Traces  | `tempo.beacon.famillallier.net:4317`        | gRPC (OTLP)    |

## Components

### Promtail
Collects Docker container logs and pushes to Loki.

- **Config**: `promtail/promtail-config.yml`
- **Discovery**: Automatic Docker container discovery
- **Labels**: `service`, `env`, `instance`, `compose_project`, `trace_id`

### Grafana Alloy
Single agent for metrics scraping and OTLP trace collection.

- **Config**: `alloy/config.alloy`
- **Metrics Sources**: cAdvisor (container metrics), Backend `/metrics`
- **Trace Receiver**: OTLP on ports 4317 (gRPC) and 4318 (HTTP)

### cAdvisor
Exposes container-level metrics (CPU, memory, network, disk).

- **Metrics Endpoint**: `http://cadvisor:8080/metrics`
- **Scraped by**: Grafana Alloy

## Usage

### Start Observability Collectors

```bash
# Start with full stack
make up

# Or start collectors only
make observability-up
```

### Check Status

```bash
make observability-status
```

### View Collector Logs

```bash
make observability-logs
```

### Stop Collectors

```bash
make observability-down
```

## Environment Variables

Configure these in `.env` or as environment variables:

| Variable           | Default                                          | Description                     |
|--------------------|--------------------------------------------------|---------------------------------|
| `ENV`              | `local`                                          | Environment label (local/dev/ppe/prod) |
| `LOKI_URL`         | `http://loki.beacon.famillallier.net:3100`       | Loki push endpoint              |
| `PROMETHEUS_URL`   | `http://prometheus.beacon.famillallier.net:9090` | Prometheus remote_write endpoint|
| `TEMPO_URL`        | `tempo.beacon.famillallier.net:4317`             | Tempo OTLP endpoint             |
| `OTLP_ENDPOINT`    | `http://alloy:4317`                              | Backend trace export endpoint   |
| `OTEL_TRACING_ENABLED` | `true`                                       | Enable/disable tracing          |
| `LOG_LEVEL`        | `INFO`                                           | Backend log level               |

## Labels (Metadata)

All signals include these standard labels for filtering and correlation:

| Label             | Description                                  | Example                    |
|-------------------|----------------------------------------------|----------------------------|
| `service`         | Service/container name                       | `beacon-library-api`       |
| `env`             | Environment                                  | `local`, `dev`, `prod`     |
| `instance`        | Container instance identifier                | Container ID               |
| `compose_project` | Docker Compose project                       | `beacon-library`           |
| `trace_id`        | Distributed trace ID (logs only, if present) | `abc123...`                |

## Correlation: Logs ↔ Traces

The backend injects `trace_id` into structured JSON logs. To correlate:

1. Find an error in Loki logs
2. Extract the `trace_id` label
3. Search Tempo for that trace ID
4. View the full distributed trace

## Troubleshooting

### Logs not appearing in Loki

1. Check Promtail is running: `docker compose ps promtail`
2. Check Promtail logs: `docker compose logs promtail`
3. Verify Loki endpoint is reachable: `curl -s http://loki.beacon.famillallier.net:3100/ready`

### Metrics not in Prometheus

1. Check Alloy is running: `docker compose ps alloy`
2. Check Alloy logs: `docker compose logs alloy`
3. Verify backend exposes metrics: `curl http://localhost:8000/metrics`
4. Verify Prometheus remote_write endpoint

### Traces not appearing in Tempo

1. Check Alloy is running and OTLP ports are exposed (4317, 4318)
2. Verify `OTEL_TRACING_ENABLED=true` in backend environment
3. Check backend logs for OpenTelemetry errors
4. Verify Tempo endpoint is reachable

### Backend /metrics returns 404

Ensure the backend started correctly with observability instrumentation:
```bash
docker compose logs backend | grep -i "prometheus\|metrics"
```

## Adding a New Service

To add observability to a new service:

1. **Logs**: Automatically collected if the service outputs to stdout/stderr
2. **Metrics**:
   - Expose a `/metrics` endpoint
   - Add scrape config to `alloy/config.alloy`
3. **Traces**:
   - Add OpenTelemetry SDK to your service
   - Configure OTLP exporter to `http://alloy:4317`
   - Set `service.name` resource attribute

Example Alloy scrape config addition:
```alloy
prometheus.scrape "my_new_service" {
  targets = [{
    __address__ = "my-service:8080",
  }]
  forward_to = [prometheus.relabel.add_labels.receiver]
  scrape_interval = "15s"
  metrics_path = "/metrics"
}
```
