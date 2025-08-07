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



-- User Table
CREATE TABLE `users` (
    `id` CHAR(36) NOT NULL COMMENT 'UUID 형식의 고유 식별자',
    `userid` varchar(255) NOT NULL COMMENT '유저 고유 아이디',
    `email` varchar(255) NOT NULL DEFAULT '' COMMENT '이메일',
    `password` varchar(255) NOT NULL DEFAULT '',
    `phone` varchar(255) DEFAULT NULL COMMENT '전화번호',
    `name` varchar(255) NOT NULL DEFAULT '' COMMENT 'user 이름',
    `sign_in_count` int NOT NULL DEFAULT '0',
    `last_sign_in_at` datetime DEFAULT NULL COMMENT '마지막 로그인 시간',
    `last_sign_in_ip` varchar(255) DEFAULT NULL COMMENT '마지막 로그인 아이피',
    `access_token` varchar(255) DEFAULT NULL,
    `refresh_token` varchar(255) DEFAULT '' COMMENT 'refresh token',
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    `avatar_url` varchar(255) DEFAULT '' COMMENT '프로필 이미지',
    `exposure` int DEFAULT '0' COMMENT '노출여부',
    `uuid` varchar(255) DEFAULT '' COMMENT 'SNS id or random generated uuid',
    `sign_up_from` varchar(255) DEFAULT 'stocking' COMMENT 'SNS(kakao, google, naver, facebook) or stocking',
    `is_admin` tinyint(1) DEFAULT '0' COMMENT '어드민여부',
    `push_token` varchar(255) DEFAULT '' COMMENT 'push token',
    `platform` varchar(255) DEFAULT '' COMMENT '폰 플랫폼',
    `push_on` tinyint(1) DEFAULT '1',
    `balance` decimal(10,2) DEFAULT '0.00' COMMENT '보유중인 예치금',
    PRIMARY KEY (`id`),
    UNIQUE KEY `idx_userid` (`userid`),
    UNIQUE KEY `idx_email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE users
ADD COLUMN point DECIMAL(10, 2) NULL DEFAULT 0.00 COMMENT '보유중인 포인트',
ADD COLUMN total_challenge_amount DECIMAL(10, 2) NULL DEFAULT 0.00 COMMENT '총 도전금액(누적)',
ADD COLUMN total_acquired_points DECIMAL(10, 2) NULL DEFAULT 0.00 COMMENT '총 획득포인트(누적)',
ADD COLUMN current_challenge_amount DECIMAL(10, 2) NULL DEFAULT 0.00 COMMENT '현재 도전중인금액 합';



-- 공지사항
CREATE TABLE notices (
    id CHAR(36) PRIMARY KEY,
    creator_id CHAR(36) NOT NULL COMMENT '생성자 ID',
    title VARCHAR(255) NOT NULL COMMENT '제목',
    content TEXT NOT NULL COMMENT '내용',
    is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT '활성화 여부',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정일시',
    FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- roles 테이블 생성
CREATE TABLE roles (
    id CHAR(36) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    name VARCHAR(50) NOT NULL,
    description VARCHAR(255),
    UNIQUE (name)
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- name 컬럼에 인덱스 생성
CREATE INDEX ix_roles_name ON roles (name);

-- UUID 생성을 위한 함수 사용 (MySQL 8.0 이상)
INSERT INTO roles (id, created_at, updated_at, name, description)
VALUES
  (UUID(), NOW(), NOW(), 'admin', '시스템 관리자 권한으로 모든 기능에 접근 가능'),
  (UUID(), NOW(), NOW(), 'moderator', '컨텐츠 관리 및 검토 권한'),
  (UUID(), NOW(), NOW(), 'premium', '프리미엄 사용자를 위한 특별 기능 접근 권한'),
  (UUID(), NOW(), NOW(), 'user', '일반 사용자 권한');

-- user_roles 테이블 생성
CREATE TABLE user_roles (
    id CHAR(36) PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_id CHAR(36) NOT NULL,
    role_id CHAR(36) NOT NULL,
    CONSTRAINT `fk_user_role_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_user_role_role_id` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE CASCADE
)ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

insert into user_roles(id, user_id, role_id) values (UUID(), '2c65f307-c3e0-4cdc-9fa8-051fa3e6fc68', '84bce2a2-219e-11f0-8a8c-061c30671109');

-- Reports Table (Polymorphic)
CREATE TABLE `reports` (
    `id` CHAR(36) NOT NULL COMMENT 'UUID 형식의 고유 식별자',
    `user_id` CHAR(36) NOT NULL COMMENT '신고한 사용자',
    `reportable_type` varchar(50) NOT NULL COMMENT '신고 대상 유형(challenge, verification, user, etc)',
    `reportable_id` CHAR(36) NOT NULL COMMENT '신고 대상 ID',
    `reason` varchar(255) NOT NULL COMMENT '신고 이유',
    `description` text COMMENT '신고 세부 내용',
    `status` varchar(20) DEFAULT 'pending' COMMENT '처리 상태: pending, in_progress, resolved',
    `handled_by` CHAR(36) NULL COMMENT '처리자(운영자) ID',
    `handled_at` DATETIME(6) NULL COMMENT '처리 시각',
--     `resolution` VARCHAR(50) NULL COMMENT '처리 결과(accepted/rejected 등)',
    `handler_comment` TEXT NULL COMMENT '처리자가 남긴 코멘트/메모',
    `created_at` datetime(6) NOT NULL,
    `updated_at` datetime(6) NOT NULL,
    PRIMARY KEY (`id`),
    KEY `fk_reports_user_id` (`user_id`),
    KEY `idx_reportable` (`reportable_type`, `reportable_id`),
    CONSTRAINT `fk_reports_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 신고 history
CREATE TABLE `report_status_histories` (
   `id` CHAR(36) NOT NULL,
   `report_id` CHAR(36) NOT NULL COMMENT '연관된 신고 ID',
   `status` VARCHAR(20) NOT NULL COMMENT '변경된 상태',
--    `resolution` VARCHAR(50) NULL COMMENT '처리 결과',
   `handled_by` CHAR(36) NOT NULL COMMENT '처리자 ID',
   `handler_comment` TEXT NULL,
   `handled_at` DATETIME(6) NOT NULL COMMENT '변경 시각',
   PRIMARY KEY (`id`),
   KEY `fk_report_status_histories_report_id` (`report_id`),
   CONSTRAINT `fk_report_status_histories_report_id`
       FOREIGN KEY (`report_id`) REFERENCES `reports` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `comments` (
  `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT 'UUID 기본키',
  `user_id` CHAR(36) COMMENT '작성자 ID',
  `commentable_id` CHAR(36) NOT NULL COMMENT '코멘트 대상 ID',
  `commentable_type` VARCHAR(255) NOT NULL COMMENT '코멘트 대상 타입',
  `content` TEXT NOT NULL COMMENT '코멘트 내용',
  `ancestry` VARCHAR(255) COMMENT '계층 구조 경로',
  `ancestry_depth` INT DEFAULT 0 COMMENT '계층 깊이 캐시',
  `children_count` INT DEFAULT 0 COMMENT '하위 코멘트 수 캐시',
  `is_question` BOOLEAN DEFAULT TRUE COMMENT '질문이면 True, 답변이면 False',
  `answer_name` VARCHAR(255) DEFAULT '' COMMENT '답변한 사람, card package 주인 혹은 system 관리자(CS)',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성 시간',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '수정 시간',
  FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='코멘트 정보 테이블';


-- 실시간 집계 쿼리 사용
SELECT
    reportable_type,
    reportable_id,
    COUNT(*) as report_count
FROM
    reports
GROUP BY
    reportable_type, reportable_id;


-- BalanceHistory 테이블 생성
CREATE TABLE `balance_histories` (
    `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT '고유 ID (UUID)',
    `user_id` CHAR(36) NOT NULL COMMENT '사용자 ID',
    `amount` DECIMAL(10,2) NOT NULL COMMENT '변동 금액',
    `balance_before` DECIMAL(10,2) NOT NULL COMMENT '변동 전 잔액',
    `balance_after` DECIMAL(10,2) NOT NULL COMMENT '변동 후 잔액',
    `transaction_type` VARCHAR(50) NOT NULL COMMENT '거래 유형(deposit, withdraw, challenge_join, etc)',
    `description` TEXT NULL COMMENT '거래 설명',
    `reference_id` VARCHAR(36) NULL COMMENT '참조 ID (관련 챌린지, 결제 등의 ID)',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',

    INDEX `idx_balance_histories_user_id` (`user_id`),
    INDEX `idx_balance_histories_created_at` (`created_at`),
    INDEX `idx_balance_histories_transaction_type` (`transaction_type`),
    INDEX `idx_balance_histories_reference_id` (`reference_id`),

    CONSTRAINT `fk_balance_histories_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='사용자 잔액 변동 이력';

-- PointHistory 테이블 생성
CREATE TABLE `point_histories` (
    `id` CHAR(36) NOT NULL PRIMARY KEY COMMENT '고유 ID (UUID)',
    `user_id` CHAR(36) NOT NULL COMMENT '사용자 ID',
    `amount` DECIMAL(10,2) NOT NULL COMMENT '변동 포인트',
    `point_before` DECIMAL(10,2) NOT NULL COMMENT '변동 전 포인트',
    `point_after` DECIMAL(10,2) NOT NULL COMMENT '변동 후 포인트',
    `transaction_type` VARCHAR(50) NOT NULL COMMENT '거래 유형(earn, use, expire, etc)',
    `description` TEXT NULL COMMENT '거래 설명',
    `reference_id` VARCHAR(36) NULL COMMENT '참조 ID (관련 챌린지, 결제 등의 ID)',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '생성일시',

    INDEX `idx_point_histories_user_id` (`user_id`),
    INDEX `idx_point_histories_created_at` (`created_at`),
    INDEX `idx_point_histories_transaction_type` (`transaction_type`),
    INDEX `idx_point_histories_reference_id` (`reference_id`),

    CONSTRAINT `fk_point_histories_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='사용자 포인트 변동 이력';