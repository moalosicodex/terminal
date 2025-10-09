#!/usr/bin/env python3
"""
Professional Payment Terminal - Secure integrated version
Requirements: streamlit, reportlab
Optional: python-iso8583 (recommended)
Security notes (read before running in prod):
 - Do NOT run this in production until you confirm PCI scope and environment.
 - Replace the demo password; move secrets to env vars.
 - Ensure ./certs is secured and not world-readable.
 - Confirm with your acquirer which DE to use for CVV2 (this code places CVV in DE127 subfield 10 as placeholder).
"""
import streamlit as st
import socket
import ssl
import struct
import os
import re
import time
import hashlib
from datetime import datetime
from io import BytesIO
from typing import Tuple, Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# Optional iso8583 library (recommended). If missing, fallback builder will be used.
try:
    from iso8583 import iso8583, versions
    HAS_ISO_LIB = True
except Exception:
    HAS_ISO_LIB = False

# === APP AUTH (DEMO) ===
# Replace with secure auth before production
APP_PASSWORD_HASH = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # "password" (demo)
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if not st.session_state.authenticated:
    st.title("🔒 Payment Terminal (Demo Auth)")
    password = st.text_input("Enter Password", type="password")
    if st.button("Access System"):
        if hashlib.sha256(password.encode()).hexdigest() == APP_PASSWORD_HASH:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()

# === Session defaults ===
if 'merchant_id' not in st.session_state:
    st.session_state.merchant_id = "000000000009020"
if 'terminal_id' not in st.session_state:
    st.session_state.terminal_id = "72000716"
if 'stan_counter' not in st.session_state:
    st.session_state.stan_counter = 100001
if 'transaction_history' not in st.session_state:
    st.session_state.transaction_history = []
if 'cert_files_uploaded' not in st.session_state:
    st.session_state.cert_files_uploaded = False
if 'show_history' not in st.session_state:
    st.session_state.show_history = False
if 'demo_mode' not in st.session_state:
    st.session_state.demo_mode = False

# Protocol / Servers
PROTOCOL_CONFIG = {
    'name': 'Visa Base I Protocol',
    'code': '101.1',
    'standard': 'ISO 8583',
    'transaction_type': 'Force Sale (OCT-like demo)'
}
SERVERS = {
    "Primary": {"host": "102.163.40.20", "port": 8090},
    "Secondary": {"host": "10.252.251.5", "port": 8080}
}
CERT_DIR = "./certs"
os.makedirs(CERT_DIR, exist_ok=True)
CAD_CERT = os.path.join(CERT_DIR, "cad.crt")
ROOT_CERT = os.path.join(CERT_DIR, "root.crt")
CLIENT_CERT = os.path.join(CERT_DIR, "client.crt")
CLIENT_KEY = os.path.join(CERT_DIR, "client.key")

# NOTE: Many acquirers require CVV in a private field (DE48/DE61/DE62/DE127 subfield). Set to True if your acquirer supports DE127.10 for CVV.
ACQUIRER_SUPPORTS_CVV_IN_DE127 = True

# ------------------ Helpers ------------------
def mask_pan_for_display(pan: str) -> str:
    """Return masked PAN for display: 4 + ' **** **** ' + last4"""
    clean = re.sub(r'\D', '', pan)
    if len(clean) >= 8:
        return f"{clean[:4]} **** **** {clean[-4:]}"
    if len(clean) >= 4:
        return f"{clean[:4]} ****"
    return clean

def mask_pan_storage(pan: str) -> str:
    """Store only masked + last4 for history"""
    clean = re.sub(r'\D', '', pan)
    if len(clean) >= 4:
        return f"**** **** **** {clean[-4:]}"
    return "****"

def luhn_check(pan: str) -> bool:
    s = ''.join(ch for ch in pan if ch.isdigit())
    if len(s) < 12:
        return False
    total = 0
    for i, d in enumerate(s[::-1]):
        n = int(d)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0

