# domain/ports/data_port.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from domain.entities.dataset import DatasetSchema
from domain.value_objects.sql_query import SQLQuery

class DataProviderPort(ABC):
    """Interfaz que la Infraestructura (DuckDB/LanceDB) debe cumplir"""
    
    @abstractmethod
    async def get_schema(self, table_name: str) -> DatasetSchema:
        pass

    @abstractmethod
    async def execute_query(self, query: SQLQuery) -> List[Dict[str, Any]]:
        pass