# app/core/logging.py
import logging
import os

import boto3
from botocore.exceptions import ClientError


class CloudWatchLogsHandler(logging.Handler):
    def __init__(self, group, stream, region):
        super().__init__()
        self.group = group
        self.stream = stream
        self.client = boto3.client("logs", region_name=region)
        self.sequence_token = None
        self._ensure_resources()

    def _ensure_resources(self):
        try:
            self.client.create_log_group(logGroupName=self.group)
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                raise
        try:
            self.client.create_log_stream(
                logGroupName=self.group, logStreamName=self.stream
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ResourceAlreadyExistsException":
                streams = self.client.describe_log_streams(
                    logGroupName=self.group,
                    logStreamNamePrefix=self.stream,
                    limit=1,
                )["logStreams"]
                if streams:
                    self.sequence_token = streams[0].get("uploadSequenceToken")
            else:
                raise

    def emit(self, record):
        message = self.format(record)
        event = {"timestamp": int(record.created * 1000), "message": message}
        kwargs = {
            "logGroupName": self.group,
            "logStreamName": self.stream,
            "logEvents": [event],
        }
        if self.sequence_token:
            kwargs["sequenceToken"] = self.sequence_token
        try:
            response = self.client.put_log_events(**kwargs)
            self.sequence_token = response.get("nextSequenceToken")
        except self.client.exceptions.InvalidSequenceTokenException as exc:
            self.sequence_token = exc.response["Error"]["Message"].rsplit(" ", 1)[-1]
            self.emit(record)


def configure_logging():
    region = os.getenv("AWS_REGION", "us-east-1")
    group = os.getenv("CLOUDWATCH_LOG_GROUP", "server")
    stream = os.getenv("ENVIRONMENT", "local")
    handler = CloudWatchLogsHandler(group, stream, region)
    handler.set_name("cloudwatch-handler")
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.set_name("cloudwatch-console")
    console_handler.setFormatter(formatter)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "app"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.propagate = False
        if handler not in logger.handlers:
            logger.addHandler(handler)
        if console_handler not in logger.handlers:
            logger.addHandler(console_handler)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if handler not in root_logger.handlers:
        root_logger.addHandler(handler)
    if console_handler not in root_logger.handlers:
        root_logger.addHandler(console_handler)