# ------------------ SSL / Cert helpers ------------------
def create_ssl_context(dev_mode: bool=False) -> Tuple[Any, bool]:
    """Create SSL/TLS context using ROOT_CERT; optionally load client cert/key for mutual auth.
       dev_mode: if True, verification is relaxed (only use for local dev)."""
    if not os.path.exists(ROOT_CERT):
        return "Root certificate missing", False
    try:
        ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
        # Load CA bundle (root and intermediate). If cad.crt exists include both by pointing to a combined file.
        # If you only have root, that's okay; ensure path set by operator.
        ctx.load_verify_locations(cafile=ROOT_CERT)
        # If intermediate (cad) exists, append it to verify locations by creating a bundle (safe approach).
        if os.path.exists(CAD_CERT):
            # load_verify_locations supports multiple calls; append intermediate too
            try:
                ctx.load_verify_locations(cafile=CAD_CERT)
            except Exception:
                # If intermediate can't be loaded, warn but continue
                st.warning("⚠️ Could not load intermediate CA; continuing with root only.")
        # Client cert/key - for mutual TLS if provided
        if os.path.exists(CLIENT_CERT) and os.path.exists(CLIENT_KEY):
            try:
                ctx.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
                st.sidebar.info("Using client certificate for mTLS")
            except Exception as e:
                st.sidebar.warning(f"Client cert/key load issue: {e}")
        # Security defaults: do not relax in production
        if dev_mode:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx, True
    except Exception as e:
        return f"SSL context creation error: {e}", False

def test_connection_to_server(server_key: str):
    if not os.path.exists(ROOT_CERT):
        st.error("root.crt is missing in ./certs")
        return
    ctx, ok = create_ssl_context(dev_mode=False)
    if not ok:
        st.error(ctx)
        return
    server = SERVERS.get(server_key, SERVERS["Primary"])
    try:
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(10)
        ssock = ctx.wrap_socket(raw, server_hostname=server["host"])
        ssock.connect((server["host"], server["port"]))
        ssock.close()
        st.success(f"✅ Connected to {server['host']}:{server['port']}")
    except Exception as e:
        st.error(f"❌ Connection failed: {e}")

# ------------------ ISO8583 Builders ------------------
def build_iso_using_library(pan: str, expiry: str, cvv: str, amount: float, approval_code: str, stan: int, merchant_name: str):
    """Use python-iso8583 if available. Caller must ensure library installed."""
    msg = iso8583.Message(spec=versions.ISO8583_1987)
    msg.MTI = "0200"
    clean_pan = re.sub(r'\D', '', pan)
    msg[2]  = clean_pan
    msg[3]  = "000000"
    msg[4]  = str(int(amount*100)).zfill(12)
    msg[7]  = datetime.now().strftime("%m%d%H%M%S")
    msg[11] = str(stan).zfill(6)
    msg[12] = datetime.now().strftime("%H%M%S")
    msg[13] = datetime.now().strftime("%m%d")
    msg[14] = expiry
    msg[18] = "5999"
    msg[22] = "010"  # manual entry
    msg[24] = "200"
    msg[25] = "08"
    msg[32] = "00000000001"
    msg[37] = f"{str(stan).zfill(6)}FSL"
    msg[38] = approval_code
    msg[41] = st.session_state.terminal_id
    msg[42] = st.session_state.merchant_id
    msg[43] = merchant_name.ljust(40)[:40]
    msg[49] = "840"
    # CVV placement: network-specific (here we place in DE127 using "10=" subfield as placeholder)
    if ACQUIRER_SUPPORTS_CVV_IN_DE127:
        msg[127] = f"10={cvv}"
    packed, _ = iso8583.encode(msg)
    length_prefix = struct.pack(">H", len(packed))
    return length_prefix + packed, str(stan).zfill(6), f"{str(stan).zfill(6)}FSL"

