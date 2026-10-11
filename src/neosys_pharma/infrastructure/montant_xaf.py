"""Franc CFA entier exact : SQLite INTEGER, PostgreSQL NUMERIC(18,0)."""
from decimal import Decimal
from sqlalchemy import BigInteger,Numeric
from sqlalchemy.types import TypeDecorator

class MontantXAF(TypeDecorator):
    impl=Numeric(18,0)
    cache_ok=True
    def load_dialect_impl(self,dialect):
        return dialect.type_descriptor(BigInteger() if dialect.name=='sqlite' else Numeric(18,0))
    def process_bind_param(self,value,dialect):
        if value is None:return None
        amount=Decimal(str(value))
        if not amount.is_finite() or amount!=amount.to_integral_value():raise ValueError('Montant XAF entier obligatoire.')
        return int(amount) if dialect.name=='sqlite' else amount
    def process_result_value(self,value,dialect):return Decimal(str(value)) if value is not None else None
