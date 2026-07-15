# IP Logger

A serverless AWS application that serves a secure web page where visitors can record their IP address, with an admin dashboard to view all logged IPs.

## Architecture

```
Browser → CloudFront (HTTPS) → S3 (static HTML/JS)
                                      │
                              API Gateway (REST)
                                      │
                        ┌─────────────┴─────────────┐
                  Lambda: log_ip             Lambda: get_ips
                        │                           │
                        └─────────── DynamoDB ──────┘
```

| Service | Purpose |
|---|---|
| **CloudFront** | HTTPS delivery, HTTP→HTTPS redirect, caches S3 content |
| **S3** | Private bucket hosting static HTML/JS (no public access) |
| **API Gateway** | REST API — `POST /log-ip` and `GET /admin/ips` |
| **Lambda** | `ip-logger-log` writes IPs; `ip-logger-get` reads all IPs |
| **DynamoDB** | `ip_logs` table (pay-per-request), stores `id`, `ip_address`, `timestamp` |

## Repository Structure

```
├── template.yaml          # CloudFormation template (full stack)
├── lambda/
│   ├── log_ip.py          # Lambda: record IP address to DynamoDB
│   └── get_ips.py         # Lambda: list all IP records (admin, key-protected)
├── static/
│   ├── index.html         # Public page with "Record My IP" button
│   └── admin.html         # Admin dashboard — view/search all logged IPs
└── README.md
```

## Deploy with CloudFormation

### Prerequisites
- AWS CLI configured with sufficient permissions
- An S3 bucket for packaging (or use inline code in the template)

### 1. Deploy the stack

```bash
aws cloudformation deploy \
  --template-file template.yaml \
  --stack-name ip-logger \
  --parameter-overrides AdminApiKey=YOUR_STRONG_SECRET_HERE \
  --capabilities CAPABILITY_NAMED_IAM \
  --region ap-southeast-5
```

### 2. Get the URLs

```bash
aws cloudformation describe-stacks \
  --stack-name ip-logger \
  --query 'Stacks[0].Outputs' \
  --output table
```

### 3. Upload static files

After the stack is created, get the S3 bucket name from outputs and upload:

```bash
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name ip-logger \
  --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
  --output text)

# Update the API_URL in both HTML files to match the ApiEndpoint output, then:
aws s3 cp static/index.html s3://$BUCKET/index.html --content-type text/html
aws s3 cp static/admin.html s3://$BUCKET/admin.html --content-type text/html
```

### 4. Update HTML with your API URL

In both `static/index.html` and `static/admin.html`, replace:
```javascript
const API_URL = 'https://YOUR_API_ID.execute-api.REGION.amazonaws.com/prod';
```
with the `ApiEndpoint` value from the CloudFormation stack outputs.

## Usage

### Public page (`/index.html`)
Open the page and click **"Record My IP"**. Your IP address is sent via `POST /log-ip` and stored in DynamoDB with a UTC timestamp.

### Admin page (`/admin.html`)
Enter the `AdminApiKey` you used during deployment. The dashboard shows:
- Total entries, unique IPs, and today's count
- Full table of IPs with timestamps, sortable and searchable

## Security

- S3 bucket has **all public access blocked** — only CloudFront can read it via OAC
- All traffic is **HTTPS only** (CloudFront enforces HTTP → HTTPS redirect)
- IP is sourced from **API Gateway `sourceIp`** (not a user-supplied header — cannot be spoofed)
- Admin endpoint protected by **API key in `X-Admin-Key` header**, validated inside Lambda
- Lambda IAM role is **least-privilege**: only `PutItem` and `Scan` on the specific DynamoDB table
- CORS origin is reflected from the request (lock it to your CloudFront domain in production)

## Cost Estimate (ap-southeast-5 — Asia Pacific, Malaysia)

Prices sourced from the AWS Pricing API. All figures in USD. This stack is designed to cost nearly nothing at low traffic — every service either has a generous free tier or is pay-per-request with no idle cost.

### Pricing per service

