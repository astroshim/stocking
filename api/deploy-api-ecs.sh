#!/bin/bash
# deploy-ecs-simple.sh
# 기존 태스크 정의를 기반으로 이미지만 업데이트하여 ECS 서비스를 배포합니다.

set -e

# --- 설정 ---
CLUSTER_NAME="stockingApiEc2Cluster"
SERVICE_NAME="stockingApiEc2Service"
TASK_FAMILY="stocking-api"
CONTAINER_NAME="stocking-api-container"
AWS_PROFILE="stocking-profile"
AWS_REGION="ap-northeast-2"
AWS_ACCOUNT_ID="775405889390"
ECR_REPOSITORY="stocking/stocking-api"

ASG_NAME="stocking-ecs-ec2-cloudfront-api-stack-EC2AutoScalingGroup-5qCr7nkQpZPA"
DESIRED_CAPACITY=2

# 1. 사용자로부터 새 이미지 버전 입력받기
read -p "배포할 이미지 버전을 입력하세요 (예: v1.2): " IMAGE_VERSION
if [ -z "$IMAGE_VERSION" ]; then
  echo "오류: 이미지 버전은 필수입니다."
  exit 1
fi

echo "배포를 위해서 인스턴스 용량을 증가합니다."
aws autoscaling update-auto-scaling-group \
  --auto-scaling-group-name $ASG_NAME \
  --desired-capacity $DESIRED_CAPACITY \
  --profile stocking-profile

echo "✅ Auto Scaling Group 용량을 $DESIRED_CAPACITY 로 설정했습니다."

# 인스턴스가 준비될 때까지 대기
echo "🔄 인스턴스가 준비될 때까지 기다립니다..."
while true; do
    # 현재 InService 상태인 인스턴스 수 확인
    IN_SERVICE_COUNT=$(aws autoscaling describe-auto-scaling-groups \
        --auto-scaling-group-names $ASG_NAME \
        --profile stocking-profile \
        --query 'AutoScalingGroups[0].Instances[?LifecycleState==`InService`]' \
        --output json | jq '. | length')
    
    echo "현재 InService 상태 인스턴스: $IN_SERVICE_COUNT/$DESIRED_CAPACITY"
    
    if [ "$IN_SERVICE_COUNT" -eq "$DESIRED_CAPACITY" ]; then
        echo "✅ 모든 인스턴스가 준비되었습니다!"
        break
    fi
    
    echo "⏳ 30초 후 다시 확인합니다..."
    sleep 30
done

# ECS 클러스터에서 컨테이너 인스턴스 상태 확인
echo "🔄 ECS 컨테이너 인스턴스 상태를 확인합니다..."
CONTAINER_INSTANCES=$(aws ecs list-container-instances \
    --cluster $CLUSTER_NAME \
    --profile stocking-profile \
    --query 'containerInstanceArns' \
    --output json | jq '. | length')

echo "ECS 클러스터에 등록된 컨테이너 인스턴스: $CONTAINER_INSTANCES 개"

if [ "$CONTAINER_INSTANCES" -lt "$DESIRED_CAPACITY" ]; then
    echo "⏳ ECS 컨테이너 인스턴스가 클러스터에 등록될 때까지 기다립니다..."
    while [ "$CONTAINER_INSTANCES" -lt "$DESIRED_CAPACITY" ]; do
        sleep 15
        CONTAINER_INSTANCES=$(aws ecs list-container-instances \
            --cluster $CLUSTER_NAME \
            --profile stocking-profile \
            --query 'containerInstanceArns' \
            --output json | jq '. | length')
        echo "현재 등록된 컨테이너 인스턴스: $CONTAINER_INSTANCES/$DESIRED_CAPACITY"
    done
fi

echo "✅ ECS 클러스터 준비 완료!"
echo "ecs 배포를 시작합니다."

# jq 설치 확인
if ! command -v jq &> /dev/null
then
    echo "jq가 설치되어 있지 않습니다. 이 스크립트를 실행하려면 jq가 필요합니다."
    echo "macOS: brew install jq"
    echo "Amazon Linux: sudo yum install jq"
    echo "Ubuntu: sudo apt-get install jq"
    exit 1
fi


# 2. 전체 이미지 URL 구성
IMAGE_URL="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_VERSION"
echo "✅ 새 이미지로 업데이트합니다: $IMAGE_URL"

# 3. 최신 활성 태스크 정의 가져오기
echo "🔍 최신 태스크 정의를 가져옵니다 (패밀리: $TASK_FAMILY)..."
LATEST_TASK_DEF=$(aws ecs describe-task-definition --profile "$AWS_PROFILE" --region "$AWS_REGION" --task-definition "$TASK_FAMILY" --query 'taskDefinition')

# 4. 새 태스크 정의 JSON 생성 (이미지 주소만 교체)
NEW_TASK_DEF_INPUT=$(echo "$LATEST_TASK_DEF" | \
  jq --arg IMAGE_URL "$IMAGE_URL" --arg CONTAINER_NAME "$CONTAINER_NAME" \
  '
    .containerDefinitions |= map(if .name == $CONTAINER_NAME then .image = $IMAGE_URL else . end) |
    {
      family: .family,
      taskRoleArn: .taskRoleArn,
      executionRoleArn: .executionRoleArn,
      networkMode: .networkMode,
      containerDefinitions: .containerDefinitions,
      requiresCompatibilities: .requiresCompatibilities,
      cpu: .cpu,
      memory: .memory,
      volumes: .volumes,
      placementConstraints: .placementConstraints
    }
  ')

# 5. 새 태스크 정의 등록
echo "📑 새 태스크 정의를 등록합니다..."
NEW_TASK_INFO=$(aws ecs register-task-definition \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --cli-input-json "$NEW_TASK_DEF_INPUT")

NEW_TASK_DEF_ARN=$(echo "$NEW_TASK_INFO" | jq -r '.taskDefinition.taskDefinitionArn')
echo "✅ 새 태스크 정의가 등록되었습니다: $NEW_TASK_DEF_ARN"

# 6. ECS 서비스 업데이트
echo "🚀 서비스를 업데이트합니다: $SERVICE_NAME..."
aws ecs update-service \
  --profile "$AWS_PROFILE" \
  --region "$AWS_REGION" \
  --cluster "$CLUSTER_NAME" \
  --service "$SERVICE_NAME" \
  --task-definition "$NEW_TASK_DEF_ARN" \
  --force-new-deployment > /dev/null

echo "✅ 서비스 업데이트가 시작되었습니다."
echo "배포 상태를 확인하려면 다음 명령어를 사용하세요:"
echo "aws ecs describe-services --cluster $CLUSTER_NAME --services $SERVICE_NAME --query 'services[0].deployments[0]'" 