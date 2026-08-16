"""
One-time (idempotent) setup of the AWS resources for S3-event-driven policy PDF
ingestion: a main SQS queue + dead-letter queue, a queue policy scoped to the
policies bucket, and a bucket notification wiring ObjectCreated events for
*.pdf under the configured prefix to the main queue.

Requires POLICIES_S3_BUCKET (and optionally POLICIES_S3_PREFIX, AWS_REGION) set
in .env, and AWS credentials with S3/SQS admin permissions in the environment
(e.g. `aws configure`, or exported AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY).

The bucket itself must already exist -- this script does not create it.

Run from project root: python scripts/setup_s3_ingestion.py

Prints the resulting queue URL -- copy it into POLICIES_SQS_QUEUE_URL in .env
(and into the deployed app's environment) once the script finishes.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

MAIN_QUEUE_NAME = "policies-ingest-queue"
DLQ_NAME = "policies-ingest-dlq"
MAX_RECEIVE_COUNT = 3


def _get_or_create_queue(sqs, name: str, attributes: dict | None = None) -> str:
    try:
        return sqs.get_queue_url(QueueName=name)["QueueUrl"]
    except ClientError as e:
        if e.response["Error"]["Code"] != "AWS.SimpleQueueService.NonExistentQueue":
            raise
    print(f"Creating queue {name} ...")
    response = sqs.create_queue(QueueName=name, Attributes=attributes or {})
    return response["QueueUrl"]


def _queue_arn(sqs, queue_url: str) -> str:
    return sqs.get_queue_attributes(QueueUrl=queue_url, AttributeNames=["QueueArn"])["Attributes"]["QueueArn"]


def main():
    if not settings.POLICIES_S3_BUCKET:
        print("POLICIES_S3_BUCKET is not set in .env -- nothing to configure.")
        sys.exit(1)

    region = settings.AWS_REGION or None
    sqs = boto3.client("sqs", region_name=region)
    s3 = boto3.client("s3", region_name=region)
    bucket = settings.POLICIES_S3_BUCKET
    prefix = settings.POLICIES_S3_PREFIX

    try:
        s3.head_bucket(Bucket=bucket)
    except ClientError as e:
        print(f"Bucket {bucket!r} is not reachable with current credentials ({e}). Create it first.")
        sys.exit(1)

    # ── Dead-letter queue ────────────────────────────────────────────────────
    dlq_url = _get_or_create_queue(sqs, DLQ_NAME)
    dlq_arn = _queue_arn(sqs, dlq_url)
    print(f"DLQ ready: {dlq_url}")

    # ── Main queue, with redrive policy pointing at the DLQ ─────────────────
    redrive_policy = json.dumps({"deadLetterTargetArn": dlq_arn, "maxReceiveCount": MAX_RECEIVE_COUNT})
    main_url = _get_or_create_queue(sqs, MAIN_QUEUE_NAME, attributes={"RedrivePolicy": redrive_policy})
    sqs.set_queue_attributes(QueueUrl=main_url, Attributes={"RedrivePolicy": redrive_policy})
    main_arn = _queue_arn(sqs, main_url)
    print(f"Main queue ready: {main_url}")

    # ── Queue policy: only this bucket may SendMessage ──────────────────────
    bucket_arn = f"arn:aws:s3:::{bucket}"
    queue_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowS3BucketToSendMessage",
                "Effect": "Allow",
                "Principal": {"Service": "s3.amazonaws.com"},
                "Action": "sqs:SendMessage",
                "Resource": main_arn,
                "Condition": {"ArnEquals": {"aws:SourceArn": bucket_arn}},
            }
        ],
    }
    sqs.set_queue_attributes(QueueUrl=main_url, Attributes={"Policy": json.dumps(queue_policy)})
    print("Queue policy set (SendMessage restricted to this bucket).")

    # ── Bucket notification: ObjectCreated -> main queue, filtered to prefix/.pdf ──
    filter_rules = [{"Name": "Suffix", "Value": ".pdf"}]
    if prefix:
        filter_rules.append({"Name": "Prefix", "Value": prefix})

    s3.put_bucket_notification_configuration(
        Bucket=bucket,
        NotificationConfiguration={
            "QueueConfigurations": [
                {
                    "QueueArn": main_arn,
                    "Events": ["s3:ObjectCreated:*"],
                    "Filter": {"Key": {"FilterRules": filter_rules}},
                }
            ]
        },
    )
    print(f"Bucket notification configured on {bucket!r} (prefix={prefix!r}, suffix=.pdf).")

    print("\nDone. Set this in .env (and the deployed app's environment):")
    print(f"POLICIES_SQS_QUEUE_URL={main_url}")


if __name__ == "__main__":
    main()
