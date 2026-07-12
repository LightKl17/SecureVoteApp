"""
Script de inicialización de votantes de prueba.

MIGRADO: la versión original usaba mysql.connector contra una base MySQL
local (localhost:3306). El proyecto fue migrado a PostgreSQL (Azure Database
for PostgreSQL) para poder desplegarlo en la nube, así que este script ahora
usa psycopg2 y lee la configuración de conexión desde las mismas variables
de entorno que usa app.py, para apuntar siempre a la misma base de datos
que usa la aplicación en producción.
"""
import os
import hashlib
import psycopg2

db_config = {
    'host': os.environ.get('DB_HOST', 'db-pq.postgres.database.azure.com'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'postgres'),
    'user': os.environ.get('DB_USER', 'user'),
    'password': os.environ.get('DB_PASSWORD'),
    'sslmode': 'require',
    'connect_timeout': 10,
}


def get_hash(dni):
    return hashlib.sha256(dni.encode('utf-8')).hexdigest()


def main():
    if not db_config['password']:
        print("ERROR: la variable de entorno DB_PASSWORD no está definida. "
              "Configúrala antes de ejecutar este script (igual que en app.py).")
        return

    test_voters = [
        ('77777777', get_hash('77777777')),
        ('88888888', get_hash('88888888')),
        ('99999999', get_hash('99999999')),
    ]

    print(f"Connecting to {db_config['host']} to set up test voters...")
    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()

        for dni, h_dni in test_voters:
            cursor.execute(
                'SELECT "id_votante", "ha_votado" FROM "public"."votantes" '
                'WHERE "hash_dni" = %s;',
                (h_dni,),
            )
            res = cursor.fetchone()
            if res:
                print(f"Voter DNI: {dni} (Hash: {h_dni}) already exists. ha_votado: {res[1]}")
                # Reiniciamos el estado de voto para poder volver a probar
                if res[1]:
                    cursor.execute(
                        'UPDATE "public"."votantes" SET "ha_votado" = FALSE '
                        'WHERE "hash_dni" = %s;',
                        (h_dni,),
                    )
                    print(f"-> Reset ha_votado to FALSE for DNI: {dni} for fresh testing!")
            else:
                cursor.execute(
                    'INSERT INTO "public"."votantes" ("hash_dni", "ha_votado") '
                    'VALUES (%s, FALSE);',
                    (h_dni,),
                )
                print(f"Inserted Voter DNI: {dni} (Hash: {h_dni}) with ha_votado = FALSE")

        conn.commit()
        print("\nSetup of test voters completed successfully!")

        cursor.execute('SELECT COUNT(*) FROM "public"."votantes";')
        print(f"Total voters in database: {cursor.fetchone()[0]}")

        cursor.close()
        conn.close()

    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        print(f"Error during setup: {e}")


if __name__ == '__main__':
    main()
