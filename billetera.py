import streamlit as st
import requests
import re
import time
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit.components.v1 as components

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="S³ Pay", page_icon="💳", layout="centered")

try:
    ARIA_KEY = st.secrets["ARIA_KEY"]
except:
    # Si estás probando local y no usas secrets, poné tu clave acá temporalmente
    ARIA_KEY = "TU_CLAVE_ARIA_AQUI"

ARIA_URL_BASE = "https://api.anatod.ar/api"
LINK_TIENDA = "https://ssstore.com.ar" 

# ==========================================
# 📊 FUNCIONES DE REGISTRO EN SHEETS
# ==========================================
def get_sheet_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = st.secrets["gcp_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("DB_S3Pay").sheet1

def log_consulta(dni, nombre, plan, saldo, email):
    try:
        sheet = get_sheet_client()
        ahora = datetime.datetime.now()
        fecha_hoy = ahora.strftime("%Y-%m-%d")
        hora_actual = ahora.strftime("%H:%M:%S")
        dni_str = str(dni)
        
        data = sheet.get_all_values()
        fila_encontrada = -1
        contador_consultas = 0
        
        # Buscamos si ya existe hoy
        for i, row in enumerate(data):
            if i == 0: continue
            if len(row) >= 3:
                if row[0] == fecha_hoy and row[2] == dni_str:
                    fila_encontrada = i + 1
                    try: contador_consultas = int(row[7]) 
                    except: contador_consultas = 0
                    break
        
        if fila_encontrada > 0:
            # ACTUALIZAR
            sheet.update_cell(fila_encontrada, 2, hora_actual) 
            sheet.update_cell(fila_encontrada, 8, contador_consultas + 1)
            # Si recuperamos un email y antes no tenía, actualizamos
            if email != "-" and len(row) > 6 and row[6] == "-":
                 sheet.update_cell(fila_encontrada, 7, email)
        else:
            # INSERTAR NUEVO
            sheet.append_row([fecha_hoy, hora_actual, dni_str, nombre, plan, saldo, email, 1, 0])
    except Exception as e:
        print(f"Error log consulta: {e}")

def log_click(dni):
    try:
        sheet = get_sheet_client()
        ahora = datetime.datetime.now()
        fecha_hoy = ahora.strftime("%Y-%m-%d")
        dni_str = str(dni)
        data = sheet.get_all_values()
        fila_encontrada = -1
        contador_clicks = 0
        for i, row in enumerate(data):
            if i == 0: continue
            if len(row) >= 3:
                if row[0] == fecha_hoy and row[2] == dni_str:
                    fila_encontrada = i + 1
                    try: contador_clicks = int(row[8])
                    except: contador_clicks = 0
                    break
        if fila_encontrada > 0:
            sheet.update_cell(fila_encontrada, 9, contador_clicks + 1)
        else:
            hora = ahora.strftime("%H:%M:%S")
            sheet.append_row([fecha_hoy, hora, dni_str, "Desconocido", "-", 0, "-", 1, 1])
    except Exception as e:
        print(f"Error log click: {e}")

# ==========================================
# 🧠 LÓGICA DE NEGOCIO (CON BÚSQUEDA DE EMAIL)
# ==========================================
def solo_numeros(texto):
    return re.sub(r'\D', '', str(texto))

def obtener_diseno_tarjeta(cupo):
    if cupo < 200000: return {"fondo": "linear-gradient(135deg, #00b09b 0%, #96c93d 100%)", "texto_plan": "INFINIUM"} 
    elif cupo < 500000: return {"fondo": "linear-gradient(135deg, #1A2980 0%, #26D0CE 100%)", "texto_plan": "CLASSIC"} 
    else: return {"fondo": "linear-gradient(135deg, #232526 0%, #414345 100%)", "texto_plan": "BLACK"} 

def consultar_saldo(dni):
    headers = {"x-api-key": ARIA_KEY}
    dni_limpio = solo_numeros(dni)
    if not dni_limpio: return None
    
    cliente_encontrado = None
    
    # 1. BUSQUEDA INICIAL (Para encontrar el ID)
    try:
        res = requests.get(f"{ARIA_URL_BASE}/clientes", headers=headers, params={'ident': dni_limpio}, timeout=5)
        if res.status_code == 200:
            d = res.json()
            lista = d if isinstance(d, list) else [d]
            for c in lista:
                if dni_limpio in solo_numeros(c.get('cliente_dnicuit','')): 
                    cliente_encontrado = c
                    break
    except: pass
    
    if not cliente_encontrado:
        try:
            res = requests.get(f"{ARIA_URL_BASE}/clientes", headers=headers, params={'q': dni_limpio}, timeout=5)
            if res.status_code == 200:
                d = res.json()
                lista = d['data'] if isinstance(d, dict) and 'data' in d else (d if isinstance(d, list) else [d])
                for c in lista:
                    if dni_limpio in solo_numeros(c.get('cliente_dnicuit','')): 
                        cliente_encontrado = c
                        break
        except: pass

    # 2. BÚSQUEDA DE EMAIL (Llamada específica usando el ID)
    if cliente_encontrado:
        email_recuperado = "-"
        try:
            # Obtenemos el ID del cliente encontrado
            c_id = cliente_encontrado.get('cliente_id')
            if c_id:
                # Llamamos al endpoint /cliente/{id} con relaciones=email
                res_email = requests.get(f"{ARIA_URL_BASE}/cliente/{c_id}", headers=headers, params={'relaciones': 'email'}, timeout=4)
                if res_email.status_code == 200:
                    data_email = res_email.json()
                    # Buscamos dentro de la lista 'cliente_emails'
                    lista_emails = data_email.get('cliente_emails', [])
                    if lista_emails and len(lista_emails) > 0:
                        # Extraemos el campo 'cliente_mail_mail'
                        email_recuperado = lista_emails[0].get('cliente_mail_mail', '-')
        except:
            pass
        
        # Guardamos el email en el objeto cliente para usarlo luego
        cliente_encontrado['email_final'] = email_recuperado
            
    return cliente_encontrado

# ==========================================
# 🎨 ESTILOS CSS
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inconsolata:wght@500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap');
    
    .stApp { background: linear-gradient(135deg, #eef2f3 0%, #dce4e8 100%); font-family: 'Montserrat', sans-serif; }
    .block-container { background-color: #ffffff; padding: 3rem 2rem; border-radius: 25px; box-shadow: 0 10px 40px rgba(0,0,0,0.08); max-width: 700px; margin-top: 2rem; }
    [data-testid="stForm"] { border: 0px; padding: 0px; }
    [data-testid="InputInstructions"] { display: none !important; }
    h1 { text-align: center; font-family: 'Montserrat', sans-serif; font-weight: 900; color: #1a1a1a; font-size: 2.5rem; margin-bottom: 0.5rem; letter-spacing: -1px; }
    sup { font-size: 1.2rem; color: #00d4ff; top: -0.5em; }
    .stMarkdown p { text-align: center !important; color: #666; font-size: 1rem; }
    .stTextInput > div > div > input { text-align: center; font-size: 18px; padding: 12px; border-radius: 12px; border: 2px solid #e0e0e0; transition: all 0.3s; }
    .stTextInput > div > div > input:focus { border-color: #00d4ff; box-shadow: 0 0 0 4px rgba(0, 212, 255, 0.1); }
    .stTextInput label { display: none; }
    [data-testid="stFormSubmitButton"] button { width: 100%; border-radius: 12px; padding: 12px; font-weight: 700; border: none; background: #f4f6f8; color: #555; transition: all 0.3s; }
    [data-testid="stFormSubmitButton"] button:hover { background: #e0e0e0; transform: translateY(-1px); }
    div.stButton > button:not([kind="secondary"]) { display: block; margin: 20px auto; padding: 18px 25px; width: 100%; text-align: center; text-transform: uppercase; transition: 0.4s; background-size: 200% auto; color: white !important; border-radius: 15px; font-weight: 900; letter-spacing: 1px; border: none; font-size: 16px; background-image: linear-gradient(to right, #00d4ff 0%, #0984e3 51%, #00d4ff 100%); box-shadow: 0 10px 20px rgba(0, 168, 255, 0.3); }
    div.stButton > button:not([kind="secondary"]):hover { background-position: right center; color: #fff; transform: translateY(-3px); box-shadow: 0 15px 30px rgba(0, 168, 255, 0.5); }
    .card-container { border-radius: 20px; padding: 30px; color: white; box-shadow: 0 20px 40px -10px rgba(0,0,0,0.4); position: relative; overflow: hidden; transition: transform 0.3s ease; margin: 30px 0; height: 270px; display: flex; flex-direction: column; justify-content: space-between; font-family: 'Montserrat', sans-serif; border: 1px solid rgba(255,255,255,0.15); }
    .card-container:hover { transform: translateY(-5px); }
    .card-container::before { content: ""; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 60%); pointer-events: none; }
    .card-top { display: flex; justify-content: space-between; align-items: center; z-index: 2; margin-bottom: 5px;}
    .card-logo-text { font-family: 'Montserrat', sans-serif; font-size: 24px; font-weight: 900; font-style: italic; color: #fff; text-shadow: 0 2px 4px rgba(0,0,0,0.2); line-height: 1; }
    .plan-label { font-family: 'Montserrat', sans-serif; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; color: #fff; text-shadow: 0 1px 2px rgba(0,0,0,0.3); opacity: 0.9; }
    .card-chip { width: 55px; height: 40px; background: linear-gradient(135deg, #e0aa3e 0%, #fdd835 100%); border-radius: 6px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.2); border: 1px solid #b88a00; z-index: 2; position: absolute; top: 90px; right: 35px; }
    .card-chip::before { content: ""; position: absolute; top: 50%; left: 0; width: 100%; height: 1px; background: rgba(0,0,0,0.15); transform: translateY(-50%); }
    .card-chip::after { content: ""; position: absolute; top: 0; left: 33%; width: 1px; height: 100%; background: rgba(0,0,0,0.15); }
    .chip-line-v2 { position: absolute; top: 0; left: 66%; width: 1px; height: 100%; background: rgba(0,0,0,0.15); }
    .chip-curve { position: absolute; top: 50%; left: 50%; width: 25px; height: 25px; border: 1px solid rgba(0,0,0,0.15); border-radius: 4px; transform: translate(-50%, -50%); }
    .card-middle { margin-top: 25px; margin-bottom: 15px; z-index: 2; }
    .card-name-main { font-family: 'Inconsolata', monospace; font-size: 26px; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; color: #fff; text-shadow: 0 2px 4px rgba(0,0,0,0.4); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .card-footer { display: flex; justify-content: space-between; align-items: flex-end; z-index: 2; margin-top: auto; }
    .card-balance-label { font-size: 10px; opacity: 0.9; text-transform: uppercase; letter-spacing: 1px; font-family: 'Montserrat', sans-serif; font-weight: 700; margin-bottom: 2px; }
    .card-balance { font-family: 'Inconsolata', monospace; font-size: 38px; font-weight: 700; color: #fff; text-shadow: 0 2px 5px rgba(0,0,0,0.3); letter-spacing: -1px; line-height: 1; }
    .status-capsule { display: flex; align-items: center; gap: 8px; background: rgba(255, 255, 255, 0.2); padding: 6px 14px; border-radius: 30px; color: #fff; font-size: 11px; font-weight: 800; letter-spacing: 1px; border: 1px solid rgba(255, 255, 255, 0.3); font-family: 'Montserrat', sans-serif; backdrop-filter: blur(4px); box-shadow: 0 2px 5px rgba(0,0,0,0.1); margin-right: 2px; }
    .dot { width: 8px; height: 8px; background-color: #fff; border-radius: 50%; box-shadow: 0 0 10px #fff; animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 1; box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); } 70% { opacity: 1; box-shadow: 0 0 0 8px rgba(255, 255, 255, 0); } 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); } }
    .soft-block-box { background-color: #f8f9fa; border: 2px solid #e9ecef; border-radius: 15px; padding: 25px; text-align: center; margin-top: 20px; color: #495057; }
    .soft-block-title { font-size: 20px; font-weight: 800; margin-bottom: 10px; color: #212529; }
    .soft-block-text { font-size: 15px; font-weight: 500; line-height: 1.5; color: #6c757d; }
    .legal-text { text-align: center; font-size: 13px; color: #333; margin-top: 20px; font-weight: 700; letter-spacing: 0.5px; }
    .footer-security { text-align: center; margin-top: 40px; font-size: 13px; color: #555; font-weight: 700; display: flex; justify-content: center; align-items: center; gap: 6px; }

    @media only screen and (max-width: 600px) {
        .block-container { padding: 2rem 1rem !important; margin-top: 0.5rem; }
        .card-container { padding: 20px; height: 250px; }
        .card-logo-text { font-size: 20px; }
        .card-name-main { font-size: 22px; }
        .card-balance { font-size: 32px; }
        .status-capsule { padding: 5px 10px; font-size: 10px; margin-right: 5px; }
        h1 { font-size: 2rem; }
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📱 INTERFAZ PRINCIPAL
# ==========================================
st.markdown("<h1>S<sup>3</sup> Pay</h1>", unsafe_allow_html=True)
st.markdown("<p style='margin-bottom: 25px;'>Ingresá tu DNI para conocer tu saldo disponible.</p>", unsafe_allow_html=True)

if 'cliente_data' not in st.session_state:
    st.session_state.cliente_data = None

with st.form("consulta_form"):
    st.markdown("<p style='text-align: center; font-weight: 800; font-size: 12px; margin-bottom: 5px; color:#333;'>DNI DEL TITULAR</p>", unsafe_allow_html=True)
    dni_input = st.text_input("DNI", max_chars=12, placeholder="Ej: 30123456", label_visibility="collapsed")
    submitted = st.form_submit_button("🔍 CONSULTAR SALDO", use_container_width=True)

if submitted:
    if len(dni_input) < 6:
        st.warning("Por favor ingresá un DNI válido.")
        st.session_state.cliente_data = None
    else:
        with st.spinner("Procesando consulta..."):
            time.sleep(0.5)
            # 1. Buscamos cliente y email (función actualizada)
            cliente = consultar_saldo(dni_input)
            
            if cliente:
                nom = f"{cliente.get('cliente_nombre','')} {cliente.get('cliente_apellido','')}"
                try: cupo = float(cliente.get('clienteScoringFinanciable', 0))
                except: cupo = 0.0
                mora = int(cliente.get('cliente_meses_atraso', 0) or 0)
                
                # 2. Recuperamos el email que la función 'consultar_saldo' encontró
                email = cliente.get('email_final', '-')
                
                estilo = obtener_diseno_tarjeta(cupo)
                st.session_state.cliente_data = {
                    "nombre": nom, "cupo": cupo, "mora": mora, "estilo": estilo, "dni": dni_input, "email": email
                }
                
                if mora == 0:
                    log_consulta(dni_input, nom, estilo['texto_plan'], cupo, email)
            else:
                st.error("❌ No encontramos un cliente con ese DNI.")
                st.session_state.cliente_data = None

# LOGICA DE VISUALIZACIÓN
if st.session_state.cliente_data:
    data = st.session_state.cliente_data
    mora = data['mora']
    
    if mora > 0:
        st.markdown("""
        <div class="soft-block-box">
            <div class="soft-block-title">¡Hola! 👋</div>
            <div class="soft-block-text">
                En este momento no podemos informarte tu cupo disponible.<br>
                Te sugerimos volver a consultar más adelante.
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        estilo = data['estilo']
        cupo = data['cupo']
        nom = data['nombre']
        
        html_raw = f"""
        <div class="card-container" style="background: {estilo['fondo']};">
            <div class="card-top">
                <div class="card-logo-text">SSSERVICIOS</div>
                <div class="plan-label">{estilo['texto_plan']}</div>
            </div>
            <div class="card-chip">
                <div class="chip-line-v2"></div>
                <div class="chip-curve"></div>
            </div>
            <div class="card-middle">
                <div class="card-name-main">{nom}</div>
            </div>
            <div class="card-footer">
                <div class="card-balance-group">
                    <div class="card-balance-label">Saldo Disponible</div>
                    <div class="card-balance">${cupo:,.2f}</div>
                </div>
                <div class="status-capsule">
                    <div class="dot"></div> ACTIVO
                </div>
            </div>
        </div>
        """
        st.markdown(html_raw, unsafe_allow_html=True)
        
        if st.button("🛒 USAR MI SALDO AHORA ➜", use_container_width=True):
            log_click(data['dni'])
            js = f"window.open('{LINK_TIENDA}', '_blank')"
            html = f"<script>{js}</script>"
            st.components.v1.html(html, height=0)
            
        st.markdown('<div class="legal-text">* Al finalizar tu compra elegí la opción "A Convenir"</div>', unsafe_allow_html=True)

st.markdown('<div class="footer-security">🔒 Sistema seguro de SSServicios</div>', unsafe_allow_html=True)

