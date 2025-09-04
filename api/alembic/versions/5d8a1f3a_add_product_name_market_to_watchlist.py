"""watch_lists에 product_name, market 추가 및 기본값 채움

Revision ID: 5d8a1f3a
Revises: 48ab17309e7a
Create Date: 2025-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = '5d8a1f3a'
down_revision: Union[str, Sequence[str], None] = '48ab17309e7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 컬럼 추가 (nullable=True로 먼저 추가)
    op.add_column('watch_lists', sa.Column('product_name', sa.String(length=100), nullable=True, comment='상품명 (삼성전자, Apple Inc., 비트코인)'))
    op.add_column('watch_lists', sa.Column('market', sa.String(length=50), nullable=True, comment='시장/거래소 (KOSPI, NYSE, NASDAQ, Upbit)'))

    # 2) 기존 행에 기본값 채우기 (product_code를 임시로 이름/시장 미상으로 채움)
    conn = op.get_bind()
    conn.execute(sa.text("""
        UPDATE watch_lists
        SET product_name = COALESCE(product_name, product_code),
            market = COALESCE(market, 'UNKNOWN')
        WHERE product_name IS NULL OR market IS NULL
    """))

    # 3) NOT NULL로 변경 (MySQL은 existing_type 명시 필요)
    op.alter_column('watch_lists', 'product_name',
        existing_type=mysql.VARCHAR(length=100),
        nullable=False,
        existing_nullable=True,
        comment='상품명 (삼성전자, Apple Inc., 비트코인)'
    )
    op.alter_column('watch_lists', 'market',
        existing_type=mysql.VARCHAR(length=50),
        nullable=False,
        existing_nullable=True,
        comment='시장/거래소 (KOSPI, NYSE, NASDAQ, Upbit)'
    )


def downgrade() -> None:
    # 되돌리기: 컬럼 제거
    op.drop_column('watch_lists', 'market')
    op.drop_column('watch_lists', 'product_name')


