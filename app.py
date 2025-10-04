#!/usr/bin/env python3
"""
Professional Payment Terminal - Full app with masked PDF receipts
Requirements: streamlit, reportlab
"""
import streamlit as st
import socket
import ssl
import struct
import os
import re
from datetime import datetime
import time
import hashlib
from typing import Tuple, Dict, Any
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# === PASSWORD PROTECTION === 
APP_PASSWORD_HASH = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # password: password

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 Payment Terminal")
    password = st.text_input("Enter Password", type="password")
    if st.button("Access System"):
        if hashlib.sha256(password.encode()).hexdigest() == APP_PASSWORD_HASH:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()
# === END PASSWORD PROTECTION ===

# ---------------------- Helper functions ----------------------
def mask_pan_for_display(pan: str) -> str:
    """Return masked PAN for display: 4 + ' **** **** ' + last4"""
    clean = re.sub(r'\D', '', pan)
    if len(clean) >= 8:
        return f"{clean[:4]} **** **** {clean[-4:]}"
    if len(clean) >= 4:
        return f"{clean[:4]} ****"
    return clean

def build_iso8583_force_sale(pan: str, expiry: str, amount: float, approval_code: str, stan: int, merchant_name: str):
    """
    Build a simple Visa Base I Force Sale-like message.
    Returns: bytes message with 2-byte length prefix, plus stan and rrn.
    """
    mti = "0200"
    rrn = f"{str(stan).zfill(6)}FSL"
    now = datetime.now()
    transmission_time = now.strftime("%m%d%H%M%S")
    local_time = now.strftime("%H%M%S")
    local_date = now.strftime("%m%d")

    data_elements = {
        2: pan,
        3: "000000",
        4: str(int(amount * 100)).zfill(12),
        7: transmission_time,
        11: str(stan).zfill(6),
        12: local_time,
        13: local_date,
        14: expiry,
        18: "5999",
        22: "012",
        24: "200",
        25: "08",
        32: "00000000001",
        35: pan + "=" + expiry + "100",
        37: rrn,
        38: approval_code,
        41: st.session_state.terminal_id,
        42: st.session_state.merchant_id,
        43: merchant_name.ljust(40)[:40],
        49: "840",
        60: "00108001"
    }

    # bitmap for fields 1-64
    bitmap = bytearray(8)
    for field_num in data_elements.keys():
        if 1 <= field_num <= 64:
            byte_index = (field_num - 1) // 8
            bit_index = 7 - ((field_num - 1) % 8)
            bitmap[byte_index] |= (1 << bit_index)

    bitmap_hex = bitmap.hex().upper()
    data_str = ""
    for field_num in sorted(data_elements.keys()):
        val = data_elements[field_num]
        # LLVAR fields
        if field_num in [2, 32, 35]:
            data_str += f"{len(val):02d}{val}"
        elif field_num == 60:
            data_str += f"{len(val):03d}{val}"
        else:
            data_str += val

    iso_message = mti + bitmap_hex + data_str
    msg_bytes = iso_message.encode("ascii")
    length_prefix = struct.pack(">H", len(msg_bytes))
    return length_prefix + msg_bytes, str(stan).zfill(6), rrn

def parse_iso8583_response(resp: bytes) -> Dict[str, Any]:
    """Parse minimal info from response: get field 39 (response code) and maybe auth code."""
    out = {"response_code": None, "approval_code": None}
    if not resp:
        return out
    # remove length prefix if present
    if len(resp) > 2:
        prefix = struct.unpack(">H", resp[:2])[0]
        if prefix == len(resp) - 2:
            resp = resp[2:]
    s = resp.decode("ascii", errors="ignore")
    # field 39 usually is two chars at a particular offset — simplistic approach:
    # we look for '39' indicator in this simple format (not robust for all ISO messages).
    # Best-effort: search for '39' as field number then next 2 chars.
    idx = s.find("39")
    if idx != -1 and len(s) >= idx + 2 + 2:
        out["response_code"] = s[idx + 2: idx + 4]
    # approval code field 38
    idx38 = s.find("38")
    if idx38 != -1 and len(s) >= idx38 + 2 + 6:
        out["approval_code"] = s[idx38 + 2: idx38 + 8]
    return out

