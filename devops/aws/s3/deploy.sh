#!/bin/bash

# # 개발 환경에 배포
# sam deploy --config-env dev

# # 스테이징 환경에 배포
# sam deploy --config-env staging

# # 프로덕션 환경에 배포
# sam deploy --config-env prod


AWS_PROFILE=keauty-profile

sam deploy --profile ${AWS_PROFILE} --config-file samconfig-kayty.toml  
