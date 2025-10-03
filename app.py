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
    
    # Demo result
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
        'response_message': 'APPROVED - Demo Transaction',
        'approval_code': 'DEMO',
        'full_auth_code': '123456',
        'response_code': '00',
        'systems_trace_number': demo_stan,  # Add STAN
        'retrieval_reference_number': demo_rrn,  # Add RRN
        'protocol': self.PROTOCOL_CONFIG['name']  # Add protocol
    }
    
    # Add to transaction history
    transaction_record = {
        'timestamp': datetime.now(),
        'amount': demo_data['amount'],
        'card': self.format_card_display(demo_data['card_input']),
        'status': demo_result['response_message'],
        'approval_code': demo_result['approval_code'],
        'response_code': demo_result['response_code'],
        'stan': demo_stan,
        'rrn': demo_rrn,
        'demo': True
    }
    st.session_state.transaction_history.append(transaction_record)
    
    # Show receipt
    self.show_receipt(demo_data, demo_result)

def show_receipt(self, form_data, result):
    """Show payment receipt with protocol information"""
    st.markdown("---")
    st.header("🧾 Payment Receipt")
    
    # Get transition IDs - handle both real and demo transactions
    stan = result.get('systems_trace_number', 
                     st.session_state.last_transaction.get('stan', 'N/A') if st.session_state.last_transaction else 'N/A')
    rrn = result.get('retrieval_reference_number', 
                    st.session_state.last_transaction.get('rrn', 'N/A') if st.session_state.last_transaction else 'N/A')
    protocol = result.get('protocol', self.PROTOCOL_CONFIG['name'])
    
    # Display transition IDs
    st.markdown(f"""
    <div class="transition-info">
        <strong>Transaction Identifiers:</strong><br>
        • STAN (Systems Trace): {stan}<br>
        • RRN (Retrieval Reference): {rrn}<br>
        • Protocol: {protocol}
    </div>
    """, unsafe_allow_html=True)
    
    receipt_html = f"""
    <div class="receipt-box success-box">
        <h3 style="text-align: center; margin-bottom: 20px;">FORCE SALE RECEIPT</h3>
        <p style="text-align: center; font-style: italic;">{protocol} - {self.PROTOCOL_CONFIG['standard']}</p>
        
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
            <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Merchant ID:</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #ccc;">{st.session_state.merchant_id}</td>
        </tr>
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Protocol:</strong></td>
            <td style="padding: 8px; border-bottom: 1px solid #ccc;">{protocol}</td>
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
    receipt_text = self.generate_receipt_text(form_data, result, stan, rrn, protocol)
    st.download_button(
        label="📄 Download Receipt",
        data=receipt_text,
        file_name=f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain"
    )

def generate_receipt_text(self, form_data, result, stan, rrn, protocol):
    """Generate receipt text for download with protocol info"""
    return f"""
FORCE SALE RECEIPT - {protocol}
==================================================
Merchant: {form_data['merchant_name']}
Terminal ID: {st.session_state.terminal_id}
Merchant ID: {st.session_state.merchant_id}
Protocol: {protocol} ({self.PROTOCOL_CONFIG['standard']})
--------------------------------------------------
Card: {self.format_card_display(form_data['card_input'])}
Expiry: {self.format_expiry_display(form_data['expiry_input'])}
Amount: ${form_data['amount']:.2f}
Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
--------------------------------------------------
TRANSACTION IDENTIFIERS:
STAN: {stan}
RRN: {rrn}
--------------------------------------------------
Status: {result.get('response_message', 'Unknown')}
Approval Code: {result.get('approval_code', 'N/A')}
Auth Code: {result.get('full_auth_code', 'N/A')}
Response Code: {result.get('response_code', 'N/A')}
==================================================
THANK YOU FOR YOUR BUSINESS
"""

def handle_transaction_result(self, result, form_data):
    """Handle transaction result"""
    if 'error' in result:
        st.error(f"❌ Transaction failed: {result['error']}")
    else:
        st.success("✅ Payment Approved!")
        
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
            'status': result.get('response_message', 'Unknown'),
            'approval_code': result.get('approval_code', 'N/A'),
            'response_code': result.get('response_code', 'N/A'),
            'stan': stan,
            'rrn': rrn,
            'demo': False
        }
        st.session_state.transaction_history.append(transaction_record)
        
        # Show receipt
        self.show_receipt(form_data, result)