| Service | Dimension | Price |
|---|---|---|
| **Lambda** | Requests | $0.18 per 1M requests |
| **Lambda** | Duration (x86, 128 MB) | $0.0000135 per GB-second |
| **API Gateway** (REST) | Requests | $0.0000038 per request (~$3.83 per 1M) |
| **DynamoDB** (on-demand) | Write request unit | $0.64 per 1M WRUs |
| **DynamoDB** (on-demand) | Read request unit | $0.1285 per 1M RRUs |
| **DynamoDB** | Storage | Free for first 25 GB/month |
| **S3** | Storage (Standard) | $0.0225 per GB/month |
| **S3** | PUT/POST requests | $0.0045 per 1,000 |
| **S3** | GET requests | $0.00036 per 1,000 |
| **CloudFront** | HTTPS requests | $0.012 per 10,000 |
| **CloudFront** | Data transfer out | $0.120 per GB (first 10 TB) |

### Monthly cost scenarios

#### Scenario 1 — Low traffic (1,000 button clicks/month)

| Service | Usage | Cost |
|---|---|---|
| Lambda (log + get) | ~2,000 invocations × 200ms × 128MB | < $0.01 |
| API Gateway | 2,000 requests | < $0.01 |
| DynamoDB | 1,000 WRUs + occasional reads | < $0.01 |
| S3 | ~2 KB stored, ~2,000 GET requests | < $0.01 |
| CloudFront | ~2,000 HTTPS requests + ~1 MB transfer | < $0.01 |
| **Total** | | **~$0.00 – $0.05/month** |

> Comfortably within AWS Free Tier limits (Lambda: 1M req free, DynamoDB: 25 GB + 2.5M reads/writes free, S3: 5 GB free, CloudFront: 1 TB transfer + 10M requests free for first 12 months).

#### Scenario 2 — Moderate traffic (100,000 button clicks/month)

| Service | Usage | Cost |
|---|---|---|
| Lambda | 200,000 invocations × 200ms × 128MB | ~$0.07 |
| API Gateway | 200,000 requests | ~$0.77 |
| DynamoDB | 100,000 WRUs + 10,000 RRUs | ~$0.07 |
| S3 | Negligible storage + requests | ~$0.01 |
| CloudFront | 200,000 requests + ~100 MB transfer | ~$0.26 |
| **Total** | | **~$1.18/month** |

#### Scenario 3 — High traffic (1,000,000 button clicks/month)

| Service | Usage | Cost |
|---|---|---|
| Lambda | 2M invocations × 200ms × 128MB | ~$0.68 |
| API Gateway | 2M requests | ~$7.65 |
| DynamoDB | 1M WRUs + 100K RRUs | ~$0.65 |
| S3 | ~1 MB storage + GET requests | ~$0.01 |
| CloudFront | 2M requests + ~1 GB transfer | ~$2.36 |
| **Total** | | **~$11.35/month** |

> At this scale, consider switching from REST API Gateway to HTTP API Gateway (60–70% cheaper at $0.0000011 per request) to reduce API costs to ~$2.20/month.

### Cost optimisation tips

- **HTTP API vs REST API** — REST API is used here for familiarity; HTTP API would cut API Gateway costs by ~70%.
- **CloudFront free tier** — 1 TB data transfer out + 10M HTTPS requests free per month for the first 12 months.
- **DynamoDB free tier** — 25 GB storage + 2.5M read/write request units free, permanently.
- **Lambda free tier** — 1M requests + 400,000 GB-seconds free per month, permanently.
- **TTL on DynamoDB** — Add a TTL attribute to auto-expire old records and keep storage near zero.

---

## Tear Down

```bash
# Empty the S3 bucket first (required before stack deletion)
BUCKET=$(aws cloudformation describe-stacks \
  --stack-name ip-logger \
  --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' \
  --output text)
aws s3 rm s3://$BUCKET --recursive

# Delete the stack
aws cloudformation delete-stack --stack-name ip-logger --region ap-southeast-5
```
