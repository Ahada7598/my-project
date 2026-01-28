# dashboard/app.py 
import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime, timedelta
import os
import hashlib
import json
from pathlib import Path
import traceback

# ==================== PAGE SETUP ====================
st.set_page_config(
    page_title="Procurement Anomaly Detection",
    page_icon="🏛️",
    layout="wide"
)

# ==================== DATABASE CONNECTION ====================
@st.cache_resource
def get_connection():
    """Get SQLite database connection"""
    db_path = Path("procurement.db")
    
    # Create basic tables if database doesn't exist
    if not db_path.exists():
        create_basic_tables()
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def create_basic_tables():
    """Create basic database tables if they don't exist"""
    try:
        conn = sqlite3.connect("procurement.db")
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agencies (
                agency_code TEXT PRIMARY KEY,
                agency_name TEXT,
                agency_type TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendors (
                vendor_code TEXT PRIMARY KEY,
                vendor_name TEXT,
                vendor_country TEXT,
                vendor_type TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS world_bank_indicators (
                indicator_year INTEGER PRIMARY KEY,
                gdp_growth REAL,
                inflation_rate REAL,
                government_expenditure REAL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS procurements (
                procurement_id INTEGER PRIMARY KEY,
                procurement_year INTEGER,
                agency_code TEXT,
                agency_name TEXT,
                project_name TEXT,
                procurement_category TEXT,
                estimated_cost REAL,
                actual_cost REAL,
                procurement_method TEXT,
                vendor_code TEXT,
                vendor_name TEXT,
                contract_start_date DATE,
                contract_end_date DATE,
                procurement_status TEXT,
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bids (
                bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
                procurement_id INTEGER,
                vendor_code TEXT,
                vendor_name TEXT,
                bid_amount REAL,
                bid_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'Submitted'
            )
        """)
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error creating database: {e}")
        return False

@st.cache_data(ttl=300)
def load_data():
    """Load data from SQLite"""
    try:
        conn = get_connection()
        
        # Check if tables have data
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM procurements")
        count = cursor.fetchone()[0]
        
        if count == 0:
            # Tables exist but are empty
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        
        # Load data with SQL queries
        procurements = pd.read_sql_query("""
            SELECT procurement_id, procurement_year, agency_code, agency_name, 
                   project_name, procurement_category, estimated_cost, actual_cost,
                   procurement_method, vendor_code, vendor_name,
                   contract_start_date, contract_end_date,
                   procurement_status
            FROM procurements
        """, conn)
        
        agencies = pd.read_sql_query("SELECT * FROM agencies", conn)
        vendors = pd.read_sql_query("SELECT * FROM vendors", conn)
        world_bank = pd.read_sql_query("SELECT * FROM world_bank_indicators", conn)
        
        # Convert dates and numeric columns
        date_cols = ['contract_start_date', 'contract_end_date']
        for col in date_cols:
            if col in procurements.columns:
                procurements[col] = pd.to_datetime(procurements[col], errors='coerce')
        
        for col in ['estimated_cost', 'actual_cost']:
            if col in procurements.columns:
                procurements[col] = pd.to_numeric(procurements[col], errors='coerce')
        
        return procurements, agencies, vendors, world_bank
        
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# ==================== LOAD DATA FROM CSV ====================
def load_data_from_csv():
    """Load data from CSV files and insert into database"""
    try:
        data_dir = Path("data")
        
        # Check if data directory exists
        if not data_dir.exists():
            st.error("Data directory not found. Please create a 'data' folder with CSV files.")
            return False
        
        # Load CSV files
        agencies_df = pd.read_csv(data_dir / "agencies.csv")
        vendors_df = pd.read_csv(data_dir / "vendors.csv")
        world_bank_df = pd.read_csv(data_dir / "world_bank_indicators.csv")
        procurements_df = pd.read_csv(data_dir / "procurements.csv")
        
        # Connect to database
        conn = sqlite3.connect("procurement.db")
        
        # Insert data
        agencies_df.to_sql('agencies', conn, if_exists='replace', index=False)
        vendors_df.to_sql('vendors', conn, if_exists='replace', index=False)
        world_bank_df.to_sql('world_bank_indicators', conn, if_exists='replace', index=False)
        procurements_df.to_sql('procurements', conn, if_exists='replace', index=False)
        
        conn.commit()
        conn.close()
        
        st.success(f"✅ Loaded {len(agencies_df)} agencies, {len(vendors_df)} vendors, "
                   f"{len(world_bank_df)} World Bank records, and {len(procurements_df)} procurements")
        return True
        
    except FileNotFoundError as e:
        st.error(f"CSV file not found: {e}")
        return False
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return False

# ==================== AUTHENTICATION SYSTEM ====================
class AuthenticationSystem:
    """Simple authentication system for 3 roles"""
    
    USERS = {
        "viewer": {
            "password_hash": hashlib.sha256("view123".encode()).hexdigest(),
            "role": "viewer",
            "name": "Analyst Viewer"
        },
        "admin": {
            "password_hash": hashlib.sha256("admin123".encode()).hexdigest(),
            "role": "admin",
            "name": "System Administrator"
        },
        "buyer": {
            "password_hash": hashlib.sha256("buy123".encode()).hexdigest(),
            "role": "buyer",
            "name": "Vendor Buyer"
        }
    }
    
    @staticmethod
    def login(username, password):
        """Verify user credentials"""
        if username in AuthenticationSystem.USERS:
            stored_hash = AuthenticationSystem.USERS[username]["password_hash"]
            input_hash = hashlib.sha256(password.encode()).hexdigest()
            
            if stored_hash == input_hash:
                return {
                    "authenticated": True,
                    "username": username,
                    "role": AuthenticationSystem.USERS[username]["role"],
                    "name": AuthenticationSystem.USERS[username]["name"]
                }
        return {"authenticated": False}
    
    @staticmethod
    def logout():
        """Clear session state"""
        for key in ['authenticated', 'username', 'role', 'name']:
            if key in st.session_state:
                del st.session_state[key]

# ==================== ANOMALY DETECTION FUNCTIONS ====================
def calculate_anomalies(procurements):
    """Calculate anomaly flags and risk scores"""
    df = procurements.copy()
    
    # Cost overrun percentage
    df['cost_overrun_%'] = 0.0
    mask = (df['estimated_cost'] > 0) & df['actual_cost'].notna()
    df.loc[mask, 'cost_overrun_%'] = (
        (df['actual_cost'] - df['estimated_cost']) / df['estimated_cost'] * 100
    )
    
    # Anomaly flags
    df['high_overrun_flag'] = df['cost_overrun_%'] > 10
    df['large_direct_flag'] = (
        (df['estimated_cost'] > 1000000) & 
        df['procurement_method'].isin(['Direct', 'Limited'])
    )
    
    valid_dates = df['contract_start_date'].notna() & df['contract_end_date'].notna()
    df['contract_duration'] = 0
    df.loc[valid_dates, 'contract_duration'] = (
        df['contract_end_date'] - df['contract_start_date']
    ).dt.days
    df['short_duration_flag'] = df['contract_duration'] < 30
    
    # Risk score
    df['risk_score'] = (
        df['high_overrun_flag'].astype(int) +
        df['large_direct_flag'].astype(int) +
        df['short_duration_flag'].astype(int)
    )
    
    return df

# ==================== BIDDING SYSTEM FUNCTIONS ====================
class BiddingSystem:
    """Simple bidding system"""
    
    @staticmethod
    def load_bids():
        """Load bids from database"""
        try:
            conn = get_connection()
            bids_df = pd.read_sql_query("SELECT * FROM bids ORDER BY bid_date DESC", conn)
            return bids_df.to_dict('records')
        except:
            return []
    
    @staticmethod
    def submit_bid(procurement_id, vendor_code, vendor_name, bid_amount):
        """Submit a new bid to database"""
        try:
            conn = get_connection()
            cursor = conn.cursor()
            
            # Create bids table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bids (
                    bid_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    procurement_id INTEGER,
                    vendor_code TEXT,
                    vendor_name TEXT,
                    bid_amount REAL,
                    bid_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'Submitted'
                )
            """)
            
            # Insert bid
            cursor.execute("""
                INSERT INTO bids (procurement_id, vendor_code, vendor_name, bid_amount)
                VALUES (?, ?, ?, ?)
            """, (procurement_id, vendor_code, vendor_name, bid_amount))
            
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Bid submission error: {e}")
            return False

# ==================== LOGIN PAGE ====================
def show_login_page():
    """Display login page with 3 role options"""
    
    st.title("🏛️ Procurement Anomaly Detection System")
    st.markdown("### **Multi-User Portal**")
    st.markdown("---")
    
    st.markdown("""
    <div style='text-align: center; padding: 30px; border-radius: 10px;'>
        <h3>Select Your Role to Continue</h3>
        <p>Choose your role to access the appropriate dashboard features</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""<div style='text-align: center; padding: 20px; border: 2px solid #1E90FF; border-radius: 10px;'>
            <h4>👁️ VIEWER</h4><p>Read-only access</p><p>• View analytics</p><p>• ML predictions</p><p>• No editing</p>
        </div>""", unsafe_allow_html=True)
        
        with st.expander("Login as Viewer", expanded=False):
            username = st.text_input("Username", key="viewer_user")
            password = st.text_input("Password", type="password", key="viewer_pass")
            if st.button("Login as Viewer", type="primary"):
                result = AuthenticationSystem.login(username, password)
                if result["authenticated"] and result["role"] == "viewer":
                    for key, value in result.items():
                        st.session_state[key] = value
                    st.rerun()
                else:
                    st.error("Invalid viewer credentials")
    
    with col2:
        st.markdown("""<div style='text-align: center; padding: 20px; border: 2px solid #32CD32; border-radius: 10px;'>
            <h4>⚙️ ADMIN</h4><p>Full system control</p><p>• Edit all data</p><p>• Manage users</p><p>• System settings</p>
        </div>""", unsafe_allow_html=True)
        
        with st.expander("Login as Admin", expanded=False):
            username = st.text_input("Username", key="admin_user")
            password = st.text_input("Password", type="password", key="admin_pass")
            if st.button("Login as Admin", type="primary"):
                result = AuthenticationSystem.login(username, password)
                if result["authenticated"] and result["role"] == "admin":
                    for key, value in result.items():
                        st.session_state[key] = value
                    st.rerun()
                else:
                    st.error("Invalid admin credentials")
    
    with col3:
        st.markdown("""<div style='text-align: center; padding: 20px; border: 2px solid #FF8C00; border-radius: 10px;'>
            <h4>💰 BUYER</h4><p>Bidding access</p><p>• View open projects</p><p>• Submit bids</p><p>• Track bids</p>
        </div>""", unsafe_allow_html=True)
        
        with st.expander("Login as Buyer", expanded=False):
            username = st.text_input("Username", key="buyer_user")
            password = st.text_input("Password", type="password", key="buyer_pass")
            if st.button("Login as Buyer", type="primary"):
                result = AuthenticationSystem.login(username, password)
                if result["authenticated"] and result["role"] == "buyer":
                    for key, value in result.items():
                        st.session_state[key] = value
                    st.rerun()
                else:
                    st.error("Invalid buyer credentials")
    
    st.markdown("---")
    st.markdown("""
    **Demo Credentials:**
    - **Viewer**: username=`viewer`, password=`view123`
    - **Admin**: username=`admin`, password=`admin123`
    - **Buyer**: username=`buyer`, password=`buy123`
    """)

# ==================== VIEWER DASHBOARD ====================
def show_viewer_dashboard():
    """Dashboard for Viewer role (read-only)"""
    
    # Load data
    procurements, agencies, vendors, world_bank = load_data()
    
    if procurements.empty:
        st.error("No data available. Please load data from CSV files.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📂 Load Data from CSV Files", type="primary"):
                with st.spinner("Loading data from CSV files..."):
                    if load_data_from_csv():
                        st.cache_data.clear()
                        st.rerun()
        
        with col2:
            if st.button("🔄 Check Database Connection"):
                try:
                    conn = sqlite3.connect("procurement.db")
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    tables = cursor.fetchall()
                    conn.close()
                    st.success(f"✅ Database connected. Tables: {[t[0] for t in tables]}")
                except Exception as e:
                    st.error(f"❌ Database error: {e}")
        
        return
    
    # Calculate anomalies
    procurements = calculate_anomalies(procurements)
    
    # Header with logout
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        st.title("📊 Procurement Analytics Dashboard")
        st.markdown(f"**Welcome, {st.session_state.name} (Viewer)**")
    with col3:
        if st.button("🚪 Logout", type="secondary"):
            AuthenticationSystem.logout()
            st.rerun()
    
    st.markdown("---")
    
    # Executive Summary
    st.header("📈 Executive Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Contracts", len(procurements))
    with col2:
        high_risk = len(procurements[procurements['risk_score'] >= 2])
        st.metric("High Risk Contracts", high_risk)
    with col3:
        cost_overruns = procurements['high_overrun_flag'].sum()
        st.metric("Cost Overruns >10%", int(cost_overruns))
    with col4:
        large_direct = procurements['large_direct_flag'].sum()
        st.metric("Large Direct Contracts", int(large_direct))
    
    st.markdown("---")
    
    # High Risk Contracts
    st.header("🚨 High Risk Contracts")
    high_risk_df = procurements[procurements['risk_score'] >= 2].sort_values('risk_score', ascending=False)
    
    if not high_risk_df.empty:
        st.dataframe(
            high_risk_df[['procurement_id', 'agency_name', 'vendor_name', 
                         'estimated_cost', 'actual_cost', 'cost_overrun_%',
                         'procurement_method', 'risk_score']].head(10),
            use_container_width=True
        )
    else:
        st.info("✅ No high-risk contracts detected")
    
    st.markdown("---")
    
    # ML Anomaly Detection
    st.header("🤖 Machine Learning Anomaly Detection")
    
    with st.expander("Run ML Analysis", expanded=False):
        st.info("""
        **Isolation Forest Algorithm** detects anomalies by isolating outliers in the data.
        Features used: Cost, Duration, Vendor Frequency
        """)
        
        if st.button("🔍 Run ML Detection", type="secondary"):
            try:
                from sklearn.ensemble import IsolationForest
                import numpy as np
                
                with st.spinner("Running ML analysis..."):
                    # Prepare features
                    features = pd.DataFrame()
                    features['log_cost'] = np.log1p(procurements['estimated_cost'].fillna(0))
                    
                    # Duration feature
                    features['duration'] = procurements['contract_duration'].fillna(0)
                    
                    # Vendor frequency
                    if 'vendor_code' in procurements.columns:
                        vendor_counts = procurements['vendor_code'].value_counts()
                        features['vendor_freq'] = procurements['vendor_code'].map(vendor_counts).fillna(1)
                    else:
                        features['vendor_freq'] = 1
                    
                    features = features.fillna(0)
                    
                    # Train Isolation Forest model
                    model = IsolationForest(
                        contamination=0.15,
                        random_state=42,
                        n_estimators=100
                    )
                    
                    ml_predictions = model.fit_predict(features)
                    procurements['ml_anomaly'] = (ml_predictions == -1)
                    procurements['ml_confidence'] = model.decision_function(features) * -1
                    
                    ml_anomalies = procurements[procurements['ml_anomaly'] == True]
                    
                    st.success(f"✅ ML detected **{len(ml_anomalies)}** anomalous contracts!")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Contracts", len(procurements))
                    with col2:
                        st.metric("ML Anomalies", len(ml_anomalies))
                    with col3:
                        anomaly_percent = (len(ml_anomalies) / len(procurements)) * 100
                        st.metric("Anomaly %", f"{anomaly_percent:.1f}%")
                    
                    if not ml_anomalies.empty:
                        st.subheader(f"ML-Detected Anomalies ({len(ml_anomalies)} records)")
                        
                        ml_anomalies_sorted = ml_anomalies.sort_values('ml_confidence', ascending=False)
                        
                        st.dataframe(
                            ml_anomalies_sorted[[
                                'procurement_id', 'agency_name', 'vendor_name',
                                'estimated_cost', 'contract_duration', 'ml_confidence'
                            ]],
                            use_container_width=True,
                            height=400
                        )
                        
                        # Download button
                        csv_data = ml_anomalies_sorted.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download ML Anomalies (CSV)",
                            data=csv_data,
                            file_name=f"ml_anomalies_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            type="secondary"
                        )
                    else:
                        st.info("✅ No anomalies detected by ML algorithm")
                        
            except Exception as e:
                st.error(f"ML Error: {e}")
                st.info("To install required package: `pip install scikit-learn`")
    
    # Visualizations
    st.header("📊 Visualizations")
    
    col1, col2 = st.columns(2)
    with col1:
        if not procurements.empty:
            fig1 = px.histogram(
                procurements[procurements['estimated_cost'] <= procurements['estimated_cost'].quantile(0.95)],
                x='estimated_cost',
                title='Contract Value Distribution',
                nbins=15,
                color_discrete_sequence=['#3366CC']
            )
            st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        if not procurements.empty:
            method_counts = procurements['procurement_method'].value_counts()
            fig2 = px.pie(
                values=method_counts.values,
                names=method_counts.index,
                title='Procurement Methods',
                hole=0.3
            )
            st.plotly_chart(fig2, use_container_width=True)
    
    # Export Data
    st.markdown("---")
    st.header("📥 Export Data")
    
    if not procurements.empty:
        csv_data = procurements.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Download Analytics Data (CSV)",
            data=csv_data,
            file_name="procurement_analytics.csv",
            mime="text/csv"
        )

# ==================== MAIN APPLICATION FLOW ====================
def main():
    """Main application entry point"""
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    # Check authentication status
    if not st.session_state.authenticated:
        show_login_page()
    else:
        # Show appropriate dashboard based on role
        role = st.session_state.get('role', 'viewer')
        
        if role == 'viewer':
            show_viewer_dashboard()
        elif role == 'admin':
            show_viewer_dashboard()  # For now, show same as viewer
            st.info("Admin features coming soon!")
        elif role == 'buyer':
            show_viewer_dashboard()  # For now, show same as viewer
            st.info("Buyer features coming soon!")
        else:
            st.error("Invalid role detected")
            AuthenticationSystem.logout()
            st.rerun()

# Run the main application
if __name__ == "__main__":
    main()
    
    # Footer
    st.markdown("---")
    st.markdown(f"""
    <div style="text-align: center; color: #666; padding: 10px; border-radius: 10px;">
        <h4 style="color: #1E3A8A;">Procurement Anomaly Detection System</h4>
        <p><b>Final Year Project | Government Contract Monitoring & Fraud Detection</b></p>
        <p>🔍 Detection Rules: Cost overruns (>10%) • Large direct contracts • Short durations (<30 days)</p>
        <p>⏱️ Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
    """, unsafe_allow_html=True)
