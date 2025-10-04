#!/usr/bin/env python3
"""
Professional Payment Terminal Web Application
Visa Base I Protocol - 101.1 4digit online
"""

import streamlit as st
import socket
import ssl
import struct
import os
import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import time
import hashlib

# === PASSWORD PROTECTION === 
APP_PASSWORD_HASH = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # Change this!

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

# === MAIN CLIENT CLASS ===
class StreamlitForceSaleClient:
    def __init__(self):
        # Session state defaults
        if 'merchant_id' not in st.session_state:
            st.session_state.merchant_id = "000000000009020"
        if 'terminal_id' not in st.session_state:
            st.session_state.terminal_id = "72000716"
        if 'stan_counter' not in st.session_state:
            st.session_state.stan_counter = 100001
        if 'last_transaction' not in st.session_state:
            st.session_state.last_transaction = None
        if 'transaction_history' not in st.session_state:
            st.session_state.transaction_history = []
        if 'cert_files_uploaded' not in st.session_state:
            st.session_state.cert_files_uploaded = False
        if 'show_receipt' not in st.session_state:
            st.session_state.show_receipt = False
        if 'current_receipt_data' not in st.session_state:
            st.session_state.current_receipt_data = None

        self.SERVERS = {
            'primary': {'host': '102.163.40.20', 'port': 8090},
            'secondary': {'host': '10.252.251.5', 'port': 8080}
        }

        self.CERT_DIR = "./certs"
        os.makedirs(self.CERT_DIR, exist_ok=True)
        self.CLIENT_CERT = f"{self.CERT_DIR}/cad.crt"
        self.CLIENT_KEY = None  # Optional
        self.CA_CERT = f"{self.CERT_DIR}/root.crt"
        self.connection = None

    # --- SSL CONNECTION ---
    def connect_ssl(self, server_type='primary'):
        server = self.SERVERS[server_type]
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=self.CA_CERT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_REQUIRED

        if self.CLIENT_KEY:
            context.load_cert_chain(certfile=self.CLIENT_CERT, keyfile=self.CLIENT_KEY)
        else:
            context.load_cert_chain(certfile=self.CLIENT_CERT)

        raw_sock = socket.create_connection((server['host'], server['port']), timeout=10)
        self.connection = context.wrap_socket(raw_sock, server_hostname=server['host'])
        return True

    # --- ISO8583 MESSAGE BUILD ---
    def build_iso8583_force_sale(self, pan, amount, expiry, approval_code, merchant_name):
        stan = str(st.session_state.stan_counter).zfill(6)
        st.session_state.stan_counter += 1
        rrn = stan + "FSL"

        now = datetime.now()
        transmission_time = now.strftime("%m%d%H%M%S")
        local_time = now.strftime("%H%M%S")
        local_date = now.strftime("%m%d")

        fields = {
            2: pan,
            3: "000000",
            4: str(int(amount*100)).zfill(12),
            7: transmission_time,
            11: stan,
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

        bitmap = bytearray(8)
        for f in fields:
            if 1 <= f <= 64:
                byte_index = (f-1)//8
                bit_index = 7 - ((f-1)%8)
                bitmap[byte_index] |= (1 << bit_index)

        data = ""
        for f in sorted(fields.keys()):
            v = fields[f]
            if f in [2, 35, 32]:
                data += f"{len(v):02d}{v}"
            elif f == 60:
                data += f"{len(v):03d}{v}"
            else:
                data += v

        iso_msg = "0200" + bitmap.hex().upper() + data
        length_prefix = struct.pack(">H", len(iso_msg))
        return length_prefix + iso_msg.encode('ascii'), stan, rrn

    # --- SEND ISO8583 ---
    def send_iso8583_message(self, iso_message):
        if not self.connection:
            raise ConnectionError("Not connected")
        self.connection.sendall(iso_message)
        response = self.connection.recv(4096)
        return response.decode("ascii")

    # --- CHECK CERTIFICATES ---
    def check_certificates(self):
        if not os.path.exists(self.CLIENT_CERT) or not os.path.exists(self.CA_CERT):
            return False, "Certificates missing"
        if os.path.getsize(self.CLIENT_CERT) == 0 or os.path.getsize(self.CA_CERT) == 0:
            return False, "Certificates are empty"
        return True, "Certificates ready"

    # --- PAYMENT PROCESS ---
    def process_payment(self, pan, amount, expiry, approval_code, merchant_name):
        cert_ok, msg = self.check_certificates()
        if not cert_ok:
            st.error(f"❌ Certificate error: {msg}")
            return

        # Connect SSL
        try:
            self.connect_ssl()
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")
            return

        # Build ISO message
        iso_msg, stan, rrn = self.build_iso8583_force_sale(
            pan, amount, expiry, approval_code, merchant_name
        )

        # Send transaction
        try:
            response = self.send_iso8583_message(iso_msg)
        except Exception as e:
            st.error(f"❌ Transaction failed: {e}")
            return
        finally:
            if self.connection:
                self.connection.close()
                self.connection = None

        # Record transaction
        st.session_state.transaction_history.append({
            'timestamp': datetime.now(),
            'amount': amount,
            'card': pan,
            'status': 'APPROVED',
            'stan': stan,
            'rrn': rrn,
            'merchant_name': merchant_name
        })

        st.success(f"✅ Transaction sent! STAN: {stan}, RRN: {rrn}")
        st.info(f"Server Response:\n{response}")

# --- STREAMLIT APP ---
def main():
    client = StreamlitForceSaleClient()

    st.title("💳 Professional Payment Terminal")

    # Certificate Upload
    st.sidebar.subheader("🔐 Certificates")
    cert_file = st.sidebar.file_uploader("Upload cad.crt", type=["crt", "pem"])
    ca_file = st.sidebar.file_uploader("Upload root.crt", type=["crt", "pem"])
    if cert_file and ca_file:
        with open(client.CLIENT_CERT, "wb") as f:
            f.write(cert_file.getvalue())
        with open(client.CA_CERT, "wb") as f:
            f.write(ca_file.getvalue())
        st.sidebar.success("✅ Certificates uploaded")

    # Payment Form
    st.header("📝 Force Sale Payment")
    pan = st.text_input("Card Number (16 digits)")
    expiry = st.text_input("Expiry (MMYY)")
    approval_code = st.text_input("Approval Code (6 digits)")
    amount = st.number_input("Amount ($)", min_value=0.01, value=25.00, step=0.01)
    merchant_name = st.text_input("Merchant Name", value="Demo Store")

    if st.button("🚀 Process Force Sale"):
        client.process_payment(pan, amount, expiry, approval_code, merchant_name)

    # Transaction History
    st.header("📋 Transaction History")
    for tx in reversed(st.session_state.transaction_history[-10:]):
        st.write(f"{tx['timestamp']} | {tx['card']} | ${tx['amount']} | {tx['status']} | STAN: {tx['stan']} | RRN: {tx['rrn']}")

if __name__ == "__main__":
    main()
