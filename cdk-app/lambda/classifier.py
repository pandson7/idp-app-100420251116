import json
import boto3
from typing import Dict, Any

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')

CATEGORIES = [
    "Dietary Supplement",
    "Stationery", 
    "Kitchen Supplies",
    "Medicine",
    "Driver License",
    "Invoice",
    "W2",
    "Other"
]

def handler(event, context):
    try:
        document_id = event['documentId']
        table_name = event['tableName']
        
        table = dynamodb.Table(table_name)
        
        # Update status to processing classification
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'processing_classification'}
        )
        
        # Get OCR results from previous step
        response = table.get_item(Key={'documentId': document_id})
        if 'Item' not in response:
            raise Exception("Document not found")
        
        ocr_results = response['Item'].get('ocrResults', {})
        text_content = ocr_results.get('rawText', '')
        
        if not text_content:
            raise Exception("No text content found for classification")
        
        # Classify document using Bedrock
        classification_result = classify_document(text_content)
        
        # Store classification results
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET classification = :classification, #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':classification': classification_result,
                ':status': 'classification_complete'
            }
        )
        
        return {
            'statusCode': 200,
            'documentId': document_id,
            'classification': classification_result
        }
        
    except Exception as e:
        # Update status to error with fallback to "Other"
        if 'document_id' in locals() and 'table' in locals():
            fallback_classification = {
                'category': 'Other',
                'confidence': 0.0,
                'reason': f'Classification failed: {str(e)}'
            }
            table.update_item(
                Key={'documentId': document_id},
                UpdateExpression='SET classification = :classification, #status = :status, classificationError = :error',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':classification': fallback_classification,
                    ':status': 'classification_error',
                    ':error': str(e)
                }
            )
        
        return {
            'statusCode': 500,
            'error': str(e)
        }

def classify_document(text_content: str) -> Dict[str, Any]:
    """Classify document using Amazon Bedrock Claude Sonnet model"""
    
    prompt = f"""
    Please classify the following document text into one of these categories:
    {', '.join(CATEGORIES)}
    
    Document text:
    {text_content[:2000]}  # Limit text to avoid token limits
    
    Respond with a JSON object containing:
    - category: the most appropriate category from the list above
    - confidence: a confidence score between 0.0 and 1.0
    - reason: a brief explanation for the classification
    
    Example response:
    {{
        "category": "Invoice",
        "confidence": 0.95,
        "reason": "Document contains invoice number, billing address, and itemized charges"
    }}
    """
    
    try:
        # Prepare the request for Claude Sonnet
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        # Call Bedrock
        response = bedrock.invoke_model(
            modelId='global.anthropic.claude-sonnet-4-20250514-v1:0',
            body=json.dumps(request_body)
        )
        
        # Parse response
        response_body = json.loads(response['body'].read())
        content = response_body['content'][0]['text']
        
        # Extract JSON from response
        try:
            # Try to parse the entire response as JSON
            classification = json.loads(content)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                classification = json.loads(json_match.group())
            else:
                raise Exception("Could not parse classification response")
        
        # Validate the classification
        if classification.get('category') not in CATEGORIES:
            classification['category'] = 'Other'
            classification['reason'] = f"Original category not in allowed list. {classification.get('reason', '')}"
        
        # Ensure confidence is between 0 and 1
        confidence = classification.get('confidence', 0.5)
        if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
            classification['confidence'] = 0.5
        
        return classification
        
    except Exception as e:
        # Return default classification on error
        return {
            'category': 'Other',
            'confidence': 0.0,
            'reason': f'Classification failed: {str(e)}'
        }
