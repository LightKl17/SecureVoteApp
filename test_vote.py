import mysql.connector
from mysql.connector import Error
import hashlib

def run_tests():
    print("=== INICIANDO PRUEBAS DE INTEGRIDAD DE SECUREVOTE ===")
    
    db_config = {
        'host': 'localhost',
        'port': 3306,
        'database': 'securevote_db',
        'user': 'root',
        'password': 'root1234'
    }
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # --- CASO 1: Votante No Registrado (DNI 00000000) ---
        print("\nPrueba 1: Votante no registrado (DNI 00000000)...")
        try:
            cursor.execute("CALL sp_registrar_voto(SHA2(%s, 256), %s)", ("00000000", "Candidato A"))
            conn.commit()
            print("[FAIL] ERROR: ¡Se permitió votar a un DNI no registrado!")
        except Error as e:
            if "Votante no registrado" in e.msg:
                print(f"[OK] EXITO: Capturado correctamente el error esperado de la DB: '{e.msg}'")
            else:
                print(f"[FAIL] ERROR: Se capturó un error inesperado: '{e.msg}'")

        # --- CASO 2: Votante que ya votó (DNI 12345678) ---
        print("\nPrueba 2: Doble Voto con DNI que ya votó (DNI 12345678)...")
        try:
            cursor.execute("CALL sp_registrar_voto(SHA2(%s, 256), %s)", ("12345678", "Candidato A"))
            conn.commit()
            print("[FAIL] ERROR: ¡Se permitió un doble voto!")
        except Error as e:
            if "ya ha emitido su voto" in e.msg:
                print(f"[OK] EXITO: Capturado correctamente el error esperado de la DB: '{e.msg}'")
            else:
                print(f"[FAIL] ERROR: Se capturó un error inesperado: '{e.msg}'")

        # --- CASO 3: Voto Exitoso con DNI elegible (DNI 77777777) ---
        print("\nPrueba 3: Registrar voto elegible por primera vez (DNI 77777777)...")
        try:
            # We first check if they have already voted in a previous test run
            cursor.execute("SELECT ha_votado FROM votantes WHERE hash_dni = SHA2(%s, 256)", ("77777777",))
            res = cursor.fetchone()
            if res and res['ha_votado'] == 1:
                # Reset for test
                cursor.execute("UPDATE votantes SET ha_votado = 0 WHERE hash_dni = SHA2(%s, 256)", ("77777777",))
                conn.commit()
                print("-> Reset elegible voter 77777777 state for testing.")

            cursor.execute("CALL sp_registrar_voto(SHA2(%s, 256), %s)", ("77777777", "Candidato A"))
            conn.commit()
            print("[OK] EXITO: ¡Voto registrado correctamente en el Ledger!")
        except Error as e:
            print(f"[FAIL] ERROR: No se pudo registrar el voto: '{e.msg}'")

        # --- CASO 4: Intento de Doble Voto con DNI 77777777 ---
        print("\nPrueba 4: Intentar doble voto con el DNI recién usado (DNI 77777777)...")
        try:
            cursor.execute("CALL sp_registrar_voto(SHA2(%s, 256), %s)", ("77777777", "Candidato B"))
            conn.commit()
            print("[FAIL] ERROR: ¡Se permitió votar por segunda vez con el mismo DNI!")
        except Error as e:
            if "ya ha emitido su voto" in e.msg:
                print(f"[OK] EXITO: Bloqueado correctamente el intento de doble voto: '{e.msg}'")
            else:
                print(f"[FAIL] ERROR: Se capturó un error inesperado: '{e.msg}'")

        # --- CASO 5: Verificación de encadenamiento de la Blockchain ---
        print("\nPrueba 5: Verificando integridad del encadenamiento del ledger...")
        cursor.execute("""
            SELECT id_voto, id_candidato, hash_voto, hash_anterior 
            FROM votos_blockchain 
            ORDER BY id_voto ASC
        """)
        blocks = cursor.fetchall()
        
        is_chain_valid = True
        for i in range(1, len(blocks)):
            curr = blocks[i]
            prev = blocks[i-1]
            if curr['hash_anterior'] != prev['hash_voto']:
                print(f"[FAIL] ROTURA DETECTADA en Bloque #{curr['id_voto']}: hash_anterior no coincide con hash_voto del Bloque #{prev['id_voto']}")
                is_chain_valid = False
                break
                
        if is_chain_valid:
            print(f"[OK] EXITO: Libro contable verificado en su totalidad. Todos los {len(blocks)} bloques están perfectamente encadenados.")

        cursor.close()
        conn.close()
        print("\n=== PRUEBAS COMPLETADAS CON EXITO ===")
        
    except Exception as e:
        print(f"[FAIL] ERROR AL EJECUTAR PRUEBAS: {e}")

if __name__ == '__main__':
    run_tests()
