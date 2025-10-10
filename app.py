#!/usr/bin/env python3
"""
Professional Payment Terminal Web Application
For ONLINE Transactions with 4-Digit Approval Codes
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
import hashlib

# === PASSWORD PROTECTION === 
APP_PASSWORD_HASH = "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"  # "password"

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

class StreamlitOnlineSaleClient:
    """
    Online Sale Client with 4-Digit Approval Codes
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
        # Force 4-digit for online transactions
        st.session_state.approval_code_length = "4-digit"
            
        self.SERVERS = {
            'primary': {'host': '102.163.40.20', 'port': 8090},
            'secondary': {'host': '10.252.251.5', 'port': 8080}
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
            page_title="Professional Payment Terminal",
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
        .debug-box {
            border: 1px solid #6c757d;
            border-radius: 5px;
            padding: 10px;
            margin: 5px 0;
            background-color: #f8f9fa;
            font-family: monospace;
            font-size: 0.8em;
        }
        .config-box {
            border: 1px solid #17a2b8;
            border-radius: 5px;
            padding: 15px;
            margin: 10px 0;
            background-color: #d1ecf1;
        }
        </style>
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
                
                st.subheader("Transaction Configuration")
                st.info("🟢 **Online Transaction Mode**")
                st.info("🔑 **4-Digit Approval Codes**")
                
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
                    
                # Debug toggle
                st.session_state.debug_mode = st.checkbox("🔧 Debug Mode", value=False)
            else:
                st.warning("⚠️ Please upload certificates to continue")

    def render_demo_mode(self):
        """Render demo mode when certificates aren't available"""
        st.warning("🔒 DEMO MODE - Certificates not configured")
        
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
        if st.button("🎮 Process Demo Transaction", type="secondary"):
            self.process_demo_transaction()

    def process_demo_transaction(self):
        """Process a demo transaction for testing"""
        st.info("🔄 Processing demo transaction...")
        
        # Simulate processing delay
        with st.spinner("Processing payment..."):
            time.sleep(2)
        
        # Demo result
        st.success("✅ Demo Payment Approved!")
        
        # Create demo receipt
        demo_data = {
            'card_input': '4111111111111111',
            'expiry_input': '1225',
            'amount': 25.00,
            'approval_input': '1234',
            'merchant_name': 'Demo Store'
        }
        
        demo_result = {
            'response_message': 'APPROVED - Demo Transaction',
            'approval_code': '1234',
            'full_auth_code': '123400',
            'response_code': '00'
        }
        
        # Add to transaction history
        transaction_record = {
            'timestamp': datetime.now(),
            'amount': demo_data['amount'],
            'card': self.format_card_display(demo_data['card_input']),
            'status': demo_result['response_message'],
            'approval_code': demo_result['approval_code'],
            'response_code': demo_result['response_code'],
            'demo': True
        }
        st.session_state.transaction_history.append(transaction_record)
        
        # Show receipt
        self.show_receipt(demo_data, demo_result)

    def render_main_header(self):
        """Render main header"""
        st.markdown('<div class="main-header">💳 Online Payment Terminal</div>', 
                   unsafe_allow_html=True)
        
        # Show current configuration
        st.markdown(f"""
        <div class="config-box">
            <strong>Transaction Mode: 🟢 ONLINE</strong><br>
            • <strong>4-Digit Approval Codes</strong> (Standard Online Auth)<br>
            • Merchant ID: {st.session_state.merchant_id}<br>
            • Terminal ID: {st.session_state.terminal_id}
        </div>
        """, unsafe_allow_html=True)
        
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
        
        return True, clean_expiry

    def validate_approval_code(self, approval_input: str) -> Tuple[bool, str]:
        """Validate 4-digit approval code"""
        clean_code = re.sub(r'\D', '', approval_input)
        
        if len(clean_code) != 4:
            return False, f"Approval code must be exactly 4 digits (you entered {len(clean_code)})"
        
        if not clean_code.isdigit():
            return False, "Approval code must contain only digits"
        
        return True, clean_code

    def render_payment_form(self):
        """Render payment form"""
        st.header("📝 Payment Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Card Number
            card_input = st.text_input(
                "💳 Card Number (16 digits)",
                placeholder="4111 1111 1111 1111",
                help="Enter the 16-digit card number"
            )
            
            # Expiry Date
            expiry_input = st.text_input(
                "📅 Expiry Date (MMYY)",
                placeholder="1225",
                help="Enter expiry date as MMYY (e.g., 1225 for December 2025)"
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
            
            # Approval Code - 4-digit only for online transactions
            approval_input = st.text_input(
                "✅ Approval Code (4 digits)",
                placeholder="1234",
                help="Enter 4-digit online approval code from issuer"
            )
            
            # Merchant Name
            merchant_name = st.text_input(
                "🏪 Merchant Name",
                value="Your Store",
                help="Business name for receipt"
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
        if form_data['card_input']:
            valid, message = self.validate_card_number(form_data['card_input'])
            if not valid:
                errors.append(f"Card: {message}")
        else:
            errors.append("Card number is required")
            
        # Validate expiry
        if form_data['expiry_input']:
            valid, message = self.validate_expiry_date(form_data['expiry_input'])
            if not valid:
                errors.append(f"Expiry: {message}")
        else:
            errors.append("Expiry date is required")
            
        # Validate approval code
        if not form_data['approval_input']:
            errors.append("Approval code is required")
        else:
            valid, message = self.validate_approval_code(form_data['approval_input'])
            if not valid:
                errors.append(f"Approval: {message}")
            
        return errors

    def format_card_display(self, pan: str) -> str:
        """Format card for display"""
        clean_pan = re.sub(r'\D', '', pan)
        return f"{clean_pan[:4]} {clean_pan[4:8]} {clean_pan[8:12]} {clean_pan[12:16]}"

    def format_expiry_display(self, expiry: str) -> str:
        """Format expiry for display"""
        clean_expiry = re.sub(r'\D', '', expiry)
        return f"{clean_expiry[:2]}/{clean_expiry[2:4]}"

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
            
            self.connection.settimeout(10)
            self.connection.connect((server['host'], server['port']))
            
            return "Connected successfully", True
            
        except Exception as e:
            return f"Connection failed: {e}", False

    def build_online_sale_message(self, pan: str, amount: float, expiry: str, approval_code: str, merchant_name: str):
        """Build Online Sale ISO message with 4-digit approval codes"""
        stan = str(st.session_state.stan_counter).zfill(6)
        st.session_state.stan_counter += 1
        
        now = datetime.now()
        transmission_time = now.strftime("%m%d%H%M%S")
        local_time = now.strftime("%H%M%S")
        local_date = now.strftime("%m%d")
        
        # For online transactions: pad 4-digit code to 6 digits for ISO 8583
        auth_code = approval_code.ljust(6, '0')
        
        # ISO 8583 data elements - ONLINE TRANSACTION
        data_elements = {
            2: pan,  # LLVAR field
            3: "000000",  # CORRECTED: Processing Code for Purchase (not Force Sale)
            4: str(int(amount * 100)).zfill(12),  # Amount in cents
            7: transmission_time,  # Transmission date & time
            11: stan,  # Systems trace audit number
            12: local_time,  # Local time
            13: local_date,  # Local date
            14: expiry,  # Expiration date
            18: "5999",  # Merchant type
            22: "012",  # POS entry mode - Manual key entry
            24: "00",  # CORRECTED: Function code - Purchase (not Force Sale)
            25: "00",  # CORRECTED: POS condition code - Normal presentment
            32: "00000000001",  # Acquiring institution ID code
            35: pan + "=" + expiry + "100",  # Track 2 data
            37: stan + "ONL",  # Retrieval reference number
            38: auth_code,  # Approval code (4-digit padded to 6)
            41: st.session_state.terminal_id,  # Terminal ID
            42: st.session_state.merchant_id,  # Merchant ID
            43: merchant_name.ljust(40)[:40],  # Merchant name (40 chars)
            49: "840",  # Currency code (USD)
            60: "00108001",  # Additional data
        }

        # Build bitmap
        bitmap = bytearray(8)
        for field_num in data_elements.keys():
            if 1 <= field_num <= 64:
                byte_index = (field_num - 1) // 8
                bit_index = 7 - ((field_num - 1) % 8)
                bitmap[byte_index] |= (1 << bit_index)

        mti = "0200"  # Financial transaction request
        bitmap_hex = bitmap.hex().upper()

        # Build data string with proper length prefixes
        data_str = ""
        for field_num in sorted(data_elements.keys()):
            value = data_elements[field_num]
            
            # Handle variable length fields
            if field_num in [2, 35, 32, 60]:  # LLVAR fields (2-digit length)
                data_str += f"{len(value):02d}{value}"
            elif field_num in [43]:  # Fixed length field
                data_str += value.ljust(40)[:40]  # Ensure exactly 40 chars
            else:  # Fixed length fields
                data_str += value

        iso_message = mti + bitmap_hex + data_str
        message_length = len(iso_message)
        length_prefix = struct.pack('>H', message_length)
        
        # Debug output
        if st.session_state.get('debug_mode', False):
            st.sidebar.markdown("### 🔧 ISO 8583 Debug Info")
            st.sidebar.markdown(f"""
            <div class="debug-box">
            <strong>Message Details:</strong><br>
            Transaction Type: <strong>ONLINE SALE</strong><br>
            MTI: {mti}<br>
            DE 3 (Processing): {data_elements[3]}<br>
            DE 24 (Function): {data_elements[24]}<br>
            DE 38 (Auth): {data_elements[38]}<br>
            Input Code: {approval_code}<br>
            Sent Code: {auth_code}<br>
            STAN: {stan}
            </div>
            """, unsafe_allow_html=True)
    
        return length_prefix + iso_message.encode('ascii')

    def parse_visa_response(self, response: bytes) -> Dict[str, Any]:
        """Parse Visa response"""
        try:
            if len(response) < 4:
                return {"error": "Response too short"}
                
            # Parse message length
            if len(response) > 2:
                potential_length = struct.unpack('>H', response[:2])[0]
                if potential_length == len(response) - 2:
                    response = response[2:]
            
            response_str = response.decode('ascii', errors='ignore')
            
            result = {
                "mti": response_str[0:4] if len(response_str) >= 4 else "",
                "raw_response": response_str,
                "length": len(response)
            }
            
            # Visa response codes
            visa_codes = {
                '00': 'APPROVED - Transaction Completed',
                '01': 'REFER TO ISSUER', 
                '05': 'DECLINED - Do Not Honor',
                '12': 'ERROR - Invalid Transaction',
                '13': 'ERROR - Invalid Amount',
                '14': 'ERROR - Invalid Card',
                '51': 'DECLINED - Insufficient Funds',
                '54': 'ERROR - Expired Card',
                '55': 'ERROR - Invalid PIN',
                '57': 'TRANSACTION NOT PERMITTED',
                '58': 'TRANSACTION NOT PERMITTED',
                '61': 'EXCEEDS WITHDRAWAL LIMIT',
                '62': 'RESTRICTED CARD',
                '65': 'EXCEEDS WITHDRAWAL FREQUENCY',
                '75': 'EXCEEDS PIN TRIES',
                '76': 'INVALID ROUTING',
                '91': 'UNAVAILABLE - Issuer Unavailable',
                '96': 'ERROR - System Malfunction'
            }
            
            # Extract response code (DE 39)
            if "39" in response_str:
                idx = response_str.find("39")
                if idx + 2 < len(response_str):
                    resp_code = response_str[idx+2:idx+4]
                    result["response_code"] = resp_code
                    result["response_message"] = visa_codes.get(resp_code, f"UNKNOWN CODE: {resp_code}")
            
            # Extract auth code (DE 38)
            if "38" in response_str:
                idx = response_str.find("38")
                if idx + 2 < len(response_str):
                    # DE 38 is 6 characters fixed length
                    auth_code = response_str[idx+2:idx+8]
                    result["auth_code"] = auth_code
                    
                    # For online transactions, show only first 4 digits
                    result["approval_code"] = auth_code[:4]  # First 4 digits only
                    result["full_auth_code"] = auth_code
            
            # If we didn't find structured fields, try to extract basic info
            if "response_code" not in result and len(response_str) >= 4:
                if len(response_str) > 20:
                    result["response_code"] = response_str[20:22] if len(response_str) > 22 else "XX"
                    result["response_message"] = visa_codes.get(result["response_code"], "UNKNOWN")
            
            # Debug output
            if st.session_state.get('debug_mode', False):
                st.sidebar.markdown("### 🔧 Response Debug")
                st.sidebar.markdown(f"""
                <div class="debug-box">
                <strong>Parsed Response:</strong><br>
                Response Code: {result.get('response_code', 'N/A')}<br>
                Approval Code: {result.get('approval_code', 'N/A')}<br>
                Full Auth Code: {result.get('full_auth_code', 'N/A')}<br>
                Message: {result.get('response_message', 'N/A')}
                </div>
                """, unsafe_allow_html=True)
            
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
                return {"error": "No response"}
                
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
        approval_valid, clean_approval = self.validate_approval_code(form_data['approval_input'])
        
        if not card_valid or not expiry_valid or not approval_valid:
            st.error("❌ Invalid input data")
            return
        
        # Build message
        with st.spinner("🔄 Building Online Sale message..."):
            message = self.build_online_sale_message(
                pan=clean_card,
                amount=form_data['amount'],
                expiry=clean_expiry,
                approval_code=clean_approval,
                merchant_name=form_data['merchant_name']
            )
        
        # Connect and send
        with st.spinner("🔗 Connecting to payment server..."):
            connection_result, success = self.connect_to_server()
            if not success:
                st.error(f"❌ Connection failed: {connection_result}")
                if st.session_state.get('debug_mode', False):
                    st.info("💡 Check server IP/port and certificate configuration")
                return
        
        # Send transaction
        with st.spinner("📤 Processing online payment..."):
            result = self.send_transaction(message)
            self.disconnect()
        
        # Handle result
        self.handle_transaction_result(result, form_data)

    def handle_transaction_result(self, result, form_data):
        """Handle transaction result"""
        if 'error' in result:
            st.error(f"❌ Transaction failed: {result['error']}")
            
            # Add failed transaction to history
            transaction_record = {
                'timestamp': datetime.now(),
                'amount': form_data['amount'],
                'card': self.format_card_display(form_data['card_input']),
                'status': f"FAILED: {result['error']}",
                'approval_code': 'N/A',
                'response_code': 'ER',
                'demo': False
            }
            st.session_state.transaction_history.append(transaction_record)
        else:
            if result.get('response_code') == '00':
                st.success("✅ Online Payment Approved!")
            else:
                st.warning(f"⚠️ {result.get('response_message', 'Transaction completed with warning')}")
            
            # Add to transaction history
            transaction_record = {
                'timestamp': datetime.now(),
                'amount': form_data['amount'],
                'card': self.format_card_display(form_data['card_input']),
                'status': result.get('response_message', 'Unknown'),
                'approval_code': result.get('approval_code', 'N/A'),
                'response_code': result.get('response_code', 'N/A'),
                'demo': False
            }
            st.session_state.transaction_history.append(transaction_record)
            
            # Show receipt
            self.show_receipt(form_data, result)

    def show_receipt(self, form_data, result):
        """Show payment receipt"""
        st.markdown("---")
        st.header("🧾 Online Payment Receipt")
        
        status_color = "success-box" if result.get('response_code') == '00' else "receipt-box"
        
        receipt_html = f"""
        <div class="receipt-box {status_color}">
            <h3 style="text-align: center; margin-bottom: 20px;">ONLINE PAYMENT RECEIPT</h3>
            
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
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Transaction Type:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">🟢 Online Sale</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Card Number:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{self.format_card_display(form_data['card_input'])}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Expiry:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{self.format_expiry_display(form_data['expiry_input'])}</td>
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
        """Generate receipt text for download"""
        return f"""
ONLINE PAYMENT RECEIPT
=====================
Merchant: {form_data['merchant_name']}
Terminal ID: {st.session_state.terminal_id}
Merchant ID: {st.session_state.merchant_id}
Transaction Type: Online Sale
-----------------------------
Card: {self.format_card_display(form_data['card_input'])}
Expiry: {self.format_expiry_display(form_data['expiry_input'])}
Amount: ${form_data['amount']:.2f}
Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Status: {result.get('response_message', 'Unknown')}
Approval Code: {result.get('approval_code', 'N/A')}
Response Code: {result.get('response_code', 'N/A')}
=====================
THANK YOU FOR YOUR BUSINESS
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
            
        with st.spinner("Testing connection..."):
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
            
        for i, transaction in enumerate(reversed(st.session_state.transaction_history[-10:]), 1):
            demo_indicator = " (Demo)" if transaction.get('demo', False) else ""
            status_color = "✅" if transaction['status'].startswith('APPROVED') else "❌" if transaction['status'].startswith('FAILED') else "⚠️"
            
            with st.expander(f"{status_color} Transaction {i} - ${transaction['amount']:.2f} - {transaction['timestamp'].strftime('%H:%M:%S')}{demo_indicator}"):
                st.write(f"**Card:** {transaction['card']}")
                st.write(f"**Amount:** ${transaction['amount']:.2f}")
                st.write(f"**Status:** {transaction['status']}")
                st.write(f"**Approval Code:** {transaction['approval_code']}")
                st.write(f"**Response Code:** {transaction['response_code']}")
                st.write(f"**Time:** {transaction['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
                
        # Clear history button
        if st.button("🗑️ Clear History"):
            st.session_state.transaction_history = []
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
                if st.button("🚀 Process Online Payment", type="primary", use_container_width=True):
                    self.process_payment(form_data)

def main():
    """Main function"""
    client = StreamlitOnlineSaleClient()
    client.run()

if __name__ == "__main__":
    main()
