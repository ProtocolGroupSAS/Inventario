import os
import hashlib
import streamlit as st

try:
    import psycopg2
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False

# Unified Exception Classes
class Error(Exception):
    pass

class IntegrityError(Error):
    pass

# Global Connection Cache
DB_MODE = None

class PostgresConnection:
    def __init__(self, conn):
        self.conn = conn
    
    def cursor(self):
        return PostgresCursor(self.conn.cursor())
        
    def commit(self):
        try:
            self.conn.commit()
        except Exception as e:
            raise Error(str(e))
        
    def close(self):
        self.conn.close()

class PostgresCursor:
    def __init__(self, cursor):
        self.cursor = cursor
        self.lastrowid = None
        
    def execute(self, query, params=None):
        q_converted = query.replace('?', '%s')
        try:
            if params:
                import numpy as np
                clean_params = []
                for p in params:
                    if isinstance(p, (np.integer, np.floating, np.bool_)):
                        clean_params.append(p.item())
                    else:
                        clean_params.append(p)
                params = tuple(clean_params)
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
        except psycopg2.IntegrityError as e:
            raise IntegrityError(str(e))
        except psycopg2.Error as e:
            raise Error(str(e))
        except Exception as e:
            raise Error(str(e))
                
    def fetchone(self):
        return self.cursor.fetchone()
        
    def fetchall(self):
        return self.cursor.fetchall()
        
    def fetchmany(self, size):
        return self.cursor.fetchmany(size)
        
    @property
    def description(self):
        return self.cursor.description
        
    def close(self):
        self.cursor.close()

def get_db_url():
    try:
        return st.secrets["SUPABASE_URL"]
    except:
        return os.environ.get("SUPABASE_URL")

def get_connection():
    global DB_MODE
    
    if not HAS_POSTGRES:
        DB_MODE = "UNAVAILABLE"
        raise Exception("El driver psycopg2 no está instalado en este sistema.")
        
    url = get_db_url()
    if not url:
        DB_MODE = "UNAVAILABLE"
        raise Exception("Falta configurar SUPABASE_URL en st.secrets o en el entorno.")
        
    try:
        conn = psycopg2.connect(url, connect_timeout=5)
        DB_MODE = "POSTGRES"
        return PostgresConnection(conn)
    except Exception as e:
        DB_MODE = "UNAVAILABLE"
        raise Exception(f"No se pudo establecer conexión con Supabase: {e}")

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
    
    # Tablas: Solicitudes y Órdenes de Compra
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
    return None

if __name__ == "__main__":
    try:
        init_db()
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Database initialization failed: {e}")
