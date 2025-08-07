
AWS_PROFILE=keauty-profile

sam deploy --profile ${AWS_PROFILE}

#sam deploy --template-file bastion-template.yaml \
#  --stack-name bastion-server \
#  --parameter-overrides \
#    NetworkStackName=network-infrastructure \
#    InstanceType=t3.micro \
#    KeyPairName=YOUR_KEY_NAME \
#    YourIpAddress=YOUR_IP_ADDRESS/32 \
#    SSHPort=22 \
#  --capabilities CAPABILITY_IAM