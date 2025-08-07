#!/bin/bash
set -e

AWS_ACCOUNT_ID=775405889390
AWS_PROFILE=keauty-profile
AWS_REGION=ap-northeast-2

VpcId="vpc-058182c6a505dbde5"
PrivateSubnets="subnet-0ae5e1d6b473d21ed,subnet-05edd02fb670e163e"
ECSCluster="KeautyApiCluster"

# aws ec2 describe-security-groups --profile keauty-profile --filters "Name=group-name,Values=*keauty-api*" --query 'SecurityGroups[*].GroupId' --output text
ServiceSecurityGroup="sg-04f2acdff5a9a3775"

sam deploy --profile $AWS_PROFILE \
  --template-file template.yaml \
  --stack-name keauty-redis-stack \
  --parameter-overrides \
    VpcId=$VpcId \
    PrivateSubnets=$PrivateSubnets \
    ECSCluster=$ECSCluster \
    ServiceSecurityGroup=$ServiceSecurityGroup \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM