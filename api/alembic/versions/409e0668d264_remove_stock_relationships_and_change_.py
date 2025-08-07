"""Remove stock relationships and change stock_id to string

Revision ID: 409e0668d264
Revises: a62ef903a48e
Create Date: 2025-08-07 17:24:36.912291

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '409e0668d264'
down_revision: Union[str, Sequence[str], None] = 'a62ef903a48e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 먼저 모든 외래 키 제약 조건을 삭제
    op.drop_constraint('orders_ibfk_1', 'orders', type_='foreignkey')
    op.drop_constraint('portfolios_ibfk_2', 'portfolios', type_='foreignkey')
    op.drop_constraint('transactions_ibfk_3', 'transactions', type_='foreignkey')
    op.drop_constraint('watch_lists_ibfk_2', 'watch_lists', type_='foreignkey')
    
    # 그 다음 컬럼 변경
    op.alter_column('orders', 'stock_id',
               existing_type=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               type_=sa.String(length=20),
               comment='주식 종목 코드 (예: 097230)',
               existing_comment='주식 종목 ID',
               existing_nullable=False)
    
    op.alter_column('portfolios', 'stock_id',
               existing_type=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               type_=sa.String(length=20),
               comment='주식 종목 코드 (예: 097230)',
               existing_comment='주식 종목 ID',
               existing_nullable=False)
    
    op.alter_column('transactions', 'stock_id',
               existing_type=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               type_=sa.String(length=20),
               comment='주식 종목 코드 (주식 거래시, 예: 097230)',
               existing_comment='주식 종목 ID (주식 거래시)',
               existing_nullable=True)
    
    op.alter_column('watch_lists', 'stock_id',
               existing_type=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               type_=sa.String(length=20),
               comment='주식 종목 코드 (예: 097230)',
               existing_comment='주식 종목 ID',
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    # 먼저 컬럼을 원래 타입으로 변경
    op.alter_column('orders', 'stock_id',
               existing_type=sa.String(length=20),
               type_=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               comment='주식 종목 ID',
               existing_comment='주식 종목 코드 (예: 097230)',
               existing_nullable=False)
    
    op.alter_column('portfolios', 'stock_id',
               existing_type=sa.String(length=20),
               type_=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               comment='주식 종목 ID',
               existing_comment='주식 종목 코드 (예: 097230)',
               existing_nullable=False)
    
    op.alter_column('transactions', 'stock_id',
               existing_type=sa.String(length=20),
               type_=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               comment='주식 종목 ID (주식 거래시)',
               existing_comment='주식 종목 코드 (주식 거래시, 예: 097230)',
               existing_nullable=True)
    
    op.alter_column('watch_lists', 'stock_id',
               existing_type=sa.String(length=20),
               type_=mysql.VARCHAR(collation='utf8mb3_unicode_ci', length=36),
               comment='주식 종목 ID',
               existing_comment='주식 종목 코드 (예: 097230)',
               existing_nullable=False)
    
    # 그 다음 외래 키 제약 조건 재생성
    op.create_foreign_key('orders_ibfk_1', 'orders', 'stocks', ['stock_id'], ['id'])
    op.create_foreign_key('portfolios_ibfk_2', 'portfolios', 'stocks', ['stock_id'], ['id'])
    op.create_foreign_key('transactions_ibfk_3', 'transactions', 'stocks', ['stock_id'], ['id'])
    op.create_foreign_key('watch_lists_ibfk_2', 'watch_lists', 'stocks', ['stock_id'], ['id'])
