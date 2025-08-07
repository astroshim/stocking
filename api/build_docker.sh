#!/bin/bash
set -e

AWS_REGION=ap-northeast-2
AWS_PROFILE=stocking-profile
AWS_ACCOUNT=775405889390
REPO_NAME='stocking/stocking-api'
ECR_REPO="$AWS_ACCOUNT.dkr.ecr.ap-northeast-2.amazonaws.com/${REPO_NAME}"


# aws key 입력
if [ -z "${AWS_ACCESS_KEY_ID}" ]; then
  read -p "aws key 입력: " AWS_ACCESS_KEY_ID
fi
if [ -z "${AWS_ACCESS_KEY_ID}" ]; then
  echo "aws key 입력 오류!"
  exit 1
fi

if [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then
  read -p "aws secret 입력: " AWS_SECRET_ACCESS_KEY
fi
if [ -z "${AWS_SECRET_ACCESS_KEY}" ]; then
  echo "aws secret 입력 오류!"
  exit 1
fi


# ecr login
RESULT=$(aws ecr get-login-password --profile ${AWS_PROFILE} --region ${AWS_REGION} | docker login -u AWS ${ECR_REPO} --password-stdin)
if [ "$RESULT" != "Login Succeeded" ]; then
  echo "ECR에 로그인 실패 하였습니다. aws Key를 확인해 주세요. result=$RESULT"
  exit 1
fi

# get latest container version
LATEST_IMAGE_TAG=$(aws ecr describe-images --profile ${AWS_PROFILE} --region ${AWS_REGION} --output json --repository-name ${REPO_NAME} --query 'sort_by(imageDetails,& imagePushedAt)[*].imageTags[0]' | jq '.[]' |tail -30)
echo "최근 ECR 에 등록된 image 는 아래와 같습니다."
printf '%s\n' "${LATEST_IMAGE_TAG[@]}"
echo ""

read -p "build 할 버전을 입력해 주세요: " build_version
if [ -z "$build_version" ]; then
  echo "image version 입력 오류!"
  exit 1;
fi

read -p "log level (debug): " log_level
if [ -z "$log_level" ]; then
  log_level="debug"
fi

# set
IMAGE=$ECR_REPO:$build_version

echo $IMAGE

# build docker
docker build -f Dockerfile --platform linux/arm64 \
  --build-arg PYTHON_ENV=production \
  --build-arg LOG_LEVEL=${log_level} \
  --build-arg AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID} \
  --build-arg AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY} \
  --label git-commit=$(git log -1 --format=%h) -t $IMAGE .
# docker build -f Dockerfile --platform linux/amd64 \

# push docker image
docker push $IMAGE

echo "SUCCESS!"