def build_iso_fallback(pan: str, expiry: str, cvv: str, amount: float, approval_code: str, stan: int, merchant_name: str):
    """
    Fallback manual builder:
     - MTI '0200' ascii
     - 8-byte binary primary bitmap
     - LLVAR as ASCII for fields 2 & 35, LLLVAR for 60
    NOTE: This is a generic fallback. Confirm encoding (BCD, ASCII or packed numeric) with acquirer.
    """
    mti = "0200"
    rrn = f"{str(stan).zfill(6)}FSL"
    now = datetime.now()
    transmission_time = now.strftime("%m%d%H%M%S")
    local_time = now.strftime("%H%M%S")
    local_date = now.strftime("%m%d")

    clean_pan = re.sub(r'\D', '', pan)
    data_elements = {
        2: clean_pan,
        3: "000000",
        4: str(int(amount * 100)).zfill(12),
        7: transmission_time,
        11: str(stan).zfill(6),
        12: local_time,
        13: local_date,
        14: expiry,
        18: "5999",
        22: "010",
        24: "200",
        25: "08",
        32: "00000000001",
        35: clean_pan + "=" + expiry + "100",
        37: rrn,
        38: approval_code,
        41: st.session_state.terminal_id,
        42: st.session_state.merchant_id,
        43: merchant_name.ljust(40)[:40],
        49: "840",
        60: "00108001"
    }
    if ACQUIRER_SUPPORTS_CVV_IN_DE127:
        data_elements[127] = f"10={cvv}"

    # build primary bitmap
    bitmap = bytearray(8)
    for field_num in data_elements.keys():
        if 1 <= field_num <= 64:
            byte_index = (field_num - 1) // 8
            bit_index = 7 - ((field_num - 1) % 8)
            bitmap[byte_index] |= (1 << bit_index)

    # Build data bytes (ASCII-encoded values; LLVAR fields include length as ASCII digits)
    data_bytes = b""
    for field_num in sorted(data_elements.keys()):
        val = str(data_elements[field_num])
        if field_num in [2, 32, 35]:
            data_bytes += f"{len(val):02d}".encode("ascii") + val.encode("ascii")
        elif field_num == 60:
            data_bytes += f"{len(val):03d}".encode("ascii") + val.encode("ascii")
        else:
            data_bytes += val.encode("ascii")

    msg_body = mti.encode("ascii") + bytes(bitmap) + data_bytes
    length_prefix = struct.pack(">H", len(msg_body))
    return length_prefix + msg_body, str(stan).zfill(6), rrn

def build_iso_message(pan: str, expiry: str, cvv: str, amount: float, approval_code: str, stan: int, merchant_name: str):
    """Select builder: library preferred, fallback otherwise. Returns (msg_bytes, stan, rrn)"""
    if HAS_ISO_LIB:
        try:
            return build_iso_using_library(pan, expiry, cvv, amount, approval_code, stan, merchant_name)
        except Exception as e:
            st.warning(f"ISO lib failed, falling back to manual builder: {e}")
            return build_iso_fallback(pan, expiry, cvv, amount, approval_code, stan, merchant_name)
    else:
        return build_iso_fallback(pan, expiry, cvv, amount, approval_code, stan, merchant_name)

# ------------------ Minimal robust response parsing (fallback) ------------------
def parse_iso8583_response(resp: bytes) -> Dict[str, Any]:
    """
    If iso lib available, decode properly. Otherwise attempt a best-effort parse:
     - drop 2-byte length if present
     - find MTI + binary bitmap then walk fields (best-effort)
    Note: for production use a proper ISO8583 parser library.
    """
    out = {"response_code": None, "approval_code": None, "raw": resp}
    if not resp:
        return out
    # remove length prefix if present
    if len(resp) >= 2:
        prefix = struct.unpack(">H", resp[:2])[0]
        if prefix == len(resp) - 2:
            resp = resp[2:]
    if HAS_ISO_LIB:
        try:
            decoded = iso8583.decode(resp)
            out["response_code"] = decoded.get(39) or decoded.get('39')
            out["approval_code"] = decoded.get(38) or decoded.get('38')
            return out
        except Exception:
            pass
    # Fallback: parse ascii response for DE39/DE38 tokens (best-effort)
    try:
        s = resp.decode("ascii", errors="ignore")
        # Not reliable; we try to find '39' token and read next 2 chars if present.
        idx = s.find("39")
        if idx != -1 and len(s) >= idx + 4:
            out["response_code"] = s[idx+2:idx+4]
        idx38 = s.find("38")
        if idx38 != -1 and len(s) >= idx38 + 8:
            out["approval_code"] = s[idx38+2:idx38+8]
    except Exception:
        pass
    return out

# ------------------ Socket send/receive ------------------
def connect_socket():
    server_key = st.session_state.get("selected_server", "Primary")
    server = SERVERS[server_key]
    ctx, ok = create_ssl_context(dev_mode=False)
    if not ok:
        return None, f"SSL error: {ctx}"
    try:
        raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw.settimeout(15)
        ssock = ctx.wrap_socket(raw, server_hostname=server["host"])
        ssock.settimeout(30)
        ssock.connect((server["host"], server["port"]))
        return ssock, None
    except Exception as e:
        return None, f"Connection failed: {e}"

