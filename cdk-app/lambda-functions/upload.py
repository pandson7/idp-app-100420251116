import json
import boto3
import uuid
import os
from datetime import datetime

s3_client = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')

def handler(event, context):
    try:
        table_name = os.environ['TABLE_NAME']
        bucket_name = os.environ['BUCKET_NAME']
        table = dynamodb.Table(table_name)
        
        body = json.loads(event.get('body', '{}'))
        document_id = str(uuid.uuid4())
        file_name = body.get('fileName', 'document')
        
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': bucket_name, 'Key': document_id},
            ExpiresIn=3600
        )
        
        table.put_item(
            Item={
                'documentId': document_id,
                'fileName': file_name,
                'uploadTime': datetime.utcnow().isoformat(),
                'status': 'uploaded',
                'ocrResults': {},
                'classification': {},
                'summary': {}
            }
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps({
                'documentId': document_id,
                'uploadUrl': presigned_url
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
            },
            'body': json.dumps({'error': str(e)})
        }
