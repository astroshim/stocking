"""extend watchlist directory id to char 41

Revision ID: d5ba8f4db345
Revises: 4aa95e87f643
Create Date: 2025-08-26 18:25:34.004955

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'd5ba8f4db345'
down_revision: Union[str, Sequence[str], None] = '4aa95e87f643'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. 먼저 외래 키 제약 조건 삭제
    op.drop_constraint('watch_lists_ibfk_2', 'watch_lists', type_='foreignkey')
    
    # 2. watchlist_directories 테이블의 id 컬럼 타입 변경
    op.alter_column('watchlist_directories', 'id',
               existing_type=mysql.CHAR(collation='utf8mb3_unicode_ci', length=36),
               type_=mysql.CHAR(length=41),
               existing_nullable=False)
    
    # 3. watch_lists 테이블의 directory_id 컬럼 타입 변경
    op.alter_column('watch_lists', 'directory_id',
               existing_type=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               type_=sa.String(length=41),
               existing_comment='디렉토리 ID',
               existing_nullable=True)
    
    # 4. 외래 키 제약 조건 다시 생성
    op.create_foreign_key('watch_lists_ibfk_2', 'watch_lists', 'watchlist_directories', ['directory_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    # 1. 먼저 외래 키 제약 조건 삭제
    op.drop_constraint('watch_lists_ibfk_2', 'watch_lists', type_='foreignkey')
    
    # 2. watch_lists 테이블의 directory_id 컬럼 타입 원복
    op.alter_column('watch_lists', 'directory_id',
               existing_type=sa.String(length=41),
               type_=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               existing_comment='디렉토리 ID',
               existing_nullable=True)
    
    # 3. watchlist_directories 테이블의 id 컬럼 타입 원복
    op.alter_column('watchlist_directories', 'id',
               existing_type=mysql.CHAR(length=41),
               type_=mysql.CHAR(collation='utf8mb3_unicode_ci', length=36),
               existing_nullable=False)
    
    # 4. 외래 키 제약 조건 다시 생성
    op.create_foreign_key('watch_lists_ibfk_2', 'watch_lists', 'watchlist_directories', ['directory_id'], ['id'])
