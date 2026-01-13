# infrastructure/security/sql_sanitizer.py
import sqlglot
from sqlglot import exp
from domain.value_objects.sql_query import SQLQuery

class SQLSanitizer:
    """
    Componente de seguridad infraestructural.
    Analiza el AST (Abstract Syntax Tree) de la query para asegurar que sea inocua.
    """
    
    @staticmethod
    def validate_query(query: SQLQuery) -> SQLQuery:
        """
        Toma una query, la valida y retorna una nueva instancia marcada como segura o insegura.
        """
        sql_text = query.raw_query.strip().rstrip(';')
        
        try:
            # 1. Parsear SQL (esto valida sintaxis automáticamente)
            # read="duckdb" se asegura que se entiende el dialecto específico
            parsed = sqlglot.parse_one(sql_text, read="duckdb")
            
            # 2. Se Verifica que el nodo raíz sea SELECT
            # Esto bloquea DROP, DELETE, INSERT, UPDATE, ALTER, etc.
            if not isinstance(parsed, exp.Select):
                return query.mark_as_unsafe("Política de Seguridad: Solo se permiten consultas SELECT (Lectura).")
            
            # 3. (Opcional) Análisis más profundo: verificar subqueries o funciones peligrosas
            return query.mark_as_safe()
            
        except sqlglot.errors.ParseError as e:
            return query.mark_as_unsafe(f"Error de Sintaxis SQL: {str(e)}")
        except Exception as e:
            return query.mark_as_unsafe(f"Error de Validación Desconocido: {str(e)}")