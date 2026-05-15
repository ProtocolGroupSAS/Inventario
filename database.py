import os
import psycopg2
from datetime import datetime
import hashlib
import streamlit as st

def get_db_url():
    # Intenta leer de st.secrets, si no, del entorno
    try:
        return st.secrets["SUPABASE_URL"]
    except:
        return os.environ.get("SUPABASE_URL")

class PostgresConnection:
    def __init__(self, conn):
        self.conn = conn
    
    def cursor(self):
        return PostgresCursor(self.conn.cursor())
        
    def commit(self):
        self.conn.commit()
        
    def close(self):
        self.conn.close()

class PostgresCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None
        
    def execute(self, query, params=None):
        # Convert SQLite ? to Postgres %s
        q_converted = query.replace('?', '%s')
            
        if params:
            self.cursor.execute(q_converted, params)
        else:
            self.cursor.execute(q_converted)
            
        is_insert = q_converted.strip().upper().startswith('INSERT')
        if is_insert and "RETURNING" in q_converted.upper():
            try:
                res = self.cursor.fetchone()
                if res:
                    self.lastrowid = res[0]
            except Exception as e:
                pass
                
    def fetchone(self):
        return self.cursor.fetchone()
        
    def fetchall(self):
        return self.cursor.fetchall()
        
    def fetchmany(self, size):
        return self.cursor.fetchmany(size)
        
    @property
    def description(self):
        return self.cursor.description

def get_connection():
    url = get_db_url()
    if not url:
        raise Exception("Falta configurar SUPABASE_URL en .streamlit/secrets.toml")
    conn = psycopg2.connect(url)
    return PostgresConnection(conn)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Insumos, Proyectos, Operarios, Categorias, Cuentas, Proveedores
    cursor.execute('CREATE TABLE IF NOT EXISTS insumos (id SERIAL PRIMARY KEY, nombre_insumo TEXT UNIQUE, unidad_medida TEXT, stock_actual REAL DEFAULT 0, categoria_id INTEGER, cuenta_id INTEGER, ultimo_precio REAL DEFAULT 0, ultimo_proveedor TEXT, ajuste_precio REAL DEFAULT 0)')
    cursor.execute('CREATE TABLE IF NOT EXISTS proyectos (id SERIAL PRIMARY KEY, nombre_proyecto TEXT UNIQUE, fecha_creacion TEXT, estado TEXT DEFAULT \'ACTIVO\')')
    cursor.execute('CREATE TABLE IF NOT EXISTS proveedores (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE, nit TEXT UNIQUE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS operarios (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS categorias (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS cuentas_contables (id SERIAL PRIMARY KEY, nombre TEXT UNIQUE)')
    
    # Nuevas Tablas: Solicitudes y Órdenes de Compra
    cursor.execute("CREATE TABLE IF NOT EXISTS solicitudes (id SERIAL PRIMARY KEY, user_id INTEGER, fecha TEXT, material TEXT, insumo_id INTEGER, proyecto_id INTEGER, cantidad REAL, proveedor TEXT, estado TEXT DEFAULT 'PENDIENTE')")
    cursor.execute("CREATE TABLE IF NOT EXISTS ordenes_compra (id SERIAL PRIMARY KEY, proyecto_id INTEGER, fecha TEXT, estado TEXT DEFAULT 'PENDIENTE')")
    cursor.execute("CREATE TABLE IF NOT EXISTS ordenes_items (id SERIAL PRIMARY KEY, orden_id INTEGER, insumo_id INTEGER, proveedor TEXT, solicitado REAL, disponible REAL, faltante REAL, recibido BOOLEAN DEFAULT FALSE)")
    cursor.execute("CREATE TABLE IF NOT EXISTS stock_comprometido (insumo_id INTEGER, proyecto_id INTEGER, cantidad REAL DEFAULT 0, PRIMARY KEY (insumo_id, proyecto_id))")
    cursor.execute("CREATE TABLE IF NOT EXISTS proyecto_materiales (proyecto_id INTEGER, insumo_id INTEGER, solicitado REAL DEFAULT 0, PRIMARY KEY (proyecto_id, insumo_id))")
    
    # Users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, 
            username TEXT UNIQUE, 
            password_hash TEXT, 
            role TEXT CHECK(role IN ('ADMIN', 'USER')),
            nombre TEXT,
            apellido TEXT,
            cc TEXT UNIQUE,
            pin_hash TEXT
        )
    ''')
    
    # Create default admin if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        pwd_hash = hashlib.sha256("admin".encode()).hexdigest()
        pin_hash = hashlib.sha256("1234".encode()).hexdigest()
        cursor.execute("INSERT INTO users (username, password_hash, role, nombre, apellido, cc, pin_hash) VALUES ('admin', %s, 'ADMIN', 'Administrador', 'Sistema', '000', %s)", (pwd_hash, pin_hash))
    
    # Movimientos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS movimientos (
            id SERIAL PRIMARY KEY,
            insumo_id INTEGER,
            proyecto_id INTEGER,
            operario_id INTEGER,
            categoria_id INTEGER,
            cuenta_id INTEGER,
            user_id INTEGER,
            cantidad REAL NOT NULL,
            tipo TEXT CHECK(tipo IN ('ENTRADA', 'SALIDA')),
            fecha_hora TEXT NOT NULL,
            precio_unitario REAL DEFAULT 0,
            proveedor TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def backup_db():
    return None # En la nube, Supabase hace los backups automáticamente

if __name__ == "__main__":
    init_db()
    print("PostgreSQL Database initialized.")
