import mysql.connector
import hashlib

def get_hash(dni):
    return hashlib.sha256(dni.encode('utf-8')).hexdigest()

def main():
    test_voters = [
        ('77777777', get_hash('77777777')),
        ('88888888', get_hash('88888888')),
        ('99999999', get_hash('99999999'))
    ]

    print("Connecting to securevote_db to set up test voters...")
    try:
        conn = mysql.connector.connect(
            host="localhost",
            port=3306,
            database="securevote_db",
            user="root",
            password="root1234"
        )
        cursor = conn.cursor()

        # 1. Insert test voters if not exists
        for dni, h_dni in test_voters:
            cursor.execute("SELECT id_votante, ha_votado FROM votantes WHERE hash_dni = %s", (h_dni,))
            res = cursor.fetchone()
            if res:
                print(f"Voter DNI: {dni} (Hash: {h_dni}) already exists. ha_votado: {res[1]}")
                # Reset voting status to allow re-testing if needed
                if res[1] == 1:
                    cursor.execute("UPDATE votantes SET ha_votado = 0 WHERE hash_dni = %s", (h_dni,))
                    print(f"-> Reset ha_votado to 0 for DNI: {dni} for fresh testing!")
            else:
                cursor.execute("INSERT INTO votantes (hash_dni, ha_votado) VALUES (%s, 0)", (h_dni,))
                print(f"Inserted Voter DNI: {dni} (Hash: {h_dni}) with ha_votado = 0")

        conn.commit()
        print("\nSetup of test voters completed successfully!")
        
        # Verify total voter count
        cursor.execute("SELECT COUNT(*) FROM votantes")
        print(f"Total voters in database: {cursor.fetchone()[0]}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error during setup: {e}")

if __name__ == '__main__':
    main()
