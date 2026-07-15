import boto3
import json
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('ip_logs')

def handler(event, context):
    # Check for admin API key
    headers = event.get('headers') or {}
    api_key = headers.get('x-admin-key') or headers.get('X-Admin-Key', '')

    import os
    expected_key = os.environ.get('ADMIN_API_KEY', '')
    if not expected_key or api_key != expected_key:
        return {
            'statusCode': 403,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'error': 'Forbidden'})
        }

    result = table.scan()
    items = result.get('Items', [])

    # Handle pagination
    while 'LastEvaluatedKey' in result:
        result = table.scan(ExclusiveStartKey=result['LastEvaluatedKey'])
        items.extend(result.get('Items', []))

    items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    origin = event.get('headers', {}).get('origin', '')

    return {
        'statusCode': 200,
        'headers': {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Headers': 'Content-Type,X-Admin-Key',
            'Access-Control-Allow-Methods': 'GET,OPTIONS',
            'Content-Type': 'application/json'
        },
        'body': json.dumps({'items': items, 'count': len(items)})
    }
