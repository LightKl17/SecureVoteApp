import os
import psycopg2
from psycopg2.extras import RealDictCursor
import hashlib
import hmac
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Lectura de la cadena de conexión de Render o valores separados por compatibilidad
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL)
    else:
        return psycopg2.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            port=int(os.environ.get('DB_PORT', 5432)),
            database=os.environ.get('DB_NAME', 'postgres'),
            user=os.environ.get('DB_USER', 'postgres'),
            password=os.environ.get('DB_PASSWORD', ''),
            sslmode='require',
            connect_timeout=10
        )

# Permite leer tanto SECRET_PEPPER como DNI_PEPPER
DNI_PEPPER = os.environ.get('SECRET_PEPPER') or os.environ.get('DNI_PEPPER') or 'PEPPER_DEMO'

def hashear_dni(dni_limpio):
    return hmac.new(
        DNI_PEPPER.encode('utf-8'),
        dni_limpio.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

@app.route('/')
def index():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Fetch election info
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
        conn.autocommit = True
        cursor = conn.cursor()
        
        dni_limpio = dni.strip()
        hash_dni = hashear_dni(dni_limpio)
        candidato_limpio = str(candidato).strip()

        # Llamar al procedimiento almacenado
        query = 'CALL "public"."sp_registrar_voto"(%s, %s);'
        cursor.execute(query, (hash
