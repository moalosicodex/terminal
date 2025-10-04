import streamlit as st
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

# Your existing app continues here...
st.title("💳 Professional Payment Terminal")
# ... rest of your code
