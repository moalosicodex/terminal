#!/usr/bin/env python3
"""
ISO-8583 Base I Terminal
Online Authorization with Protocol 101.1
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
import random

# === PASSWORD PROTECTION === 
APP_PASSWORD_HASH = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # "password"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🔒 ISO-8583 Base I Terminal")
    password = st.text_input("Enter Password", type="password")
    if st.button("Access System"):
        if hashlib.sha256(password.encode()).hexdigest() == APP_PASSWORD_HASH:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()
# === END PASSWORD PROTECTION ===

class ISO8583BaseITerminal:
    """
    ISO-8583 Base I Terminal - Protocol 101.1
    Online Authorization with 4-Digit Approval Codes
    """
    
    def __init__(self):
        # Session state initialization
        if 'merchant_id' not in st.session_state:
            st.session_state.merchant_id = "000000000009020"
        if 'terminal_id' not in st.session_state:
            st.session_state.terminal_id = "72000716"
        if 'stan_counter' not in st.session_state:
            st.session_state.stan_counter = 100001
        if 'batch_number' not in st.session_state:
            st.session_state.batch_number = random.randint(1000, 9999)
        if 'receipt_counter' not in st.session_state:
            st.session_state.receipt_counter = 1
        if 'last_transaction' not in st.session_state:
            st.session_state.last_transaction = None
        if 'transaction_history' not in st.session_state:
            st.session_state.transaction_history = []
        if 'cert_files_uploaded' not in st.session_state:
            st.session_state.cert_files_uploaded = False
        
        # Server configuration with defaults
        if 'server_config' not in st.session_state:
            st.session_state.server_config = {
                'primary': {
                    'host': '102.163.40.20',
                    'port': 8090,
                    'protocol': 'HTTPS'
                },
                'secondary': {
                    'host': '10.252.251.5', 
                    'port': 8080,
                    'protocol': 'HTTPS'
                }
            }
            
        # Create certs directory if it doesn't exist
        self.CERT_DIR = "./certs"
        os.makedirs(self.CERT_DIR, exist_ok=True)
        
        self.CLIENT_CERT = f"{self.CERT_DIR}/cad.crt" 
        self.CLIENT_KEY = f"{self.CLIENT_DIR}/client.key"
        self.connection = None

    def setup_page(self):
        """Configure Streamlit page"""
        st.set_page_config(
            page_title="ISO-8583 Base I Terminal",
            page_icon="💳",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS for better styling
        st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 1rem;
        }
        .sub-header {
            font-size: 1.2rem;
            color: #6c757d;
            text-align: center;
            margin-bottom: 2rem;
        }
        .receipt-container {
            border: 3px solid #1f77b4;
            border-radius: 15px;
            padding: 25px;
            margin: 20px 0;
            background-color: #f8f9fa;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .receipt-header {
            text-align: center;
            color: #1f77b4;
            border-bottom: 2px solid #dee2e6;
            padding-bottom: 15px;
            margin-bottom: 20px;
        }
        .success-receipt {
            border-color: #28a745;
            background-color: #d4edda;
        }
        .warning-receipt {
            border-color: #ffc107;
            background-color: #fff3cd;
        }
        .receipt-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin: 15px 0;
        }
        .receipt-field {
            font-weight: bold;
            color: #555;
        }
        .receipt-value {
            color: #212529;
        }
        .monospace {
            font-family: 'Courier New', monospace;
        }
        </style>
        """, unsafe_allow_html=True)

    # ... [Keep all the previous methods the same until show_receipt method] ...

    def show_receipt(self, form_data, result):
        """Show payment receipt using Streamlit components (no HTML)"""
        st.markdown("---")
        st.header("🧾 Payment Receipt")
        
        # Create a container for the receipt
        receipt_container = st.container()
        
        with receipt_container:
            # Determine receipt style based on status
            if result.get('response_code') == '00':
                st.success("✅ PAYMENT APPROVED")
                receipt_class = "success-receipt"
            else:
                st.warning("⚠️ PAYMENT PROCESSED")
                receipt_class = "warning-receipt"
            
            # Create receipt using Streamlit components
            with st.container():
                st.markdown(f"""
                <div class="receipt-container {receipt_class}">
                    <div class="receipt-header">
                        <h2>💳 PAYMENT RECEIPT</h2>
                        <p>ISO-8583 Base I Terminal • Protocol 101.1</p>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Merchant Information
                st.subheader("🏪 Merchant Information")
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Merchant", form_data['merchant_name'], disabled=True)
                    st.text_input("Terminal ID", st.session_state.terminal_id, disabled=True)
                with col2:
                    st.text_input("Merchant ID", st.session_state.merchant_id, disabled=True)
                    st.text_input("Transaction Type", "🟢 Online Authorization", disabled=True)
                
                # Transaction Details
                st.subheader("📊 Transaction Details")
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Receipt Number", str(result.get('receipt_number', 'N/A')), disabled=True)
                    st.text_input("Batch Number", str(result.get('batch_number', 'N/A')), disabled=True)
                    st.text_input("Card Number", self.format_card_receipt(form_data['card_input']), disabled=True)
                with col2:
                    st.text_input("RRN", result.get('rrn', 'N/A'), disabled=True)
                    st.text_input("STAN", result.get('stan', 'N/A'), disabled=True)
                    st.text_input("Expiry Date", self.format_expiry_display(form_data['expiry_input']), disabled=True)
                
                # Amount and Date
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Amount", f"${form_data['amount']:.2f}", disabled=True)
                with col2:
                    st.text_input("Date/Time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), disabled=True)
                
                # Authorization Information
                st.subheader("🔐 Authorization Information")
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Status", result.get('response_message', 'Unknown'), disabled=True)
                    st.text_input("Approval Code", result.get('approval_code', 'N/A'), disabled=True)
                with col2:
                    st.text_input("Response Code", result.get('response_code', 'N/A'), disabled=True)
                    st.text_input("Auth Code", result.get('full_auth_code', 'N/A'), disabled=True)
                
                # Footer
                st.markdown("---")
                st.markdown("### **THANK YOU FOR YOUR BUSINESS**")
                st.caption("Keep this receipt for your records")
        
        # Download buttons
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            col_a, col_b = st.columns(2)
            
            with col_a:
                # Download as TXT
                receipt_text = self.generate_receipt_text(form_data, result)
                st.download_button(
                    label="📄 Download TXT Receipt",
                    data=receipt_text,
                    file_name=f"receipt_{result.get('receipt_number', 'unknown')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col_b:
                # Print functionality
                if st.button("🖨️ Print Receipt", use_container_width=True):
                    st.success("📠 Ready for printing! Use your browser's print function (Ctrl+P).")

    def generate_receipt_text(self, form_data, result):
        """Generate formatted receipt text for download"""
        return f"""
{'=' * 50}
         PAYMENT RECEIPT
        ISO-8583 Base I Terminal
{'=' * 50}

MERCHANT INFORMATION:
{'-' * 50}
Merchant: {form_data['merchant_name']}
Terminal ID: {st.session_state.terminal_id}
Merchant ID: {st.session_state.merchant_id}
Transaction: Online Authorization (Protocol 101.1)

TRANSACTION DETAILS:
{'-' * 50}
Receipt Number: {result.get('receipt_number', 'N/A')}
Batch Number: {result.get('batch_number', 'N/A')}
RRN: {result.get('rrn', 'N/A')}
STAN: {result.get('stan', 'N/A')}
Card: {self.format_card_receipt(form_data['card_input'])}
Expiry: {self.format_expiry_display(form_data['expiry_input'])}
Amount: ${form_data['amount']:.2f}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

AUTHORIZATION INFORMATION:
{'-' * 50}
Status: {result.get('response_message', 'Unknown')}
Approval Code: {result.get('approval_code', 'N/A')}
Auth Code: {result.get('full_auth_code', 'N/A')}
Response Code: {result.get('response_code', 'N/A')}

{'-' * 50}
      THANK YOU FOR YOUR BUSINESS
{'=' * 50}
"""

    # ... [Keep all other methods the same] ...

    def format_card_receipt(self, pan: str) -> str:
        """Format card for receipt - show only last 4 digits"""
        clean_pan = re.sub(r'\D', '', pan)
        if len(clean_pan) == 16:
            return f"XXXX-XXXX-XXXX-{clean_pan[12:16]}"
        return clean_pan

    def format_expiry_display(self, expiry: str) -> str:
        """Format expiry for display"""
        clean_expiry = re.sub(r'\D', '', expiry)
        return f"{clean_expiry[:2]}/{clean_expiry[2:4]}"

    # ... [Rest of the methods remain unchanged] ...

def main():
    """Main function"""
    terminal = ISO8583BaseITerminal()
    terminal.run()

if __name__ == "__main__":
    main()
