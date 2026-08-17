# Policy Ingestion DLQ Runbook

## What lands here

`policies-ingest-dlq` receives a message when a policy PDF has failed
ingestion 3 times in a row (`RedrivePolicy.maxReceiveCount: 3` on
`policies-ingest-queue`). The consumer (`app/workers/s3_ingest_consumer.py`)
never deletes a message on failure — SQS redelivers it after the 30s
visibility timeout, up to 3 times, then moves it here automatically. A
message in the DLQ means: this PDF needs a human to look at it, not another
automatic retry.

## Alerting

- **SNS topic**: `policies-ingest-dlq-alerts` (account `432510056936`,
  `ap-south-1`)
- **CloudWatch alarm**: `policies-ingest-dlq-has-messages` — fires when
  `ApproximateNumberOfMessagesVisible` on the DLQ goes above 0
- Subscribed email gets notified on both alarm (`ALARM`) and recovery (`OK`)

To change the alert email:
```bash
aws sns subscribe --topic-arn arn:aws:sns:ap-south-1:432510056936:policies-ingest-dlq-alerts \
  --protocol email --notification-endpoint <new-email> --profile insurance-ai
```
(the new address must click the confirmation link AWS sends before it starts receiving)

## 1. Inspect what's there

```bash
aws sqs receive-message \
  --queue-url https://sqs.ap-south-1.amazonaws.com/432510056936/policies-ingest-dlq \
  --max-number-of-messages 10 \
  --visibility-timeout 300 \
  --profile insurance-ai
```
This makes the message(s) invisible for 5 minutes while you look — it does
**not** delete them, so if you do nothing further they reappear and stay in
the DLQ. Each message body is the original S3 event JSON; the PDF key is at
`Records[0].s3.object.key`.

Cross-check the actual failure reason in the app logs around when it first
failed (search for the filename):
```bash
aws lightsail get-container-log --service-name insurance-advisor-ai \
  --container-name app --region ap-south-1 \
  --start-time <unix-ts-near-failure> --profile insurance-ai
```
Look for `SQS ingest: <file> could not be read, will retry/DLQ — ...` —
the text after the dash is the real cause (e.g. `invalid pdf header`,
`EOF marker not found`, an S3 permission error, etc.).

## 2. Decide: bad file, or transient failure?

**Genuinely corrupt/invalid PDF** (extraction error, wrong file type,
truncated upload): the file itself needs fixing, not a retry.
1. Delete the bad object and the DLQ message (below)
2. Fix/re-export the PDF properly
3. Upload the corrected file to S3 under the same key — this creates a
   fresh `ObjectCreated` event and goes through the normal pipeline again

**Transient failure** (S3 fetch error, temporary AWS outage, OpenAI API
blip during embedding): the same bytes would likely succeed now. Redrive it
back to the main queue instead of re-uploading:
```bash
aws sqs start-message-move-task \
  --source-arn arn:aws:sqs:ap-south-1:432510056936:policies-ingest-dlq \
  --profile insurance-ai
```
This moves messages from the DLQ back to `policies-ingest-queue` for the
consumer to pick up again. Check progress with:
```bash
aws sqs list-message-move-tasks \
  --source-arn arn:aws:sqs:ap-south-1:432510056936:policies-ingest-dlq \
  --profile insurance-ai
```

## 3. Delete a message you've resolved (or don't want retried)

Use the `ReceiptHandle` from the `receive-message` call above:
```bash
aws sqs delete-message \
  --queue-url https://sqs.ap-south-1.amazonaws.com/432510056936/policies-ingest-dlq \
  --receipt-handle "<ReceiptHandle-from-receive-message>" \
  --profile insurance-ai
```
Or, to clear everything in the DLQ at once (careful — this is a blunt
instrument, only use it once you've confirmed nothing in there still needs
attention):
```bash
aws sqs purge-queue \
  --queue-url https://sqs.ap-south-1.amazonaws.com/432510056936/policies-ingest-dlq \
  --profile insurance-ai
```

## Verified behavior

This whole path was tested live in production: a corrupt PDF was uploaded,
failed 3 times over ~90s (30s visibility timeout apart), correctly landed in
the DLQ, and the app's `/health` endpoint returned 200 continuously
throughout — one bad file never affects ingestion of other files or the
app's availability.
