import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as path from 'path';

export class IdpApp100420251116Stack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const suffix = '100420251116';

    // S3 Bucket for document storage
    const documentBucket = new s3.Bucket(this, `DocumentBucket${suffix}`, {
      bucketName: `idp-documents-${suffix}`,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      cors: [{
        allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.POST, s3.HttpMethods.PUT],
        allowedOrigins: ['*'],
        allowedHeaders: ['*'],
      }],
      eventBridgeEnabled: true,
    });

    // DynamoDB table for results storage
    const resultsTable = new dynamodb.Table(this, `ResultsTable${suffix}`, {
      tableName: `idp-results-${suffix}`,
      partitionKey: { name: 'documentId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PROVISIONED,
      readCapacity: 5,
      writeCapacity: 5,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // IAM role for Lambda functions
    const lambdaRole = new iam.Role(this, `LambdaRole${suffix}`, {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
      inlinePolicies: {
        S3Access: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
              resources: [documentBucket.bucketArn + '/*'],
            }),
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['s3:ListBucket'],
              resources: [documentBucket.bucketArn],
            }),
          ],
        }),
        DynamoDBAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['dynamodb:PutItem', 'dynamodb:GetItem', 'dynamodb:UpdateItem', 'dynamodb:Query'],
              resources: [resultsTable.tableArn],
            }),
          ],
        }),
        TextractAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['textract:AnalyzeDocument', 'textract:DetectDocumentText'],
              resources: ['*'],
            }),
          ],
        }),
        BedrockAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: ['bedrock:InvokeModel'],
              resources: [
                'arn:aws:bedrock:*:*:inference-profile/global.anthropic.claude-sonnet-4-20250514-v1:0',
                'arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0'
              ],
            }),
          ],
        }),
      },
    });

    // Upload Lambda function
    const uploadLambda = new lambda.Function(this, `UploadLambda${suffix}`, {
      functionName: `idp-upload-${suffix}`,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'upload.handler',
      role: lambdaRole,
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda-functions')),
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: resultsTable.tableName,
      },
    });

    // Results Lambda function
    const resultsLambda = new lambda.Function(this, `ResultsLambda${suffix}`, {
      functionName: `idp-results-${suffix}`,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'results.handler',
      role: lambdaRole,
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda-functions')),
      environment: {
        TABLE_NAME: resultsTable.tableName,
      },
    });

    // Processing Lambda function (combines OCR, Classification, and Summarization)
    const processingLambda = new lambda.Function(this, `ProcessingLambda${suffix}`, {
      functionName: `idp-processing-${suffix}`,
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'processing.handler',
      role: lambdaRole,
      timeout: cdk.Duration.minutes(10),
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda-functions')),
      environment: {
        BUCKET_NAME: documentBucket.bucketName,
        TABLE_NAME: resultsTable.tableName,
      },
    });

    // EventBridge rule to trigger processing on S3 upload
    const s3UploadRule = new events.Rule(this, `S3UploadRule${suffix}`, {
      eventPattern: {
        source: ['aws.s3'],
        detailType: ['Object Created'],
        detail: {
          bucket: {
            name: [documentBucket.bucketName],
          },
        },
      },
    });

    s3UploadRule.addTarget(new targets.LambdaFunction(processingLambda));

    // API Gateway
    const api = new apigateway.RestApi(this, `IdpApi${suffix}`, {
      restApiName: `idp-api-${suffix}`,
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key'],
      },
    });

    const uploadIntegration = new apigateway.LambdaIntegration(uploadLambda);
    const resultsIntegration = new apigateway.LambdaIntegration(resultsLambda);

    api.root.addResource('upload').addMethod('POST', uploadIntegration);
    const resultsResource = api.root.addResource('results');
    resultsResource.addResource('{documentId}').addMethod('GET', resultsIntegration);

    // Output the API endpoint
    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: api.url,
      description: 'API Gateway endpoint URL',
    });

    new cdk.CfnOutput(this, 'BucketName', {
      value: documentBucket.bucketName,
      description: 'S3 bucket name for documents',
    });
  }
}
