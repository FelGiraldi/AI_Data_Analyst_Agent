
# domain/entities/dataset.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

@dataclass(slots=True)
class DatasetSchema:
    """Entidad que representa la metadata de los datos, no los datos en sí"""
    id: str
    table_name: str
    row_count: int
    columns: Dict[str, str]  # ej: {"ingresos": "FLOAT", "fecha": "DATE"}
    summary: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)

    def get_context_for_llm(self) -> str:
        """Formatea el esquema para inyectarlo en el prompt del LLM"""
        cols_str = ", ".join([f"{col} ({dtype})" for col, dtype in self.columns.items()])
        return f"Table: {self.table_name} | Columns: {cols_str} | Rows: {self.row_count}"