# ---------------------- Main Client Class ----------------------
class StreamlitForceSaleClient:
    def __init__(self):
        # session state defaults
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

        # Servers
        self.SERVERS = {
            "Primary": {"host": "102.163.40.20", "port": 8090},
            "Secondary": {"host": "10.252.251.5", "port": 8080}
        }

        # Cert paths
        self.CERT_DIR = "./certs"
        os.makedirs(self.CERT_DIR, exist_ok=True)
        self.CAD_CERT = os.path.join(self.CERT_DIR, "cad.crt")
        self.ROOT_CERT = os.path.join(self.CERT_DIR, "root.crt")
        self.CLIENT_KEY = os.path.join(self.CERT_DIR, "client.key")
        self.connection = None

    # ---- UI helpers ----
    def setup_page(self):
        st.set_page_config(
            page_title="Professional Payment Terminal", 
            page_icon="💳", 
            layout="wide",
            initial_sidebar_state="expanded"
        )

    def render_sidebar(self):
        st.sidebar.title("⚙️ Setup")
        # server selection
        server = st.sidebar.selectbox("Select Server", list(self.SERVERS.keys()), index=0)
        st.session_state.selected_server = server

        st.sidebar.markdown("---")
        st.sidebar.subheader("🔐 Certificates (upload)")
        cad = st.sidebar.file_uploader("Intermediate CA (cad.crt)", type=["crt", "pem"], key="cad")
        root = st.sidebar.file_uploader("Root CA (root.crt)", type=["crt", "pem"], key="root")
        key = st.sidebar.file_uploader("Client Key (client.key)", type=["key", "pem"], key="ckey")

        if cad:
            with open(self.CAD_CERT, "wb") as f:
                f.write(cad.getvalue())
            st.sidebar.success("cad.crt saved")
        if root:
            with open(self.ROOT_CERT, "wb") as f:
                f.write(root.getvalue())
            st.sidebar.success("root.crt saved")
        if key:
            with open(self.CLIENT_KEY, "wb") as f:
                f.write(key.getvalue())
            st.sidebar.success("client.key saved")

        if os.path.exists(self.CAD_CERT) and os.path.exists(self.ROOT_CERT):
            st.sidebar.success("✅ Certificates present")
            st.session_state.cert_files_uploaded = True
        else:
            st.sidebar.warning("⚠️ Please upload cad.crt and root.crt")

        st.sidebar.markdown("---")
        if st.sidebar.button("🔄 Test Connection", use_container_width=True):
            self.test_connection()

        if st.sidebar.button("📋 Transaction History", use_container_width=True):
            self.show_transaction_history()

    # ---- certificate/SSL helpers ----
    def create_ssl_context(self) -> Tuple[Any, bool]:
        """Create SSL context trusting root.crt; attempt to load cad.crt as cert."""
        try:
            if not os.path.exists(self.ROOT_CERT):
                return "Root certificate missing", False
            context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=self.ROOT_CERT)
            # Attempt to load client cert
            try:
                if os.path.exists(self.CLIENT_KEY):
                    context.load_cert_chain(certfile=self.CAD_CERT, keyfile=self.CLIENT_KEY)
                else:
                    context.load_cert_chain(certfile=self.CAD_CERT)
            except Exception as e:
                st.sidebar.warning(f"Client certificate issue: {e}")
            context.check_hostname = False
            context.verify_mode = ssl.CERT_REQUIRED
            return context, True
        except Exception as e:
            return f"SSL context error: {e}", False

    def test_connection(self):
        if not os.path.exists(self.ROOT_CERT):
            st.error("root.crt is missing in ./certs")
            return
        ctx, ok = self.create_ssl_context()
        if not ok:
            st.error(ctx)
            return
        server_key = st.session_state.get("selected_server", "Primary")
        server = self.SERVERS[server_key]
        try:
            raw = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw.settimeout(10)
            ssock = ctx.wrap_socket(raw, server_hostname=server["host"])
            ssock.connect((server["host"], server["port"]))
            ssock.close()
            st.success(f"✅ Connected to {server['host']}:{server['port']}")
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")

    # ---- ISO8583 send/receive ----
    def connect_socket(self):
        server_key = st.session_state.get("selected_server", "Primary")
        server = self.SERVERS[server_key]
        ctx, ok = self.create_ssl_context()
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

    def send_iso_message(self, msg: bytes) -> Tuple[bool, str, bytes]:
        sock, err = self.connect_socket()
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

    # ---- PDF generation ----
    def generate_pdf_receipt(self, txn: Dict[str, Any]) -> BytesIO:
        """Generate a printable PDF receipt with masked PAN."""
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Header
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(width / 2, height - 50, "PAYMENT RECEIPT")
        c.setFont("Helvetica", 11)

        y = height - 100
        line_gap = 20

        def draw(label, value):
            nonlocal y
            c.drawString(72, y, f"{label}: {value}")
            y -= line_gap

        masked = mask_pan_for_display(txn.get("pan", ""))

        draw("Merchant", txn.get("merchant_name", "Your Store"))
        draw("Terminal ID", st.session_state.terminal_id)
        draw("Date/Time", txn.get("timestamp", datetime.now()).strftime("%Y-%m-%d %H:%M:%S"))
        draw("Card Number", masked)
        draw("Amount", f"${txn.get('amount', 0.0):.2f}")
        draw("Approval Code", txn.get("approval_code", "N/A"))
        draw("Reference Number", txn.get("rrn", "N/A"))
        draw("Status", txn.get("status", "N/A"))

        # Footer
        c.setFont("Helvetica-Oblique", 9)
        c.drawCentredString(width / 2, 40, "Thank you for your business!")

        c.showPage()
        c.save()
        buffer.seek(0)
        return buffer

    # ---- high-level transaction flow ----
    def process_force_sale(self, pan: str, expiry: str, amount: float, approval_code: str, merchant_name: str):
        # validate basic
        if len(re.sub(r'\D', '', pan)) != 16:
            return False, "PAN must be 16 digits", None
        if len(re.sub(r'\D', '', expiry)) != 4:
            return False, "Expiry must be MMYY (4 digits)", None
        if len(approval_code) != 6 or not approval_code.isdigit():
            return False, "Approval code must be 6 digits", None

        stan = st.session_state.stan_counter
        st.session_state.stan_counter += 1

        msg, stan_str, rrn = build_iso8583_force_sale(pan, expiry, amount, approval_code, stan, merchant_name)
        sent, status, data = self.send_iso_message(msg)
        if not sent:
            return False, status, (stan_str, rrn)

        parsed = parse_iso8583_response(data)
        rc = parsed.get("response_code")
        approved = rc == "00" or rc is None and "APPROVED" in status.upper()
        approval_code_from_resp = parsed.get("approval_code") or approval_code

        status_text = "APPROVED" if approved else f"DECLINED ({rc})" if rc else "DECLINED"
        txn = {
            "timestamp": datetime.now(),
            "merchant_name": merchant_name,
            "pan": re.sub(r'\D', '', pan),
            "amount": amount,
            "approval_code": approval_code_from_resp,
            "rrn": rrn,
            "stan": stan_str,
            "status": status_text
        }
        st.session_state.transaction_history.append(txn)

        return True, status_text, txn

    # ---- UI: Payment form & actions ----
    def render_payment_form(self):
        st.header("📝 Payment Details")
        col1, col2 = st.columns(2)
        with col1:
            pan = st.text_input("💳 Card Number (16 digits)", placeholder="4111111111111111", max_chars=19)
            expiry = st.text_input("📅 Expiry Date (MMYY)", placeholder="1225", max_chars=4)
        with col2:
            amount = st.number_input("💰 Amount ($)", min_value=0.01, value=25.00, step=0.01)
            approval_code = st.text_input("✅ Approval Code (6 digits)", max_chars=6)
        merchant_name = st.text_input("🏪 Merchant Name", value="Your Store Name", max_chars=40)
        return pan, expiry, amount, approval_code, merchant_name

    def show_receipt_and_download(self, txn: Dict[str, Any]):
        """Render a simple formatted receipt and give PDF download (masked card)."""
        masked = mask_pan_for_display(txn.get("pan", ""))
        
        st.markdown("### 🧾 Payment Receipt")
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Merchant:** {txn.get('merchant_name')}")
            st.write(f"**Terminal ID:** {st.session_state.terminal_id}")
            st.write(f"**Date/Time:** {txn.get('timestamp').strftime('%Y-%m-%d %H:%M:%S')}")
            st.write(f"**Card:** {masked}")
        with col2:
            st.write(f"**Amount:** ${txn.get('amount'):.2f}")
            st.write(f"**Approval Code:** {txn.get('approval_code')}")
            st.write(f"**Reference:** {txn.get('rrn')}")
            st.write(f"**Status:** {txn.get('status')}")

        # PDF Download
        pdf_buf = self.generate_pdf_receipt(txn)
        st.download_button(
            "📄 Download PDF Receipt",
            data=pdf_buf,
            file_name=f"receipt_{txn.get('stan', int(time.time()))}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    def show_transaction_history(self):
        """Show transaction history in sidebar or main area"""
        st.header("📋 Transaction History")
        if not st.session_state.transaction_history:
            st.info("No transactions yet")
            return
        
        for i, txn in enumerate(reversed(st.session_state.transaction_history[-10:])):
            with st.expander(f"Transaction {i+1} - ${txn['amount']:.2f} - {txn['timestamp'].strftime('%H:%M:%S')}"):
                st.write(f"**Merchant:** {txn['merchant_name']}")
                st.write(f"**Card:** {mask_pan_for_display(txn['pan'])}")
                st.write(f"**Amount:** ${txn['amount']:.2f}")
                st.write(f"**Status:** {txn['status']}")
                st.write(f"**Approval:** {txn['approval_code']}")
                st.write(f"**Reference:** {txn['rrn']}")

    # ---- main run ----
    def run(self):
        self.setup_page()
        self.render_sidebar()

        st.title("💳 Professional Payment Terminal")
        st.markdown("---")
        
        pan, expiry, amount, approval_code, merchant_name = self.render_payment_form()

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("🚀 Process Force Sale", type="primary", use_container_width=True):
                if not st.session_state.cert_files_uploaded:
                    st.error("❌ Please upload certificates first")
                else:
                    ok, msg, result = self.process_force_sale(pan, expiry, amount, approval_code, merchant_name)
                    if ok:
                        st.success(f"✅ {msg}")
                        # show receipt and download
                        self.show_receipt_and_download(result)
                    else:
                        st.error(f"❌ {msg}")
                        # if result contains stan/rrn show minimal info
                        if isinstance(result, tuple) and result[0]:
                            st.write(f"STAN: {result[0]}, RRN: {result[1]}")

def main():
    client = StreamlitForceSaleClient()
    client.run()

if __name__ == "__main__":
    main()
