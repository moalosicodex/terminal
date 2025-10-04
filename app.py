import streamlit as st
import ssl
import os
import socket
import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from datetime import datetime
from pathlib import Path

# ==============================================================
# === PASSWORD PROTECTION ===
# ==============================================================

# Simple password auth (you can replace with secrets or DB later)
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets.get("APP_PASSWORD", "admin123"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("🔐 Enter Password", type="password", on_change=password_entered, key="password")
        st.stop()
    elif not st.session_state["password_correct"]:
        st.text_input("🔐 Enter Password", type="password", on_change=password_entered, key="password")
        st.error("❌ Incorrect password. Please try again.")
        st.stop()

# ==============================================================
# === CUSTOM HTTPS ADAPTER ===
# ==============================================================

class SSLAdapter(HTTPAdapter):
    """Custom HTTPS adapter using a provided SSLContext."""

    def __init__(self, ssl_context=None, **kwargs):
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs["ssl_context"] = self.ssl_context
        return super().proxy_manager_for(*args, **kwargs)

# ==============================================================
# === PAYMENT CLIENT CLASS ===
# ==============================================================

class PaymentClient:
    def __init__(self, base_url: str):
        self.BASE_DIR = Path(__file__).resolve().parent
        self.CERT_DIR = self.BASE_DIR / "certs"
        os.makedirs(self.CERT_DIR, exist_ok=True)

        # Certificate paths
        self.ROOT_CERT = self.CERT_DIR / "root.crt"
        self.CAD_CERT = self.CERT_DIR / "cad.crt"
        self.CLIENT_CERT = self.CERT_DIR / "client.crt"
        self.CLIENT_KEY = self.CERT_DIR / "client.key"

        # Base URL
        self.SERVER_URL = base_url

        # SSL setup
        self.ssl_context, self.cert_status = self.create_ssl_context()

        # HTTPS session
        self.session = requests.Session()
        if isinstance(self.ssl_context, ssl.SSLContext):
            self.session.mount("https://", SSLAdapter(self.ssl_context))

    # ------------------------------------------------------------
    # Create SSL context
    # ------------------------------------------------------------
    def create_ssl_context(self):
        """Creates SSL context trusting root.crt and cad.crt"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = False

        try:
            # Combine CA certs into one file
            ca_bundle_path = self.CERT_DIR / "ca_bundle.crt"
            with open(ca_bundle_path, "w") as bundle:
                if self.ROOT_CERT.exists():
                    bundle.write(self.ROOT_CERT.read_text())
                if self.CAD_CERT.exists():
                    bundle.write(self.CAD_CERT.read_text())

            # Load CA certificates
            context.load_verify_locations(cafile=str(ca_bundle_path))

            # Load optional client certs
            if self.CLIENT_CERT.exists() and self.CLIENT_KEY.exists():
                context.load_cert_chain(certfile=str(self.CLIENT_CERT), keyfile=str(self.CLIENT_KEY))

            return context, True

        except Exception as e:
            return f"Certificate load error: {e}", False

    # ------------------------------------------------------------
    # Test server connection
    # ------------------------------------------------------------
    def test_connection(self):
        """Test a secure GET request"""
        try:
            response = self.session.get(self.SERVER_URL, timeout=5, verify=False)
            return f"✅ Connected to {self.SERVER_URL} (HTTP {response.status_code})"
        except Exception as e:
            return f"❌ Connection failed: {e}"

# ==============================================================
# === STREAMLIT UI ===
# ==============================================================

def main():
    st.set_page_config(page_title="SSL Payment Client", page_icon="💳", layout="centered")

    # Password protection
    check_password()

    st.title("💳 Secure Payment Client")
    st.write("This tool allows you to test SSL-secured payment connections with uploaded CA certificates.")

    # ------------------------------------------------------------
    # Server selection
    # ------------------------------------------------------------
    st.sidebar.header("🌐 Server Configuration")
    servers = {
        "Server 1 (Main)": "https://102.163.40.20:8090",
        "Server 2 (Backup)": "https://10.252.251.5:8080"
    }
    selected_server = st.sidebar.selectbox("Select server:", list(servers.keys()))
    base_url = servers[selected_server]

    st.sidebar.markdown("---")

    # ------------------------------------------------------------
    # Certificate uploads
    # ------------------------------------------------------------
    st.sidebar.header("📄 Certificate Uploads")

    root_file = st.sidebar.file_uploader("Root Certificate (root.crt)", type=["crt", "pem"], key="root")
    cad_file = st.sidebar.file_uploader("Intermediate CA (cad.crt)", type=["crt", "pem"], key="cad")
    client_cert_file = st.sidebar.file_uploader("Client Certificate (optional)", type=["crt", "pem"], key="client_cert")
    client_key_file = st.sidebar.file_uploader("Client Key (optional)", type=["key", "pem"], key="client_key")

    cert_dir = Path(__file__).resolve().parent / "certs"
    os.makedirs(cert_dir, exist_ok=True)

    if root_file:
        (cert_dir / "root.crt").write_bytes(root_file.read())
        st.sidebar.success("✅ Root CA uploaded")

    if cad_file:
        (cert_dir / "cad.crt").write_bytes(cad_file.read())
        st.sidebar.success("✅ Intermediate CA uploaded")

    if client_cert_file:
        (cert_dir / "client.crt").write_bytes(client_cert_file.read())
        st.sidebar.info("ℹ️ Client certificate uploaded")

    if client_key_file:
        (cert_dir / "client.key").write_bytes(client_key_file.read())
        st.sidebar.info("ℹ️ Client key uploaded")

    # ------------------------------------------------------------
    # Initialize client
    # ------------------------------------------------------------
    client = PaymentClient(base_url)

    st.write("### 🧾 SSL Context Status")
    if client.cert_status is True:
        st.success("SSL context created successfully ✅")
    else:
        st.error(f"SSL initialization failed: {client.cert_status}")

    # ------------------------------------------------------------
    # Test connection
    # ------------------------------------------------------------
    if st.button("🔍 Test Server Connection"):
        result = client.test_connection()
        st.info(result)

    st.markdown("---")
    st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ==============================================================
# === ENTRY POINT ===
# ==============================================================

if __name__ == "__main__":
    main()
