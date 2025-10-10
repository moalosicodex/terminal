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
                    'protocol': 'SSL'
                },
                'secondary': {
                    'host': '10.252.251.5', 
                    'port': 8080,
                    'protocol': 'SSL'
                }
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
        .iso-message {
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 5px;
            padding: 10px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        </style>
        """, unsafe_allow_html=True)

    def run(self):
        """Main application flow"""
        self.setup_page()
        
        st.markdown('<h1 class="main-header">💳 ISO-8583 Base I Terminal</h1>', unsafe_allow_html=True)
        st.markdown('<p class="sub-header">Online Authorization • Protocol 101.1 • 4-Digit Approval Codes</p>', unsafe_allow_html=True)
        
        # Sidebar for configuration
        with st.sidebar:
            st.header("⚙️ Configuration")
            self.show_configuration()
            
            st.header("📊 Transaction History")
            self.show_transaction_history()
            
            st.header("🔐 Certificate Setup")
            self.show_certificate_upload()
        
        # Main content area
        tab1, tab2, tab3, tab4 = st.tabs(["💳 Online Authorization", "🔄 Transaction Reversal", "📡 Connection Test", "🔍 Message Debug"])
        
        with tab1:
            self.show_payment_terminal()
        
        with tab2:
            self.show_reversal_terminal()
        
        with tab3:
            self.show_connection_test()
            
        with tab4:
            self.show_message_debug()

    def show_configuration(self):
        """Show configuration settings"""
        st.session_state.merchant_id = st.text_input("Merchant ID", st.session_state.merchant_id)
        st.session_state.terminal_id = st.text_input("Terminal ID", st.session_state.terminal_id)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Reset STAN Counter"):
                st.session_state.stan_counter = 100001
                st.success("STAN counter reset to 100001")
        
        with col2:
            if st.button("New Batch"):
                st.session_state.batch_number = random.randint(1000, 9999)
                st.success(f"New batch: {st.session_state.batch_number}")
        
        st.info(f"Current STAN: {st.session_state.stan_counter}")
        st.info(f"Current Batch: {st.session_state.batch_number}")

    def show_transaction_history(self):
        """Show recent transactions"""
        if not st.session_state.transaction_history:
            st.write("No transactions yet")
            return
        
        for i, tx in enumerate(st.session_state.transaction_history[-5:]):
            with st.expander(f"Tx {i+1}: {tx.get('pan_mask', 'N/A')} - ${tx.get('amount', 0):.2f}"):
                st.json(tx)

    def show_certificate_upload(self):
        """Handle certificate file uploads"""
        if st.session_state.cert_files_uploaded:
            st.success("✅ Certificates uploaded")
            if st.button("Remove Certificates"):
                st.session_state.cert_files_uploaded = False
                st.rerun()
            return
        
        cert_file = st.file_uploader("Upload Client Certificate", type=['crt', 'pem'])
        key_file = st.file_uploader("Upload Client Key", type=['key', 'pem'])
        
        if cert_file and key_file:
            # Save uploaded files
            with open(self.CLIENT_CERT, "wb") as f:
                f.write(cert_file.getvalue())
            with open(self.CLIENT_KEY, "wb") as f:
                f.write(key_file.getvalue())
            
            st.session_state.cert_files_uploaded = True
            st.success("✅ Certificates uploaded successfully!")
            st.rerun()

    def show_payment_terminal(self):
        """Show payment terminal interface for ISO-8583 Online Authorization"""
        st.header("💳 ISO-8583 Online Authorization")
        st.info("4-Digit Approval Code • No CVV Required • Online Authorization")
        
        with st.form("payment_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                merchant_name = st.text_input("Merchant Name", "Test Merchant")
                card_input = st.text_input("Card Number (PAN)", "4111111111111111", 
                                         help="Enter 16-digit card number")
                expiry_input = st.text_input("Expiry Date (MMYY)", "1225",
                                           help="Month and Year (MMYY)")
                
            with col2:
                amount = st.number_input("Amount ($)", min_value=0.01, value=1.00, step=0.01)
                pin_input = st.text_input("PIN", "1234", type="password", max_chars=4,
                                        help="4-digit PIN for online authorization")
                processing_code = st.selectbox("Processing Code", 
                                             ["000000", "000000", "010000", "020000"],
                                             help="Transaction processing code")
            
            # Process payment
            if st.form_submit_button("🚀 Process Online Authorization", use_container_width=True):
                if self.validate_payment_input(card_input, expiry_input, amount):
                    form_data = {
                        'merchant_name': merchant_name,
                        'card_input': card_input,
                        'expiry_input': expiry_input,
                        'amount': amount,
                        'pin_input': pin_input,
                        'processing_code': processing_code
                    }
                    
                    with st.spinner("Processing ISO-8583 Online Authorization..."):
                        result = self.process_iso8583_authorization(form_data)
                    
                    # Show receipt
                    self.show_receipt(form_data, result)
                    
                    # Store transaction
                    st.session_state.transaction_history.append({
                        'timestamp': datetime.now().isoformat(),
                        'pan_mask': self.format_card_receipt(card_input),
                        'amount': amount,
                        'response_code': result.get('response_code'),
                        'approval_code': result.get('approval_code'),
                        'rrn': result.get('rrn'),
                        'stan': result.get('stan'),
                        'auth_code': result.get('full_auth_code')
                    })
                    
                    # Update STAN counter
                    st.session_state.stan_counter += 1
                    st.session_state.last_transaction = result

    def show_reversal_terminal(self):
        """Show transaction reversal interface"""
        st.header("🔄 Transaction Reversal")
        
        if not st.session_state.last_transaction:
            st.warning("No recent transaction to reverse")
            return
        
        st.info("Last transaction details:")
        st.json(st.session_state.last_transaction)
        
        if st.button("🔄 Reverse Last Transaction", use_container_width=True):
            with st.spinner("Reversing transaction..."):
                result = self.process_iso8583_reversal()
            
            if result.get('success'):
                st.success("✅ Transaction reversed successfully!")
                st.session_state.last_transaction = None
            else:
                st.error("❌ Reversal failed")

    def show_connection_test(self):
        """Show connection testing interface"""
        st.header("📡 Connection Test")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Primary Server")
            if st.button("Test Primary Connection", use_container_width=True):
                with st.spinner("Testing primary connection..."):
                    success, message = self.test_iso8583_connection('primary')
                if success:
                    st.success("✅ Primary connection successful")
                else:
                    st.error(f"❌ Primary connection failed: {message}")
        
        with col2:
            st.subheader("Secondary Server")
            if st.button("Test Secondary Connection", use_container_width=True):
                with st.spinner("Testing secondary connection..."):
                    success, message = self.test_iso8583_connection('secondary')
                if success:
                    st.success("✅ Secondary connection successful")
                else:
                    st.error(f"❌ Secondary connection failed: {message}")

    def show_message_debug(self):
        """Show ISO-8583 message debugging"""
        st.header("🔍 ISO-8583 Message Debug")
        
        if st.session_state.last_transaction:
            st.subheader("Last Authorization Message")
            st.code(st.session_state.last_transaction.get('iso_message', 'No message available'), language='text')
            
            st.subheader("Last Response Message")
            st.code(st.session_state.last_transaction.get('iso_response', 'No response available'), language='text')
        else:
            st.info("No transactions processed yet")

    def validate_payment_input(self, card_input: str, expiry_input: str, amount: float) -> bool:
        """Validate payment form inputs"""
        clean_pan = re.sub(r'\D', '', card_input)
        if len(clean_pan) != 16:
            st.error("❌ Card number must be 16 digits")
            return False
        
        clean_expiry = re.sub(r'\D', '', expiry_input)
        if len(clean_expiry) != 4:
            st.error("❌ Expiry date must be 4 digits (MMYY)")
            return False
        
        if amount <= 0:
            st.error("❌ Amount must be greater than 0")
            return False
        
        return True

    def build_iso8583_authorization_message(self, form_data: Dict) -> str:
        """Build ISO-8583 authorization message (0100)"""
        # MTI: 0100 - Authorization Request
        mti = "0100"
        
        # Bitmap - indicating which fields are present
        bitmap = "7230000008C08001"  # Simplified bitmap for demo
        
        # Field 2: Primary Account Number (PAN)
        pan = re.sub(r'\D', '', form_data['card_input']).zfill(19)
        
        # Field 3: Processing Code
        processing_code = form_data.get('processing_code', '000000')
        
        # Field 4: Amount
        amount = str(int(form_data['amount'] * 100)).zfill(12)
        
        # Field 7: Transmission Date & Time
        transmission_time = datetime.now().strftime("%m%d%H%M%S")
        
        # Field 11: Systems Trace Audit Number (STAN)
        stan = str(st.session_state.stan_counter).zfill(6)
        
        # Field 12: Local Transaction Time
        local_time = datetime.now().strftime("%H%M%S")
        
        # Field 13: Local Transaction Date
        local_date = datetime.now().strftime("%m%d")
        
        # Field 14: Expiration Date
        expiry = re.sub(r'\D', '', form_data['expiry_input'])
        
        # Field 22: POS Entry Mode
        pos_entry_mode = "010"  # Manual entry
        
        # Field 25: POS Condition Code
        pos_condition = "00"  # Normal presentment
        
        # Field 35: Track 2 Data
        track2 = f";{pan}={expiry}100000000000000000000?"
        
        # Field 41: Terminal ID
        terminal_id = st.session_state.terminal_id
        
        # Field 42: Merchant ID
        merchant_id = st.session_state.merchant_id
        
        # Field 52: PIN Data (encrypted)
        pin_data = form_data['pin_input'].zfill(16)
        
        # Build message
        iso_message = f"{mti}{bitmap}{pan}{processing_code}{amount}{transmission_time}{stan}{local_time}{local_date}{expiry}{pos_entry_mode}{pos_condition}{track2}{terminal_id}{merchant_id}{pin_data}"
        
        return iso_message

    def parse_iso8583_response(self, response: str) -> Dict:
        """Parse ISO-8583 response message (0110)"""
        try:
            # Simplified parsing for demo
            mti = response[0:4]
            response_code = response[39:41] if len(response) > 41 else "96"
            
            # Generate 4-digit approval code
            approval_code = str(random.randint(1000, 9999))
            
            return {
                'mti': mti,
                'response_code': response_code,
                'approval_code': approval_code,
                'full_auth_code': f"{approval_code}{response_code}",
                'response_message': self.get_response_message(response_code)
            }
        except Exception as e:
            return {
                'response_code': '96',
                'response_message': f'Parse Error: {str(e)}',
                'approval_code': '0000',
                'full_auth_code': '000096'
            }

    def get_response_message(self, response_code: str) -> str:
        """Get human-readable response message"""
        response_messages = {
            '00': 'APPROVED',
            '01': 'REFER TO ISSUER',
            '05': 'DECLINED',
            '12': 'INVALID TRANSACTION',
            '13': 'INVALID AMOUNT',
            '14': 'INVALID CARD NUMBER',
            '15': 'NO SUCH ISSUER',
            '41': 'LOST CARD',
            '43': 'STOLEN CARD',
            '51': 'INSUFFICIENT FUNDS',
            '54': 'EXPIRED CARD',
            '55': 'INCORRECT PIN',
            '57': 'TRANSACTION NOT PERMITTED',
            '58': 'TRANSACTION NOT PERMITTED',
            '61': 'EXCEEDS WITHDRAWAL LIMIT',
            '62': 'RESTRICTED CARD',
            '63': 'SECURITY VIOLATION',
            '65': 'EXCEEDS WITHDRAWAL FREQUENCY',
            '75': 'EXCEEDS PIN TRIES',
            '76': 'INVALID ROUTING',
            '91': 'ISSUER UNAVAILABLE',
            '94': 'DUPLICATE TRANSACTION',
            '96': 'SYSTEM MALFUNCTION'
        }
        return response_messages.get(response_code, 'UNKNOWN RESPONSE')

    def process_iso8583_authorization(self, form_data: Dict) -> Dict:
        """Process ISO-8583 online authorization"""
        try:
            # Generate transaction details
            stan = str(st.session_state.stan_counter).zfill(6)
            rrn = datetime.now().strftime("%Y%m%d%H%M%S")
            
            # Build ISO-8583 message
            iso_message = self.build_iso8583_authorization_message(form_data)
            
            # Simulate network communication
            time.sleep(2)
            
            # Simulate response (0110 - Authorization Response)
            response_code = "00" if random.random() < 0.9 else "05"
            response_data = self.parse_iso8583_response(f"0110{iso_message[4:39]}{response_code}")
            
            return {
                'success': True,
                'response_code': response_data['response_code'],
                'response_message': response_data['response_message'],
                'approval_code': response_data['approval_code'],
                'full_auth_code': response_data['full_auth_code'],
                'stan': stan,
                'rrn': rrn,
                'receipt_number': st.session_state.receipt_counter,
                'batch_number': st.session_state.batch_number,
                'timestamp': datetime.now().isoformat(),
                'iso_message': iso_message,
                'iso_response': f"0110{iso_message[4:39]}{response_code}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'response_code': '96',
                'response_message': f'SYSTEM MALFUNCTION: {str(e)}',
                'approval_code': '0000',
                'full_auth_code': '000096',
                'stan': str(st.session_state.stan_counter).zfill(6),
                'rrn': datetime.now().strftime("%Y%m%d%H%M%S"),
                'receipt_number': st.session_state.receipt_counter,
                'batch_number': st.session_state.batch_number,
                'timestamp': datetime.now().isoformat()
            }

    def process_iso8583_reversal(self) -> Dict:
        """Process ISO-8583 transaction reversal"""
        try:
            # Build reversal message (0400)
            time.sleep(2)
            
            return {
                'success': True,
                'message': 'Reversal processed successfully',
                'timestamp': datetime.now().isoformat(),
                'response_code': '00'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Reversal failed: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }

    def test_iso8583_connection(self, server: str) -> Tuple[bool, str]:
        """Test ISO-8583 connection to server"""
        try:
            # Simulate connection test with network echo
            time.sleep(1)
            
            # 80% success rate for demo
            if random.random() < 0.8:
                return True, "ISO-8583 Connection Successful"
            else:
                return False, "Network Timeout"
                
        except Exception as e:
            return False, f"Connection Error: {str(e)}"

    def show_receipt(self, form_data, result):
        """Show payment receipt with ISO-8583 specific information"""
        st.markdown("---")
        st.header("🧾 ISO-8583 Authorization Receipt")
        
        # Create a container for the receipt
        receipt_container = st.container()
        
        with receipt_container:
            # Determine receipt style based on status
            if result.get('response_code') == '00':
                st.success("✅ ISO-8583 AUTHORIZATION APPROVED")
                receipt_class = "success-receipt"
            else:
                st.warning("⚠️ ISO-8583 AUTHORIZATION PROCESSED")
                receipt_class = "warning-receipt"
            
            # Create receipt using Streamlit components
            with st.container():
                st.markdown(f"""
                <div class="receipt-container {receipt_class}">
                    <div class="receipt-header">
                        <h2>💳 ISO-8583 AUTHORIZATION RECEIPT</h2>
                        <p>Base I Terminal • Protocol 101.1 • 4-Digit Approval Code</p>
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
                st.subheader("📊 ISO-8583 Transaction Details")
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Receipt Number", str(result.get('receipt_number', 'N/A')), disabled=True)
                    st.text_input("Batch Number", str(result.get('batch_number', 'N/A')), disabled=True)
                    st.text_input("Card Number", self.format_card_receipt(form_data['card_input']), disabled=True)
                    st.text_input("Processing Code", form_data.get('processing_code', '000000'), disabled=True)
                with col2:
                    st.text_input("RRN", result.get('rrn', 'N/A'), disabled=True)
                    st.text_input("STAN", result.get('stan', 'N/A'), disabled=True)
                    st.text_input("Expiry Date", self.format_expiry_display(form_data['expiry_input']), disabled=True)
                    st.text_input("POS Entry Mode", "010 - Manual", disabled=True)
                
                # Amount and Date
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Amount", f"${form_data['amount']:.2f}", disabled=True)
                with col2:
                    st.text_input("Date/Time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), disabled=True)
                
                # Authorization Information
                st.subheader("🔐 ISO-8583 Authorization")
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Status", result.get('response_message', 'Unknown'), disabled=True)
                    st.text_input("4-Digit Approval", result.get('approval_code', 'N/A'), disabled=True)
                with col2:
                    st.text_input("Response Code", result.get('response_code', 'N/A'), disabled=True)
                    st.text_input("Full Auth Code", result.get('full_auth_code', 'N/A'), disabled=True)
                
                # ISO-8583 Specific
                st.subheader("📨 ISO-8583 Message Info")
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Message Type", "0100 - Authorization", disabled=True)
                with col2:
                    st.text_input("Response Type", "0110 - Response", disabled=True)
                
                # Footer
                st.markdown("---")
                st.markdown("### **ISO-8583 ONLINE AUTHORIZATION COMPLETE**")
                st.caption("4-Digit Approval Code • Keep this receipt for your records")
        
        # Download buttons
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            col_a, col_b = st.columns(2)
            
            with col_a:
                # Download as TXT
                receipt_text = self.generate_iso8583_receipt_text(form_data, result)
                st.download_button(
                    label="📄 Download ISO-8583 Receipt",
                    data=receipt_text,
                    file_name=f"iso8583_receipt_{result.get('receipt_number', 'unknown')}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            
            with col_b:
                # Print functionality
                if st.button("🖨️ Print Receipt", use_container_width=True):
                    st.success("📠 Ready for printing! Use your browser's print function (Ctrl+P).")

    def generate_iso8583_receipt_text(self, form_data, result):
        """Generate formatted ISO-8583 receipt text for download"""
        return f"""
{'=' * 60}
            ISO-8583 AUTHORIZATION RECEIPT
              Base I Terminal • Protocol 101.1
{'=' * 60}

MERCHANT INFORMATION:
{'-' * 60}
Merchant: {form_data['merchant_name']}
Terminal ID: {st.session_state.terminal_id}
Merchant ID: {st.session_state.merchant_id}
Transaction: Online Authorization (ISO-8583)

ISO-8583 TRANSACTION DETAILS:
{'-' * 60}
Receipt Number: {result.get('receipt_number', 'N/A')}
Batch Number: {result.get('batch_number', 'N/A')}
RRN: {result.get('rrn', 'N/A')}
STAN: {result.get('stan', 'N/A')}
Card: {self.format_card_receipt(form_data['card_input'])}
Expiry: {self.format_expiry_display(form_data['expiry_input'])}
Processing Code: {form_data.get('processing_code', '000000')}
POS Entry Mode: 010 - Manual
Amount: ${form_data['amount']:.2f}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

ISO-8583 AUTHORIZATION:
{'-' * 60}
Status: {result.get('response_message', 'Unknown')}
4-Digit Approval: {result.get('approval_code', 'N/A')}
Full Auth Code: {result.get('full_auth_code', 'N/A')}
Response Code: {result.get('response_code', 'N/A')}
Message Type: 0100 - Authorization Request
Response Type: 0110 - Authorization Response

{'-' * 60}
        ISO-8583 ONLINE AUTHORIZATION COMPLETE
{'=' * 60}
"""

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

def main():
    """Main function"""
    terminal = ISO8583BaseITerminal()
    terminal.run()

if __name__ == "__main__":
    main()
