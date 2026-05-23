# 4IR Guestbook Monitoring

## Overview
This project extends the Pulumi Kubernetes Guestbook example by adding a full 
monitoring stack using Prometheus and Grafana. The entire infrastructure is 
defined as code using Pulumi Python and deploys to a Kubernetes cluster with 
a single command.

## Architecture
- **Guestbook Frontend**: PHP/Redis application exposed via ClusterIP Service
- **Redis Backend**: Leader/follower setup with 1 leader and 2 replicas
- **Prometheus**: Deployed via kube-prometheus-stack Helm chart, scrapes 
  pod metrics via annotations and kube-state-metrics
- **Grafana**: Deployed via separate Helm chart, exposed as NodePort on 
  port 32000, pre-configured with Prometheus datasource and auto-provisioned 
  dashboard

## Prerequisites
- Docker Desktop with Kubernetes enabled
- kubectl
- Pulumi CLI v3.x
- Python 3.x
- Helm 3.x

## Setup

### 1. Clone the Repository
```bash
git clone git@github.com:invadgir/4ir-monitoring.git
cd 4ir-monitoring
```

### 2. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Pulumi
```bash
pulumi login
pulumi stack init dev
pulumi config set namespace monitoring
pulumi config set --secret grafana_password <your-password>
```

### 4. Deploy
```bash
pulumi up
```

## Accessing Grafana
- URL: `http://localhost:32000`
- Username: admin
- Password: The password you set during configuration


## Verifying Metrics Are Being Scraped

### Option 1: Prometheus Targets UI
```bash
kubectl port-forward -n monitoring svc/kube-prometheus-stack-da34-prometheus 9090:9090
```
Open `http://localhost:9090/targets` and look for the `kubernetes-pods` job.
Guestbook pods will appear as targets in the default namespace.

### Option 2: Grafana Explore
1. Open Grafana at `http://localhost:32000`
2. Navigate to Explore
3. Run the following query to see CPU metrics for guestbook pods:

```promql
rate(container_cpu_usage_seconds_total{namespace="default"}[$__rate_interval])
```

## Dashboard
The **Guestbook Application Metrics** dashboard is auto-provisioned on 
deployment and contains six panels:

- **Pod Readiness Status**: Shows whether each pod is ready (1) or not (0)
- **Restarts by Pod**: Total restart count per pod
- **CPU Usage by Pod**: CPU usage rate across all guestbook pods
- **Frontend CPU Usage**: Dedicated CPU view for the frontend pod
- **Memory Usage by Pod**: Memory consumption across all guestbook pods
- **Frontend Memory Usage**: Dedicated memory view for the frontend pod

## Known Limitations
- The guestbook PHP application does not expose a `/metrics` endpoint, so
  application-level metrics such as HTTP request counts are not available.
  Infrastructure metrics via cAdvisor and kube-state-metrics are used instead.
- Node exporter is disabled as it is not compatible with Docker Desktop/WSL2
  environments.
- The Prometheus service name includes a Helm-generated hash suffix. If
  redeploying from scratch the datasource URL in `__main__.py` may need
  updating to match the new hash.

## Tear Down
```bash
pulumi destroy
```