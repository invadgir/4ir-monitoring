"""4IR Guestbook Monitoring - Pulumi Python program"""

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs

with open("dashboards/guestbook-dashboard.json", "r") as f:
    dashboard_json = f.read()

config = pulumi.Config()
namespace_name = config.get("namespace") or "monitoring"
grafana_password = config.require_secret("grafana_password")


monitoring_ns = k8s.core.v1.Namespace(
    "monitoring",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name=namespace_name,
    ),
)


# Deploy Guestbook frontend
frontend = k8s.apps.v1.Deployment(
    "frontend",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="frontend",
        labels={"app": "guestbook", "tier": "frontend"},
    ),
    spec=k8s.apps.v1.DeploymentSpecArgs(
        replicas=1,
        selector=k8s.meta.v1.LabelSelectorArgs(
            match_labels={"app": "guestbook", "tier": "frontend"},
        ),
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={"app": "guestbook", "tier": "frontend"},
                annotations={"prometheus.io/scrape": "true", "prometheus.io/port": "80"},
            ),
            spec=k8s.core.v1.PodSpecArgs(
                containers=[k8s.core.v1.ContainerArgs(
                    name="php-redis",
                    image="pulumi/guestbook-php-redis",
                    ports=[k8s.core.v1.ContainerPortArgs(container_port=80)],
                )],
            ),
        ),
    ),
)

frontend_svc = k8s.core.v1.Service("frontend",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="frontend",
    ),
     spec=k8s.core.v1.ServiceSpecArgs(
    type="ClusterIP",
    ports=[k8s.core.v1.ServicePortArgs(
        port=80,
        protocol="TCP",
        target_port=80
    )],
    selector={
        "app": "guestbook",
        "tier": "frontend",
    },
))

# Redis master deployment
redis_master = k8s.apps.v1.Deployment(
    "redis-master",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="redis-master",
        labels={"app": "redis", "tier": "backend", "role": "leader"},
    ),
    spec=k8s.apps.v1.DeploymentSpecArgs(
        replicas=1,
        selector=k8s.meta.v1.LabelSelectorArgs(
            match_labels={"app": "redis", "role": "leader"},
        ),
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={"app": "redis", "tier": "backend", "role": "leader"},
            ),
            spec=k8s.core.v1.PodSpecArgs(
                containers=[k8s.core.v1.ContainerArgs(
                    name="redis",
                    image="redis:7.2",
                    ports=[k8s.core.v1.ContainerPortArgs(container_port=6379)],
                )],
            ),
        ),
    ),
)

# Redis master service
redis_master_svc = k8s.core.v1.Service(
    "redis-master",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="redis-master",
    ),
    spec=k8s.core.v1.ServiceSpecArgs(
        type="ClusterIP",
        ports=[k8s.core.v1.ServicePortArgs(
            port=6379,
            protocol="TCP",
            target_port=6379,
        )],
        selector={
            "app": "redis",
            "role": "leader",
        },
    ),
)

# Redis replica deployment
redis_follower = k8s.apps.v1.Deployment(
    "redis-follower",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="redis-follower",
        labels={"app": "redis", "tier": "backend", "role": "follower"},
    ),
    spec=k8s.apps.v1.DeploymentSpecArgs(
        replicas=2,
        selector=k8s.meta.v1.LabelSelectorArgs(
            match_labels={"app": "redis", "role": "follower"},
        ),
        template=k8s.core.v1.PodTemplateSpecArgs(
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels={"app": "redis", "tier": "backend", "role": "follower"},
            ),
            spec=k8s.core.v1.PodSpecArgs(
                containers=[k8s.core.v1.ContainerArgs(
                    name="redis",
                    image="redis:7.2",
                    args=["--replicaof", "redis-master", "6379"],
                    ports=[k8s.core.v1.ContainerPortArgs(container_port=6379)],
                )],
            ),
        ),
    ),
)

