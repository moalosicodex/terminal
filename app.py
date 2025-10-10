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
        if 'reversal_history' not in st.session_state:
            st.session_state.reversal_history = []
        
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
        
        # FIXED: Changed CLIENT_DIR to CERT_DIR
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
        .error-receipt {
            border-color: #dc3545;
            background-color: #f8d7da;
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
        .connection-status {
            padding: 10px;
            border-radius: 5px;
            margin: 5px 0;
        }
        .connection-success {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        .connection-failure {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
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
            
            st.header("🔄 Reversal History")
            self.show_reversal_history()
            
            st.header("🔐 Certificate Setup")
            self.show_certificate_upload()
        
        # Main content area
        tab1, tab2, tab3, tab4 = st.tabs(["💳 Payment Terminal", "🔄 Transaction Reversal", "📡 Connection Test", "📈 Transaction Analytics"])
        
        with tab1:
            self.show_payment_terminal()
        
        with tab2:
            self.show_reversal_terminal()
        
        with tab3:
            self.show_connection_test()
            
        with tab4:
            self.show_transaction_analytics()

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
        
        for i, tx in enumerate(st.session_state.transaction_history[-10:]):
            status_color = "🟢" if tx.get('response_code') == '00' else "🔴"
            with st.expander(f"{status_color} Tx {i+1}: {tx.get('pan_mask', 'N/A')} - ${tx.get('amount', 0):.2f} - {tx.get('timestamp', '')}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Amount:** ${tx.get('amount', 0):.2f}")
                    st.write(f"**PAN:** {tx.get('pan_mask', 'N/A')}")
                    st.write(f"**Response:** {tx.get('response_code', 'N/A')} - {tx.get('response_message', 'N/A')}")
                with col2:
                    st.write(f"**Approval:** {tx.get('approval_code', 'N/A')}")
                    st.write(f"**STAN:** {tx.get('stan', 'N/A')}")
                    st.write(f"**RRN:** {tx.get('rrn', 'N/A')}")
                
                if st.button(f"Download Receipt {i+1}", key=f"dl_{i}"):
                    receipt_text = self.generate_history_receipt_text(tx)
                    st.download_button(
                        label="Download Receipt",
                        data=receipt_text,
                        file_name=f"receipt_{tx.get('receipt_number', 'unknown')}.txt",
                        mime="text/plain",
                        key=f"dl_btn_{i}"
                    )

    def show_reversal_history(self):
        """Show reversal history"""
        if not st.session_state.reversal_history:
            st.write("No reversals yet")
            return
        
        for i, rev in enumerate(st.session_state.reversal_history[-5:]):
            status = "✅" if rev.get('success') else "❌"
            with st.expander(f"{status} Reversal {i+1}: {rev.get('timestamp', '')}"):
                st.json(rev)

    def show_certificate_upload(self):
        """Handle certificate file uploads"""
        if st.session_state.cert_files_uploaded:
            st.success("✅ Certificates uploaded")
            if st.button("Remove Certificates"):
                st.session_state.cert_files_uploaded = False
                # Remove files
                if os.path.exists(self.CLIENT_CERT):
                    os.remove(self.CLIENT_CERT)
                if os.path.exists(self.CLIENT_KEY):
                    os.remove(self.CLIENT_KEY)
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
        """Show payment terminal interface"""
        st.header("💳 Payment Terminal")
        
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
                cvv = st.text_input("CVV/CVC", "123", max_chars=4,
                                  help="3 or 4 digit security code")
                pin_input = st.text_input("PIN", "1234", type="password", max_chars=4,
                                        help="4-digit PIN")
            
            # Process payment
            if st.form_submit_button("🚀 Process Payment", use_container_width=True):
                if self.validate_payment_input(card_input, expiry_input, amount):
                    form_data = {
                        'merchant_name': merchant_name,
                        'card_input': card_input,
                        'expiry_input': expiry_input,
                        'amount': amount,
                        'cvv': cvv,
                        'pin_input': pin_input
                    }
                    
                    with st.spinner("Processing transaction..."):
                        result = self.process_payment(form_data)
                    
                    # Show receipt
                    self.show_receipt(form_data, result)
                    
                    # Store transaction
                    transaction_record = {
                        'timestamp': datetime.now().isoformat(),
                        'pan_mask': self.format_card_receipt(card_input),
                        'amount': amount,
                        'response_code': result.get('response_code'),
                        'response_message': result.get('response_message'),
                        'approval_code': result.get('approval_code'),
                        'rrn': result.get('rrn'),
                        'stan': result.get('stan'),
                        'receipt_number': result.get('receipt_number'),
                        'batch_number': result.get('batch_number')
                    }
                    st.session_state.transaction_history.append(transaction_record)
                    
                    # Update STAN counter and receipt counter
                    st.session_state.stan_counter += 1
                    st.session_state.receipt_counter += 1
                    st.session_state.last_transaction = result

    def show_reversal_terminal(self):
        """Show transaction reversal interface"""
        st.header("🔄 Transaction Reversal")
        
        if not st.session_state.last_transaction:
            st.warning("No recent transaction to reverse")
        else:
            st.info("Last transaction details:")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Amount:** ${st.session_state.last_transaction.get('amount', 0):.2f}")
                st.write(f"**STAN:** {st.session_state.last_transaction.get('stan', 'N/A')}")
                st.write(f"**RRN:** {st.session_state.last_transaction.get('rrn', 'N/A')}")
            with col2:
                st.write(f"**Approval Code:** {st.session_state.last_transaction.get('approval_code', 'N/A')}")
                st.write(f"**Response:** {st.session_state.last_transaction.get('response_code', 'N/A')}")
                st.write(f"**Timestamp:** {st.session_state.last_transaction.get('timestamp', 'N/A')}")
        
        # Manual reversal option
        st.subheader("Manual Reversal")
        col1, col2, col3 = st.columns(3)
        with col1:
            reversal_stan = st.text_input("STAN for Reversal", help="Enter STAN to reverse")
        with col2:
            reversal_amount = st.number_input("Amount to Reverse", min_value=0.01, value=1.00, step=0.01)
        with col3:
            reversal_rrn = st.text_input("RRN for Reversal", help="Enter RRN to reverse")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Reverse Last Transaction", use_container_width=True, disabled=not st.session_state.last_transaction):
                with st.spinner("Reversing transaction..."):
                    result = self.process_reversal()
                
                if result.get('success'):
                    st.success("✅ Transaction reversed successfully!")
                    st.session_state.reversal_history.append(result)
                    st.session_state.last_transaction = None
                else:
                    st.error("❌ Reversal failed")
                    st.session_state.reversal_history.append(result)
        
        with col2:
            if st.button("🔁 Reverse Specific Transaction", use_container_width=True):
                if reversal_stan and reversal_amount:
                    with st.spinner("Reversing specified transaction..."):
                        result = self.process_manual_reversal(reversal_stan, reversal_amount, reversal_rrn)
                    
                    if result.get('success'):
                        st.success("✅ Manual reversal successful!")
                        st.session_state.reversal_history.append(result)
                    else:
                        st.error("❌ Manual reversal failed")
                        st.session_state.reversal_history.append(result)
                else:
                    st.error("Please provide STAN and Amount for reversal")

    def show_connection_test(self):
        """Show connection testing interface"""
        st.header("📡 Connection Test")
        
        # Server configuration
        st.subheader("Server Configuration")
        col1, col2 = st.columns(2)
        
        with col1:
            primary_host = st.text_input("Primary Host", st.session_state.server_config['primary']['host'])
            primary_port = st.number_input("Primary Port", value=st.session_state.server_config['primary']['port'])
            st.session_state.server_config['primary']['host'] = primary_host
            st.session_state.server_config['primary']['port'] = primary_port
            
        with col2:
            secondary_host = st.text_input("Secondary Host", st.session_state.server_config['secondary']['host'])
            secondary_port = st.number_input("Secondary Port", value=st.session_state.server_config['secondary']['port'])
            st.session_state.server_config['secondary']['host'] = secondary_host
            st.session_state.server_config['secondary']['port'] = secondary_port
        
        # Connection testing
        st.subheader("Connection Testing")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🧪 Test Primary Connection", use_container_width=True):
                with st.spinner("Testing primary connection..."):
                    success, message, details = self.test_connection('primary')
                
                if success:
                    st.markdown(f'<div class="connection-status connection-success">✅ {message}</div>', unsafe_allow_html=True)
                    st.json(details)
                else:
                    st.markdown(f'<div class="connection-status connection-failure">❌ {message}</div>', unsafe_allow_html=True)
        
        with col2:
            if st.button("🧪 Test Secondary Connection", use_container_width=True):
                with st.spinner("Testing secondary connection..."):
                    success, message, details = self.test_connection('secondary')
                
                if success:
                    st.markdown(f'<div class="connection-status connection-success">✅ {message}</div>', unsafe_allow_html=True)
                    st.json(details)
                else:
                    st.markdown(f'<div class="connection-status connection-failure">❌ {message}</div>', unsafe_allow_html=True)
        
        # Batch connection test
        if st.button("🚀 Test All Connections", use_container_width=True):
            col1, col2 = st.columns(2)
            with col1:
                with st.spinner("Testing primary..."):
                    primary_success, primary_msg, _ = self.test_connection('primary')
                st.success("Primary: ✅") if primary_success else st.error("Primary: ❌")
            
            with col2:
                with st.spinner("Testing secondary..."):
                    secondary_success, secondary_msg, _ = self.test_connection('secondary')
                st.success("Secondary: ✅") if secondary_success else st.error("Secondary: ❌")

    def show_transaction_analytics(self):
        """Show transaction analytics"""
        st.header("📈 Transaction Analytics")
        
        if not st.session_state.transaction_history:
            st.info("No transaction data available yet")
            return
        
        # Basic statistics
        total_transactions = len(st.session_state.transaction_history)
        approved_transactions = len([t for t in st.session_state.transaction_history if t.get('response_code') == '00'])
        total_amount = sum([t.get('amount', 0) for t in st.session_state.transaction_history])
        approval_rate = (approved_transactions / total_transactions * 100) if total_transactions > 0 else 0
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Transactions", total_transactions)
        with col2:
            st.metric("Approved", approved_transactions)
        with col3:
            st.metric("Total Amount", f"${total_amount:.2f}")
        with col4:
            st.metric("Approval Rate", f"{approval_rate:.1f}%")
        
        # Recent transactions table
        st.subheader("Recent Transactions")
        if st.session_state.transaction_history:
            recent_tx = st.session_state.transaction_history[-10:]
            for tx in recent_tx:
                status = "✅" if tx.get('response_code') == '00' else "❌"
                col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                with col1:
                    st.write(f"{tx.get('pan_mask', 'N/A')}")
                with col2:
                    st.write(f"${tx.get('amount', 0):.2f}")
                with col3:
                    st.write(f"{status} {tx.get('response_code', 'N/A')}")
                with col4:
                    st.write(f"{tx.get('approval_code', 'N/A')}")

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

    def process_payment(self, form_data: Dict) -> Dict:
        """Process payment transaction"""
        # Generate transaction details
        stan = str(st.session_state.stan_counter).zfill(6)
        rrn = datetime.now().strftime("%Y%m%d%H%M%S")
        approval_code = str(random.randint(1000, 9999))
        
        # Simulate processing delay
        time.sleep(2)
        
        # Simulate response (90% approval rate)
        if random.random() < 0.9:
            response_code = "00"
            response_message = "APPROVED"
        else:
            response_code = "05"
            response_message = "DECLINED"
            approval_code = "0000"
        
        return {
            'success': True,
            'response_code': response_code,
            'response_message': response_message,
            'approval_code': approval_code,
            'full_auth_code': f"{approval_code}{response_code}",
            'stan': stan,
            'rrn': rrn,
            'receipt_number': st.session_state.receipt_counter,
            'batch_number': st.session_state.batch_number,
            'timestamp': datetime.now().isoformat(),
            'amount': form_data['amount']
        }

    def process_reversal(self) -> Dict:
        """Process transaction reversal"""
        # Simulate reversal processing
        time.sleep(2)
        
        return {
            'success': True,
            'message': 'Reversal processed successfully',
            'timestamp': datetime.now().isoformat(),
            'reversed_stan': st.session_state.last_transaction.get('stan') if st.session_state.last_transaction else 'N/A',
            'reversed_amount': st.session_state.last_transaction.get('amount') if st.session_state.last_transaction else 0
        }

    def process_manual_reversal(self, stan: str, amount: float, rrn: str = None) -> Dict:
        """Process manual transaction reversal"""
        time.sleep(2)
        
        return {
            'success': True,
            'message': 'Manual reversal processed successfully',
            'timestamp': datetime.now().isoformat(),
            'reversed_stan': stan,
            'reversed_amount': amount,
            'reversed_rrn': rrn or 'N/A'
        }

    def test_connection(self, server: str) -> Tuple[bool, str, Dict]:
        """Test connection to server"""
        try:
            config = st.session_state.server_config[server]
            
            # Simulate connection test with realistic timing
            time.sleep(1.5)
            
            # 80% success rate for demo
            if random.random() < 0.8:
                return True, f"{server.title()} Connection Successful", {
                    'server': server,
                    'host': config['host'],
                    'port': config['port'],
                    'protocol': config['protocol'],
                    'response_time': f"{random.uniform(0.1, 0.5):.3f}s",
                    'timestamp': datetime.now().isoformat()
                }
            else:
                return False, f"{server.title()} Connection Failed - Timeout", {
                    'server': server,
                    'host': config['host'],
                    'port': config['port'],
                    'error': 'Connection timeout',
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            return False, f"{server.title()} Connection Error", {
                'server': server,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

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
            elif result.get('response_code') == '05':
                st.error("❌ PAYMENT DECLINED")
                receipt_class = "error-receipt"
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
                    st.text_input("Merchant", form_data['merchant_name'], disabled=True, key="merchant_name")
                    st.text_input("Terminal ID", st.session_state.terminal_id, disabled=True, key="terminal_id")
                with col2:
                    st.text_input("Merchant ID", st.session_state.merchant_id, disabled=True, key="merchant_id")
                    st.text_input("Transaction Type", "🟢 Online Authorization", disabled=True, key="tx_type")
                
                # Transaction Details
                st.subheader("📊 Transaction Details")
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Receipt Number", str(result.get('receipt_number', 'N/A')), disabled=True, key="receipt_num")
                    st.text_input("Batch Number", str(result.get('batch_number', 'N/A')), disabled=True, key="batch_num")
                    st.text_input("Card Number", self.format_card_receipt(form_data['card_input']), disabled=True, key="card_num")
                with col2:
                    st.text_input("RRN", result.get('rrn', 'N/A'), disabled=True, key="rrn")
                    st.text_input("STAN", result.get('stan', 'N/A'), disabled=True, key="stan")
                    st.text_input("Expiry Date", self.format_expiry_display(form_data['expiry_input']), disabled=True, key="expiry")
                
                # Amount and Date
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Amount", f"${form_data['amount']:.2f}", disabled=True, key="amount")
                with col2:
                    st.text_input("Date/Time", datetime.now().strftime('%Y-%m-%d %H:%M:%S'), disabled=True, key="datetime")
                
                # Authorization Information
                st.subheader("🔐 Authorization Information")
                col1, col2 = st.columns(2)
                with col1:
                    st.text_input("Status", result.get('response_message', 'Unknown'), disabled=True, key="status")
                    st.text_input("Approval Code", result.get('approval_code', 'N/A'), disabled=True, key="approval")
                with col2:
                    st.text_input("Response Code", result.get('response_code', 'N/A'), disabled=True, key="response_code")
                    st.text_input("Auth Code", result.get('full_auth_code', 'N/A'), disabled=True, key="auth_code")
                
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
                    use_container_width=True,
                    key="download_txt"
                )
            
            with col_b:
                # Print functionality
                if st.button("🖨️ Print Receipt", use_container_width=True, key="print_btn"):
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

    def generate_history_receipt_text(self, transaction):
        """Generate receipt text from transaction history"""
        return f"""
{'=' * 50}
         PAYMENT RECEIPT
        ISO-8583 Base I Terminal
{'=' * 50}

MERCHANT INFORMATION:
{'-' * 50}
Terminal ID: {st.session_state.terminal_id}
Merchant ID: {st.session_state.merchant_id}
Transaction: Online Authorization (Protocol 101.1)

TRANSACTION DETAILS:
{'-' * 50}
Receipt Number: {transaction.get('receipt_number', 'N/A')}
Batch Number: {transaction.get('batch_number', 'N/A')}
RRN: {transaction.get('rrn', 'N/A')}
STAN: {transaction.get('stan', 'N/A')}
Card: {transaction.get('pan_mask', 'N/A')}
Amount: ${transaction.get('amount', 0):.2f}
Date: {transaction.get('timestamp', 'N/A')}

AUTHORIZATION INFORMATION:
{'-' * 50}
Status: {transaction.get('response_message', 'Unknown')}
Approval Code: {transaction.get('approval_code', 'N/A')}
Response Code: {transaction.get('response_code', 'N/A')}

{'-' * 50}
      THANK YOU FOR YOUR BUSINESS
{'=' * 50}
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
