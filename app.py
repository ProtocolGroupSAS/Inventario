import streamlit as st
import pandas as pd
from database import get_connection, init_db, backup_db
from datetime import datetime, date
import sqlite3
import hashlib
import os

# Configuration
st.set_page_config(page_title="Protocol Inventory", layout="wide", initial_sidebar_state="expanded")
init_db()

# --- AUTH SYSTEM ---
def hash_val(val): return hashlib.sha256(val.encode()).hexdigest() if val else ""

def check_admin_login(cc, pwd):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT id, role, nombre FROM users WHERE cc=? AND password_hash=? AND role='ADMIN'", (cc, hash_val(pwd)))
    res = cursor.fetchone()
    conn.close()
    return res if res else None

def verify_user_pin(uid, pin):
    conn = get_connection(); cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, apellido FROM users WHERE id=? AND pin_hash=?", (uid, hash_val(pin)))
    res = cursor.fetchone()
    conn.close()
    return res if res else None

if 'admin_logged_in' not in st.session_state: st.session_state.admin_logged_in = False
if 'admin_user' not in st.session_state: st.session_state.admin_user = None
if 'feedback' not in st.session_state: st.session_state.feedback = None
if 'current_page' not in st.session_state: st.session_state.current_page = "Salidas"
if 'salida_cart' not in st.session_state: st.session_state.salida_cart = []
if 'entrada_cart' not in st.session_state: st.session_state.entrada_cart = []
if 'solicitud_cart' not in st.session_state: st.session_state.solicitud_cart = []

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #FFFFFF;
        color: #2D3436;
    }
    
    .main { padding: 2rem; }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: #F8F9FA;
        border-right: 1px solid #E9ECEF;
    }
    
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        font-size: 1.1rem;
        font-weight: 600;
        color: #00AEEF;
    }

    /* Remove radio button dots/circles (Minimalist approach) */
    [data-testid="stSidebarNav"] ul {
        padding-top: 2rem;
    }
    
    /* Generic buttons */
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        border: none;
        background-color: #00AEEF;
        color: white !important;
        font-weight: 700;
        height: 3rem;
        transition: all 0.3s ease;
        box-shadow: 0 4px 6px rgba(0, 174, 239, 0.2);
    }
    
    .stButton>button div p {
        color: white !important;
    }
    
    .stButton>button:hover {
        background-color: #FF8C00;
        box-shadow: 0 6px 12px rgba(255, 140, 0, 0.3);
        transform: translateY(-2px);
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #00AEEF;
        font-weight: 800;
    }
    
    /* Expander and containers */
    .stExpander {
        border-radius: 12px !important;
        border: 1px solid #E9ECEF !important;
        background-color: #FFFFFF !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
    }
    
    /* Input fields */
    .stTextInput>div>div>input, .stNumberInput>div>div>input {
        border-radius: 10px;
        border: 1px solid #E9ECEF;
    }
    
    /* Data Editor */
    [data-testid="stDataEditor"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #E9ECEF;
    }
    
    /* Feedback messages */
    .success-msg { padding: 1rem; background-color: #E3FCEF; color: #006644; border-radius: 12px; text-align: center; font-weight: 600; border-left: 5px solid #00AEEF; }
    .warning-msg { padding: 1rem; background-color: #FFF9E6; color: #856604; border-radius: 12px; text-align: center; font-weight: 600; border-left: 5px solid #FF8C00; }
    .error-msg { padding: 1rem; background-color: #FFEBE6; color: #BF2600; border-radius: 12px; text-align: center; font-weight: 600; border-left: 5px solid #FF5630; }
    
    /* Hide specific streamlit elements for a cleaner look */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Custom Logo Container */
    .logo-container {
        text-align: center;
        padding: 2rem 1rem;
        margin-bottom: 1rem;
    }
    .logo-text {
        color: #00AEEF;
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: -1px;
    }
    .logo-dot {
        color: #FF8C00;
    }

    /* Responsive adaptations for Tablets and Mobile */
    @media screen and (max-width: 1024px) {
        .main { padding: 1rem; }
        .logo-text { font-size: 2.2rem; }
        .stButton>button { height: 3.5rem; font-size: 1.1rem; color: white !important; }
        [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
        [data-testid="stHorizontalBlock"] > div { min-width: 280px !important; flex: 1 1 auto !important; }
        [data-testid="stMetricValue"] { font-size: 1.5rem !important; }
        
        /* Aumentar tamaño de opciones de radio en móviles */
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
            font-size: 1.2rem !important;
        }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
            font-size: 1.2rem !important;
        }
        div[role="radiogroup"] label {
            padding: 12px 0px !important;
            font-size: 1.1rem !important;
        }
        div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {
            font-size: 1.1rem !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
def normalize(text): return str(text).strip().upper() if text and not pd.isna(text) else ""
def fmt_und(u): return str(u) if pd.notna(u) and str(u).strip() else 'UND'

def get_data(table, columns="*", order_by="id"):
    conn = get_connection(); df = pd.read_sql_query(f"SELECT {columns} FROM {table} ORDER BY {order_by}", conn); conn.close()
    return df

def delete_item(table, item_id):
    conn = get_connection(); cursor = conn.cursor()
    try:
        if table == 'movimientos':
            cursor.execute("SELECT insumo_id, cantidad, tipo FROM movimientos WHERE id=?", (item_id,))
            m = cursor.fetchone()
            if m:
                f = -1 if m[2] == "ENTRADA" else 1
                cursor.execute("UPDATE insumos SET stock_actual = stock_actual + ? WHERE id=?", (m[1] * f, m[0]))
        cursor.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
        conn.commit(); return True
    except sqlite3.Error: return False
    finally: conn.close()

def to_excel_bytes(df):
    from io import BytesIO
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Datos')
    return output.getvalue()

# --- SIDEBAR NAVIGATION ---
with st.sidebar:
    st.markdown('<div class="logo-container"><span class="logo-text">protocol<span class="logo-dot">.</span></span></div>', unsafe_allow_html=True)
    
    if st.session_state.admin_logged_in:
        menu_options = ["Salidas", "Entradas", "Solicitar Material", "Inventario", "Dashboard", "Proyectos", "Ordenes de Compra", "Analisis", " Configs", " Importar/Exportar", "Usuarios", "Backup"]
    else:
        menu_options = ["Salidas", "Entradas", "Solicitar Material"]
    
    page = st.radio("Navegacion", menu_options, key="nav_radio")
    
    st.write("---")
    if not st.session_state.admin_logged_in:
        st.write("Acceso Administrador")
        admin_cc = st.text_input("Cedula", key="admin_cc")
        admin_pwd = st.text_input("Contrasena", type="password", key="admin_pwd")
        if st.button("Iniciar Sesion"):
            admin = check_admin_login(admin_cc, admin_pwd)
            if admin:
                st.session_state.admin_logged_in = True
                st.session_state.admin_user = admin
                st.rerun()
            else:
                st.error("Credenciales invalidas")
    else:
        st.write(f"Admin: {st.session_state.admin_user[2]}")
        if st.button("Cerrar Sesion"):
            st.session_state.admin_logged_in = False
            st.rerun()

# --- MAIN PAGE LOGIC ---
if st.session_state.feedback:
    msg, type_ = st.session_state.feedback
    st.markdown(f'<div class="{type_}-msg">{msg}</div>', unsafe_allow_html=True)
    st.session_state.feedback = None

if page == "Salidas":
    st.subheader("Registro de Salida de Material (Carga Masiva)")
    
    # 1. Datos Generales (Se mantienen para todos los items)
    with st.expander("1. Datos del Proyecto y Responsable", expanded=True):
        df_p = get_data("proyectos")
        p_opts = {r['nombre_proyecto']: r['id'] for _, r in df_p.iterrows()} if not df_p.empty else {}
        df_us = get_data("users", "id, nombre, apellido")
        u_opt = {f"{r['nombre']} {r['apellido']}": r['id'] for _, r in df_us.iterrows()}
        
        c1, c2 = st.columns(2)
        proy_name = c1.selectbox("Proyecto Destino", list(p_opts.keys()), index=None, placeholder="Seleccione Proyecto")
        u_sel_name = c2.selectbox("Quien entrega?", list(u_opt.keys()), index=None, placeholder="Seleccione Usuario")
    
    # 2. Agregar Items a la lista
    with st.expander("2. Agregar Materiales a la Lista", expanded=True):
        df_i = pd.read_sql_query("SELECT id, nombre_insumo, stock_actual, unidad_medida FROM insumos", get_connection())
        i_opts = {f"{r['nombre_insumo']} (Stock: {r['stock_actual']})": (r['id'], r['nombre_insumo'], r['stock_actual']) for _, r in df_i.iterrows()} if not df_i.empty else {}
        
        ca1, ca2, ca3 = st.columns([2, 1, 1])
        sel_i_key = ca1.selectbox("Material", list(i_opts.keys()), key="salida_mat_sel", index=None, placeholder="Seleccione Material")
        cant = ca2.number_input("Cantidad", min_value=0.01, key="salida_cant", value=None)
        
        if ca3.button("➕ Agregar a Lista", use_container_width=True):
            if sel_i_key:
                ins_id, m_name, stock = i_opts[sel_i_key]
                # Verificar si ya está en el carrito para no duplicar filas sino sumar (opcional, aquí solo agregamos)
                st.session_state.salida_cart.append({
                    "ID": ins_id,
                    "MATERIAL": m_name,
                    "CANTIDAD": cant,
                    "STOCK_ACTUAL": stock
                })
                st.rerun()

    # 3. Mostrar Lista y Procesar
    if st.session_state.salida_cart:
        st.write("#### Lista de Materiales a Salir")
        df_cart = pd.DataFrame(st.session_state.salida_cart)
        
        # Permitir eliminar de la lista
        df_cart.insert(0, "QUITAR", False)
        ed_cart = st.data_editor(df_cart, use_container_width=True, hide_index=True, key="ed_salida_cart")
        
        if st.button("Limpiar Lista"):
            st.session_state.salida_cart = []
            st.rerun()

        # Actualizar el carrito si se quitó algo
        if not ed_cart[ed_cart["QUITAR"]].empty:
            st.session_state.salida_cart = ed_cart[~ed_cart["QUITAR"]].drop(columns=["QUITAR"]).to_dict('records')
            st.rerun()
            
        st.write("---")
        c_p1, c_p2 = st.columns([1, 1])
        pin = c_p1.text_input("PIN Autorizacion para Procesar Todo", type="password")
        
        if c_p2.button("🚀 REGISTRAR TODA LA SALIDA", use_container_width=True):
            if not pin: st.error("Debe ingresar el PIN")
            else:
                p_id = p_opts[proy_name]
                u_id = u_opt[u_sel_name]
                if verify_user_pin(u_id, pin):
                    conn = get_connection(); cursor = conn.cursor()
                    errores = []
                    for item in st.session_state.salida_cart:
                        if item['CANTIDAD'] > item['STOCK_ACTUAL']:
                            errores.append(f"Stock insuficiente para {item['MATERIAL']}")
                            continue
                        
                        cursor.execute("INSERT INTO movimientos (insumo_id, proyecto_id, user_id, tipo, cantidad, fecha_hora) VALUES (?, ?, ?, 'SALIDA', ?, ?)",
                                       (item['ID'], p_id, u_id, item['CANTIDAD'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                        cursor.execute("UPDATE insumos SET stock_actual = stock_actual - ? WHERE id=?", (item['CANTIDAD'], item['ID']))
                        cursor.execute("UPDATE stock_comprometido SET cantidad = MAX(0, cantidad - ?) WHERE insumo_id=? AND proyecto_id=?", (item['CANTIDAD'], item['ID'], p_id))
                    
                    if errores:
                        st.error(" / ".join(errores))
                    else:
                        conn.commit(); conn.close()
                        st.session_state.salida_cart = []
                        st.session_state.feedback = ("Todas las salidas registradas correctamente", "success"); st.rerun()
                else: st.error("PIN Incorrecto")

elif page == "Entradas":
    st.subheader("Registro de Entrada de Material (Carga Masiva)")
    
    # 1. Datos del Proveedor
    with st.expander("1. Datos de la Compra", expanded=True):
        prov = st.text_input("Proveedor").upper()
    
    # 2. Agregar Items
    with st.expander("2. Agregar Materiales a la Lista", expanded=True):
        df_i = get_data("insumos", "id, nombre_insumo")
        i_opts = {r['nombre_insumo']: r['id'] for _, r in df_i.iterrows()} if not df_i.empty else {}
        
        ca1, ca2, ca3 = st.columns([2, 1, 1])
        ins_name = ca1.selectbox("Material", list(i_opts.keys()), key="ent_mat_sel", index=None, placeholder="Seleccione Material")
        cant = ca2.number_input("Cantidad", min_value=0.01, key="ent_cant", value=None)
        precio = ca3.number_input("Precio Unitario", min_value=0.0, key="ent_precio", value=None)
        
        if st.button("➕ Agregar a Lista", key="btn_add_ent"):
            if ins_name:
                st.session_state.entrada_cart.append({
                    "ID": i_opts[ins_name],
                    "MATERIAL": ins_name,
                    "CANTIDAD": cant,
                    "PRECIO": precio
                })
                st.rerun()

    # 3. Mostrar Lista y Procesar
    if st.session_state.entrada_cart:
        st.write("#### Lista de Materiales a Ingresar")
        df_cart = pd.DataFrame(st.session_state.entrada_cart)
        df_cart.insert(0, "QUITAR", False)
        ed_cart = st.data_editor(df_cart, use_container_width=True, hide_index=True, key="ed_ent_cart")
        
        if st.button("Limpiar Lista", key="btn_clear_ent"):
            st.session_state.entrada_cart = []
            st.rerun()
            
        if not ed_cart[ed_cart["QUITAR"]].empty:
            st.session_state.entrada_cart = ed_cart[~ed_cart["QUITAR"]].drop(columns=["QUITAR"]).to_dict('records')
            st.rerun()

        if st.button("🚀 REGISTRAR TODA LA ENTRADA", use_container_width=True):
            conn = get_connection(); cursor = conn.cursor()
            for item in st.session_state.entrada_cart:
                cursor.execute("INSERT INTO movimientos (insumo_id, tipo, cantidad, precio_unitario, proveedor, fecha_hora) VALUES (?, 'ENTRADA', ?, ?, ?, ?)",
                               (item['ID'], item['CANTIDAD'], item['PRECIO'], prov, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                cursor.execute("UPDATE insumos SET stock_actual = stock_actual + ?, ultimo_precio = ? WHERE id=?", (item['CANTIDAD'], item['PRECIO'], item['ID']))
            conn.commit(); conn.close()
            st.session_state.entrada_cart = []
            st.session_state.feedback = ("Todas las entradas registradas correctamente", "success"); st.rerun()

elif page == "Inventario" and st.session_state.admin_logged_in:
    st.subheader("Gestion de Inventario")
    t_list, t_new = st.tabs(["Listado e Inventario", "Crear Nuevo Insumo"])
    
    with t_list:
        df_s = pd.read_sql_query("""
            SELECT i.id as "ID", i.nombre_insumo as "MATERIAL", i.unidad_medida as "UND",
                   COALESCE((SELECT SUM(cantidad) FROM movimientos WHERE insumo_id = i.id AND tipo = 'ENTRADA'), 0) as "INGRESADO",
                   COALESCE((SELECT SUM(cantidad) FROM movimientos WHERE insumo_id = i.id AND tipo = 'SALIDA'), 0) as "SALIDO",
                   i.stock_actual as "STOCK",
                   COALESCE((SELECT SUM(cantidad) FROM stock_comprometido WHERE insumo_id = i.id), 0) as "COMPROMETIDO",
                   (i.stock_actual - COALESCE((SELECT SUM(cantidad) FROM stock_comprometido WHERE insumo_id = i.id), 0)) as "DISPONIBLE",
                   0 as "FALTANTE",
                   i.ajuste_precio as "AJUSTE", i.ultimo_precio as "PRECIO", (i.ultimo_precio + i.ajuste_precio) as "PRECIO_AJUSTADO",
                   cat.nombre as "CATEGORIA", cta.nombre as "CUENTA"
            FROM insumos i
            LEFT JOIN categorias cat ON i.categoria_id = cat.id
            LEFT JOIN cuentas_contables cta ON i.cuenta_id = cta.id
        """, get_connection())
        
        c_f1, c_f2, c_f3 = st.columns([2,1,1])
        search = c_f1.text_input("Buscar Material").upper()
        cat_filt = c_f2.selectbox("Filtro Categoria", ["TODAS"] + list(df_s['CATEGORIA'].dropna().unique()))
        cta_filt = c_f3.selectbox("Filtro Cuenta", ["TODAS"] + list(df_s['CUENTA'].dropna().unique()))
        
        if search: df_s = df_s[df_s['MATERIAL'].str.contains(search)]
        if cat_filt != "TODAS": df_s = df_s[df_s['CATEGORIA'] == cat_filt]
        if cta_filt != "TODAS": df_s = df_s[df_s['CUENTA'] == cta_filt]
        
        df_s.insert(0, "ELIMINAR", False)
        
        ed_stock = st.data_editor(df_s, use_container_width=True, hide_index=True,
                                  disabled=["ID", "INGRESADO", "SALIDO", "STOCK", "COMPROMETIDO", "DISPONIBLE", "FALTANTE", "PRECIO", "PRECIO_AJUSTADO"])
        
        c_b1, c_b2 = st.columns(2)
        if c_b1.button("Guardar Cambios"):
            conn = get_connection(); cursor = conn.cursor()
            for _, r in ed_stock.iterrows():
                cursor.execute("UPDATE insumos SET nombre_insumo=?, unidad_medida=?, ajuste_precio=? WHERE id=?",
                               (r['MATERIAL'], r['UND'], r['AJUSTE'], r['ID']))
            conn.commit(); conn.close()
            st.session_state.feedback = ("Inventario actualizado", "success"); st.rerun()
            
        if c_b2.button("Eliminar Seleccionados"):
            del_ids = ed_stock[ed_stock["ELIMINAR"]]["ID"].tolist()
            if del_ids:
                conn = get_connection(); cursor = conn.cursor()
                for d_id in del_ids: cursor.execute("DELETE FROM insumos WHERE id=?", (d_id,))
                conn.commit(); conn.close()
                st.session_state.feedback = ("Insumos eliminados", "success"); st.rerun()

        st.write("---")
        st.write("#### Distribucion de Stock Comprometido por Proyecto")
        conn = get_connection()
        df_sc = pd.read_sql_query("""
            SELECT sc.insumo_id as "INS_ID", i.nombre_insumo as "MATERIAL", sc.proyecto_id as "PROY_ID", p.nombre_proyecto as "PROYECTO", sc.cantidad as "SEPARADO"
            FROM stock_comprometido sc 
            JOIN insumos i ON sc.insumo_id = i.id 
            JOIN proyectos p ON sc.proyecto_id = p.id
            WHERE sc.cantidad > 0
        """, conn)
        conn.close()
        if not df_sc.empty:
            df_sc.insert(0, "LIBERAR_TODO", False)
            ed_sc = st.data_editor(df_sc, hide_index=True, disabled=["INS_ID", "MATERIAL", "PROY_ID", "PROYECTO"])
            if st.button("Aplicar Cambios de Distribucion"):
                conn = get_connection(); cursor = conn.cursor()
                for _, r_new in ed_sc.iterrows():
                    if r_new['LIBERAR_TODO']:
                        cursor.execute("DELETE FROM stock_comprometido WHERE insumo_id=? AND proyecto_id=?", (r_new['INS_ID'], r_new['PROY_ID']))
                    else:
                        cursor.execute("UPDATE stock_comprometido SET cantidad = ? WHERE insumo_id=? AND proyecto_id=?", (r_new['SEPARADO'], r_new['INS_ID'], r_new['PROY_ID']))
                conn.commit(); conn.close()
                st.session_state.feedback = ("Distribucion actualizada", "success"); st.rerun()

    with t_new:
        st.write("#### Registrar Nuevo Material")
        c1, c2 = st.columns(2)
        n_ins = c1.text_input("Nombre del Material", key="new_mat").upper()
        n_und = c1.text_input("Unidad de Medida").upper()
        
        df_cat = get_data("categorias")
        cat_opt = {r['nombre']: r['id'] for _, r in df_cat.iterrows()}
        sel_cat = c2.selectbox("Categoria", list(cat_opt.keys()))
        
        df_cta = get_data("cuentas_contables")
        cta_opt = {r['nombre']: r['id'] for _, r in df_cta.iterrows()}
        sel_cta = c2.selectbox("Cuenta Contable", list(cta_opt.keys()))
        
        if st.button("Crear Insumo"):
            if n_ins:
                conn = get_connection(); cursor = conn.cursor()
                cursor.execute("INSERT INTO insumos (nombre_insumo, unidad_medida, categoria_id, cuenta_id) VALUES (?, ?, ?, ?)",
                               (n_ins, n_und, cat_opt[sel_cat], cta_opt[sel_cta]))
                conn.commit(); conn.close()
                st.session_state.feedback = ("Insumo creado", "success"); st.rerun()

elif page == "Solicitar Material":
    st.subheader("Solicitud de Material (Carga Masiva)")
    
    # 1. Datos del Solicitante
    with st.expander("1. Datos del Solicitante", expanded=True):
        df_us = get_data("users", "id, nombre, apellido")
        u_opt = {f"{r['nombre']} {r['apellido']}": r['id'] for _, r in df_us.iterrows()}
        u_sel_name = st.selectbox("Quien solicita?", list(u_opt.keys()), key="req_u_sel")
    
    # 2. Agregar Items
    with st.expander("2. Agregar Materiales a la Lista", expanded=True):
        df_i = get_data("insumos", "id, nombre_insumo")
        i_opts = {r['nombre_insumo']: r['id'] for _, r in df_i.iterrows()} if not df_i.empty else {}
        i_list = ["(NUEVO)"] + list(i_opts.keys())
        
        ca1, ca2, ca3 = st.columns([2, 1, 1])
        mat_sel = ca1.selectbox("Material", i_list, key="req_mat_sel")
        if mat_sel == "(NUEVO)":
            mat_name = ca1.text_input("Especificar Material Nuevo", key="req_mat_new").upper()
            ins_id = None
        else:
            mat_name = mat_sel
            ins_id = i_opts[mat_sel]
            
        cant = ca2.number_input("Cantidad", min_value=0.1, key="req_cant")
        
        if ca3.button("➕ Agregar", key="btn_add_req"):
            if mat_name:
                st.session_state.solicitud_cart.append({
                    "ID": ins_id,
                    "MATERIAL": mat_name,
                    "CANTIDAD": cant
                })
                st.rerun()

    # 3. Mostrar Lista y Procesar
    if st.session_state.solicitud_cart:
        st.write("#### Lista de Materiales Solicitados")
        df_cart = pd.DataFrame(st.session_state.solicitud_cart)
        df_cart.insert(0, "QUITAR", False)
        ed_cart = st.data_editor(df_cart, use_container_width=True, hide_index=True, key="ed_req_cart")
        
        if st.button("Limpiar Lista", key="btn_clear_req"):
            st.session_state.solicitud_cart = []
            st.rerun()

        if not ed_cart[ed_cart["QUITAR"]].empty:
            st.session_state.solicitud_cart = ed_cart[~ed_cart["QUITAR"]].drop(columns=["QUITAR"]).to_dict('records')
            st.rerun()
            
        st.write("---")
        c_p1, c_p2 = st.columns([1, 1])
        pin = c_p1.text_input("PIN para Confirmar Solicitud", type="password", key="req_pin")
        
        if c_p2.button("🚀 ENVIAR TODA LA SOLICITUD", use_container_width=True):
            if not pin: st.error("Debe ingresar el PIN")
            else:
                u_id = u_opt[u_sel_name]
                if verify_user_pin(u_id, pin):
                    conn = get_connection(); cursor = conn.cursor()
                    for item in st.session_state.solicitud_cart:
                        cursor.execute("INSERT INTO solicitudes (user_id, material, insumo_id, cantidad, fecha, estado) VALUES (?, ?, ?, ?, ?, 'PENDIENTE')",
                                       (u_id, item['MATERIAL'], item['ID'], item['CANTIDAD'], datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    conn.commit(); conn.close()
                    st.session_state.solicitud_cart = []
                    st.session_state.feedback = ("Todas las solicitudes enviadas correctamente", "success"); st.rerun()
                else: st.error("PIN Incorrecto")


# --- ADMIN RESTRICTED PAGES ---
elif page == "Dashboard" and st.session_state.admin_logged_in:
    st.subheader("Dashboard Analitico")
    try:
        import plotly.express as px
        conn = get_connection()
        df_py = pd.read_sql_query("""
            SELECT p.nombre_proyecto as "PROYECTO", SUM(m.cantidad * m.precio_unitario) as "TOTAL"
            FROM movimientos m JOIN proyectos p ON m.proyecto_id = p.id
            WHERE m.tipo = 'SALIDA' GROUP BY p.nombre_proyecto
        """, conn)
        df_top = pd.read_sql_query("""
            SELECT i.nombre_insumo as "MATERIAL", SUM(m.cantidad) as "CONSUMO"
            FROM movimientos m JOIN insumos i ON m.insumo_id = i.id
            WHERE m.tipo = 'SALIDA' GROUP BY i.nombre_insumo ORDER BY "CONSUMO" DESC LIMIT 5
        """, conn)
        conn.close()
        
        c1, c2 = st.columns(2)
        if not df_py.empty: c1.plotly_chart(px.bar(df_py, x='PROYECTO', y='TOTAL', title='Gastos Totales por Proyecto', color='PROYECTO'))
        if not df_top.empty: c2.plotly_chart(px.pie(df_top, names='MATERIAL', values='CONSUMO', title='Top 5 Insumos Más Consumidos', hole=0.3))
    except ImportError: st.error("Instalando gráficos... Por favor reinicia la aplicación en unos segundos.")

elif page == "Proyectos" and st.session_state.admin_logged_in:
    st.subheader("Gestion de Proyectos (BOM y Compras)")
    df_p = get_data("proyectos", "id, nombre_proyecto")
    if df_p.empty:
        st.warning("No hay proyectos creados.")
    else:
        p_opts = {r['nombre_proyecto']: r['id'] for _, r in df_p.iterrows()}
        sel_proy_name = st.selectbox("Seleccione Proyecto", options=list(p_opts.keys()))
        proy_id = p_opts[sel_proy_name]
        
        with st.expander(" Requerir Material para este Proyecto"):
            df_i = get_data("insumos", "id, nombre_insumo")
            i_opts = {r['nombre_insumo']: r['id'] for _, r in df_i.iterrows()} if not df_i.empty else {}
            c_r1, c_r2, c_r3 = st.columns([2,1,1])
            req_i_name = c_r1.selectbox("Material", list(i_opts.keys()))
            req_cant = c_r2.number_input("Cantidad a Requerir", min_value=0.01)
            if c_r3.button("Añadir al Proyecto") and req_i_name:
                conn = get_connection(); cursor = conn.cursor()
                cursor.execute("INSERT INTO proyecto_materiales (proyecto_id, insumo_id, solicitado) VALUES (?, ?, ?) ON CONFLICT(proyecto_id, insumo_id) DO UPDATE SET solicitado = proyecto_materiales.solicitado + EXCLUDED.solicitado", (proy_id, i_opts[req_i_name], req_cant))
                conn.commit(); conn.close()
                st.session_state.feedback = (" Requerimiento añadido.", "success"); st.rerun()
                
        st.write("#### Materiales del Proyecto")
        conn = get_connection()
        df_pm = pd.read_sql_query(f'''
            SELECT i.id as "INS_ID", i.nombre_insumo as "MATERIAL", pm.solicitado as "SOLICITADO",
                   COALESCE((SELECT SUM(cantidad) FROM stock_comprometido WHERE insumo_id = i.id AND proyecto_id = {proy_id}), 0) as "SEPARADO",
                   COALESCE((SELECT SUM(cantidad) FROM movimientos WHERE insumo_id = i.id AND proyecto_id = {proy_id} AND tipo = 'SALIDA'), 0) as "CONSUMIDO",
                   (i.ultimo_precio + i.ajuste_precio) as "PRECIO_UNITARIO",
                   (i.stock_actual - COALESCE((SELECT SUM(cantidad) FROM stock_comprometido WHERE insumo_id = i.id), 0)) as "DISP_GENERAL"
            FROM proyecto_materiales pm
            JOIN insumos i ON pm.insumo_id = i.id
            WHERE pm.proyecto_id = {proy_id}
        ''', conn)
        conn.close()
        
        if not df_pm.empty:
            df_pm['FALTANTE'] = (df_pm['SOLICITADO'] - df_pm['SEPARADO'] - df_pm['CONSUMIDO']).clip(lower=0)
            df_pm['COMPRAR'] = 0.0
            
            t_sol = (df_pm['SOLICITADO'] * df_pm['PRECIO_UNITARIO']).sum()
            t_cons = (df_pm['CONSUMIDO'] * df_pm['PRECIO_UNITARIO']).sum()
            t_fal = (df_pm['FALTANTE'] * df_pm['PRECIO_UNITARIO']).sum()
            t_sep = (df_pm['SEPARADO'] * df_pm['PRECIO_UNITARIO']).sum()
            
            pct_comp = ((t_sep + t_cons) / t_sol * 100) if t_sol > 0 else 0
            pct_ejec = (t_cons / t_sol * 100) if t_sol > 0 else 0
            
            c_m1, c_m2, c_m3, c_m4 = st.columns(4)
            c_m1.metric("Total Solicitado", f"${t_sol:,.2f}")
            c_m2.metric("Total Consumido", f"${t_cons:,.2f}")
            c_m3.metric("Total Faltante", f"${t_fal:,.2f}")
            with c_m4:
                st.markdown(f"""
                <div style="margin-bottom: 8px;">
                  <div style="display:flex; justify-content:space-between; font-size:0.85rem; font-weight:600; color:#6C757D;">
                     <span>COMPRA</span> <span style="color:#00AEEF;">{pct_comp:.1f}%</span>
                  </div>
                  <div style="width:100%; height:8px; background-color:#E9ECEF; border-radius:4px; margin-top:4px;">
                     <div style="width:{min(pct_comp, 100)}%; height:100%; background-color:#00AEEF; border-radius:4px;"></div>
                  </div>
                </div>
                <div>
                  <div style="display:flex; justify-content:space-between; font-size:0.85rem; font-weight:600; color:#6C757D;">
                     <span>EJECUCIÓN</span> <span style="color:#FF8C00;">{pct_ejec:.1f}%</span>
                  </div>
                  <div style="width:100%; height:8px; background-color:#E9ECEF; border-radius:4px; margin-top:4px;">
                     <div style="width:{min(pct_ejec, 100)}%; height:100%; background-color:#FF8C00; border-radius:4px;"></div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.write("Modifica 'SEPARADO' para reservar/liberar inventario para este proyecto. Escribe en 'COMPRAR' la cantidad faltante para montar orden de compra.")
            ed_pm = st.data_editor(df_pm[['INS_ID', 'MATERIAL', 'SOLICITADO', 'SEPARADO', 'CONSUMIDO', 'FALTANTE', 'PRECIO_UNITARIO', 'DISP_GENERAL', 'COMPRAR']], 
                                   hide_index=True, disabled=['INS_ID', 'MATERIAL', 'SOLICITADO', 'CONSUMIDO', 'FALTANTE', 'PRECIO_UNITARIO', 'DISP_GENERAL'],
                                   key=f"ed_pm_{proy_id}")
            
            c_b1, c_b2 = st.columns(2)
            
            if c_b1.button(" Guardar Cambios de Stock 'Separado'"):
                conn = get_connection(); cursor = conn.cursor()
                for _, r_new in ed_pm.iterrows():
                    r_old = df_pm[df_pm['INS_ID'] == r_new['INS_ID']].iloc[0]
                    delta = r_new['SEPARADO'] - r_old['SEPARADO']
                    if delta != 0:
                        if delta > r_old['DISP_GENERAL']:
                            st.error(f"No hay suficiente stock general disponible para separar {delta} más de {r_old['MATERIAL']}")
                        elif r_new['SEPARADO'] < 0:
                            st.error(f"El valor separado no puede ser negativo para {r_old['MATERIAL']}")
                        else:
                            cursor.execute("INSERT OR IGNORE INTO stock_comprometido (insumo_id, proyecto_id) VALUES (?, ?)", (r_new['INS_ID'], proy_id))
                            cursor.execute("UPDATE stock_comprometido SET cantidad = ? WHERE insumo_id=? AND proyecto_id=?", (r_new['SEPARADO'], r_new['INS_ID'], proy_id))
                conn.commit(); conn.close()
                st.session_state.feedback = (" Stock separado actualizado.", "success"); st.rerun()
                
            if c_b2.button(" Montar Orden de Compra"):
                items_to_buy = ed_pm[ed_pm['COMPRAR'] > 0]
                if not items_to_buy.empty:
                    conn = get_connection(); cursor = conn.cursor()
                    cursor.execute("INSERT INTO ordenes_compra (proyecto_id, fecha, estado) VALUES (?, ?, 'ENVIADA') RETURNING id", (proy_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                    o_id = cursor.lastrowid
                    for _, r_buy in items_to_buy.iterrows():
                        cursor.execute("INSERT INTO ordenes_items (orden_id, insumo_id, solicitado, disponible, faltante, recibido) VALUES (?, ?, ?, ?, ?, 0)",
                                       (o_id, r_buy['INS_ID'], r_buy['SOLICITADO'], r_buy['SEPARADO'], r_buy['COMPRAR']))
                    conn.commit(); conn.close()
                    st.session_state.feedback = (" Orden de Compra generada.", "success"); st.rerun()
                else:
                    st.warning("No pusiste cantidades mayores a 0 en la columna COMPRAR.")

elif page == "Ordenes de Compra" and st.session_state.admin_logged_in:
    st.subheader("Gestion de Ordenes de Compra")
    
    t_view, t_create = st.tabs(["Historico / Ver", "Crear Orden General"])
    
    with t_view:
        st.write("Visualiza las órdenes generales o por proyecto.")
        conn = get_connection()
        df_o = pd.read_sql_query("""
            SELECT oc.id as "ID", COALESCE(p.nombre_proyecto, 'ORDEN GENERAL') as "PROYECTO", oc.fecha as "FECHA"
            FROM ordenes_compra oc LEFT JOIN proyectos p ON oc.proyecto_id = p.id ORDER BY oc.id DESC
        """, conn)
        conn.close()
        
        if not df_o.empty:
            for _, r in df_o.iterrows():
                with st.expander(f"Orden #{r['ID']} - {r['PROYECTO']} ({r['FECHA']})"):
                    conn = get_connection()
                    df_items = pd.read_sql_query(f"""
                        SELECT i.id as "ID", i.nombre_insumo as "MATERIAL", 
                               oi.solicitado as "REQUERIDO", oi.disponible as "SEPARADO", oi.faltante as "A_COMPRAR"
                        FROM ordenes_items oi 
                        JOIN insumos i ON oi.insumo_id = i.id 
                        WHERE oi.orden_id={r['ID']}
                    """, conn)
                    conn.close()
                    st.dataframe(df_items[['MATERIAL', 'REQUERIDO', 'SEPARADO', 'A_COMPRAR']], hide_index=True)
                    
                    c_dl, c_del = st.columns(2)
                    df_dl = df_items.copy()
                    df_dl.insert(0, 'Orden', f"#{r['ID']}")
                    df_dl.insert(1, 'Proyecto', r['PROYECTO'])
                    c_dl.download_button(" Descargar Orden PDF/Excel", to_excel_bytes(df_dl), f"Orden_{r['ID']}.xlsx", mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key=f"dl_{r['ID']}")
                    
                    if c_del.button(f" Eliminar Orden", key=f"del_o_{r['ID']}"):
                        conn = get_connection(); cursor = conn.cursor()
                        cursor.execute("DELETE FROM ordenes_items WHERE orden_id=?", (r['ID'],))
                        cursor.execute("DELETE FROM ordenes_compra WHERE id=?", (r['ID'],))
                        conn.commit(); conn.close()
                        st.session_state.feedback = (" Orden Eliminada.", "success"); st.rerun()

    with t_create:
        st.write("#### Añade materiales y cantidades a tu orden de compra general (Sin Proyecto)")
        if 'oc_gen_cart' not in st.session_state: st.session_state.oc_gen_cart = []
        
        conn = get_connection()
        df_i = pd.read_sql_query('SELECT id, nombre_insumo, (stock_actual - COALESCE((SELECT SUM(cantidad) FROM stock_comprometido WHERE insumo_id = insumos.id), 0)) as "DISP" FROM insumos', conn)
        conn.close()
        
        if not df_i.empty:
            i_opts = {f"{r['nombre_insumo']} (Disp: {r['DISP']})": (r['id'], r['nombre_insumo'], r['DISP']) for _, r in df_i.iterrows()}
            
            c_sel, c_cant, c_add = st.columns([2, 1, 1])
            sel_m_key = c_sel.selectbox("Seleccionar Insumo", list(i_opts.keys()))
            cant_to_buy = c_cant.number_input("Cantidad a Comprar", min_value=0.01, value=1.0)
            
            if c_add.button(" Agregar a la Orden") and sel_m_key:
                m_id, m_name, m_disp = i_opts[sel_m_key]
                st.session_state.oc_gen_cart.append({'ID': m_id, 'MATERIAL': m_name, 'DISPONIBLE': m_disp, 'CANTIDAD': cant_to_buy})
                st.rerun()
                
            if st.session_state.oc_gen_cart:
                st.write("---")
                st.write("#### Carrito de Orden General")
                df_cart = pd.DataFrame(st.session_state.oc_gen_cart)
                st.dataframe(df_cart[['MATERIAL', 'CANTIDAD']], hide_index=True)
                
                c_del_last, c_gen = st.columns(2)
                if c_del_last.button(" Deshacer Último"):
                    st.session_state.oc_gen_cart.pop()
                    st.rerun()
                    
                if c_gen.button(" CREAR ORDEN DE COMPRA GENERAL"):
                    conn = get_connection(); cursor = conn.cursor()
                    cursor.execute("INSERT INTO ordenes_compra (proyecto_id, fecha, estado) VALUES (NULL, ?, 'ENVIADA') RETURNING id", (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
                    o_id = cursor.lastrowid
                    for r_b in st.session_state.oc_gen_cart:
                        cursor.execute("INSERT INTO ordenes_items (orden_id, insumo_id, solicitado, disponible, faltante, recibido) VALUES (?, ?, ?, ?, ?, 0)",
                                       (o_id, r_b['ID'], r_b['CANTIDAD'], r_b['DISPONIBLE'], r_b['CANTIDAD']))
                    conn.commit(); conn.close()
                    st.session_state.oc_gen_cart = []
                    st.session_state.feedback = (" Orden General Generada exitosamente.", "success"); st.rerun()
        else: st.info("No hay insumos en el catálogo.")



elif page == "Analisis" and st.session_state.admin_logged_in:
    st.subheader("Analisis de Entradas y Salidas")
    f1, f2 = st.columns(2)
    start_date = f1.date_input("Fecha Inicio", date(2024, 1, 1))
    end_date = f2.date_input("Fecha Fin", date.today())
    
    conn = get_connection()
    # Query for ENTRADAS
    df_in = pd.read_sql_query("""
        SELECT m.id as "ID", m.fecha_hora as "FECHA", i.nombre_insumo as "MATERIAL", m.proveedor as "PROVEEDOR",
               cat.nombre as "CATEGORIA", cta.nombre as "CUENTA",
               m.cantidad as "CANTIDAD", m.precio_unitario as "PRECIO",
               (m.cantidad * m.precio_unitario) as "TOTAL",
               u.nombre || ' ' || u.apellido as "RESPONSABLE"
        FROM movimientos m
        JOIN insumos i ON m.insumo_id = i.id
        LEFT JOIN categorias cat ON i.categoria_id = cat.id
        LEFT JOIN cuentas_contables cta ON i.cuenta_id = cta.id
        LEFT JOIN users u ON m.user_id = u.id
        WHERE m.tipo = 'ENTRADA'
    """, conn)
    
    # Query for SALIDAS (Added PRECIO to outputs based on ultimo_precio)
    df_out = pd.read_sql_query("""
        SELECT m.id as "ID", m.fecha_hora as "FECHA", i.nombre_insumo as "MATERIAL", p.nombre_proyecto as "PROYECTO",
               cat.nombre as "CATEGORIA", cta.nombre as "CUENTA",
               m.cantidad as "CANTIDAD",
               m.precio_unitario as "PRECIO",
               (m.cantidad * m.precio_unitario) as "VALOR_TOTAL",
               u.nombre || ' ' || u.apellido as "RESPONSABLE"
        FROM movimientos m
        JOIN insumos i ON m.insumo_id = i.id
        LEFT JOIN proyectos p ON m.proyecto_id = p.id
        LEFT JOIN categorias cat ON i.categoria_id = cat.id
        LEFT JOIN cuentas_contables cta ON i.cuenta_id = cta.id
        LEFT JOIN users u ON m.user_id = u.id
        WHERE m.tipo = 'SALIDA'
    """, conn)
    conn.close()
    
    # Date Filtering
    if not df_in.empty: df_in['FECHA_DT'] = pd.to_datetime(df_in['FECHA']).dt.date
    if not df_out.empty: df_out['FECHA_DT'] = pd.to_datetime(df_out['FECHA']).dt.date
    
    df_in_filt = df_in[(df_in['FECHA_DT'] >= start_date) & (df_in['FECHA_DT'] <= end_date)].drop(columns=['FECHA_DT']) if not df_in.empty else pd.DataFrame()
    df_out_filt = df_out[(df_out['FECHA_DT'] >= start_date) & (df_out['FECHA_DT'] <= end_date)].drop(columns=['FECHA_DT']) if not df_out.empty else pd.DataFrame()

    tab_in, tab_out = st.tabs([" Entradas (Gastos)", " Salidas (Consumo)"])
    
    with tab_in:
        if not df_in_filt.empty:
            c1, c2, c3, c4 = st.columns(4)
            cat_f = c1.selectbox("Categoría", ["TODAS"] + list(df_in_filt['CATEGORIA'].dropna().unique()), key="in_cat")
            cta_f = c2.selectbox("Cuenta Contable", ["TODAS"] + list(df_in_filt['CUENTA'].dropna().unique()), key="in_cta")
            prov_f = c3.selectbox("Proveedor", ["TODOS"] + list(df_in_filt['PROVEEDOR'].dropna().unique()), key="in_prov")
            resp_f = c4.selectbox("Responsable", ["TODOS"] + list(df_in_filt['RESPONSABLE'].dropna().unique()), key="in_resp")
            
            if cat_f != "TODAS": df_in_filt = df_in_filt[df_in_filt['CATEGORIA'] == cat_f]
            if cta_f != "TODAS": df_in_filt = df_in_filt[df_in_filt['CUENTA'] == cta_f]
            if prov_f != "TODOS": df_in_filt = df_in_filt[df_in_filt['PROVEEDOR'] == prov_f]
            if resp_f != "TODOS": df_in_filt = df_in_filt[df_in_filt['RESPONSABLE'] == resp_f]
            
            c_dl, c_tot = st.columns([1, 3])
            c_dl.download_button(label=" Exportar Entradas", data=to_excel_bytes(df_in_filt.drop(columns=['ID'])), file_name='entradas.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            c_tot.metric("Inversión Total Mostrada", f"${df_in_filt['TOTAL'].sum():,.2f}")
            
            df_in_filt.insert(0, "ELIMINAR", False)
            ed_in = st.data_editor(df_in_filt, use_container_width=True, hide_index=True, disabled=[c for c in df_in_filt.columns if c != "ELIMINAR"])
            in_dels = ed_in[ed_in["ELIMINAR"]]["ID"].tolist()
            if in_dels and st.button(f" ELIMINAR {len(in_dels)} ENTRADAS"):
                for idx in in_dels: delete_item("movimientos", idx)
                st.session_state.feedback = (" Entradas eliminadas.", "success"); st.rerun()
        else: st.info("No hay registros de entradas en este rango.")
        
    with tab_out:
        if not df_out_filt.empty:
            c1, c2, c3, c4 = st.columns(4)
            cat_f_o = c1.selectbox("Categoría", ["TODAS"] + list(df_out_filt['CATEGORIA'].dropna().unique()), key="out_cat")
            cta_f_o = c2.selectbox("Cuenta Contable", ["TODAS"] + list(df_out_filt['CUENTA'].dropna().unique()), key="out_cta")
            proy_f_o = c3.selectbox("Proyecto", ["TODOS"] + list(df_out_filt['PROYECTO'].dropna().unique()), key="out_proy")
            resp_f_o = c4.selectbox("Responsable", ["TODOS"] + list(df_out_filt['RESPONSABLE'].dropna().unique()), key="out_resp")
            
            if cat_f_o != "TODAS": df_out_filt = df_out_filt[df_out_filt['CATEGORIA'] == cat_f_o]
            if cta_f_o != "TODAS": df_out_filt = df_out_filt[df_out_filt['CUENTA'] == cta_f_o]
            if proy_f_o != "TODOS": df_out_filt = df_out_filt[df_out_filt['PROYECTO'] == proy_f_o]
            if resp_f_o != "TODOS": df_out_filt = df_out_filt[df_out_filt['RESPONSABLE'] == resp_f_o]
            
            c_dl_o, c_tot_o = st.columns([1, 3])
            c_dl_o.download_button(label=" Exportar Salidas", data=to_excel_bytes(df_out_filt.drop(columns=['ID'])), file_name='salidas.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            c_tot_o.metric("Consumo Total Mostrado", f"${df_out_filt['VALOR_TOTAL'].sum():,.2f}")
            
            df_out_filt.insert(0, "ELIMINAR", False)
            ed_out = st.data_editor(df_out_filt, use_container_width=True, hide_index=True, disabled=[c for c in df_out_filt.columns if c != "ELIMINAR"])
            out_dels = ed_out[ed_out["ELIMINAR"]]["ID"].tolist()
            if out_dels and st.button(f" ELIMINAR {len(out_dels)} SALIDAS"):
                for idx in out_dels: delete_item("movimientos", idx)
                st.session_state.feedback = (" Salidas eliminadas.", "success"); st.rerun()
        else: st.info("No hay registros de salidas en este rango.")

elif page == " Configs" and st.session_state.admin_logged_in:
    st.subheader(" Configuración de Maestros")
    st.info("Gestiona los elementos principales. Puedes agregar nuevos o editar/eliminar los existentes.")
    
    t_proy, t_prov, t_cat, t_cta = st.tabs([" Proyectos", " Proveedores", " Categorías", " Cuentas Contables"])
    
    def render_maestro(table, col_name, label):
        nuevo = st.text_input(f"Nuevo {label}", key=f"n_{table}").upper()
        if st.button(f" Agregar {label}"):
            if nuevo:
                conn = get_connection(); cursor = conn.cursor()
                try:
                    if table == "proyectos": cursor.execute(f"INSERT INTO {table} ({col_name}, fecha_creacion) VALUES (?, ?)", (nuevo, datetime.now().strftime("%Y-%m-%d")))
                    else: cursor.execute(f"INSERT INTO {table} ({col_name}) VALUES (?)", (nuevo,))
                    conn.commit(); st.session_state.feedback = (f" {label} Creado", "success"); st.rerun()
                except sqlite3.IntegrityError: st.error("Error: Registro duplicado.")
                finally: conn.close()
        
        df_m = get_data(table, f"id, {col_name} as NOMBRE", "id DESC")
        if not df_m.empty:
            df_m.insert(0, "ELIMINAR", False)
            ed = st.data_editor(df_m, hide_index=True, key=f"ed_{table}", disabled=["id"])
            if st.button(f" Guardar Cambios en {label}"):
                conn = get_connection(); cursor = conn.cursor()
                for i, r in ed.iterrows():
                    if r['ELIMINAR']:
                        cursor.execute(f"DELETE FROM {table} WHERE id=?", (r['id'],))
                    else:
                        cursor.execute(f"UPDATE {table} SET {col_name}=? WHERE id=?", (normalize(r['NOMBRE']), r['id']))
                conn.commit(); conn.close()
                st.session_state.feedback = (f" {label} actualizado.", "success"); st.rerun()

    with t_proy: render_maestro("proyectos", "nombre_proyecto", "Proyecto")
    
    with t_prov:
        st.write("#### Proveedor")
        c_pn, c_pnit = st.columns(2)
        nuevo_p = c_pn.text_input("Nombre Proveedor", key="n_prov").upper()
        nuevo_nit = c_pnit.text_input("NIT/CC", key="nit_prov").upper()
        if st.button(" Agregar Proveedor"):
            if nuevo_p:
                conn = get_connection(); cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO proveedores (nombre, nit) VALUES (?, ?)", (nuevo_p, nuevo_nit))
                    conn.commit(); st.session_state.feedback = (" Proveedor Creado", "success"); st.rerun()
                except sqlite3.IntegrityError: st.error("Error: Proveedor o NIT duplicado.")
                finally: conn.close()
                
        df_pr = get_data('proveedores', 'id, nombre as "NOMBRE", nit as NIT', 'id DESC')
        if not df_pr.empty:
            df_pr.insert(0, "ELIMINAR", False)
            ed_pr = st.data_editor(df_pr, hide_index=True, key="ed_proveedores", disabled=["id"])
            if st.button(" Guardar Cambios en Proveedores"):
                conn = get_connection(); cursor = conn.cursor()
                for i, r in ed_pr.iterrows():
                    if r['ELIMINAR']: cursor.execute("DELETE FROM proveedores WHERE id=?", (r['id'],))
                    else: cursor.execute("UPDATE proveedores SET nombre=?, nit=? WHERE id=?", (normalize(r['NOMBRE']), normalize(r['NIT']), r['id']))
                conn.commit(); conn.close()
                st.session_state.feedback = (" Proveedores actualizados.", "success"); st.rerun()

    with t_cat: render_maestro("categorias", "nombre", "Categoría")
    with t_cta: render_maestro("cuentas_contables", "nombre", "Cuenta Contable")

elif page == " Importar/Exportar" and st.session_state.admin_logged_in:
    st.subheader(" Sincronización Avanzada Excel")
    col_exp, col_imp = st.columns(2)
    with col_exp:
        st.write("#### 1. Exportar Datos Maestros")
        if st.button(" DESCARGAR EXCEL COMPLETO"):
            conn = get_connection()
            df_i = pd.read_sql_query("""
                SELECT i.id, i.nombre_insumo as "NOMBRE", i.unidad_medida as "UNIDAD", i.stock_actual as "STOCK",
                       i.ultimo_precio as "PRECIO", i.ajuste_precio as "AJUSTE",
                       i.ultimo_proveedor as "PROVEEDOR",
                       c.nombre as "CATEGORIA", cta.nombre as "CUENTA"
                FROM insumos i
                LEFT JOIN categorias c ON i.categoria_id = c.id
                LEFT JOIN cuentas_contables cta ON i.cuenta_id = cta.id
            """, conn)
            df_m = pd.read_sql_query("SELECT * FROM movimientos", conn)
            df_p = pd.read_sql_query("SELECT * FROM proyectos", conn)
            df_c = pd.read_sql_query("SELECT * FROM categorias", conn)
            df_cta = pd.read_sql_query("SELECT * FROM cuentas_contables", conn)
            df_u = pd.read_sql_query("SELECT id, username, role, nombre, apellido, cc FROM users", conn)
            conn.close()
            with pd.ExcelWriter("inventario.xlsx") as w:
                df_i.to_excel(w, sheet_name="INSUMOS", index=False)
                df_m.to_excel(w, sheet_name="MOVIMIENTOS", index=False)
                df_p.to_excel(w, sheet_name="PROYECTOS", index=False)
                df_c.to_excel(w, sheet_name="CATEGORIAS", index=False)
                df_cta.to_excel(w, sheet_name="CUENTAS", index=False)
                df_u.to_excel(w, sheet_name="USUARIOS", index=False)
            with open("inventario.xlsx", "rb") as f: st.download_button("Guardar Excel", f, "inventario.xlsx")
    with col_imp:
        st.write("#### 2. Importar / Actualizar")
        up = st.file_uploader("Subir Archivo Excel", type="xlsx")
        if up and st.button(" SINCRONIZAR DATOS"):
            try:
                xl = pd.ExcelFile(up)
                conn = get_connection(); cursor = conn.cursor()
                if "INSUMOS" in xl.sheet_names:
                    df_imp = xl.parse("INSUMOS")
                    for _, r in df_imp.iterrows():
                        cursor.execute("SELECT id FROM categorias WHERE nombre=?", (normalize(r.get('CATEGORIA')),))
                        c_res = cursor.fetchone(); c_id = c_res[0] if c_res else None
                        cursor.execute("SELECT id FROM cuentas_contables WHERE nombre=?", (normalize(r.get('CUENTA')),))
                        cta_res = cursor.fetchone(); ct_id = cta_res[0] if cta_res else None
                        
                        if not pd.isna(r.get('id')):
                            cursor.execute("UPDATE insumos SET nombre_insumo=?, unidad_medida=?, stock_actual=?, categoria_id=?, cuenta_id=?, ultimo_precio=?, ajuste_precio=?, ultimo_proveedor=? WHERE id=?",
                                           (normalize(r['NOMBRE']), normalize(r['UNIDAD']), r['STOCK'], c_id, ct_id, r.get('PRECIO', 0), r.get('AJUSTE', 0), normalize(r.get('PROVEEDOR', '')), r['id']))
                        else:
                            cursor.execute("INSERT OR IGNORE INTO insumos (nombre_insumo, unidad_medida, stock_actual, categoria_id, cuenta_id, ultimo_precio, ajuste_precio, ultimo_proveedor) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                           (normalize(r['NOMBRE']), normalize(r['UNIDAD']), r['STOCK'], c_id, ct_id, r.get('PRECIO', 0), r.get('AJUSTE', 0), normalize(r.get('PROVEEDOR', ''))))
                conn.commit(); conn.close()
                st.session_state.feedback = (" Sincronización Exitosa", "success"); st.rerun()
            except Exception as e: st.error(f"Error al procesar el Excel: {e}")

elif page == "Usuarios" and st.session_state.admin_logged_in:
    st.subheader(" Gestión de Personal")
    t_crear, t_editar, t_eliminar = st.tabs(["Crear Usuario", "Editar Usuario", "Eliminar Usuarios"])
    
    with t_crear:
        st.write("#### Registrar Nuevo Empleado/Administrador")
        c1, c2 = st.columns(2)
        with c1:
            u_rol = st.radio("Rol:", ["USER", "ADMIN"], horizontal=True, key="c_rol")
            u_nom = st.text_input("Nombre", key="c_nom")
            u_ape = st.text_input("Apellido", key="c_ape")
        with c2:
            u_cc = st.text_input("CC (Documento)", key="c_cc")
            u_pwd = st.text_input("Contraseña de Login", type="password", key="c_pwd") if u_rol == "ADMIN" else None
            u_pin = st.text_input("PIN (4 dígitos)", type="password", key="c_pin", max_chars=4)
        if st.button(" REGISTRAR"):
            if not all([u_nom, u_ape, u_cc, u_pin]) or (u_rol == "ADMIN" and not u_pwd): st.warning(" Faltan datos.")
            else:
                conn = get_connection(); cursor = conn.cursor()
                try:
                    cursor.execute("INSERT INTO users (password_hash, role, nombre, apellido, cc, pin_hash) VALUES (?, ?, ?, ?, ?, ?)",
                                   (hash_val(u_pwd) if u_rol=="ADMIN" else None, u_rol, u_nom, u_ape, u_cc, hash_val(u_pin)))
                    conn.commit(); st.session_state.feedback = (" Creado exitosamente.", "success"); st.rerun()
                except sqlite3.IntegrityError: st.error(" La CC ya existe.")
                finally: conn.close()

    with t_editar:
        st.write("#### Modificar Datos de Usuario Existente")
        df_u = get_data("users", "id, nombre, apellido, cc, role")
        if not df_u.empty:
            u_dict = {f"{r['nombre']} {r['apellido']} (CC: {r['cc']})": r['id'] for _, r in df_u.iterrows()}
            u_sel = st.selectbox("Seleccione el Usuario a Editar", options=list(u_dict.keys()), index=None, placeholder="Seleccione usuario...")
            if u_sel:
                u_id = u_dict[u_sel]
                conn = get_connection()
                cur_user = pd.read_sql_query(f"SELECT * FROM users WHERE id={u_id}", conn).iloc[0]
                conn.close()
                
                with st.form("edit_user_form"):
                    e_rol = st.radio("Rol", ["USER", "ADMIN"], index=0 if cur_user['role']=="USER" else 1, horizontal=True)
                    e_nom = st.text_input("Nombre", value=cur_user['nombre'])
                    e_ape = st.text_input("Apellido", value=cur_user['apellido'])
                    e_cc = st.text_input("CC", value=cur_user['cc'])
                    st.info("Deje la contraseña o PIN en blanco si NO desea cambiarlos.")
                    e_pwd = st.text_input("Nueva Contraseña de Login (Solo ADMIN)", type="password") if e_rol == "ADMIN" else None
                    e_pin = st.text_input("Nuevo PIN de 4 dígitos", type="password", max_chars=4)
                    
                    if st.form_submit_button(" GUARDAR CAMBIOS"):
                        conn = get_connection(); cursor = conn.cursor()
                        try:
                            cursor.execute("UPDATE users SET nombre=?, apellido=?, cc=?, role=? WHERE id=?", (e_nom, e_ape, e_cc, e_rol, u_id))
                            if e_pwd and e_rol == "ADMIN": cursor.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_val(e_pwd), u_id))
                            if e_pin: cursor.execute("UPDATE users SET pin_hash=? WHERE id=?", (hash_val(e_pin), u_id))
                            conn.commit(); st.session_state.feedback = (" Usuario actualizado.", "success"); st.rerun()
                        except sqlite3.IntegrityError: st.error(" Error al actualizar. Verifique que la CC no esté duplicada.")
                        finally: conn.close()

    with t_eliminar:
        st.write("#### Eliminación de Usuarios")
        if not df_u.empty:
            df_del = df_u.copy()
            df_del.insert(0, "SEL", False)
            ed_u = st.data_editor(df_del, hide_index=True, column_config={"SEL": st.column_config.CheckboxColumn()}, disabled=[c for c in df_del.columns if c != "SEL"])
            u_ids = ed_u[ed_u["SEL"] == True]["id"].tolist()
            if u_ids and st.button(f" ELIMINAR {len(u_ids)} USUARIOS SELECCIONADOS"):
                for uid in u_ids: delete_item("users", uid)
                st.session_state.feedback = (" Usuarios eliminados", "success"); st.rerun()

elif page == "Backup" and st.session_state.admin_logged_in:
    st.subheader("Copias de Seguridad (Backup)")
    if st.button("Generar Nuevo Backup"):
        b_name = backup_db()
        if b_name: st.success(f"Backup creado: {b_name}")
        else: st.error("Error al crear backup")
        
    st.write("Backups disponibles:")
    b_files = [f for f in os.listdir(".") if f.startswith("backup_") and f.endswith(".db")]
    for b in sorted(b_files, reverse=True):
        st.write(f"- {b}")

else:
    st.warning("Debe iniciar sesión como administrador para acceder a esta funcion o pagina no encontrada.")
