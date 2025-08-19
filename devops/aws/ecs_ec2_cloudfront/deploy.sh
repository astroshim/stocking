#!/bin/bash
set -e

read -p "Enter the api image version (e.g., v1.1): " IMAGE_VERSION
if [ -z "$IMAGE_VERSION" ]; then
  echo "Image version is required."
  exit 1
fi

read -p "Enter the domain name (e.g., api2.keauty.com): " DOMAIN_NAME
if [ -z "$DOMAIN_NAME" ]; then
  echo "Domain name is required."
  exit 1
fi

read -p "Enter the ACM certificate ARN from us-east-1 (optional): " ACM_CERT_ARN

AWS_ACCOUNT_ID=775405889390
AWS_REGION=ap-northeast-2
ECR_REPOSITORY=keauty/keauty-api
AWS_PROFILE=keauty-profile

ImageUrl="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_VERSION"
ContainerPort="5100"
VpcId="vpc-058182c6a505dbde5"
PublicSubnets="subnet-031de741cc3bdeea5,subnet-0e2e503589388ceab"
PrivateSubnets="subnet-0ae5e1d6b473d21ed,subnet-05edd02fb670e163e"

echo "Image URL: $ImageUrl"
echo "Domain Name: $DOMAIN_NAME"
echo "ACM Certificate ARN: ${ACM_CERT_ARN:-"Not provided"}"

PARAM_OVERRIDES="ImageUrl=$ImageUrl ContainerPort=5100 MinContainers=1 MaxContainers=1 CPUUtilizationThreshold=70 DomainName=$DOMAIN_NAME"

if [ ! -z "$ACM_CERT_ARN" ]; then
  PARAM_OVERRIDES="$PARAM_OVERRIDES AcmCertificateArn=$ACM_CERT_ARN"
fi

echo "Deploying CloudFront + ECS EC2 stack..."

sam deploy --profile $AWS_PROFILE \
  --template-file template.yaml \
  --stack-name stocking-ecs-ec2-cloudfront-api-stack \
  --parameter-overrides $PARAM_OVERRIDES \
  --capabilities CAPABILITY_IAM

echo "Deployment completed!"
echo "CloudFront distribution will take 10-15 minutes to deploy completely." 