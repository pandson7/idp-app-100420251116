# Design Document

## Architecture Overview

The IDP application follows a serverless architecture using AWS services for scalable document processing. The system consists of a React frontend, API Gateway for REST endpoints, Lambda functions for processing logic, S3 for document storage, and DynamoDB for results storage.

## System Components

### Frontend Layer
- **React Application**: Simple upload interface and results display
- **AWS SDK Integration**: Direct S3 upload with presigned URLs
- **Real-time Updates**: Polling mechanism for processing status

### API Layer
- **API Gateway**: RESTful endpoints for document operations
- **Lambda Functions**:
  - Upload Handler: Generates presigned URLs and initiates processing
  - OCR Processor: Extracts text using Amazon Textract
  - Classifier: Categorizes documents using Amazon Bedrock
  - Summarizer: Generates summaries using Amazon Bedrock
  - Results Handler: Retrieves processing results

### Storage Layer
- **S3 Bucket**: Document storage with lifecycle policies
- **DynamoDB Table**: Flexible schema for processing results
  - Partition Key: documentId
  - Attributes: uploadTime, status, ocrResults, classification, summary

### Processing Pipeline
- **Step Functions**: Orchestrates the sequential processing workflow
- **EventBridge**: Triggers pipeline on S3 upload events
- **Error Handling**: Dead letter queues and retry mechanisms

## Sequence Diagrams

### Document Upload Flow
```
User -> Frontend: Select and upload document
Frontend -> API Gateway: POST /upload
API Gateway -> Lambda: Generate presigned URL
Lambda -> S3: Create presigned URL
Lambda -> DynamoDB: Create document record
Lambda -> API Gateway: Return presigned URL
API Gateway -> Frontend: Presigned URL response
Frontend -> S3: Upload document directly
S3 -> EventBridge: Object created event
EventBridge -> Step Functions: Start processing workflow
```

### Processing Pipeline Flow
```
Step Functions -> OCR Lambda: Extract text
OCR Lambda -> Textract: Analyze document
Textract -> OCR Lambda: Return extracted text
OCR Lambda -> DynamoDB: Store OCR results
OCR Lambda -> Step Functions: OCR complete

Step Functions -> Classifier Lambda: Classify document
Classifier Lambda -> Bedrock: Classify text
Bedrock -> Classifier Lambda: Return category
Classifier Lambda -> DynamoDB: Store classification
Classifier Lambda -> Step Functions: Classification complete

Step Functions -> Summarizer Lambda: Generate summary
Summarizer Lambda -> Bedrock: Summarize text
Bedrock -> Summarizer Lambda: Return summary
Summarizer Lambda -> DynamoDB: Store summary
Summarizer Lambda -> Step Functions: Pipeline complete
```

### Results Retrieval Flow
```
Frontend -> API Gateway: GET /results/{documentId}
API Gateway -> Lambda: Get results
Lambda -> DynamoDB: Query document results
DynamoDB -> Lambda: Return results
Lambda -> API Gateway: Results response
API Gateway -> Frontend: Display results
```

## Technology Stack

### Backend Services
- **Amazon Textract**: OCR text extraction
- **Amazon Bedrock**: Claude Sonnet model for classification and summarization
- **AWS Step Functions**: Workflow orchestration
- **Amazon S3**: Document storage
- **Amazon DynamoDB**: Results database
- **AWS Lambda**: Serverless compute
- **Amazon API Gateway**: REST API endpoints
- **Amazon EventBridge**: Event-driven triggers

### Frontend Technologies
- **React**: User interface framework
- **AWS SDK for JavaScript**: AWS service integration
- **Fetch API**: HTTP requests to backend

## Security Considerations

- **IAM Roles**: Least privilege access for Lambda functions
- **S3 Bucket Policies**: Restricted access with presigned URLs
- **API Gateway**: CORS configuration for frontend access
- **DynamoDB**: Encryption at rest enabled
- **VPC**: Optional VPC deployment for enhanced security

## Performance Considerations

- **Asynchronous Processing**: Non-blocking pipeline execution
- **Provisioned DynamoDB**: Consistent performance for database operations
- **Lambda Concurrency**: Appropriate reserved concurrency limits
- **S3 Transfer Acceleration**: Faster uploads for global users
- **Caching**: API Gateway response caching for frequently accessed results

## Monitoring and Logging

- **CloudWatch Logs**: Centralized logging for all Lambda functions
- **CloudWatch Metrics**: Performance monitoring and alerting
- **X-Ray Tracing**: Distributed tracing for debugging
- **Step Functions Execution History**: Workflow monitoring and troubleshooting
