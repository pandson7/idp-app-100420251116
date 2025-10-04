#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { IdpApp100420251116Stack } from '../lib/idp-app-100420251116-stack';

const app = new cdk.App();
new IdpApp100420251116Stack(app, 'IdpApp100420251116Stack', {
  env: { 
    account: process.env.CDK_DEFAULT_ACCOUNT, 
    region: process.env.CDK_DEFAULT_REGION 
  },
});
