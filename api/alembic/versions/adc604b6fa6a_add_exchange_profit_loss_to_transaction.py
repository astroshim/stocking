"""add_exchange_profit_loss_to_transaction

Revision ID: adc604b6fa6a
Revises: 0e6321424c47
Create Date: 2025-01-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'adc604b6fa6a'
down_revision: Union[str, None] = '0e6321424c47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Transaction 테이블에 환율 관련 손익 컬럼 추가
    op.add_column('transactions', sa.Column('purchase_average_exchange_rate', sa.Numeric(precision=10, scale=4), nullable=True, comment='매도시점의 평균 매수 환율'))
    op.add_column('transactions', sa.Column('exchange_profit_loss', sa.Numeric(precision=20, scale=2), nullable=True, comment='환율 차익 (원)'))
    op.add_column('transactions', sa.Column('price_profit_loss', sa.Numeric(precision=20, scale=2), nullable=True, comment='가격 차익 (원)'))
    op.add_column('transactions', sa.Column('current_exchange_rate', sa.Numeric(precision=10, scale=4), nullable=True, comment='매도 시점 환율'))


def downgrade() -> None:
    # 컬럼 제거
    op.drop_column('transactions', 'current_exchange_rate')
    op.drop_column('transactions', 'price_profit_loss')
    op.drop_column('transactions', 'exchange_profit_loss')
    op.drop_column('transactions', 'purchase_average_exchange_rate')