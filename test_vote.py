"""
Pruebas de integridad de SecureVote.

MIGRADO: la versión original usaba mysql.connector + SHA2() de MySQL contra
una base local. El proyecto fue migrado a PostgreSQL, este script
ahora usa psycopg2, calcula el hash del DNI en Python con hashlib (igual
que app.py) y lee la configuración de conexión desde las mismas variables
de entorno que la aplicación en producción.
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


def hash_dni(dni):
    return hashlib.sha256(dni.encode('utf-8')).hexdigest()


def error_text(e):
    """Extrae el mensaje de error de forma legible (psycopg2 lo trae en .pgerror)."""
    msg = e.pgerror if getattr(e, 'pgerror', None) else str(e)
    if "CONTEXT:" in msg:
        msg = msg.split("CONTEXT:")[0]
    return msg.strip()


def run_tests():
    if not db_config['password']:
        print("ERROR: la variable de entorno DB_PASSWORD no está definida.")
        return

    print("=== INICIANDO PRUEBAS DE INTEGRIDAD DE SECUREVOTE ===")

    conn = None
    try:
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        cursor = conn.cursor()

        #CASO 1: Votante No Registrado (DNI 00000000)
        print("\nPrueba 1: Votante no registrado (DNI 00000000)...")
        try:
            cursor.execute(
                'CALL "public"."sp_registrar_voto"(%s, %s);',
                (hash_dni("00000000"), "Candidato A"),
            )
            conn.commit()
            print("[FAIL] ERROR: ¡Se permitió votar a un DNI no registrado!")
        except psycopg2.Error as e:
            conn.rollback()
            msg = error_text(e)
            if "Votante no registrado" in msg:
                print(f"[OK] EXITO: Capturado correctamente el error esperado de la DB: '{msg}'")
            else:
                print(f"[FAIL] ERROR: Se capturó un error inesperado: '{msg}'")

        #CASO 2: Votante que ya votó (DNI 12345678)
        print("\nPrueba 2: Doble Voto con DNI que ya votó (DNI 12345678)...")
        try:
            cursor.execute(
                'CALL "public"."sp_registrar_voto"(%s, %s);',
                (hash_dni("12345678"), "Candidato A"),
            )
            conn.commit()
            print("[FAIL] ERROR: ¡Se permitió un doble voto!")
        except psycopg2.Error as e:
            conn.rollback()
            msg = error_text(e)
            if "ya ha emitido su voto" in msg:
                print(f"[OK] EXITO: Capturado correctamente el error esperado de la DB: '{msg}'")
            else:
                print(f"[FAIL] ERROR: Se capturó un error inesperado: '{msg}'")

        # CASO 3: Voto Exitoso con DNI elegible (DNI 77777777)
        print("\nPrueba 3: Registrar voto elegible por primera vez (DNI 77777777)...")
        try:
            cursor.execute(
                'SELECT "ha_votado" FROM "public"."votantes" WHERE "hash_dni" = %s;',
                (hash_dni("77777777"),),
            )
            res = cursor.fetchone()
            if res and res[0]:
                cursor.execute(
                    'UPDATE "public"."votantes" SET "ha_votado" = FALSE WHERE "hash_dni" = %s;',
                    (hash_dni("77777777"),),
                )
                conn.commit()
                print("-> Reset elegible voter 77777777 state for testing.")

            cursor.execute(
                'CALL "public"."sp_registrar_voto"(%s, %s);',
                (hash_dni("77777777"), "Candidato A"),
            )
            conn.commit()
            print("[OK] EXITO: ¡Voto registrado correctamente en el Ledger!")
        except psycopg2.Error as e:
            conn.rollback()
            print(f"[FAIL] ERROR: No se pudo registrar el voto: '{error_text(e)}'")

        # CASO 4: Intento de Doble Voto con DNI 77777777
        print("\nPrueba 4: Intentar doble voto con el DNI recién usado (DNI 77777777)...")
        try:
            cursor.execute(
                'CALL "public"."sp_registrar_voto"(%s, %s);',
                (hash_dni("77777777"), "Candidato B"),
            )
            conn.commit()
            print("[FAIL] ERROR: ¡Se permitió votar por segunda vez con el mismo DNI!")
        except psycopg2.Error as e:
            conn.rollback()
            msg = error_text(e)
            if "ya ha emitido su voto" in msg:
                print(f"[OK] EXITO: Bloqueado correctamente el intento de doble voto: '{msg}'")
            else:
                print(f"[FAIL] ERROR: Se capturó un error inesperado: '{msg}'")

        #  Verificación de encadenamiento de la Blockchain
        print("\nPrueba 5: Verificando integridad del encadenamiento del ledger...")
        cursor.execute(
            'SELECT "id_voto", "id_candidato", "hash_voto", "hash_anterior" '
            'FROM "public"."votos_blockchain" ORDER BY "id_voto" ASC;'
        )
        blocks = cursor.fetchall()  # tuplas: (id_voto, id_candidato, hash_voto, hash_anterior)

        is_chain_valid = True
        for i in range(1, len(blocks)):
            curr = blocks[i]
            prev = blocks[i - 1]
            curr_hash_anterior = curr[3]
            prev_hash_voto = prev[2]
            if curr_hash_anterior != prev_hash_voto:
                print(f"[FAIL] ROTURA DETECTADA en Bloque #{curr[0]}: "
                      f"hash_anterior no coincide con hash_voto del Bloque #{prev[0]}")
                is_chain_valid = False
                break

        if is_chain_valid:
            print(f"[OK] EXITO: Libro contable verificado en su totalidad. "
                  f"Todos los {len(blocks)} bloques están perfectamente encadenados.")

        cursor.close()
        conn.close()
        print("\n=== PRUEBAS COMPLETADAS ===")

    except Exception as e:
        if conn:
            conn.close()
        print(f"[FAIL] ERROR AL EJECUTAR PRUEBAS: {e}")


if __name__ == '__main__':
    run_tests()