def send_iso_message(msg: bytes) -> Tuple[bool, str, bytes]:
    sock, err = connect_socket()
    if not sock:
        return False, err, b""
    try:
        sock.sendall(msg)
        data = sock.recv(8192)
        return True, "OK", data
    except Exception as e:
        return False, f"Send/recv failed: {e}", b""
    finally:
        try:
            sock.close()
        except:
            pass

# ------------------ PDF receipt ------------------
def generate_pdf_receipt(txn: Dict[str, Any]) -> BytesIO:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 50, "PAYMENT RECEIPT")
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2, height - 70, f"Protocol: {PROTOCOL_CONFIG['name']}")

    y = height - 100
    line_gap = 20
    def draw(label, value):
        nonlocal y
        c.drawString(72, y, f"{label}: {value}")
        y -= line_gap

    masked = txn.get("masked_pan", "****")

    draw("Merchant", txn.get("merchant_name", "Your Store"))
    draw("Terminal ID", st.session_state.terminal_id)
    draw("Date/Time", txn.get("timestamp", datetime.now()).strftime("%Y-%m-%d %H:%M:%S"))
    draw("Card Number", masked)
    draw("Amount", f"${txn.get('amount', 0.0):.2f}")
    draw("Approval Code", txn.get("approval_code", "N/A"))
    draw("Reference Number", txn.get("rrn", "N/A"))
    draw("Status", txn.get("status", "N/A"))
    draw("Protocol", PROTOCOL_CONFIG['name'])

    c.setFont("Helvetica-Oblique", 9)
    c.drawCentredString(width / 2, 40, "Thank you for your business!")
    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

# ------------------ Demo transaction ------------------
def process_demo_transaction():
    st.info("🔄 Processing demo transaction...")
    demo_stan = st.session_state.stan_counter
    st.session_state.stan_counter += 1
    time.sleep(1.2)
    st.success("✅ Demo Payment Approved!")

    demo_rrn = f"{str(demo_stan).zfill(6)}FSL"
    txn = {
        'timestamp': datetime.now(),
        'amount': 25.00,
        'masked_pan': mask_pan_storage("4111111111111111"),
        'status': 'APPROVED',
        'approval_code': 'DEMO123',
        'response_code': '00',
        'stan': str(demo_stan).zfill(6),
        'rrn': demo_rrn,
        'demo': True,
        'merchant_name': 'Demo Electronics Store',
        'protocol': PROTOCOL_CONFIG['name']
    }
    st.session_state.transaction_history.append(txn)
    show_receipt_and_download(txn)

# ------------------ High-level transaction flow ------------------
def process_force_sale(pan: str, expiry: str, cvv: str, amount: float, approval_code: str, merchant_name: str):
    # Validate basic inputs
    clean_pan = re.sub(r'\D', '', pan)
    if len(clean_pan) < 12 or not luhn_check(clean_pan):
        return False, "PAN failed Luhn or too short", None
    if not (len(expiry) == 4 and expiry.isdigit()):
        return False, "Expiry must be MMYY (4 digits)", None
    if not (3 <= len(cvv) <= 4 and cvv.isdigit()):
        return False, "CVV must be 3-4 digits", None
    if len(approval_code) != 6 or not approval_code.isdigit():
        return False, "Approval code must be 6 digits", None

    stan = st.session_state.stan_counter
    st.session_state.stan_counter += 1

    try:
        msg_bytes, stan_str, rrn = build_iso_message(pan, expiry, cvv, amount, approval_code, stan, merchant_name)
    except Exception as e:
        return False, f"ISO message build error: {e}", None

    sent, status, data = send_iso_message(msg_bytes)
    if not sent:
        # Append minimal info (masked pan only)
        txn_min = (str(stan_str).zfill(6), rrn)
        return False, status, txn_min

    parsed = parse_iso8583_response(data)
    rc = parsed.get("response_code")
    approval_code_from_resp = parsed.get("approval_code") or approval_code
    approved = (rc == "00") or (rc is None and "APPROVED" in status.upper())

    status_text = "APPROVED" if approved else (f"DECLINED ({rc})" if rc else "DECLINED")
    txn = {
        "timestamp": datetime.now(),
        "merchant_name": merchant_name,
        "masked_pan": mask_pan_storage(clean_pan),
        "amount": amount,
        "approval_code": approval_code_from_resp,
        "rrn": rrn,
        "stan": stan_str,
        "status": status_text,
        "protocol": PROTOCOL_CONFIG['name'],
        "demo": False
    }
    # Store only masked PAN and minimal transaction metadata
    st.session_state.transaction_history.append(txn)
    return True, status_text, txn

