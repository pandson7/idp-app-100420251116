import json
import boto3
import re
import os
from decimal import Decimal

textract = boto3.client('textract')
bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')

CATEGORIES = ["Dietary Supplement", "Stationery", "Kitchen Supplies", "Medicine", "Driver License", "Invoice", "W2", "Other"]

def handler(event, context):
    try:
        # Extract document info from S3 event
        bucket_name = event['detail']['bucket']['name']
        document_id = event['detail']['object']['key']
        
        table_name = os.environ['TABLE_NAME']
        table = dynamodb.Table(table_name)
        
        # Step 1: OCR Processing
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'processing_ocr'}
        )
        
        ocr_results = perform_ocr(bucket_name, document_id)
        
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET ocrResults = :ocr, #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':ocr': ocr_results,
                ':status': 'processing_classification'
            }
        )
        
        # Step 2: Classification
        classification = classify_document(ocr_results.get('rawText', ''))
        
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET classification = :classification, #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':classification': classification,
                ':status': 'processing_summarization'
            }
        )
        
        # Step 3: Summarization
        summary = generate_summary(ocr_results.get('rawText', ''), classification.get('category', 'Other'))
        
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET summary = :summary, #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':summary': summary,
                ':status': 'complete'
            }
        )
        
        return {'statusCode': 200, 'message': 'Processing complete'}
        
    except Exception as e:
        if 'document_id' in locals() and 'table' in locals():
            table.update_item(
                Key={'documentId': document_id},
                UpdateExpression='SET #status = :status, processingError = :error',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'error',
                    ':error': str(e)
                }
            )
        return {'statusCode': 500, 'error': str(e)}

def perform_ocr(bucket_name, document_id):
    try:
        response = textract.analyze_document(
            Document={'S3Object': {'Bucket': bucket_name, 'Name': document_id}},
            FeatureTypes=['FORMS', 'TABLES']
        )
        
        blocks = response['Blocks']
        all_text = []
        key_value_pairs = {}
        
        for block in blocks:
            if block['BlockType'] == 'LINE':
                all_text.append(block['Text'])
        
        raw_text = '\n'.join(all_text)
        
        # Handle markdown JSON
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        matches = re.findall(json_pattern, raw_text, re.DOTALL | re.IGNORECASE)
        
        result = {
            'keyValuePairs': key_value_pairs,
            'rawText': raw_text,
            'extractedAt': 'lambda'
        }
        
        if matches:
            parsed_json = []
            for match in matches:
                try:
                    parsed_json.append(json.loads(match))
                except:
                    pass
            if parsed_json:
                result['markdownJson'] = parsed_json
        
        return result
    except Exception as e:
        return {'error': str(e), 'rawText': '', 'keyValuePairs': {}}

def classify_document(text_content):
    if not text_content:
        return {'category': 'Other', 'confidence': Decimal('0.0'), 'reason': 'No text content'}
    
    prompt = f"""Classify this document into one of these categories: {', '.join(CATEGORIES)}

Document: {text_content[:2000]}

Respond with JSON: {{"category": "name", "confidence": 0.95, "reason": "explanation"}}"""
    
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = bedrock.invoke_model(
            modelId='global.anthropic.claude-sonnet-4-20250514-v1:0',
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        content = response_body['content'][0]['text']
        
        try:
            classification = json.loads(content)
        except:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                classification = json.loads(json_match.group())
            else:
                classification = {'category': 'Other', 'confidence': 0.5, 'reason': 'Parse error'}
        
        if classification.get('category') not in CATEGORIES:
            classification['category'] = 'Other'
        
        # Convert confidence to Decimal for DynamoDB
        confidence = classification.get('confidence', 0.5)
        if isinstance(confidence, (int, float)):
            classification['confidence'] = Decimal(str(confidence))
        
        return classification
        
    except Exception as e:
        return {'category': 'Other', 'confidence': Decimal('0.0'), 'reason': f'Error: {str(e)}'}

def generate_summary(text_content, document_category):
    if not text_content:
        return {'text': 'No content to summarize', 'keyPoints': [], 'category': document_category}
    
    prompt = f"""Create a summary of this {document_category} document.

Document: {text_content[:3000]}

Respond with JSON: {{"text": "brief summary", "keyPoints": ["point1", "point2"], "category": "{document_category}"}}"""
    
    try:
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": prompt}]
        }
        
        response = bedrock.invoke_model(
            modelId='global.anthropic.claude-sonnet-4-20250514-v1:0',
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response['body'].read())
        content = response_body['content'][0]['text']
        
        try:
            summary = json.loads(content)
        except:
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                summary = json.loads(json_match.group())
            else:
                summary = {
                    "text": content[:500] if content else "Summary unavailable",
                    "keyPoints": [content[:200]] if content else [],
                    "category": document_category
                }
        
        summary['generatedAt'] = 'lambda'
        return summary
        
    except Exception as e:
        return {
            'text': f'Error: {str(e)}',
            'keyPoints': [],
            'category': document_category,
            'generatedAt': 'lambda'
        }
