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
        # En Render se conecta directamente mediante la URI completa
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
