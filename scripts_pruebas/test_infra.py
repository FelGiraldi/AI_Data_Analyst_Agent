import asyncio
from infrastructure.persistence.duckdb_adapter import DuckDBAdapter
from infrastructure.security.sql_sanitizer import SQLSanitizer
from domain.value_objects.sql_query import SQLQuery

async def main():
    print("--- 🧪 Iniciando Test de Infraestructura ---")
    
    # 1. Setup DB
    db = DuckDBAdapter() # Memoria
    
    # Crear un CSV dummy al vuelo
    with open("test_data.csv", "w") as f:
        f.write("producto,ventas,fecha\nManzana,100,2026-01-01\nPera,50,2026-01-02")
    
    print("📂 Cargando datos...")
    schema = await db.load_csv("test_data.csv", "ventas")
    print(f"✅ Esquema detectado: {schema.columns}")
    
    # 2. Test Seguridad (Query Maliciosa)
    print("\n🛡️ Probando Query Maliciosa (DROP TABLE)...")
    bad_sql = SQLQuery("DROP TABLE ventas")
    validated_bad = SQLSanitizer.validate_query(bad_sql)
    
    if not validated_bad.is_safe:
        print(f"✅ Seguridad OK! Query bloqueada: {validated_bad.validation_error}")
    else:
        print("❌ ALERTA: El validador falló.")

    # 3. Test Query Correcta
    print("\n📊 Probando Query Correcta...")
    good_sql = SQLQuery("SELECT producto, ventas FROM ventas WHERE ventas > 60")
    validated_good = SQLSanitizer.validate_query(good_sql)
    
    if validated_good.is_safe:
        results = await db.execute_query(validated_good)
        print(f"✅ Resultados: {results}")
    else:
        print(f"❌ Error: {validated_good.validation_error}")

    # Limpieza
    import os
    os.remove("test_data.csv")

if __name__ == "__main__":
    asyncio.run(main())