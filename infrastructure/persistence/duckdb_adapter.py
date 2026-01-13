# infrastructure/persistence/duckdb_adapter.py
import duckdb
import pandas as pd
import os
from typing import List, Dict, Any
from domain.ports.data_port import DataProviderPort
from domain.entities.dataset import DatasetSchema
from domain.value_objects.sql_query import SQLQuery

class DuckDBAdapter(DataProviderPort):
    def __init__(self, db_path: str = ":memory:"):
        self.conn = duckdb.connect(db_path)
    
    async def load_file(self, file_path: str, table_name: str) -> DatasetSchema:
        """
        Carga agnóstica de archivos (CSV o Excel).
        Usa Pandas como intermediario para máxima compatibilidad.
        """
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()
        
        try:
            if ext == '.csv':
                # DuckDB nativo es más rápido para CSV
                self.conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM read_csv_auto('{file_path}')")
            
            elif ext in ['.xlsx', '.xls']:
                # Pandas para Excel -> DuckDB
                df = pd.read_excel(file_path)
                # Normalizar nombres de columnas (quitar espacios y caracteres raros)
                df.columns = [c.strip().replace(" ", "_").replace("-", "_").lower() for c in df.columns]
                # Registrar el DataFrame como tabla en DuckDB
                self.conn.register("temp_df_view", df)
                self.conn.execute(f"CREATE OR REPLACE TABLE {table_name} AS SELECT * FROM temp_df_view")
                self.conn.unregister("temp_df_view")
            
            else:
                raise ValueError(f"Formato no soportado: {ext}")
                
            return await self.get_schema(table_name)
            
        except Exception as e:
            raise RuntimeError(f"Error cargando archivo {file_path}: {str(e)}")

    async def get_schema(self, table_name: str) -> DatasetSchema:
        # Obtener info de columnas
        query = f"DESCRIBE {table_name}"
        df = self.conn.execute(query).df()
        
        columns = dict(zip(df['column_name'], df['column_type']))
        count = self.conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        
        return DatasetSchema(
            id=table_name,
            table_name=table_name,
            row_count=count,
            columns=columns,
            summary=f"Dataset {table_name} cargado en DuckDB"
        )

    async def execute_query(self, query: SQLQuery) -> List[Dict[str, Any]]:
        if not query.is_safe:
            raise SecurityError(f"Intento de ejecución de query insegura: {query.validation_error}")
        
        try:
            # DuckDB retorna pandas df
            df = self.conn.execute(query.raw_query).df()
            # Convertir Timestamp a string para evitar errores de JSON serialization luego
            for col in df.select_dtypes(include=['datetime64[ns]']).columns:
                df[col] = df[col].astype(str)
                
            return df.to_dict(orient='records')
        except Exception as e:
            raise RuntimeError(f"Database Error: {str(e)}")

class SecurityError(Exception):
    pass