# ------------------ UI ------------------
def setup_page():
    st.set_page_config(
        page_title="Professional Payment Terminal", 
        page_icon="💳", 
        layout="wide",
        initial_sidebar_state="expanded"
    )

def render_protocol_info():
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 20px;">
        <div style="background-color: #1f77b4; color: white; padding: 8px 16px; border-radius: 20px; font-weight: bold; display: inline-block; margin: 10px 0;">
            🔒 {PROTOCOL_CONFIG['name']}
        </div>
        <p style="color: #666; font-size: 0.9em;">
            <strong>Protocol Code:</strong> {PROTOCOL_CONFIG['code']} | 
            <strong>Standard:</strong> {PROTOCOL_CONFIG['standard']}
        </p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    st.sidebar.title("⚙️ Setup")
    st.sidebar.markdown(f"**Protocol:** {PROTOCOL_CONFIG['name']}  \n**Code:** {PROTOCOL_CONFIG['code']}")
    st.sidebar.markdown("---")
    server = st.sidebar.selectbox("Select Server", list(SERVERS.keys()), index=0)
    st.session_state.selected_server = server
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔐 Certificates (Required)")
    cad = st.sidebar.file_uploader("Intermediate CA (cad.crt)", type=["crt", "pem"], key="cad")
    root = st.sidebar.file_uploader("Root CA (root.crt)", type=["crt", "pem"], key="root")
    if cad:
        with open(CAD_CERT, "wb") as f:
            f.write(cad.getvalue())
        st.sidebar.success("cad.crt saved")
    if root:
        with open(ROOT_CERT, "wb") as f:
            f.write(root.getvalue())
        st.sidebar.success("root.crt saved")
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔑 Client Certificates (Optional)")
    client_cert = st.sidebar.file_uploader("Client Certificate (client.crt)", type=["crt", "pem"], key="client_cert")
    client_key = st.sidebar.file_uploader("Client Key (client.key)", type=["key", "pem"], key="client_key")
    if client_cert:
        with open(CLIENT_CERT, "wb") as f:
            f.write(client_cert.getvalue())
        st.sidebar.success("client.crt saved")
    if client_key:
        with open(CLIENT_KEY, "wb") as f:
            f.write(client_key.getvalue())
        st.sidebar.success("client.key saved")

    certs_ready = os.path.exists(ROOT_CERT)
    if certs_ready:
        st.sidebar.success("✅ Required certificates present")
        st.session_state.cert_files_uploaded = True
        st.sidebar.markdown("---")
        st.sidebar.subheader("🏪 Merchant Information")
        st.sidebar.info(f"**Merchant ID:** {st.session_state.merchant_id}")
        st.sidebar.info(f"**Terminal ID:** {st.session_state.terminal_id}")
        has_client_cert = os.path.exists(CLIENT_CERT)
        has_client_key = os.path.exists(CLIENT_KEY)
        if has_client_cert and has_client_key:
            st.sidebar.success("✅ Client certificates present")
        elif has_client_cert or has_client_key:
            st.sidebar.warning("⚠️ Partial client certificates")
        else:
            st.sidebar.info("ℹ️ Using server authentication only")
    else:
        st.sidebar.error("❌ Please upload root.crt (and intermediate if required)")
        st.session_state.demo_mode = True

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Test Connection", use_container_width=True):
        test_connection_to_server(st.session_state.get("selected_server", "Primary"))
    if st.sidebar.button("📋 Transaction History", use_container_width=True):
        st.session_state.show_history = True
        st.rerun()
    if not certs_ready:
        st.sidebar.markdown("---")
        if st.sidebar.button("🎮 Process Demo Transaction", use_container_width=True, type="secondary"):
            process_demo_transaction()

