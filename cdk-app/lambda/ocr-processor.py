import json
import boto3
import re
from typing import Dict, Any

textract = boto3.client('textract')
dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

def handler(event, context):
    try:
        document_id = event['documentId']
        bucket_name = event['bucketName']
        table_name = event['tableName']
        
        table = dynamodb.Table(table_name)
        
        # Update status to processing
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'processing_ocr'}
        )
        
        # Analyze document with Textract
        response = textract.analyze_document(
            Document={
                'S3Object': {
                    'Bucket': bucket_name,
                    'Name': document_id
                }
            },
            FeatureTypes=['FORMS', 'TABLES']
        )
        
        # Extract key-value pairs
        ocr_results = extract_key_value_pairs(response)
        
        # Handle markdown-wrapped JSON
        ocr_results = handle_markdown_json(ocr_results)
        
        # Store OCR results in DynamoDB
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET ocrResults = :ocr, #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':ocr': ocr_results,
                ':status': 'ocr_complete'
            }
        )
        
        return {
            'statusCode': 200,
            'documentId': document_id,
            'ocrResults': ocr_results
        }
        
    except Exception as e:
        # Update status to error
        if 'document_id' in locals() and 'table' in locals():
            table.update_item(
                Key={'documentId': document_id},
                UpdateExpression='SET #status = :status, ocrError = :error',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'ocr_error',
                    ':error': str(e)
                }
            )
        
        return {
            'statusCode': 500,
            'error': str(e)
        }

def extract_key_value_pairs(textract_response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key-value pairs from Textract response"""
    blocks = textract_response['Blocks']
    
    # Create maps for blocks
    block_map = {}
    relationship_map = {}
    
    for block in blocks:
        block_id = block['Id']
        block_map[block_id] = block
        
        if 'Relationships' in block:
            relationship_map[block_id] = block['Relationships']
    
    # Extract key-value pairs
    key_value_pairs = {}
    
    for block in blocks:
        if block['BlockType'] == 'KEY_VALUE_SET':
            if 'KEY' in block['EntityTypes']:
                key_text = get_text(block, block_map, relationship_map)
                
                # Find the corresponding VALUE
                if block['Id'] in relationship_map:
                    for relationship in relationship_map[block['Id']]:
                        if relationship['Type'] == 'VALUE':
                            for value_id in relationship['Ids']:
                                value_block = block_map[value_id]
                                value_text = get_text(value_block, block_map, relationship_map)
                                if key_text and value_text:
                                    key_value_pairs[key_text.strip()] = value_text.strip()
    
    # Also extract all text as raw content
    all_text = []
    for block in blocks:
        if block['BlockType'] == 'LINE':
            all_text.append(block['Text'])
    
    return {
        'keyValuePairs': key_value_pairs,
        'rawText': '\n'.join(all_text),
        'extractedAt': context.aws_request_id if 'context' in globals() else 'unknown'
    }

def get_text(block, block_map, relationship_map):
    """Get text from a block and its children"""
    text = ''
    if 'Relationships' in block:
        for relationship in block['Relationships']:
            if relationship['Type'] == 'CHILD':
                for child_id in relationship['Ids']:
                    child = block_map[child_id]
                    if child['BlockType'] == 'WORD':
                        text += child['Text'] + ' '
    return text.strip()

def handle_markdown_json(ocr_results: Dict[str, Any]) -> Dict[str, Any]:
    """Handle markdown-wrapped JSON in OCR results"""
    raw_text = ocr_results.get('rawText', '')
    
    # Look for JSON wrapped in markdown code blocks
    json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    matches = re.findall(json_pattern, raw_text, re.DOTALL | re.IGNORECASE)
    
    parsed_json_objects = []
    for match in matches:
        try:
            parsed_json = json.loads(match)
            parsed_json_objects.append(parsed_json)
        except json.JSONDecodeError:
            continue
    
    if parsed_json_objects:
        ocr_results['markdownJson'] = parsed_json_objects
    
    return ocr_results
