import boto3
import uuid
import json
from datetime import datetime, timezone

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ip_logs')

def handler(event, context):
    # API Gateway provides the real source IP
    ip = event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown')

    item = {
        'id': str(uuid.uuid4()),
        'ip_address': ip,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    table.put_item(Item=item)

    origin = event.get('headers', {}).get('origin', '')

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST,OPTIONS',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({'message': 'IP logged', 'ip': ip})
    }
