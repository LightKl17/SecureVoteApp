from flask import Flask, render_template, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import os  # Importamos la librería de sistema para leer variables de entorno

app = Flask(__name__)

# DB Configuration - Lectura segura desde el entorno o valores por defecto
db_config = {
    'host': os.environ.get('DB_HOST', 'db-pq.postgres.database.azure.com'),
    'port': int(os.environ.get('DB_PORT', 5432)),
    'database': os.environ.get('DB_NAME', 'postgres'), 
    'user': os.environ.get('DB_USER', 'user'),
    'password': os.environ.get('DB_PASSWORD', 'SecureVote2026*'), 
    'sslmode': 'require'    
}

def get_db_connection():
    return psycopg2.connect(**db_config)

@app.route('/')
def index():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Fetch election info - Con esquema explícito
        cursor.execute('SELECT * FROM "public"."elecciones" ORDER BY "id_eleccion" DESC LIMIT 1;')
        election = cursor.fetchone()
        
        # Fetch candidates
        if election:
            cursor.execute('SELECT * FROM "public"."candidatos" WHERE "id_eleccion" = %s;', (election['id_eleccion'],))
        else:
            cursor.execute('SELECT * FROM "public"."candidatos";')
        candidates = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return render_template('index.html', election=election, candidates=candidates)
    except Exception as e:
        if conn:
            conn.close()
        return f"Error connecting to database: {e}", 500

@app.route('/results')
def results():
    return render_template('results.html')

@app.route('/api/votar', methods=['POST'])
def api_votar():
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': 'Datos no proporcionados'}), 400
        
    dni = data.get('dni')
    candidato = data.get('candidato')
    
    if not dni or not candidato:
        return jsonify({'success': False, 'message': 'DNI y Candidato son requeridos'}), 400
        
    if not dni.strip().isdigit() or len(dni.strip()) != 8:
        return jsonify({'success': False, 'message': 'El DNI debe ser numérico y contener exactamente 8 dígitos'}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Calculamos el hash SHA256 de forma local con Python
        dni_limpio = dni.strip()
        hash_dni = hashlib.sha256(dni_limpio.encode('utf-8')).hexdigest()
        
        # 2. Llamamos al procedimiento pasando parámetros limpios en texto
        query = 'CALL "public"."sp_registrar_voto"(%s, %s);'
        cursor.execute(query, (hash_dni, str(candidato).strip()))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': '¡Voto registrado y firmado exitosamente en la Blockchain!'
        })
        
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
            conn.close()
        error_msg = e.pgerror if hasattr(e, 'pgerror') else str(e)
        if "CONTEXT:" in error_msg:
            error_msg = error_msg.split("CONTEXT:")[0]
        return jsonify({'success': False, 'message': error_msg.strip()}), 400
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'success': False, 'message': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/blockchain', methods=['GET'])
def api_blockchain():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Fetch Candidates and vote counts
        cursor.execute("""
            SELECT 
                c["id_candidato"], c["nombre"], c["partido"], c["hash"],
                COUNT(v["id_voto"]) as votos
            FROM "public"."candidatos" c
            LEFT JOIN "public"."votos_blockchain" v ON c["id_candidato"] = v["id_candidato"]
            GROUP BY c["id_candidato"], c["nombre"], c["partido"], c["hash"]
            ORDER BY votos DESC;
        """)
        candidates_votes = cursor.fetchall()
        
        # 2. Fetch Blockchain ledger
        cursor.execute("""
            SELECT 
                v["id_voto"], c["nombre"] as candidato_nombre, c["partido"] as candidato_partido,
                v["hash_voto"], v["hash_anterior"], v["timestamp"]
            FROM "public"."votos_blockchain" v
            JOIN "public"."candidatos" c ON v["id_candidato"] = c["id_candidato"]
            ORDER BY v["id_voto"] ASC;
        """)
        blockchain_ledger = cursor.fetchall()
        
        # 3. Fetch Audit log
        cursor.execute('SELECT "id_log", "accion", "fecha" FROM "public"."auditoria" ORDER BY "id_log" DESC LIMIT 50;')
        audit_logs = cursor.fetchall()
        
        # 4. Count total registered voters
        cursor.execute('SELECT COUNT(*) as total FROM "public"."votantes";')
        res_total = cursor.fetchone()
        total_voters = res_total['total'] if res_total else 0
        
        # 5. Count voters who have voted
        cursor.execute('SELECT COUNT(*) as voted FROM "public"."votantes" WHERE "ha_votado" = 1;')
        res_voted = cursor.fetchone()
        voted_voters = res_voted['voted'] if res_voted else 0
        
        cursor.close()
        conn.close()
        
        # Format timestamps as strings for JSON serialization
        for block in blockchain_ledger:
            if block['timestamp']:
                block['timestamp'] = block['timestamp'].strftime('%Y-%m-%d %H:%M:%S')
                
        for log in audit_logs:
            if log['fecha']:
                log['fecha'] = log['fecha'].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({
            'success': True,
            'candidates': candidates_votes,
            'blockchain': blockchain_ledger,
            'audit': audit_logs,
            'stats': {
                'total_registered': total_voters,
                'total_voted': voted_voters,
                'participation_rate': round((voted_voters / total_voters * 100), 2) if total_voters > 0 else 0
            }
        })
        
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({'success': False, 'message': f'Error al consultar datos: {str(e)}'}), 500

if __name__ == '__main__':
    # Azure usa la variable PORT dinámicamente para enlazar el contenedor web
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)