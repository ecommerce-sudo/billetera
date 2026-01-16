import streamlit as st
import requests
import re
import time
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# ⚙️ CONFIGURACIÓN
# ==========================================
st.set_page_config(page_title="S³ Pay", page_icon="💳", layout="centered")

# --- GESTIÓN DE SECRETOS (CLAVES) ---
# Intentamos leer las claves desde los secretos de Streamlit.
# Si no están configuradas, usamos valores vacíos para que no rompa (pero avisará).
try:
    ARIA_KEY = st.secrets["ARIA_KEY"]
except:
    ARIA_KEY = "TU_CLAVE_ARIA_AQUI" # Solo para pruebas locales si no usas secrets.toml

# --- CONEXIÓN CON GOOGLE SHEETS ---
def log_to_sheets(dni, nombre, plan, saldo):
    """Guarda la consulta en Google Sheets de forma silenciosa."""
    try:
        # Definimos el alcance (scope)
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Leemos las credenciales desde los Secrets de Streamlit
        # Tienes que copiar el contenido de tu archivo JSON dentro de los secrets
        creds_dict = st.secrets["gcp_service_account"]
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Abre la hoja por su nombre (Asegurate que se llame igual)
        sheet = client.open("DB_S3Pay").sheet1
        
        # Datos a guardar
        ahora = datetime.datetime.now()
        fecha = ahora.strftime("%Y-%m-%d")
        hora = ahora.strftime("%H:%M:%S")
        
        # Agrega la fila
        sheet.append_row([fecha, hora, str(dni), nombre, plan, saldo])
        
    except Exception as e:
        # Si falla el log, imprimimos en consola pero NO mostramos error al usuario
        print(f"Error guardando métrica: {e}")

ARIA_URL_BASE = "https://api.anatod.ar/api"
LINK_TIENDA = "https://ssstore.com.ar" 

