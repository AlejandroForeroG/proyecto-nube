import logging
import os
from datetime import datetime, timezone
from typing import Dict

import boto3

logger = logging.getLogger(__name__)


class CloudWatchMetrics:
    def __init__(self):
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.namespace = os.getenv(
            "CLOUDWATCH_METRICS_NAMESPACE", "ProyectoNube/Application"
        )
        self.enabled = os.getenv("ENABLE_CW_METRICS", "true").lower() == "true"

        if self.enabled:
            try:
                self.client = boto3.client("cloudwatch", region_name=self.region)
                logger.info(
                    f"CloudWatch Metrics initialized (namespace: {self.namespace})"
                )
            except Exception as e:
                logger.error(f"Failed to initialize CloudWatch client: {e}")
                self.enabled = False

    def put_metric(
        self,
        metric_name: str,
        value: float,
        unit: str = "Count",
        dimensions: Dict[str, str] | None = None,
    ):
        if not self.enabled:
            return

        try:
            metric_data = {
                "MetricName": metric_name,
                "Value": value,
                "Unit": unit,
                "Timestamp": datetime.now(timezone.utc),
            }

            if dimensions:
                metric_data["Dimensions"] = [
                    {"Name": k, "Value": v} for k, v in dimensions.items()
                ]

            self.client.put_metric_data(
                Namespace=self.namespace, MetricData=[metric_data]
            )
        except Exception as e:
            logger.warning(f"Error sending metric to CloudWatch: {e}")

    def increment_counter(
        self, metric_name: str, dimensions: Dict[str, str] | None = None
    ):
        self.put_metric(metric_name, 1.0, "Count", dimensions)


_metrics = None


def get_metrics() -> CloudWatchMetrics:
    global _metrics
    if _metrics is None:
        _metrics = CloudWatchMetrics()
    return _metrics
