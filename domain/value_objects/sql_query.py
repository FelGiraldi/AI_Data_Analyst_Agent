# domain/value_objects/sql_query.py
from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True, slots=True)
class SQLQuery:
    """
    Value Object que representa una query SQL.
    frozen=True lo hace inmutable.
    slots=True mejora el uso de memoria en Python 3.11+
    """
    raw_query: str
    is_safe: bool = False
    validation_error: Optional[str] = None

    def __post_init__(self):
        """Validador de negocio: Una query no puede estar vacía"""
        if not self.raw_query or not self.raw_query.strip():
            raise ValueError("La query SQL no puede estar vacía")

    def mark_as_safe(self) -> 'SQLQuery':
        """Retorna una nueva instancia marcada como segura (Inmutabilidad)"""
        return SQLQuery(
            raw_query=self.raw_query,
            is_safe=True,
            validation_error=None
        )

    def mark_as_unsafe(self, error: str) -> 'SQLQuery':
        """Retorna una nueva instancia con el error de validación"""
        return SQLQuery(
            raw_query=self.raw_query,
            is_safe=False,
            validation_error=error
        )