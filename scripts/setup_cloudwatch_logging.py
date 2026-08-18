"""
One-time (idempotent) setup of the CloudWatch log group used by the app's
CloudWatch log handler (see app/core/logging.py). Only creates the log group
and sets a retention policy -- log streams are created automatically by
watchtower at runtime.

Requires CLOUDWATCH_LOG_GROUP (and optionally AWS_REGION) set in .env, and AWS
credentials with logs:CreateLogGroup / logs:PutRetentionPolicy permissions in
the environment.

Run from project root: python scripts/setup_cloudwatch_logging.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings

RETENTION_DAYS = 30


def main():
    if not settings.CLOUDWATCH_LOG_GROUP:
        print("CLOUDWATCH_LOG_GROUP is not set in .env -- nothing to configure.")
        sys.exit(1)

    logs = boto3.client("logs", region_name=settings.AWS_REGION or None)
    group = settings.CLOUDWATCH_LOG_GROUP

    try:
        logs.create_log_group(logGroupName=group)
        print(f"Created log group {group!r}.")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
            raise
        print(f"Log group {group!r} already exists.")

    logs.put_retention_policy(logGroupName=group, retentionInDays=RETENTION_DAYS)
    print(f"Retention set to {RETENTION_DAYS} days.")


if __name__ == "__main__":
    main()
