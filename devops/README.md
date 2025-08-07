

### mysql 세팅 

```
# database 생성
CREATE DATABASE walnut DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci;

# user 세팅
create user 'walnut'@'%' identified by 'walnut12!@';

grant all privileges on walnut.* to 'walnut'@'%';

flush privileges;

```


### mysql 실행

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


### redis 실행

```
docker run -d -p 6379:6379 redis:5.0-alpine
```


### meilisearch 실행

```
docker run -it --rm \
  -p 7700:7700 \
  -e MEILI_MASTER_KEY='walnut-search-engine'\
  -v $(pwd)/meili_data:/meili_data \
  getmeili/meilisearch:v1.5
```

