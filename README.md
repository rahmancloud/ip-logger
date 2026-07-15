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