# ==========================================
# 🎨 ESTILOS CSS (DISEÑO FINAL)
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inconsolata:wght@500;700;900&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;700;800;900&display=swap');
    
    .stApp { background: linear-gradient(135deg, #eef2f3 0%, #dce4e8 100%); font-family: 'Montserrat', sans-serif; }
    
    .block-container {
        background-color: #ffffff;
        padding: 3rem 2rem;
        border-radius: 25px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.08);
        max-width: 700px;
        margin-top: 2rem;
    }

    [data-testid="stForm"] { border: 0px; padding: 0px; }
    [data-testid="InputInstructions"] { display: none !important; }

    h1 { 
        text-align: center; font-family: 'Montserrat', sans-serif; font-weight: 900; 
        color: #1a1a1a; font-size: 2.5rem; margin-bottom: 0.5rem; letter-spacing: -1px;
    }
    sup { font-size: 1.2rem; color: #00d4ff; top: -0.5em; }
    .stMarkdown p { text-align: center !important; color: #666; font-size: 1rem; }

    .stTextInput > div > div > input {
        text-align: center; font-size: 18px; padding: 12px; border-radius: 12px; border: 2px solid #e0e0e0; transition: all 0.3s;
    }
    .stTextInput > div > div > input:focus { border-color: #00d4ff; box-shadow: 0 0 0 4px rgba(0, 212, 255, 0.1); }
    .stTextInput label { display: none; }

    .stButton > button {
        width: 100%; border-radius: 12px; padding: 12px; font-weight: 700; border: none; background: #f4f6f8; color: #555; transition: all 0.3s;
    }
    .stButton > button:hover { background: #e0e0e0; transform: translateY(-1px); }

    /* TARJETA */
    .card-container {
        border-radius: 20px; padding: 30px; color: white;
        box-shadow: 0 20px 40px -10px rgba(0,0,0,0.4);
        position: relative; overflow: hidden; transition: transform 0.3s ease;
        margin: 30px 0; height: 270px;
        display: flex; flex-direction: column; justify-content: space-between;
        font-family: 'Montserrat', sans-serif; border: 1px solid rgba(255,255,255,0.15);
    }
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
    
    .status-capsule { 
        display: flex; align-items: center; gap: 8px; 
        background: rgba(255, 255, 255, 0.2); 
        padding: 6px 14px; border-radius: 30px; 
        color: #fff; font-size: 11px; font-weight: 800; letter-spacing: 1px; 
        border: 1px solid rgba(255, 255, 255, 0.3); 
        font-family: 'Montserrat', sans-serif; 
        backdrop-filter: blur(4px); 
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-right: 2px; 
    }
    .dot { width: 8px; height: 8px; background-color: #fff; border-radius: 50%; box-shadow: 0 0 10px #fff; animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 1; box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); } 70% { opacity: 1; box-shadow: 0 0 0 8px rgba(255, 255, 255, 0); } 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); } }
    
    .btn-checkout {
        display: block; margin: 20px auto; padding: 18px 25px; width: 100%; max-width: 350px;
        text-align: center; text-transform: uppercase; transition: 0.4s; background-size: 200% auto;
        color: white !important; border-radius: 15px; font-weight: 900; letter-spacing: 1px;
        text-decoration: none !important; background-image: linear-gradient(to right, #00d4ff 0%, #0984e3 51%, #00d4ff 100%);
        box-shadow: 0 10px 20px rgba(0, 168, 255, 0.3); border: none; font-size: 16px;
    }
    .btn-checkout:hover { background-position: right center; color: #fff; transform: translateY(-3px); box-shadow: 0 15px 30px rgba(0, 168, 255, 0.5); }
    .btn-checkout:active { transform: scale(0.98); }

    .legal-text { text-align: center; font-size: 13px; color: #333; margin-top: 20px; font-weight: 700; letter-spacing: 0.5px; }
    .footer-security { text-align: center; margin-top: 40px; font-size: 13px; color: #555; font-weight: 700; display: flex; justify-content: center; align-items: center; gap: 6px; }

    /* MOBILE ADJUSTMENTS */
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
# 🧠 LÓGICA
# ==========================================
def solo_numeros(texto):
    return re.sub(r'\D', '', str(texto))

def obtener_diseno_tarjeta(cupo):
    if cupo < 200000: 
        return {"fondo": "linear-gradient(135deg, #00b09b 0%, #96c93d 100%)", "texto_plan": "INFINIUM"} 
    elif cupo < 500000: 
        return {"fondo": "linear-gradient(135deg, #1A2980 0%, #26D0CE 100%)", "texto_plan": "CLASSIC"} 
    else: 
        return {"fondo": "linear-gradient(135deg, #232526 0%, #414345 100%)", "texto_plan": "BLACK"} 

def consultar_saldo(dni):
    headers = {"x-api-key": ARIA_KEY}
    dni_limpio = solo_numeros(dni)
    if not dni_limpio: return None
    try:
        res = requests.get(f"{ARIA_URL_BASE}/clientes", headers=headers, params={'ident': dni_limpio}, timeout=5)
        if res.status_code == 200:
            d = res.json()
            lista = d if isinstance(d, list) else [d]
            for c in lista:
                if dni_limpio in solo_numeros(c.get('cliente_dnicuit','')): return c
    except: pass
    try:
        res = requests.get(f"{ARIA_URL_BASE}/clientes", headers=headers, params={'q': dni_limpio}, timeout=5)
        if res.status_code == 200:
            d = res.json()
            lista = d['data'] if isinstance(d, dict) and 'data' in d else (d if isinstance(d, list) else [d])
            for c in lista:
                if dni_limpio in solo_numeros(c.get('cliente_dnicuit','')): return c
    except: pass
    return None

# ==========================================
# 📱 INTERFAZ PRINCIPAL
# ==========================================

st.markdown("<h1>S<sup>3</sup> Pay</h1>", unsafe_allow_html=True)
st.markdown("<p style='margin-bottom: 25px;'>Ingresá tu DNI para conocer tu saldo disponible.</p>", unsafe_allow_html=True)

with st.form("consulta_form"):
    st.markdown("<p style='text-align: center; font-weight: 800; font-size: 12px; margin-bottom: 5px; color:#333;'>DNI DEL TITULAR</p>", unsafe_allow_html=True)
    dni_input = st.text_input("DNI", max_chars=12, placeholder="Ej: 30123456", label_visibility="collapsed")
    submitted = st.form_submit_button("🔍 CONSULTAR SALDO", use_container_width=True)

if submitted:
    if len(dni_input) < 6:
        st.warning("Por favor ingresá un DNI válido.")
    else:
        with st.spinner("Procesando consulta..."):
            time.sleep(0.5)
            cliente = consultar_saldo(dni_input)
            
            if cliente:
                nom = f"{cliente.get('cliente_nombre','')} {cliente.get('cliente_apellido','')}"
                try: cupo = float(cliente.get('clienteScoringFinanciable', 0))
                except: cupo = 0.0
                mora = int(cliente.get('cliente_meses_atraso', 0) or 0)
                
                estilo = obtener_diseno_tarjeta(cupo)
                
                if mora > 0:
                     st.error(f"⛔ Tu cuenta tiene {mora} meses de mora.")
                else:
                    # ✅ GUARDAMOS EN SHEETS (Silenciosamente)
                    log_to_sheets(dni_input, nom, estilo['texto_plan'], cupo)
                    
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

<a href="{LINK_TIENDA}" target="_blank" class="btn-checkout">
    USAR MI SALDO AHORA ➜
</a>

<div class="legal-text">
    * Al finalizar tu compra elegí la opción "A Convenir"
</div>
"""
                    html_limpio = html_raw.replace("\n", "")
                    st.markdown(html_limpio, unsafe_allow_html=True)
                    st.balloons()
            else:
                st.error("❌ No encontramos un cliente con ese DNI.")

st.markdown("""
<div class="footer-security">
    🔒 Sistema seguro de SSServicios
</div>
""", unsafe_allow_html=True)

