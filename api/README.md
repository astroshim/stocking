# StocKing API


## 로컬 테스트 방법

### 1. mysql 서버 실행

```
docker run -d \
  -p 3306:3306 \
  --name mysql \
  --restart always \
  -e TZ=Asia/Seoul \
  -e MYSQL_ROOT_PASSWORD='walnut1234!@#\$' \
  -v /Users/hsshim/walnut_data/mysql:/var/lib/mysql \
  --health-cmd="mysqladmin ping -h localhost" \
  --health-interval=30s \
  --health-timeout=20s \
  --health-retries=10 \
  mysql:8.2.0 \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_unicode_ci
```

### api 서버 실행

```shell

# test 모드
WORKER=1 uv run gunicorn main:app
```

```

## swagger

http://localhost:5100/docs


## infra 배포 순서

### 1. network 생성

```shell
# network-infrastructure

```

### 2. mysql 생성

```shell
# mysql-db

```

### 3. cloudformation stack 생성

```shell
# stocking-cloudformation-distribution

```

### 4. api 서버 배포

```shell
# stocking-api-stack

```

### 5. api update

```shell
#

```

### bastion
 - mysql 에 쿼리 하기위해서 생성해야함.
 - ec2 -> 키페어 에서 bastion 이라는 pem 키를 먼저 만들어야 함.


## tables


```sql
# db 를 만들기 위해서 admin 으로 접근. (최초?)
mysql -uadmin -p -h dev-mysql-db.ctqke428aiun.ap-northeast-2.rds.amazonaws.com


CREATE DATABASE stocking DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_unicode_ci;

create user 'stocking'@'%' identified by 'LV9Q40QJEnE82LCNGTSL6OK4zgAgduga!';
grant all privileges on stocking.* to 'stocking'@'%';
flush privileges;

# bastion 터널링을 통하여 db 접속
ssh stocking-db-tunnel
mysql -ustocking -h 127.0.0.1 -p -D stocking -P 13306

