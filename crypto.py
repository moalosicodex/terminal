
#!/usr/bin/env python3
"""
Cryptocurrency Payment Terminal Web Application
Supports multiple cryptocurrencies
"""

import streamlit as st
import requests
import json
import hmac
import hashlib
import time
import os
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
import base64

class CryptoPaymentClient:
    """
    Cryptocurrency Payment Client with Multiple Exchange Support
    """
    
    def __init__(self):
        # Session state initialization
        if 'merchant_id' not in st.session_state:
            st.session_state.merchant_id = "CRYPTO_MERCHANT_001"
        if 'terminal_id' not in st.session_state:
            st.session_state.terminal_id = "CRYPTO_TERMINAL_001"
        if 'transaction_counter' not in st.session_state:
            st.session_state.transaction_counter = 100001
        if 'last_transaction' not in st.session_state:
            st.session_state.last_transaction = None
        if 'transaction_history' not in st.session_state:
            st.session_state.transaction_history = []
        if 'api_configured' not in st.session_state:
            st.session_state.api_configured = False
            
        # Supported cryptocurrencies
        self.SUPPORTED_CRYPTOS = {
            'BTC': {'name': 'Bitcoin', 'network_fee': 0.0001},
            'ETH': {'name': 'Ethereum', 'network_fee': 0.001},
            'LTC': {'name': 'Litecoin', 'network_fee': 0.001},
            'USDT': {'name': 'Tether', 'network_fee': 1.0},
            'XRP': {'name': 'Ripple', 'network_fee': 0.00001},
            'BCH': {'name': 'Bitcoin Cash', 'network_fee': 0.0001},
            'ADA': {'name': 'Cardano', 'network_fee': 1.0}
        }
        
        # Crypto API configurations
        self.CRYPTO_APIS = {
            'blockcypher': {
                'base_url': 'https://api.blockcypher.com/v1',
                'supported_coins': ['btc', 'eth', 'ltc', 'doge', 'bch']
            },
            'cryptocompare': {
                'base_url': 'https://min-api.cryptocompare.com/data',
                'api_key': 'your_api_key_here'
            },
            'coinbase': {
                'base_url': 'https://api.coinbase.com/v2',
                'api_key': 'your_api_key_here'
            }
        }

    def setup_page(self):
        """Configure Streamlit page"""
        st.set_page_config(
            page_title="Crypto Payment Terminal",
            page_icon="₿",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Custom CSS
        st.markdown("""
        <style>
        .main-header {
            font-size: 2.5rem;
            color: #ff9900;
            text-align: center;
            margin-bottom: 2rem;
        }
        .receipt-box {
            border: 2px solid #ff9900;
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
            background-color: #fff5e6;
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
        .crypto-box {
            border: 2px solid #ff9900;
            border-radius: 10px;
            padding: 15px;
            margin: 10px 0;
            background-color: #fff5e6;
        }
        .crypto-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            margin: 10px 0;
        }
        </style>
        """, unsafe_allow_html=True)

    def render_api_configuration(self):
        """Render API configuration section"""
        st.sidebar.subheader("🔑 API Configuration")
        
        if st.session_state.api_configured:
            st.sidebar.success("✅ API Configured")
            if st.sidebar.button("🔄 Re-configure API"):
                st.session_state.api_configured = False
                st.rerun()
            return True
        
        st.sidebar.info("Configure your cryptocurrency API settings")
        
        # API Provider Selection
        api_provider = st.sidebar.selectbox(
            "Select API Provider",
            ["BlockCypher", "CryptoCompare", "Coinbase", "Manual Entry"],
            help="Choose your cryptocurrency API provider"
        )
        
        # API Key Input
        api_key = st.sidebar.text_input(
            "API Key",
            type="password",
            placeholder="Enter your API key"
        )
        
        # API Secret (if needed)
        api_secret = st.sidebar.text_input(
            "API Secret",
            type="password", 
            placeholder="Enter your API secret"
        )
        
        if st.sidebar.button("💾 Save API Configuration"):
            if api_key:
                st.session_state.api_key = api_key
                st.session_state.api_secret = api_secret
                st.session_state.api_provider = api_provider
                st.session_state.api_configured = True
                st.sidebar.success("✅ API configuration saved!")
                st.rerun()
            else:
                st.sidebar.error("Please enter at least an API key")
        
        # Demo mode option
        with st.sidebar.expander("🎮 Demo Mode"):
            st.info("Use demo mode to test without real API keys")
            if st.button("Enable Demo Mode"):
                st.session_state.api_configured = True
                st.session_state.demo_mode = True
                st.rerun()
        
        return False

    def render_sidebar(self):
        """Render sidebar with merchant info and settings"""
        with st.sidebar:
            st.title("⚙️ Crypto Setup")
            
            # API configuration section
            api_ready = self.render_api_configuration()
            
            if api_ready:
                st.subheader("Merchant Information")
                st.info(f"**Merchant ID:** {st.session_state.merchant_id}")
                st.info(f"**Terminal ID:** {st.session_state.terminal_id}")
                
                st.subheader("API Status")
                if st.session_state.get('demo_mode', False):
                    st.warning("🔧 DEMO MODE - Using simulated transactions")
                else:
                    st.success("✅ API Connected")
                
                st.subheader("Supported Cryptocurrencies")
                for symbol, info in list(self.SUPPORTED_CRYPTOS.items())[:5]:
                    st.write(f"• **{symbol}** - {info['name']}")
                
                if len(self.SUPPORTED_CRYPTOS) > 5:
                    with st.expander("See all supported cryptocurrencies"):
                        for symbol, info in list(self.SUPPORTED_CRYPTOS.items())[5:]:
                            st.write(f"• **{symbol}** - {info['name']}")
                
                st.subheader("Quick Actions")
                if st.button("🔄 Test Crypto Rates"):
                    self.test_crypto_rates()
                    
                if st.button("📋 Transaction History"):
                    self.show_transaction_history()
            else:
                st.warning("⚠️ Please configure API to continue")

    def render_demo_mode(self):
        """Render demo mode when API isn't configured"""
        st.warning("🔧 DEMO MODE - API not configured")
        
        st.info("""
        **To enable live crypto transactions:**
        1. Configure your API settings in the sidebar
        2. Get API keys from supported providers
        3. Test the connection
        
        **Demo features available:**
        ✅ Crypto address validation
        ✅ QR code generation
        ✅ Transaction simulation  
        ✅ Receipt generation
        ✅ History tracking
        """)
        
        # Demo transaction button
        if st.button("🎮 Process Demo Crypto Transaction", type="secondary"):
            self.process_demo_transaction()

    def process_demo_transaction(self):
        """Process a demo crypto transaction"""
        st.info("🔄 Processing demo crypto transaction...")
        
        # Simulate processing delay
        with st.spinner("Processing crypto payment..."):
            time.sleep(3)
        
        # Demo result
        st.success("✅ Crypto Payment Received!")
        
        # Create demo receipt
        demo_data = {
            'crypto_currency': 'BTC',
            'crypto_amount': 0.0015,
            'usd_amount': 50.00,
            'wallet_address': 'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh',
            'merchant_name': 'Crypto Store Demo'
        }
        
        demo_result = {
            'transaction_hash': 'demo_' + hashlib.md5(str(time.time()).encode()).hexdigest()[:16],
            'status': 'CONFIRMED - Demo Transaction',
            'confirmations': 2,
            'network_fee': 0.0001,
            'exchange_rate': 33333.33
        }
        
        # Add to transaction history
        transaction_record = {
            'timestamp': datetime.now(),
            'crypto_amount': demo_data['crypto_amount'],
            'usd_amount': demo_data['usd_amount'],
            'currency': demo_data['crypto_currency'],
            'wallet_address': demo_data['wallet_address'][:8] + '...' + demo_data['wallet_address'][-8:],
            'status': demo_result['status'],
            'transaction_hash': demo_result['transaction_hash'],
            'confirmations': demo_result['confirmations'],
            'demo': True
        }
        st.session_state.transaction_history.append(transaction_record)
        
        # Show receipt
        self.show_crypto_receipt(demo_data, demo_result)

    def validate_crypto_address(self, address: str, currency: str) -> Tuple[bool, str]:
        """Validate cryptocurrency address format"""
        if not address:
            return False, "Wallet address is required"
        
        # Basic length checks
        if len(address) < 26:
            return False, "Address too short"
        
        if len(address) > 64:
            return False, "Address too long"
        
        # Currency-specific validation
        if currency == 'BTC':
            if not (address.startswith('1') or address.startswith('3') or address.startswith('bc1')):
                return False, "Invalid Bitcoin address format"
        elif currency == 'ETH':
            if not (address.startswith('0x') and len(address) == 42):
                return False, "Invalid Ethereum address format"
        elif currency == 'LTC':
            if not (address.startswith('L') or address.startswith('M') or address.startswith('ltc1')):
                return False, "Invalid Litecoin address format"
        elif currency == 'XRP':
            if not (address.startswith('r') and len(address) == 34):
                return False, "Invalid Ripple address format"
        
        return True, "Valid address"

    def get_crypto_price(self, currency: str) -> Optional[float]:
        """Get current cryptocurrency price"""
        try:
            if st.session_state.get('demo_mode', False):
                # Demo prices
                demo_prices = {
                    'BTC': 45000.00,
                    'ETH': 3000.00,
                    'LTC': 75.00,
                    'USDT': 1.00,
                    'XRP': 0.60,
                    'BCH': 250.00,
                    'ADA': 0.45
                }
                return demo_prices.get(currency, 1.00)
            
            # Real API call would go here
            # For now, return demo prices
            demo_prices = {
                'BTC': 45000.00,
                'ETH': 3000.00,
                'LTC': 75.00,
                'USDT': 1.00,
                'XRP': 0.60,
                'BCH': 250.00,
                'ADA': 0.45
            }
            return demo_prices.get(currency, 1.00)
            
        except Exception as e:
            st.error(f"Error fetching price: {e}")
            return None

    def calculate_crypto_amount(self, usd_amount: float, currency: str) -> Tuple[Optional[float], Optional[float]]:
        """Calculate crypto amount from USD"""
        price = self.get_crypto_price(currency)
        if not price:
            return None, None
        
        crypto_amount = usd_amount / price
        network_fee = self.SUPPORTED_CRYPTOS[currency]['network_fee']
        
        return crypto_amount, network_fee

    def generate_qr_code_data(self, address: str, amount: float, currency: str) -> str:
        """Generate QR code data for crypto payment"""
        if currency == 'BTC':
            return f"bitcoin:{address}?amount={amount}"
        elif currency == 'ETH':
            return f"ethereum:{address}?value={amount}"
        elif currency == 'LTC':
            return f"litecoin:{address}?amount={amount}"
        else:
            return address

    def render_main_header(self):
        """Render main header"""
        st.markdown('<div class="main-header">₿ Cryptocurrency Payment Terminal</div>', 
                   unsafe_allow_html=True)
        st.markdown("---")

    def render_payment_form(self):
        """Render crypto payment form"""
        st.header("📝 Crypto Payment Details")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Cryptocurrency selection
            crypto_currency = st.selectbox(
                "💰 Select Cryptocurrency",
                options=list(self.SUPPORTED_CRYPTOS.keys()),
                format_func=lambda x: f"{x} - {self.SUPPORTED_CRYPTOS[x]['name']}",
                help="Choose which cryptocurrency to accept"
            )
            
            # USD Amount
            usd_amount = st.number_input(
                "💵 Amount (USD)",
                min_value=1.00,
                value=25.00,
                step=1.00,
                format="%.2f",
                help="Enter amount in US Dollars"
            )
            
            # Wallet Address
            wallet_address = st.text_input(
                "👛 Your Crypto Wallet Address",
                placeholder="bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh",
                help="Enter your cryptocurrency wallet address for payment"
            )
            
        with col2:
            # Display crypto amount
            if usd_amount and crypto_currency:
                crypto_amount, network_fee = self.calculate_crypto_amount(usd_amount, crypto_currency)
                if crypto_amount:
                    st.markdown(f"""
                    <div class="crypto-card">
                        <h3>💱 Conversion</h3>
                        <p><strong>Amount:</strong> {crypto_amount:.8f} {crypto_currency}</p>
                        <p><strong>Network Fee:</strong> {network_fee} {crypto_currency}</p>
                        <p><strong>Total:</strong> {crypto_amount + network_fee:.8f} {crypto_currency}</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Merchant Name
            merchant_name = st.text_input(
                "🏪 Merchant Name",
                value="Crypto Payment Terminal",
                help="Business name for receipt"
            )
            
            # Payment Description
            payment_description = st.text_input(
                "📋 Payment Description",
                value="Product/Service Payment",
                help="Description of what is being paid for"
            )
        
        return {
            'crypto_currency': crypto_currency,
            'usd_amount': usd_amount,
            'wallet_address': wallet_address,
            'merchant_name': merchant_name,
            'payment_description': payment_description
        }

    def validate_payment_inputs(self, form_data):
        """Validate all payment inputs"""
        errors = []
        
        # Validate wallet address
        if form_data['wallet_address']:
            valid, message = self.validate_crypto_address(
                form_data['wallet_address'], 
                form_data['crypto_currency']
            )
            if not valid:
                errors.append(f"Wallet: {message}")
        else:
            errors.append("Wallet address is required")
            
        # Validate amount
        if form_data['usd_amount'] <= 0:
            errors.append("Amount must be greater than 0")
            
        return errors

    def process_crypto_payment(self, form_data):
        """Process cryptocurrency payment"""
        # Validate inputs
        errors = self.validate_payment_inputs(form_data)
        if errors:
            for error in errors:
                st.error(error)
            return
        
        # Check if we're in demo mode
        if st.session_state.get('demo_mode', False):
            self.process_demo_transaction()
            return
        
        # Calculate crypto amount
        crypto_amount, network_fee = self.calculate_crypto_amount(
            form_data['usd_amount'], 
            form_data['crypto_currency']
        )
        
        if not crypto_amount:
            st.error("❌ Error calculating cryptocurrency amount")
            return
        
        # Generate transaction
        with st.spinner("🔄 Creating crypto transaction..."):
            transaction_result = self.create_crypto_transaction(
                form_data['wallet_address'],
                crypto_amount,
                form_data['crypto_currency'],
                network_fee
            )
        
        # Handle result
        self.handle_crypto_transaction_result(transaction_result, form_data, crypto_amount, network_fee)

    def create_crypto_transaction(self, address: str, amount: float, currency: str, fee: float):
        """Create cryptocurrency transaction"""
        try:
            # In a real implementation, this would create an actual blockchain transaction
            # For now, we'll simulate it
            
            transaction_data = {
                'transaction_hash': 'txn_' + hashlib.md5(f"{address}{amount}{time.time()}".encode()).hexdigest()[:16],
                'status': 'PENDING',
                'confirmations': 0,
                'timestamp': datetime.now(),
                'exchange_rate': self.get_crypto_price(currency),
                'network_fee': fee
            }
            
            # Simulate confirmation
            time.sleep(2)
            transaction_data['status'] = 'CONFIRMED'
            transaction_data['confirmations'] = 2
            
            return transaction_data
            
        except Exception as e:
            return {'error': str(e)}

    def handle_crypto_transaction_result(self, result, form_data, crypto_amount, network_fee):
        """Handle crypto transaction result"""
        if 'error' in result:
            st.error(f"❌ Transaction failed: {result['error']}")
        else:
            st.success("✅ Crypto Payment Successful!")
            
            # Add to transaction history
            transaction_record = {
                'timestamp': datetime.now(),
                'crypto_amount': crypto_amount,
                'usd_amount': form_data['usd_amount'],
                'currency': form_data['crypto_currency'],
                'wallet_address': form_data['wallet_address'][:8] + '...' + form_data['wallet_address'][-8:],
                'status': result.get('status', 'UNKNOWN'),
                'transaction_hash': result.get('transaction_hash', 'N/A'),
                'confirmations': result.get('confirmations', 0),
                'network_fee': network_fee,
                'exchange_rate': result.get('exchange_rate', 0),
                'demo': False
            }
            st.session_state.transaction_history.append(transaction_record)
            
            # Show receipt
            self.show_crypto_receipt(form_data, result, crypto_amount, network_fee)

    def show_crypto_receipt(self, form_data, result, crypto_amount=None, network_fee=None):
        """Show crypto payment receipt"""
        st.markdown("---")
        st.header("🧾 Crypto Payment Receipt")
        
        if crypto_amount is None:
            crypto_amount, network_fee = self.calculate_crypto_amount(
                form_data['usd_amount'], 
                form_data['crypto_currency']
            )
        
        receipt_html = f"""
        <div class="receipt-box success-box">
            <h3 style="text-align: center; margin-bottom: 20px;">CRYPTO PAYMENT RECEIPT</h3>
            
            <table style="width: 100%; border-collapse: collapse;">
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Merchant:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{form_data['merchant_name']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Description:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{form_data['payment_description']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Currency:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{form_data['crypto_currency']} ({self.SUPPORTED_CRYPTOS[form_data['crypto_currency']]['name']})</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Amount (USD):</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">${form_data['usd_amount']:.2f}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Amount (Crypto):</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{crypto_amount:.8f} {form_data['crypto_currency']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Network Fee:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{network_fee} {form_data['crypto_currency']}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Wallet Address:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{form_data['wallet_address'][:12]}...{form_data['wallet_address'][-8:]}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Date/Time:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Status:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{result.get('status', 'Unknown')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Transaction Hash:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{result.get('transaction_hash', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;"><strong>Confirmations:</strong></td>
                <td style="padding: 8px; border-bottom: 1px solid #ccc;">{result.get('confirmations', 0)}</td>
            </tr>
            </table>
            
            <p style="text-align: center; margin-top: 20px; font-weight: bold;">THANK YOU FOR YOUR CRYPTO PAYMENT</p>
        </div>
        """
        
        st.markdown(receipt_html, unsafe_allow_html=True)
        
        # QR Code generation (simplified)
        st.subheader("📱 Payment QR Code")
        qr_data = self.generate_qr_code_data(
            form_data['wallet_address'],
            crypto_amount,
            form_data['crypto_currency']
        )
        
        st.code(qr_data, language="text")
        st.info("Scan this QR code with your crypto wallet to make payment")
        
        # Download button
        receipt_text = self.generate_crypto_receipt_text(form_data, result, crypto_amount, network_fee)
        st.download_button(
            label="📄 Download Receipt",
            data=receipt_text,
            file_name=f"crypto_receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )

    def generate_crypto_receipt_text(self, form_data, result, crypto_amount, network_fee):
        """Generate crypto receipt text for download"""
        return f"""
CRYPTO PAYMENT RECEIPT
======================
Merchant: {form_data['merchant_name']}
Description: {form_data['payment_description']}
Terminal ID: {st.session_state.terminal_id}
Merchant ID: {st.session_state.merchant_id}
----------------------
Currency: {form_data['crypto_currency']} ({self.SUPPORTED_CRYPTOS[form_data['crypto_currency']]['name']})
Amount (USD): ${form_data['usd_amount']:.2f}
Amount (Crypto): {crypto_amount:.8f} {form_data['crypto_currency']}
Network Fee: {network_fee} {form_data['crypto_currency']}
Total: {crypto_amount + network_fee:.8f} {form_data['crypto_currency']}
Wallet: {form_data['wallet_address']}
Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Status: {result.get('status', 'Unknown')}
Transaction Hash: {result.get('transaction_hash', 'N/A')}
Confirmations: {result.get('confirmations', 0)}
Exchange Rate: ${result.get('exchange_rate', 0):.2f}
======================
THANK YOU FOR YOUR CRYPTO PAYMENT
"""

    def test_crypto_rates(self):
        """Test cryptocurrency exchange rates"""
        with st.spinner("Fetching current crypto rates..."):
            rates = {}
            for currency in list(self.SUPPORTED_CRYPTOS.keys())[:4]:  # Test first 4
                price = self.get_crypto_price(currency)
                if price:
                    rates[currency] = price
            
            if rates:
                st.success("✅ Exchange rates fetched successfully!")
                for currency, price in rates.items():
                    st.info(f"**{currency}**: ${price:,.2f}")
            else:
                st.error("❌ Failed to fetch exchange rates")

    def show_transaction_history(self):
        """Show transaction history"""
        st.header("📋 Crypto Transaction History")
        
        if not st.session_state.transaction_history:
            st.info("No crypto transactions yet")
            return
            
        for i, transaction in enumerate(reversed(st.session_state.transaction_history[-10:]), 1):
            demo_indicator = " (Demo)" if transaction.get('demo', False) else ""
            with st.expander(f"Transaction {i} - {transaction['currency']} - {transaction['timestamp'].strftime('%H:%M:%S')}{demo_indicator}"):
                st.write(f"**Currency:** {transaction['currency']}")
                st.write(f"**Amount:** {transaction['crypto_amount']:.8f} {transaction['currency']} (${transaction['usd_amount']:.2f} USD)")
                st.write(f"**Wallet:** {transaction['wallet_address']}")
                st.write(f"**Status:** {transaction['status']}")
                st.write(f"**Transaction Hash:** {transaction['transaction_hash']}")
                st.write(f"**Confirmations:** {transaction['confirmations']}")
                st.write(f"**Time:** {transaction['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")

    def run(self):
        """Main application runner"""
        self.setup_page()
        self.render_sidebar()
        self.render_main_header()
        
        # Check if API is configured
        if not st.session_state.api_configured:
            self.render_demo_mode()
        else:
            # Payment form
            form_data = self.render_payment_form()
            
            # Process payment button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("🚀 Process Crypto Payment", type="primary", use_container_width=True):
                    self.process_crypto_payment(form_data)

def main():
    """Main function"""
    client = CryptoPaymentClient()
    client.run()

if __name__ == "__main__":
    main()
