import json
import boto3
from typing import Dict, Any

bedrock = boto3.client('bedrock-runtime')
dynamodb = boto3.resource('dynamodb')

def handler(event, context):
    try:
        document_id = event['documentId']
        table_name = event['tableName']
        
        table = dynamodb.Table(table_name)
        
        # Update status to processing summarization
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={':status': 'processing_summarization'}
        )
        
        # Get document data from previous steps
        response = table.get_item(Key={'documentId': document_id})
        if 'Item' not in response:
            raise Exception("Document not found")
        
        item = response['Item']
        ocr_results = item.get('ocrResults', {})
        classification = item.get('classification', {})
        
        text_content = ocr_results.get('rawText', '')
        document_category = classification.get('category', 'Other')
        
        if not text_content:
            raise Exception("No text content found for summarization")
        
        # Generate summary using Bedrock
        summary_result = generate_summary(text_content, document_category)
        
        # Store summary results
        table.update_item(
            Key={'documentId': document_id},
            UpdateExpression='SET summary = :summary, #status = :status',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':summary': summary_result,
                ':status': 'complete'
            }
        )
        
        return {
            'statusCode': 200,
            'documentId': document_id,
            'summary': summary_result
        }
        
    except Exception as e:
        # Update status to error
        if 'document_id' in locals() and 'table' in locals():
            error_summary = {
                'text': f'Summarization failed: {str(e)}',
                'keyPoints': [],
                'generatedAt': context.aws_request_id if context else 'unknown'
            }
            table.update_item(
                Key={'documentId': document_id},
                UpdateExpression='SET summary = :summary, #status = :status, summaryError = :error',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':summary': error_summary,
                    ':status': 'summarization_error',
                    ':error': str(e)
                }
            )
        
        return {
            'statusCode': 500,
            'error': str(e)
        }

def generate_summary(text_content: str, document_category: str) -> Dict[str, Any]:
    """Generate document summary using Amazon Bedrock Claude Sonnet model"""
    
    # Customize prompt based on document category
    category_instructions = get_category_instructions(document_category)
    
    prompt = f"""
    Please create a concise summary of the following {document_category} document.
    
    {category_instructions}
    
    Document text:
    {text_content[:3000]}  # Limit text to avoid token limits
    
    Respond with a JSON object containing:
    - text: a concise summary (2-3 sentences)
    - keyPoints: an array of 3-5 key points or important details
    - category: the document category
    
    Example response:
    {{
        "text": "This invoice from ABC Company shows a total of $1,234.56 for office supplies delivered on March 15, 2024.",
        "keyPoints": [
            "Invoice #12345 from ABC Company",
            "Total amount: $1,234.56",
            "Items: Office supplies",
            "Delivery date: March 15, 2024"
        ],
        "category": "{document_category}"
    }}
    """
    
    try:
        # Prepare the request for Claude Sonnet
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1500,
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
            summary = json.loads(content)
        except json.JSONDecodeError:
            # If that fails, try to extract JSON from the response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                summary = json.loads(json_match.group())
            else:
                # Fallback: create summary from raw content
                summary = {
                    "text": content[:500] + "..." if len(content) > 500 else content,
                    "keyPoints": [content[:200] + "..." if len(content) > 200 else content],
                    "category": document_category
                }
        
        # Ensure required fields exist
        if 'text' not in summary:
            summary['text'] = "Summary could not be generated"
        if 'keyPoints' not in summary:
            summary['keyPoints'] = []
        if 'category' not in summary:
            summary['category'] = document_category
            
        summary['generatedAt'] = context.aws_request_id if 'context' in globals() else 'unknown'
        
        return summary
        
    except Exception as e:
        # Return error summary
        return {
            'text': f'Summarization failed: {str(e)}',
            'keyPoints': [],
            'category': document_category,
            'generatedAt': context.aws_request_id if 'context' in globals() else 'unknown'
        }

def get_category_instructions(category: str) -> str:
    """Get category-specific instructions for summarization"""
    instructions = {
        "Invoice": "Focus on vendor, amount, date, and items purchased.",
        "W2": "Focus on employer, employee, tax year, and key tax amounts.",
        "Driver License": "Focus on name, license number, expiration date, and restrictions.",
        "Medicine": "Focus on medication name, dosage, instructions, and prescriber.",
        "Dietary Supplement": "Focus on product name, ingredients, dosage, and manufacturer.",
        "Kitchen Supplies": "Focus on product names, quantities, and specifications.",
        "Stationery": "Focus on items, quantities, and specifications.",
        "Other": "Focus on the main purpose and key information in the document."
    }
    
    return instructions.get(category, instructions["Other"])
