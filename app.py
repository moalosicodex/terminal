#!/usr/bin/env python3
"""
Professional Payment Terminal Web Application
Visa Base I Protocol - Complete Implementation
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
            margin-bottom: 1rem;
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
        .warning-box {
            border: 2px solid #ffc107;
            background-color: #fff3cd;
            color: #856404;
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
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }
        .demo-banner {
            background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
            color: white;
            padding: 15px;
            border-radius: 10px;
            text-align: center;
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

    def render_certificate_upload(self):
        """Render certificate upload section"""
        st.sidebar.subheader("🔐 Certificate Setup")
        
        if st.session_state.cert_files_uploaded:
            st.sidebar.success("✅ Certificates Uploaded")
            if st.sidebar.button("🔄 Re-upload Certificates"):
                st.session_state.cert_files_uploaded = False
                st.rerun()
            return True
        
        st.sidebar.info("Upload your certificate files")
        
        # Certificate file upload
        cert_file = st.sidebar.file_uploader(
            "Upload Certificate File (cad.crt)",
            type=['crt', 'pem'],
            key="cert_upload"
        )
        
        key_file = st.sidebar.file_uploader(
            "Upload Key File (client.key)",
            type=['key', 'pem'],
            key="key_upload"
        )
        
        if cert_file and key_file:
            # Save uploaded files
            try:
                with open(self.CLIENT_CERT, "wb") as f:
                    f.write(cert_file.getvalue())
                
                with open(self.CLIENT_KEY, "wb") as f:
                    f.write(key_file.getvalue())
                
                st.sidebar.success("✅ Certificates saved successfully!")
                st.session_state.cert_files_uploaded = True
                st.rerun()
                
            except Exception as e:
                st.sidebar.error(f"Error saving certificates: {e}")
        
        # Alternative: Manual certificate input
        with st.sidebar.expander("📝 Or enter certificate text"):
            cert_text = st.text_area("Certificate Content (.crt)", height=100)
            key_text = st.text_area("Key Content (.key)", height=100)
            
            if st.button("Save Certificate Text"):
                if cert_text and key_text:
                    try:
                        with open(self.CLIENT_CERT, "w") as f:
                            f.write(cert_text)
                        with open(self.CLIENT_KEY, "w") as f:
                            f.write(key_text)
                        st.success("Certificates saved!")
                        st.session_state.cert_files_uploaded = True
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        return False

    def check_certificates(self):
        """Check if certificates exist and are valid"""
        if not os.path.exists(self.CLIENT_CERT) or not os.path.exists(self.CLIENT_KEY):
            return False, "Certificate files missing"
        
        try:
            # Check if files are not empty
            if os.path.getsize(self.CLIENT_CERT) == 0 or os.path.getsize(self.CLIENT_KEY) == 0:
                return False, "Certificate files are empty"
            
            # Try to load certificates to verify they're valid
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.load_cert_chain(certfile=self.CLIENT_CERT, keyfile=self.CLIENT_KEY)
            return True, "Certificates are valid"
            
        except Exception as e:
            return False, f"Certificate error: {e}"

    def render_sidebar(self):
        """Render sidebar with merchant info and settings"""
        with st.sidebar:
            st.title("⚙️ Merchant Setup")
            
            # Certificate upload section
            certs_ready = self.render_certificate_upload()
            
            if certs_ready:
                st.subheader("Account Information")
                st.info(f"**Merchant ID:** {st.session_state.merchant_id}")
                st.info(f"**Terminal ID:** {st.session_state.terminal_id}")
                
                st.subheader("Certificate Status")
                cert_valid, cert_message = self.check_certificates()
                if cert_valid:
                    st.success("✅ " + cert_message)
                else:
                    st.error("❌ " + cert_message)
                
                st.subheader("Server Configuration")
                server_choice = st.selectbox(
                    "Select Server",
                    ["Primary", "Secondary"],
                    help="Choose which payment server to use"
                )
                
                st.subheader("Quick Actions")
                if st.button("🔄 Test Connection"):
                    self.test_connection()
                    
                if st.button("📋 Transaction History"):
                    self.show_transaction_history()
                    
                if st.button("🆘 Process Demo"):
                    self.process_demo_transaction()
            else:
                st.warning("⚠️ Please upload certificates to continue")

    def render_demo_mode(self):
        """Render demo mode when certificates aren't available"""
        st.markdown('<div class="demo-banner">🎮 DEMO MODE - Certificate Required for Live Transactions</div>', unsafe_allow_html=True)
        
        st.info("""
        **To enable live transactions:**
        1. Upload your certificate files in the sidebar
        2. Ensure your merchant ID and terminal ID are correct
        3. Test the connection
        
        **Demo features available:**
        ✅ Form validation
        ✅ Receipt generation  
        ✅ Transaction simulation
        ✅ History tracking
        """)
        
        # Demo transaction button
        if st.button("🎮 Process Demo Transaction", type="secondary", use_container_width=True):
            self.process_demo_transaction()

    def process_demo_transaction(self):
        """Process a demo transaction for testing"""
        st.info("🔄 Processing demo transaction...")
        
        # Generate demo transition IDs
        demo_stan = str(st.session_state.stan_counter).zfill(6)
        demo_rrn = demo_stan + "FSL"
        st.session_state.stan_counter += 1
        
        # Simulate processing delay
        with st.spinner("Processing payment..."):
            time.sleep(2)
        
        # Demo result - clean user-friendly messages
        st.success("✅ Demo Payment Approved!")
        
        # Create demo receipt data
        demo_data = {
            'card_input': '4111111111111111',
            'expiry_input': '1225',
            'amount': 25.00,
            'approval_input': '1234',
            'merchant_name': 'Demo Store'
        }
        
        demo_result = {
            'response_message': 'APPROVED',
            'approval_code': 'DEMO123',
            'auth_code': '123456',
            'response_code': '00',
            'systems_trace_number': demo_stan,
            'retrieval_reference_number': demo_rrn,
            'protocol': self.PROTOCOL_CONFIG['name'],
            'transaction_type': 'Force Sale'
        }
        
        # Add to transaction history
        transaction_record = {
            'timestamp': datetime.now(),
            'amount': demo_data['amount'],
            'card': self.format_card_display(demo_data['card_input']),
            'status': 'APPROVED',
            'approval_code': 'DEMO123',
            'response_code': '00',
            'stan': demo_stan,
            'rrn': demo_rrn,
            'demo': True
        }
        st.session_state.transaction_history.append(transaction_record)
        
        # Show receipt
        self.show_receipt(demo_data, demo_result)

    def render_main_header(self):
        """Render main header with protocol info"""
        st.markdown('<div class="main-header">💳 Professional Payment Terminal</div>', 
                   unsafe_allow_html=True)
        self.render_protocol_info()
        st.markdown("---")

    def validate_card_number(self, card_input: str) -> Tuple[bool, str]:
        """Validate card number"""
        clean_number = re.sub(r'\D', '', card_input)
        
        if len(clean_number) != 16:
            return False, f"Card number must be EXACTLY 16 digits (you entered {len(clean_number)})"
        
        if not clean_number.isdigit():
            return False, "Card number must contain only digits"
        
        return True, clean_number

    def validate_expiry_date(self, expiry_input: str) -> Tuple[bool, str]:
        """Validate expiry date"""
        clean_expiry = re.sub(r'\D', '', expiry_input)
        
        if len(clean_expiry) != 4:
            return False, f"Expiry must be 4 digits (MMYY) - you entered {len(clean_expiry)}"
        
        month = int(clean_expiry[:2])
        if month < 1 or month > 12:
            return False, "Month must be between 01 and 12"
        
        # Check if card is expired
        current_year = datetime.now().year % 100
        current_month = datetime.now().month
        expiry_month = int(clean_expiry[:2])
        expiry_year = int(clean_expiry[2:])
        
        if expiry_year < current_year or (expiry_year == current_year and expiry_month < current_month):
            return False, "Card has expired"
        
        return True, clean_expiry

    def render_payment_form(self):
        """Render payment form"""
        st.header("📝 Payment Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Card Number
            card_input = st.text_input(
                "💳 Card Number (16 digits)",
                placeholder="4111 1111 1111 1111",
                help="Enter the 16-digit card number",
                max_chars=19
            )
            
            # Expiry Date
            expiry_input = st.text_input(
                "📅 Expiry Date (MMYY)",
                placeholder="1225",
                help="Enter expiry date as MMYY (e.g., 1225 for December 2025)",
                max_chars=4
            )
            
        with col2:
            # Amount
            amount = st.number_input(
                "💰 Amount ($)",
                min_value=0.01,
                value=25.00,
                step=0.01,
                format="%.2f"
            )
            
            # Approval Code
            approval_input = st.text_input(
                "✅ Approval Code (6 digits)",
                placeholder="123456",
                help="Force Sale requires a 6-digit approval code",
                max_chars=6
            )
            
            # Merchant Name
            merchant_name = st.text_input(
                "🏪 Merchant Name",
                value="Your Store Name",
                help="Business name for receipt",
                max_chars=40
            )
        
        return {
            'card_input': card_input,
            'expiry_input': expiry_input,
            'amount': amount,
            'approval_input': approval_input,
            'merchant_name': merchant_name
        }

    def validate_form_inputs(self, form_data):
        """Validate all form inputs"""
        errors = []
        
        # Validate card
        if not form_data['card_input']:
            errors.append("Card number is required")
        else:
            valid, message = self.validate_card_number(form_data['card_input'])
            if not valid:
                errors.append(f"Card: {message}")
                
        # Validate expiry
        if not form_data['expiry_input']:
            errors.append("Expiry date is required")
        else:
            valid, message = self.validate_expiry_date(form_data['expiry_input'])
            if not valid:
                errors.append(f"Expiry: {message}")
            
        # Validate approval code
        if not form_data['approval_input']:
            errors.append("Approval code is required")
        elif len(form_data['approval_input']) != 6 or not form_data['approval_input'].isdigit():
            errors.append("Approval code must be 6 digits")
            
        # Validate amount
        if form_data['amount'] <= 0:
            errors.append("Amount must be greater than 0")
            
        # Validate merchant name
        if not form_data['merchant_name'] or len(form_data['merchant_name'].strip()) < 2:
            errors.append("Valid merchant name is required")
            
        return errors

    def format_card_display(self, pan: str) -> str:
        """Format card for display"""
        clean_pan = re.sub(r'\D', '', pan)
        if len(clean_pan) == 16:
            return f"{clean_pan[:4]} {clean_pan[4:8]} {clean_pan[8:12]} {clean_pan[12:16]}"
        return clean_pan

    def format_expiry_display(self, expiry: str) -> str:
        """Format expiry for display"""
        clean_expiry = re.sub(r'\D', '', expiry)
        if len(clean_expiry) == 4:
            return f"{clean_expiry[:2]}/{clean_expiry[2:4]}"
        return clean_expiry

    def create_ssl_context(self):
        """Create SSL context"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        try:
            context.load_cert_chain(certfile=self.CLIENT_CERT, keyfile=self.CLIENT_KEY)
            return context, True
        except Exception as e:
            return f"Certificate error: {e}", False

    def connect_to_server(self, server_type: str = 'primary'):
        """Connect to payment server"""
        try:
            server = self.SERVERS[server_type]
            
            raw_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            raw_socket.settimeout(10)
            
            ssl_context, success = self.create_ssl_context()
            if not success:
                return ssl_context, False
                
            self.connection = ssl_context.wrap_socket(
                raw_socket,
                server_hostname=server['host']
            )
            
            self.connection.settimeout(30)
            self.connection.connect((server['host'], server['port']))
            
            return "Connected successfully", True
            
        except Exception as e:
            return f"Connection failed: {e}", False

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
            43: merchant_name.ljust(40)[:40],  # Increased length for better merchant names
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

    def extract_field(self, response_str: str, field_num: int, max_length: int) -> str:
        """Extract specific field from ISO response"""
        try:
            # Simple field extraction
            field_str = str(field_num)
            idx = response_str.find(field_str)
            if idx != -1:
                # Move past the field number
                value_start = idx + len(field_str)
                return response_str[value_start:value_start + max_length]
        except:
            pass
        return ""

    def parse_visa_response(self, response: bytes) -> Dict[str, Any]:
        """Parse Visa Base I response with clean output"""
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
                "transaction_type": "Force Sale"
            }
            
            # Visa Base I response codes with clean messages
            visa_codes = {
                '00': 'APPROVED',
                '01': 'REFER TO ISSUER', 
                '05': 'DECLINED',
                '12': 'INVALID TRANSACTION',
                '13': 'INVALID AMOUNT',
                '14': 'INVALID CARD',
                '51': 'INSUFFICIENT FUNDS',
                '54': 'EXPIRED CARD',
                '55': 'INCORRECT PIN',
                '91': 'ISSUER UNAVAILABLE',
                '96': 'SYSTEM MALFUNCTION'
            }
            
            # Extract response code (Field 39)
            response_code = self.extract_field(response_str, 39, 2)
            if response_code:
                result["response_code"] = response_code
                result["response_message"] = visa_codes.get(response_code, f"RESPONSE CODE: {response_code}")
            
            # Extract auth code (Field 38)
            auth_code = self.extract_field(response_str, 38, 6)
            if auth_code:
                result["auth_code"] = auth_code
                result["approval_code"] = auth_code  # Use full 6-digit code for display
        
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

    def send_transaction(self, message: bytes):
        """Send transaction to payment server"""
        if not self.connection:
            return {"error": "Not connected"}
        
        try:
            self.connection.send(message)
            self.connection.settimeout(30)
            response = self.connection.recv(4096)
            
            if response:
                return self.parse_visa_response(response)
            else:
                return {"error": "No response from server"}
                
        except socket.timeout:
            return {"error": "Connection timeout - no response from server"}
        except Exception as e:
            return {"error": f"Send failed: {e}"}

    def process_payment(self, form_data):
        """Process payment transaction"""
        # Validate inputs
        errors = self.validate_form_inputs(form_data)
        if errors:
            for error in errors:
                st.error(f"❌ {error}")
            return
        
        # Check certificates
        cert_valid, cert_message = self.check_certificates()
        if not cert_valid:
            st.error(f"❌ Certificate issue: {cert_message}")
            st.info("Please upload valid certificates in the sidebar")
            return
        
        # Clean inputs
        card_valid, clean_card = self.validate_card_number(form_data['card_input'])
        expiry_valid, clean_expiry = self.validate_expiry_date(form_data['expiry_input'])
        
        if not card_valid or not expiry_valid:
            st.error("❌ Invalid card data")
            return
        
        # Build message
        with st.spinner("🔄 Building transaction message..."):
            message = self.build_force_sale_message(
                pan=clean_card,
                amount=form_data['amount'],
                expiry=clean_expiry,
                approval_code=form_data['approval_input'],
                merchant_name=form_data['merchant_name']
            )
        
        # Connect and send
        with st.spinner("🔗 Connecting to payment server..."):
            connection_result, success = self.connect_to_server()
            if not success:
                st.error(f"❌ Connection failed: {connection_result}")
                return
        
        # Send transaction
        with st.spinner("📤 Processing payment..."):
            result = self.send_transaction(message)
            self.disconnect()
        
        # Handle result
        self.handle_transaction_result(result, form_data)

    def handle_transaction_result(self, result, form_data):
        """Handle transaction result with clean output"""
        if 'error' in result:
            st.error(f"❌ Transaction failed: {result['error']}")
        else:
            # Clean success message
            if result.get('response_code') == '00':
                st.success("✅ Payment Approved Successfully!")
            else:
                st.warning(f"⚠️ {result.get('response_message', 'Transaction processed')}")
            
            # Get transition IDs from result or generate them
            stan = result.get('systems_trace_number', 
                             st.session_state.last_transaction.get('stan', 'N/A') if st.session_state.last_transaction else 'N/A')
            rrn = result.get('retrieval_reference_number', 
                            st.session_state.last_transaction.get('rrn', 'N/A') if st.session_state.last_transaction else 'N/A')
            
            # Add to transaction history
            transaction_record = {
                'timestamp': datetime.now(),
                'amount': form_data['amount'],
                'card': self.format_card_display(form_data['card_input']),
                'status': result.get('response_message', 'PROCESSED'),
                'approval_code': result.get('approval_code', result.get('auth_code', 'N/A')),
                'response_code': result.get('response_code', 'N/A'),
                'stan': stan,
                'rrn': rrn,
                'demo': False
            }
            st.session_state.transaction_history.append(transaction_record)
            
            # Show receipt
            self.show_receipt(form_data, result)

    def show_receipt(self, form_data, result):
        """Show payment receipt with clean, professional output"""
        st.markdown("---")
        st.header("🧾 Payment Receipt")
        
        # Get transition IDs - handle both real and demo transactions
        stan = result.get('systems_trace_number', 
                         st.session_state.last_transaction.get('stan', 'N/A') if st.session_state.last_transaction else 'N/A')
        rrn = result.get('retrieval_reference_number', 
                        st.session_state.last_transaction.get('rrn', 'N/A') if st.session_state.last_transaction else 'N/A')
        protocol = result.get('protocol', self.PROTOCOL_CONFIG['name'])
        
        # Clean status message
        status_message = result.get('response_message', 'PROCESSED')
        if 'APPROVED' in status_message.upper() or (result.get('response_code') == '00'):
            status_display = "✅ APPROVED"
            box_class = "success-box"
        elif 'DECLINED' in status_message.upper():
            status_display = "❌ DECLINED"
            box_class = "error-box"
        else:
            status_display = f"⚠️ {status_message}"
            box_class = "warning-box"
        
        # Display transition IDs in a clean format
        st.markdown(f"""
        <div class="transition-info">
            <strong>Transaction Details:</strong><br>
            • <strong>Reference Number:</strong> {rrn}<br>
            • <strong>Trace Number:</strong> {stan}<br>
            • <strong>Processing Network:</strong> {protocol}
        </div>
        """, unsafe_allow_html=True)
        
        receipt_html = f"""
        <div class="receipt-box {box_class}">
            <h3 style="text-align: center; margin-bottom: 15px;">💳 PAYMENT RECEIPT</h3>
            <p style="text-align: center; margin-bottom: 20px; font-weight: bold;">{form_data['merchant_name']}</p>
            
            <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;"><strong>Transaction Type:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;">FORCE SALE</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;"><strong>Card Number:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;">{self.format_card_display(form_data['card_input'])}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;"><strong>Amount:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;"><strong>${form_data['amount']:.2f}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;"><strong>Date/Time:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;"><strong>Status:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;"><strong>{status_display}</strong></td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;"><strong>Approval Code:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;">{result.get('approval_code', result.get('auth_code', 'N/A'))}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;"><strong>Terminal ID:</strong></td>
                <td style="padding: 10px; border-bottom: 1px solid #ccc;">{st.session_state.terminal_id}</td>
            </tr>
            </table>
            
            <div style="text-align: center; margin-top: 25px; padding: 15px; background-color: #e8f5e8; border-radius: 5px;">
                <strong>Transaction Completed Successfully</strong><br>
                <small>Processed via {protocol}</small>
            </div>
            
            <p style="text-align: center; margin-top: 20px; font-weight: bold;">Thank you for your business! 💝</p>
        </div>
        """
        
        st.markdown(receipt_html, unsafe_allow_html=True)
        
        # Download button
        receipt_text = self.generate_receipt_text(form_data, result, stan, rrn, protocol, status_display)
        st.download_button(
            label="📄 Download Receipt",
            data=receipt_text,
            file_name=f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )

    def generate_receipt_text(self, form_data, result, stan, rrn, protocol, status_display):
        """Generate clean receipt text for download"""
        return f"""
PAYMENT RECEIPT
{'=' * 50}
Merchant: {form_data['merchant_name']}
Terminal: {st.session_state.terminal_id}
Transaction: FORCE SALE
{'=' * 50}
Card: {self.format_card_display(form_data['card_input'])}
Amount: ${form_data['amount']:.2f}
Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Status: {status_display.replace('✅ ', '').replace('❌ ', '').replace('⚠️ ', '')}
Approval: {result.get('approval_code', result.get('auth_code', 'N/A'))}
{'=' * 50}
REFERENCE: {rrn}
TRACE: {stan}
NETWORK: {protocol}
{'=' * 50}
Thank you for your business!
"""

    def disconnect(self):
        """Close connection"""
        if self.connection:
            try:
                self.connection.close()
            except:
                pass
            self.connection = None

    def test_connection(self):
        """Test server connection"""
        cert_valid, cert_message = self.check_certificates()
        if not cert_valid:
            st.error(f"❌ {cert_message}")
            return
            
        with st.spinner("Testing connection to payment server..."):
            result, success = self.connect_to_server()
            if success:
                st.success("✅ Connection successful!")
                self.disconnect()
            else:
                st.error(f"❌ {result}")

    def show_transaction_history(self):
        """Show transaction history"""
        st.header("📋 Transaction History")
        
        if not st.session_state.transaction_history:
            st.info("No transactions yet")
            return
        
        # Show last 10 transactions
        recent_transactions = list(reversed(st.session_state.transaction_history[-10:]))
        
        for i, transaction in enumerate(recent_transactions, 1):
            demo_indicator = " 🎮" if transaction.get('demo', False) else ""
            status_icon = "✅" if transaction['status'] == 'APPROVED' else "⚠️"
            
            with st.expander(f"{status_icon} Transaction {i} - ${transaction['amount']:.2f} - {transaction['timestamp'].strftime('%H:%M:%S')}{demo_indicator}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Card:** {transaction['card']}")
                    st.write(f"**Amount:** ${transaction['amount']:.2f}")
                    st.write(f"**Status:** {transaction['status']}")
                    
                with col2:
                    st.write(f"**Approval Code:** {transaction['approval_code']}")
                    st.write(f"**Reference:** {transaction.get('rrn', 'N/A')}")
                    st.write(f"**Time:** {transaction['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                
                if st.button(f"Delete Transaction {i}", key=f"delete_{i}"):
                    st.session_state.transaction_history.remove(transaction)
                    st.rerun()

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