# Redis replica service
redis_replica_svc = k8s.core.v1.Service(
    "redis-replica",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="redis-replica",
    ),
    spec=k8s.core.v1.ServiceSpecArgs(
        type="ClusterIP",
        ports=[k8s.core.v1.ServicePortArgs(
            port=6379,
            protocol="TCP",
            target_port=6379,
        )],
        selector={
            "app": "redis",
            "role": "follower",
        },
    ),
)

# prometheus helm chart
prometheus_release = Release(
    "kube-prometheus-stack",
    args=ReleaseArgs(
        chart="kube-prometheus-stack",
        version="85.2.2",
        namespace=monitoring_ns.metadata.name,
        repository_opts=RepositoryOptsArgs(
            repo="https://prometheus-community.github.io/helm-charts",
        ),
        values={
            "grafana": {
                "enabled": False,  # Disables the Grafana subchart
            },
            "nodeExporter": {  # Disables node exporter, not needed for this demo and causes issues in WSL2
                "enabled": False,
            },
            "prometheus": {
                "prometheusSpec": {
                    # kube-prometheus-stack uses the Prometheus Operator by default, which relies on
                    # ServiceMonitor CRDs for scrape config. To also honor pod annotations
                    # (prometheus.io/scrape: "true"), we add a custom scrape job that reads
                    # annotation-based targets via kubernetes_sd_configs.
                    "additionalScrapeConfigs": [
                        {
                            "job_name": "kubernetes-pods",
                            "kubernetes_sd_configs": [{"role": "pod"}],
                            "relabel_configs": [
                                {
                                    "source_labels": ["__meta_kubernetes_pod_annotation_prometheus_io_scrape"],
                                    "action": "keep",
                                    "regex": "true",
                                },
                                {
                                    "source_labels": ["__meta_kubernetes_pod_ip", "__meta_kubernetes_pod_annotation_prometheus_io_port"],
                                    "action": "replace",
                                    "target_label": "__address__",
                                    "separator": ":",
                                    "regex": "(.+):(.+)",
                                    "replacement": "$1:$2",
                                },
                            ],
                        }
                    ]
                }
            },
        },
    )
)

# Grafana helm chart
grafana = Release(
    "grafana",
    args=ReleaseArgs(
        chart="grafana",
        version="10.5.15",
        repository_opts=RepositoryOptsArgs(
            repo="https://grafana.github.io/helm-charts",
        ),
        namespace=monitoring_ns.metadata.name,
        values={
            "service": {
                "type": "NodePort",
                "nodePort": 32000,
            },
            "adminPassword": grafana_password,
            "sidecar": {
                "dashboards": {
                    "enabled": True,
                    "label": "grafana_dashboard",
                    "labelValue": "1",  # ConfigMaps with this label are auto-loaded as dashboards
                }
            },
            "datasources": {
                "datasources.yaml": {
                    "apiVersion": 1,
                    "datasources": [
                        {
                            "name": "Prometheus",
                            "type": "prometheus",
                            "url": "http://kube-prometheus-stack-da34-prometheus.monitoring.svc.cluster.local:9090",  # Full FQDN required for cross-namespace service discovery
                            "access": "proxy",
                            "isDefault": True,
                        }
                    ],
                }
            },
        },
    ),
)

# Create ConfigMap for Grafana dashboard
# The grafana_dashboard: "1" label tells the Grafana sidecar to auto-load this dashboard
grafana_dashboard = k8s.core.v1.ConfigMap(
    "guestbook-dashboard",
    metadata=k8s.meta.v1.ObjectMetaArgs(
        name="guestbook-dashboard",
        namespace=monitoring_ns.metadata.name,
        labels={"grafana_dashboard": "1"},
    ),
    data={
        "guestbook-dashboard.json": dashboard_json,
    },
)


# export the Grafana URL and admin password
pulumi.export("grafana_url", "http://localhost:32000")
pulumi.export("grafana_admin_password", grafana_password)