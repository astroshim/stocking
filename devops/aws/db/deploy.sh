# 개발 환경에 배포
sam deploy --config-env default --parameter-overrides "DBPassword=aY6pK8hN2zX4qW7dC3jR9bT5vF"

# 스테이징 환경에 배포
sam deploy --config-env staging --parameter-overrides "DBPassword=YourSecurePassword456!"

# 프로덕션 환경에 배포
sam deploy --config-env prod --parameter-overrides "DBPassword=aY6pK8hN2zX4qW7dC3jR9bT5vF!"