def render_payment_form():
    st.header("📝 Payment Details")
    if st.session_state.demo_mode:
        st.warning("🎮 **DEMO MODE** - Upload certs for live TXNs")
    col1, col2 = st.columns(2)
    with col1:
        pan = st.text_input("💳 Card Number (PAN)", placeholder="4111111111111111", max_chars=19)
        expiry = st.text_input("📅 Expiry Date (MMYY)", placeholder="1225", max_chars=4)
        cvv = st.text_input("🔒 CVV (3-4 digits)", type="password", max_chars=4)
    with col2:
        amount = st.number_input("💰 Amount ($)", min_value=0.01, value=25.00, step=0.01)
        approval_code = st.text_input("✅ Approval Code (6 digits)", max_chars=6)
    merchant_name = st.text_input("🏪 Merchant Name", value="Your Store Name", max_chars=40)
    return pan, expiry, cvv, amount, approval_code, merchant_name

def show_receipt_and_download(txn: Dict[str, Any]):
    st.markdown("### 🧾 Payment Receipt")
    st.markdown("---")
    if txn.get('demo', False):
        st.info("🎮 **This is a demo transaction**")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Merchant:** {txn.get('merchant_name')}")
        st.write(f"**Terminal ID:** {st.session_state.terminal_id}")
        st.write(f"**Date/Time:** {txn.get('timestamp').strftime('%Y-%m-%d %H:%M:%S')}")
        st.write(f"**Card:** {txn.get('masked_pan')}")
    with col2:
        st.write(f"**Amount:** ${txn.get('amount'):.2f}")
        st.write(f"**Approval Code:** {txn.get('approval_code')}")
        st.write(f"**Reference:** {txn.get('rrn')}")
        st.write(f"**Status:** {txn.get('status')}")
        st.write(f"**Processing Network:** {txn.get('protocol')}")
    pdf_buf = generate_pdf_receipt(txn)
    st.download_button(
        "📄 Download PDF Receipt",
        data=pdf_buf,
        file_name=f"receipt_{txn.get('stan', int(time.time()))}.pdf",
        mime="application/pdf",
        use_container_width=True
    )

def show_transaction_history():
    st.header("📋 Transaction History")
    if not st.session_state.transaction_history:
        st.info("No transactions yet")
        return
    for i, txn in enumerate(reversed(st.session_state.transaction_history[-20:])):
        demo_indicator = " 🎮" if txn.get('demo', False) else ""
        with st.expander(f"Transaction {i+1} - ${txn['amount']:.2f} - {txn['timestamp'].strftime('%H:%M:%S')}{demo_indicator}"):
            st.write(f"**Merchant:** {txn['merchant_name']}")
            st.write(f"**Card:** {txn['masked_pan']}")
            st.write(f"**Amount:** ${txn['amount']:.2f}")
            st.write(f"**Status:** {txn['status']}")
            st.write(f"**Approval:** {txn['approval_code']}")
            st.write(f"**Reference:** {txn['rrn']}")
            st.write(f"**Protocol:** {txn.get('protocol', PROTOCOL_CONFIG['name'])}")
            if txn.get('demo', False):
                st.write("**Type:** 🎮 Demo Transaction")

# ------------------ App run ------------------
def main():
    setup_page()
    render_sidebar()
    st.title("💳 Professional Payment Terminal")
    render_protocol_info()
    st.markdown("---")

    if st.session_state.show_history:
        show_transaction_history()
        if st.button("← Back to Payment"):
            st.session_state.show_history = False
            st.rerun()
        return

    pan, expiry, cvv, amount, approval_code, merchant_name = render_payment_form()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.session_state.demo_mode:
            if st.button("🎮 Process Demo Transaction", type="secondary", use_container_width=True):
                process_demo_transaction()
        else:
            if st.button("🚀 Process Force Sale", type="primary", use_container_width=True):
                if not st.session_state.cert_files_uploaded:
                    st.error("❌ Please upload required certificates first")
                else:
                    ok, msg, result = process_force_sale(pan, expiry, cvv, amount, approval_code, merchant_name)
                    if ok:
                        st.success(f"✅ {msg}")
                        show_receipt_and_download(result)
                    else:
                        st.error(f"❌ {msg}")
                        if isinstance(result, tuple) and result[0]:
                            st.write(f"STAN: {result[0]}, RRN: {result[1]}")

if __name__ == "__main__":
    main()
