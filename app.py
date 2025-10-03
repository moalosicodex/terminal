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

#!/usr/bin/env python3
"""
Professional Payment Terminal Web Application
With Visa Base I Protocol Identification
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
import base64

class StreamlitForceSaleClient:
    """
    Complete Force Sale Client with Visa Base I Protocol
    """
    
    def __init__(self):
        # Session state initialization
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
        if 'protocol_info' not in st.session_state:
            st.session_state.protocol_info = "Visa Base I (ISO 8583)"
            
        self.SERVERS = {
            'primary': {'host': '102.163.40.20', 'port': 8090},
            'secondary': {'host': '10.252.251.5', 'port': 8080}
        }
        
        # Visa Base I Protocol Configuration
        self.PROTOCOL_CONFIG = {
            'name': 'Visa Base I',
            'version': '1.0',
            'standard': 'ISO 8583:1993',
            'transaction_type': 'Force Sale',
            'mti_request': '0200',
            'processing_code': '000000',
            'function_code': '200'
        }
        
        # Create certs directory if it doesn't exist
        self.CERT_DIR = "./certs"
        os.makedirs(self.CERT_DIR, exist_ok=True)
        
        self.CLIENT_CERT = f"{self.CERT_DIR}/cad.crt" 
        self.CLIENT_KEY = f"{self.CERT_DIR}/client.key"
        self.connection = None

    def setup_page(self):
        """Configure Streamlit page"""
        st.set_page_config(
            page_title="Professional Payment Terminal - Visa Base I",
            page_icon="💳",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS
        st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 2rem;
        }
        .protocol-badge {
            background-color: #1f77b4;
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            display: inline-block;
            margin: 10px 0;
        }
        .receipt-box {
            border: 2px solid #1f77b4;
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            background-color: #f0f8ff;
        }
        .success-box {
            border: 2px solid #28a745;
            background-color: #d4edda;
            color: #155724;
        }
        .error-box {
            border: 2px solid #dc3545;
            background-color: #f8d7da;
            color: #721c24;
        }
        .cert-box {
            border: 2px solid #ffc107;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            background-color: #fff3cd;
        }
        .transition-info {
            background-color: #e7f3ff;
            border-left: 4px solid #1f77b4;
            padding: 10px;
            margin: 10px 0;
        }
        </style>
        """, unsafe_allow_html=True)

    def render_protocol_info(self):
        """Display protocol information"""
        st.markdown(f"""
        <div style="text-align: center;">
            <div class="protocol-badge">🔒 {self.PROTOCOL_CONFIG['name']}</div>
            <p><strong>Standard:</strong> {self.PROTOCOL_CONFIG['standard']} | 
            <strong>Transaction Type:</strong> {self.PROTOCOL_CONFIG['transaction_type']}</p>
        </div>
        """, unsafe_allow_html=True)

    def build_force_sale_message(self, pan: str, amount: float, expiry: str, approval_code: str, merchant_name: str):
        """Build Force Sale ISO message with Visa Base I protocol"""
        # Generate transition identifiers
        stan = str(st.session_state.stan_counter).zfill(6)
        st.session_state.stan_counter += 1
        
        # RRN (Retrieval Reference Number) - Critical for transaction tracking
        rrn = stan + "FSL"  # FSL indicates Force Sale
        
        now = datetime.now()
        transmission_time = now.strftime("%m%d%H%M%S")
        local_time = now.strftime("%H%M%S")
        local_date = now.strftime("%m%d")
        
        # Store transaction data with protocol info
        st.session_state.last_transaction = {
            "pan": pan,
            "expiry": expiry,
            "amount": amount,
            "stan": stan,
            "rrn": rrn,
            "type": "Force Sale",
            "merchant_name": merchant_name,
            "timestamp": datetime.now(),
            "approval_code": approval_code,
            "protocol": self.PROTOCOL_CONFIG['name'],
            "mti": self.PROTOCOL_CONFIG['mti_request']
        }

        # ISO 8583 data elements for Visa Base I Force Sale
        data_elements = {
            # Primary Account Number
            2: pan,
            # Processing Code (000000 for Force Sale)
            3: self.PROTOCOL_CONFIG['processing_code'],
            # Amount, Transaction
            4: str(int(amount * 100)).zfill(12),
            # Transmission Date & Time
            7: transmission_time,
            # STAN (Systems Trace Audit Number) - TRANSITION ID
            11: stan,
            # Local Time (HHMMSS)
            12: local_time,
            # Local Date (MMDD)
            13: local_date,
            # Expiration Date (YYMM)
            14: expiry,
            # Merchant Type
            18: "5999",  # Miscellaneous stores
            # Point of Service Entry Mode
            22: "012",   # Manual key entry
            # Function Code (200 for Force Sale)
            24: self.PROTOCOL_CONFIG['function_code'],
            # POS Condition Code
            25: "08",    # Manual, no terminal
            # Acquiring Institution ID
            32: "00000000001",
            # Track 2 Data
            35: pan + "=" + expiry + "100",
            # RRN (Retrieval Reference Number) - TRANSITION ID
            37: rrn,
            # Authorization Code
            38: approval_code,
            # Terminal ID
            41: st.session_state.terminal_id,
            # Merchant ID
            42: st.session_state.merchant_id,
            # Card Acceptor Name/Location
            43: merchant_name.ljust(16)[:16],
            # Currency Code (USD)
            49: "840",
            # Additional Data - Visa Specific (00108001 = Force Sale)
            60: "00108001",
        }

        # Build bitmap (indicates which fields are present)
        bitmap = bytearray(8)
        for field_num in data_elements.keys():
            if 1 <= field_num <= 64:
                byte_index = (field_num - 1) // 8
                bit_index = 7 - ((field_num - 1) % 8)
                bitmap[byte_index] |= (1 << bit_index)

        # MTI for Authorization Request
        mti = self.PROTOCOL_CONFIG['mti_request']
        bitmap_hex = bitmap.hex().upper()

        # Build data string with proper field formatting
        data_str = ""
        for field_num in sorted(data_elements.keys()):
            value = data_elements[field_num]
            # LLVAR and LLLVAR fields
            if field_num in [2, 35]:  # LLVAR fields
                data_str += f"{len(value):02d}{value}"
            elif field_num in [32]:   # LLVAR field
                data_str += f"{len(value):02d}{value}"
            elif field_num in [60]:   # LLLVAR field
                data_str += f"{len(value):03d}{value}"
            else:  # Fixed length fields
                data_str += value

        iso_message = mti + bitmap_hex + data_str
        message_length = len(iso_message)
        length_prefix = struct.pack('>H', message_length)
        
        return length_prefix + iso_message.encode('ascii')

    def parse_visa_response(self, response: bytes) -> Dict[str, Any]:
        """Parse Visa Base I response"""
        try:
            if len(response) < 4:
                return {"error": "Response too short"}
                
            # Check for length prefix
            if len(response) > 2:
                potential_length = struct.unpack('>H', response[:2])[0]
                if potential_length == len(response) - 2:
                    response = response[2:]
            
            response_str = response.decode('ascii', errors='ignore')
            
            result = {
                "mti": response_str[0:4] if len(response_str) >= 4 else "",
                "length": len(response),
                "protocol": self.PROTOCOL_CONFIG['name'],
                "raw_response": response_str
            }
            
            # Visa Base I response codes
            visa_codes = {
                '00': 'APPROVED - Force Sale Completed',
                '01': 'REFER TO ISSUER', 
                '05': 'DECLINED - Do Not Honor',
                '12': 'ERROR - Invalid Transaction',
                '13': 'ERROR - Invalid Amount',
                '14': 'ERROR - Invalid Card',
                '51': 'DECLINED - Insufficient Funds',
                '54': 'ERROR - Expired Card',
                '55': 'ERROR - Incorrect PIN',
                '91': 'UNAVAILABLE - Issuer Unavailable',
                '96': 'ERROR - System Malfunction'
            }
            
            # Extract response code (Field 39)
            response_code = self.extract_field(response_str, 39, 2)
            if response_code:
                result["response_code"] = response_code
                result["response_message"] = visa_codes.get(response_code, f"UNKNOWN CODE: {response_code}")
            
            # Extract auth code (Field 38)
            auth_code = self.extract_field(response_str, 38, 6)
            if auth_code:
                result["auth_code"] = auth_code
                if len(auth_code) >= 4:
                    result["approval_code"] = auth_code[:4]
                    result["full_auth_code"] = auth_code
            
            # Extract RRN (Field 37) - Transaction tracking
            rrn = self.extract_field(response_str, 37, 12)
            if rrn:
                result["retrieval_reference_number"] = rrn
            
            # Extract STAN (Field 11)
            stan = self.extract_field(response_str, 11, 6)
            if stan:
                result["systems_trace_number"] = stan
            
            return result
            
        except Exception as e:
            return {"error": f"Parse error: {e}"}

    def extract_field(self, response_str: str, field_num: int, max_length: int) -> str:
        """Extract specific field from ISO response"""
        try:
            # Simple field extraction - in production, use proper bitmap parsing
            field_str = str(field_num)
            idx = response_str.find(field_str)
            if idx != -1:
                # Move past the field number
                value_start = idx + len(field_str)
                return response_str[value_start:value_start + max_length]
        except:
            pass
        return ""

    def show_receipt(self, form_data, result):
        """Show payment receipt with protocol information"""
        st.markdown("---")
        st.header("🧾 Payment Receipt")
        
        # Display transition IDs
        st.markdown("""
        <div class="transition-info">
            <strong>Transaction Identifiers:</strong><br>
            • STAN (Systems Trace): {}<br>
            • RRN (Retrieval Reference): {}<br>
            • Protocol: {}
        </div>
        """.format(
            result.get('systems_trace_number', 'N/A'),
            result.get('retrieval_reference_number', 'N/A'),
            result.get('protocol', self.PROTOCOL_CONFIG['name'])
        ), unsafe_allow_html=True)
        
        receipt_html = f"""
        <div class="receipt-box success-box">
            <h3 style="text-align: center; margin-bottom: 20px;">FORCE SALE RECEIPT</h3>
            <p style="text-align: center; font-style: italic;">{self.PROTOCOL_CONFIG['name']} - {self.PROTOCOL_CONFIG['standard']}</p>
            
            <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Merchant:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{form_data['merchant_name']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Terminal ID:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{st.session_state.terminal_id}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Protocol:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{self.PROTOCOL_CONFIG['name']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Card Number:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{self.format_card_display(form_data['card_input'])}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Amount:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">${form_data['amount']:.2f}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Date/Time:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Status:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{result.get('response_message', 'Unknown')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Approval Code:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{result.get('approval_code', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Auth Code:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{result.get('full_auth_code', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Response Code:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{result.get('response_code', 'N/A')}</td>
            </tr>
            </table>
            
            <p style="text-align: center; margin-top: 20px; font-weight: bold;">THANK YOU FOR YOUR BUSINESS</p>
        </div>
        """
        
        st.markdown(receipt_html, unsafe_allow_html=True)
        
        # Download button
        receipt_text = self.generate_receipt_text(form_data, result)
        st.download_button(
            label="📄 Download Receipt",
            data=receipt_text,
            file_name=f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )

    def generate_receipt_text(self, form_data, result):
        """Generate receipt text for download with protocol info"""
        return f"""
FORCE SALE RECEIPT - {self.PROTOCOL_CONFIG['name']}
==================================================
Merchant: {form_data['merchant_name']}
Terminal ID: {st.session_state.terminal_id}
Merchant ID: {st.session_state.merchant_id}
Protocol: {self.PROTOCOL_CONFIG['name']} ({self.PROTOCOL_CONFIG['standard']})
--------------------------------------------------
Card: {self.format_card_display(form_data['card_input'])}
Expiry: {self.format_expiry_display(form_data['expiry_input'])}
Amount: ${form_data['amount']:.2f}
Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
--------------------------------------------------
TRANSACTION IDENTIFIERS:
STAN: {result.get('systems_trace_number', 'N/A')}
RRN: {result.get('retrieval_reference_number', 'N/A')}
--------------------------------------------------
Status: {result.get('response_message', 'Unknown')}
Approval Code: {result.get('approval_code', 'N/A')}
Auth Code: {result.get('full_auth_code', 'N/A')}
Response Code: {result.get('response_code', 'N/A')}
==================================================
THANK YOU FOR YOUR BUSINESS
"""

    def render_main_header(self):
        """Render main header with protocol info"""
        st.markdown('<div class="main-header">💳 Professional Payment Terminal</div>', 
                   unsafe_allow_html=True)
        self.render_protocol_info()
        st.markdown("---")

    # [Keep all other methods the same as your original implementation]
    # validate_card_number, validate_expiry_date, format_card_display, 
    # format_expiry_display, create_ssl_context, connect_to_server,
    # send_transaction, process_payment, handle_transaction_result, 
    # disconnect, test_connection, show_transaction_history, etc.

    def run(self):
        """Main application runner"""
        self.setup_page()
        self.render_sidebar()
        self.render_main_header()
        
        # Check if certificates are ready
        cert_valid, _ = self.check_certificates()
        
        if not cert_valid and not st.session_state.cert_files_uploaded:
            self.render_demo_mode()
        else:
            # Payment form
            form_data = self.render_payment_form()
            
            # Process payment button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 Process Force Sale", type="primary", use_container_width=True):
                    self.process_payment(form_data)

def main():
    """Main function"""
    client = StreamlitForceSaleClient()
    client.run()

if __name__ == "__main__":
    main()
