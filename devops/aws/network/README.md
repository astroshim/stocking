
# admin key
export AWS_ACCESS_KEY_ID=
export AWS_SECRET_ACCESS_KEY=
export AWS_DEFAULT_REGION=ap-northeast-2

# 프로파일 설정
aws configure --profile keauty-profile

# 배포 사용자 생성
<!-- aws iam create-user --user-name deployment-user --profile keauty-profile -->

# 액세스 키 생성:
<!-- aws iam create-access-key --user-name deployment-user -->

## 역할 생성:
aws iam create-role --role-name sam-deployment-role --assume-role-policy-document file://trust-policy.json

## 권한 정책 생성 및 연결
aws iam create-policy --policy-name sam-deployment-policy --policy-document file://sam-deployment-policy.json

# 사용자에게 정책 연결 (사용자를 사용하는 경우)
aws iam attach-user-policy --user-name deployment-user --policy-arn arn:aws:iam::775405889390:policy/sam-deployment-policy

# 또는 역할에 정책 연결 (역할을 사용하는 경우)
aws iam attach-role-policy --role-name sam-deployment-role --policy-arn arn:aws:iam::775405889390:policy/sam-deployment-policy
