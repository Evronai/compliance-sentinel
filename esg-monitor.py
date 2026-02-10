import streamlit as st
import os
import json
from datetime import datetime, timedelta
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, Optional, List
import hashlib
import re

# =============================================================================
# PAGE CONFIGURATION - Added mobile optimization
# =============================================================================

st.set_page_config(
    page_title="Compliance Sentinel",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",  # Changed to collapsed for mobile
    menu_items={
        'Get Help': 'https://github.com/your-repo',
        'Report a bug': "https://github.com/your-repo/issues",
        'About': "Compliance Sentinel - Professional HSE & Compliance Analysis"
    }
)

# =============================================================================
# CUSTOM CSS - Optimized for mobile
# =============================================================================

st.markdown("""
<style>
    /* Mobile-first responsive design */
    @media screen and (max-width: 768px) {
        .main-header {
            padding: 1.5rem 1rem !important;
            margin-bottom: 1.5rem !important;
        }
        
        .main-header h1 {
            font-size: 1.8rem !important;
        }
        
        .main-header p {
            font-size: 1rem !important;
        }
        
        /* Adjust padding for mobile */
        .stApp {
            padding: 0.5rem !important;
        }
        
        /* Make columns stack on mobile */
        .stColumn {
            margin-bottom: 1rem;
        }
        
        /* Form elements mobile optimization */
        .stTextInput input, 
        .stTextArea textarea,
        .stSelectbox select {
            font-size: 16px !important; /* Prevents zoom on iOS */
        }
        
        /* Button sizing */
        .stButton button {
            width: 100% !important;
            margin: 5px 0 !important;
            padding: 12px !important;
            font-size: 1rem !important;
        }
        
        /* Metric cards */
        .stMetric {
            margin: 5px 0 !important;
            padding: 0.75rem !important;
        }
        
        /* Tab optimization */
        .stTabs [data-baseweb="tab-list"] {
            flex-wrap: wrap;
        }
        
        .stTabs [data-baseweb="tab"] {
            padding: 8px 12px !important;
            font-size: 0.9rem !important;
        }
    }
    
    /* General mobile-friendly styles */
    html {
        font-size: 16px;
    }
    
    /* Remove white background from sidebar */
    [data-testid="stSidebar"] {
        background-color: transparent;
        min-width: 280px !important;
        max-width: 350px !important;
    }
    
    /* Sidebar mobile optimization */
    @media screen and (max-width: 768px) {
        [data-testid="stSidebar"] {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 100% !important;
        }
    }
    
    /* Main header styling */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        text-align: center;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .main-header h1 {
        font-size: 2.5rem;
        margin: 0;
        font-weight: 700;
        color: white;
    }
    
    .main-header p {
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
        opacity: 0.95;
        color: white;
    }
    
    /* Fix sidebar text visibility */
    .stRadio label {
        color: inherit !important;
        font-size: 0.95rem !important;
    }
    
    .stSelectbox label {
        color: inherit !important;
        font-size: 0.95rem !important;
    }
    
    /* Metric cards */
    .stMetric {
        background: rgba(255, 255, 255, 0.05);
        padding: 1rem;
        border-radius: 8px;
        margin: 5px;
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.2);
    }
    
    /* Form optimization */
    .stForm {
        padding: 1rem !important;
    }
    
    /* Text area optimization */
    .stTextArea textarea {
        min-height: 120px !important;
        resize: vertical !important;
    }
    
    /* Select box optimization */
    .stSelectbox div[data-baseweb="select"] {
        padding: 8px !important;
    }
    
    /* Radio button optimization */
    .stRadio > div {
        flex-direction: column !important;
        gap: 8px !important;
    }
    
    .stRadio label {
        margin-bottom: 0 !important;
    }
    
    /* Better mobile spacing */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 5rem !important;
    }
    
    /* Mobile hamburger menu */
    .st-emotion-cache-1v0mbdj {
        position: fixed !important;
        top: 10px !important;
        right: 10px !important;
        z-index: 1000 !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE INITIALIZATION - No changes needed
# =============================================================================

def init_session_state():
    """Initialize all session state variables"""
    defaults = {
        'api_key': None,
        'analysis_history': [],
        'usage_stats': {
            'total_reports': 0,
            'total_cost': 0.0,
            'total_tokens': 0,
        },
        'demo_mode': True,
        'current_analysis': None,
        'settings': {
            'temperature': 0.1,
            'max_tokens': 2000,
        }
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# =============================================================================
# DEEPSEEK API CLIENT - No changes needed
# =============================================================================

class DeepSeekClient:
    """DeepSeek API client for analysis"""
    # [Keep all existing DeepSeekClient code exactly as is]
    # ... (all existing code remains unchanged)

# =============================================================================
# UI COMPONENTS - Optimized for mobile
# =============================================================================

def render_header():
    """Render application header with mobile menu"""
    # Mobile menu button
    col1, col2, col3 = st.columns([1, 6, 1])
    with col3:
        if st.button("☰", key="mobile_menu", help="Menu"):
            st.session_state.show_menu = not st.session_state.get('show_menu', False)
    
    # Header
    st.markdown("""
    <div class="main-header">
        <h1>🛡️ Compliance Sentinel</h1>
        <p>Professional HSE & Compliance Analysis Platform</p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    """Render sidebar with configuration - optimized for mobile"""
    with st.sidebar:
        # Close button for mobile
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("✕", key="close_sidebar"):
                st.session_state.show_menu = False
        
        st.markdown("## ⚙️ Configuration")
        
        # Mode selection - vertical layout for mobile
        mode = st.radio(
            "Operating Mode:",
            ["🎯 Demo Mode (Free)", "🔑 API Mode (Live)"],
            horizontal=False,  # Changed to vertical for mobile
            help="Demo mode uses simulated responses. API mode requires DeepSeek API key."
        )
        st.session_state.demo_mode = (mode == "🎯 Demo Mode (Free)")
        
        # API key input
        if not st.session_state.demo_mode:
            st.markdown("### 🔐 API Key")
            api_key = st.text_input(
                "DeepSeek API Key:",
                type="password",
                placeholder="sk-...",
                value=st.session_state.api_key or "",
                help="Get your API key from https://platform.deepseek.com"
            )
            
            if api_key and api_key != st.session_state.api_key:
                st.session_state.api_key = api_key
                st.success("✅ API key updated")
            
            if st.session_state.api_key:
                st.info("🔗 Connected")
        else:
            st.info("💡 Demo mode - using sample data")
        
        st.markdown("---")
        
        # Usage statistics - optimized for mobile
        st.markdown("## 📊 Statistics")
        stats = st.session_state.usage_stats
        
        # Use columns that wrap on mobile
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Reports", stats['total_reports'], help="Total reports generated")
        with col2:
            st.metric("Cost", f"${stats['total_cost']:.2f}", help="Total cost of analysis")
        
        if stats['total_reports'] > 0:
            st.metric("Tokens", f"{stats['total_tokens']:,}", help="Total tokens used")
        
        st.markdown("---")
        
        # Analysis type selection
        st.markdown("## 📋 Analysis Type")
        analysis_type = st.selectbox(
            "Select Type:",
            [
                "🚨 Incident Investigation",
                "📋 Compliance Audit",
                "📜 Policy Review",
                "🌱 ESG Assessment"
            ],
            label_visibility="collapsed"
        )
        
        # Advanced settings - collapsed by default on mobile
        if st.session_state.demo_mode == False:
            st.markdown("---")
            with st.expander("⚙️ Advanced Settings", expanded=False):
                st.session_state.settings['temperature'] = st.slider(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.1,
                    step=0.1,
                    help="Lower = more focused, Higher = more creative"
                )
                
                st.session_state.settings['max_tokens'] = st.slider(
                    "Max Tokens",
                    min_value=500,
                    max_value=4000,
                    value=2000,
                    step=100,
                    help="Maximum tokens for response"
                )
        
        return analysis_type

def render_incident_form():
    """Render incident analysis form - mobile optimized"""
    st.markdown("## 🚨 Incident Investigation Report")
    
    with st.form("incident_form", clear_on_submit=False):
        # Single column layout for mobile
        description = st.text_area(
            "Incident Description:",
            height=120,
            placeholder="Describe what happened...",
            help="Include what, where, when, who, and consequences",
            key="incident_desc"
        )
        
        # Mobile-friendly date/time inputs
        col1, col2 = st.columns(2)
        
        with col1:
            severity = st.selectbox(
                "Severity Level:",
                [
                    "1 - Minor (First Aid)",
                    "2 - Moderate (Medical Treatment)",
                    "3 - Serious (Days Away)",
                    "4 - Severe (Permanent Disability)",
                    "5 - Critical (Fatality)"
                ],
                key="incident_severity"
            )
            
            location = st.text_input(
                "Location:",
                placeholder="e.g., Production Floor",
                key="incident_location"
            )
        
        with col2:
            date = st.date_input(
                "Date:",
                datetime.now(),
                key="incident_date"
            )
            
            time = st.time_input(
                "Time:",
                datetime.now().time(),
                key="incident_time"
            )
        
        # Additional fields
        reported_by = st.text_input(
            "Reported By:",
            placeholder="Optional",
            key="incident_reported"
        )
        
        witnesses = st.text_input(
            "Witnesses:",
            placeholder="Optional",
            key="incident_witnesses"
        )
        
        st.markdown("---")
        
        # Mobile-optimized buttons
        submit_col, preview_col = st.columns(2)
        
        with submit_col:
            submit = st.form_submit_button(
                "🚀 Generate Analysis",
                type="primary",
                use_container_width=True
            )
        
        with preview_col:
            preview = st.form_submit_button(
                "👁️ Preview Sample",
                use_container_width=True
            )
        
        if preview:
            return {"preview": True}
        
        if submit:
            if not st.session_state.demo_mode and not st.session_state.api_key:
                st.error("⚠️ Please enter API key or switch to Demo mode")
                return None
            
            if not description or len(description.strip()) < 20:
                st.warning("⚠️ Please provide detailed description (min 20 chars)")
                return None
            
            if not location:
                st.warning("⚠️ Please specify location")
                return None
            
            return {
                "type": "incident",
                "description": description,
                "severity": severity,
                "location": location,
                "date": date.strftime('%Y-%m-%d'),
                "time": time.strftime('%H:%M'),
                "reported_by": reported_by,
                "witnesses": witnesses
            }
    
    return None

def render_audit_form():
    """Render compliance audit form - mobile optimized"""
    st.markdown("## 📋 Compliance Audit")
    
    with st.form("audit_form", clear_on_submit=False):
        # Single column for mobile
        organization = st.text_input(
            "Organization Name:",
            placeholder="e.g., Acme Manufacturing Inc.",
            key="audit_org"
        )
        
        standards = st.multiselect(
            "Standards/Frameworks:",
            [
                "ISO 9001:2015 (Quality)",
                "ISO 14001:2015 (Environmental)",
                "ISO 45001:2018 (OH&S)",
                "ISO 27001:2022 (Information Security)",
                "ISO 50001:2018 (Energy)",
                "OSHA Standards",
                "Other"
            ],
            default=["ISO 45001:2018 (OH&S)"],
            key="audit_standards"
        )
        
        scope = st.selectbox(
            "Audit Scope:",
            [
                "Full System Audit",
                "Surveillance Audit",
                "Re-certification Audit",
                "Specific Process Audit",
                "Supplier Audit"
            ],
            key="audit_scope"
        )
        
        areas = st.text_area(
            "Areas Reviewed:",
            height=80,
            placeholder="e.g., Production, Maintenance, Quality Control...",
            key="audit_areas"
        )
        
        findings = st.text_area(
            "Key Findings/Observations:",
            height=80,
            placeholder="Describe main audit findings...",
            key="audit_findings"
        )
        
        st.markdown("---")
        
        # Mobile buttons
        submit_col, preview_col = st.columns(2)
        
        with submit_col:
            submit = st.form_submit_button(
                "🚀 Generate Report",
                type="primary",
                use_container_width=True
            )
        
        with preview_col:
            preview = st.form_submit_button(
                "👁️ Preview Sample",
                use_container_width=True
            )
        
        if preview:
            return {"preview": True}
        
        if submit:
            if not st.session_state.demo_mode and not st.session_state.api_key:
                st.error("⚠️ Please enter API key or switch to Demo mode")
                return None
            
            if not organization:
                st.warning("⚠️ Please enter organization name")
                return None
            
            return {
                "type": "audit",
                "organization": organization,
                "standards": ", ".join(standards) if standards else "ISO 45001:2018",
                "scope": scope,
                "areas": areas or "All operational areas",
                "findings": findings or "General audit observations"
            }
    
    return None

def render_policy_form():
    """Render policy review form - mobile optimized"""
    st.markdown("## 📜 Policy Review")
    
    with st.form("policy_form", clear_on_submit=False):
        # Single column layout
        policy_name = st.text_input(
            "Policy Name:",
            placeholder="e.g., Workplace Safety Policy",
            key="policy_name"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            policy_type = st.selectbox(
                "Policy Type:",
                [
                    "Health & Safety",
                    "Environmental",
                    "Quality",
                    "Human Resources",
                    "Data Privacy",
                    "Ethics & Compliance",
                    "Other"
                ],
                key="policy_type"
            )
        
        with col2:
            industry = st.text_input(
                "Industry:",
                placeholder="e.g., Manufacturing",
                key="policy_industry"
            )
        
        jurisdiction = st.text_input(
            "Jurisdiction:",
            placeholder="e.g., United States, California",
            key="policy_jurisdiction"
        )
        
        col3, col4 = st.columns(2)
        with col3:
            version = st.text_input(
                "Current Version:",
                placeholder="e.g., 2.1",
                key="policy_version"
            )
        
        with col4:
            last_updated = st.date_input(
                "Last Updated:",
                datetime.now() - timedelta(days=365),
                key="policy_last_updated"
            )
        
        content = st.text_area(
            "Policy Content/Summary:",
            height=150,
            placeholder="Paste policy content or provide summary of key provisions...",
            key="policy_content"
        )
        
        st.markdown("---")
        
        # Mobile buttons
        submit_col, preview_col = st.columns(2)
        
        with submit_col:
            submit = st.form_submit_button(
                "🚀 Generate Review",
                type="primary",
                use_container_width=True
            )
        
        with preview_col:
            preview = st.form_submit_button(
                "👁️ Preview Sample",
                use_container_width=True
            )
        
        if preview:
            return {"preview": True}
        
        if submit:
            if not st.session_state.demo_mode and not st.session_state.api_key:
                st.error("⚠️ Please enter API key or switch to Demo mode")
                return None
            
            if not policy_name:
                st.warning("⚠️ Please enter policy name")
                return None
            
            if not content or len(content.strip()) < 50:
                st.warning("⚠️ Please provide policy content/summary (min 50 chars)")
                return None
            
            return {
                "type": "policy",
                "policy_name": policy_name,
                "policy_type": policy_type,
                "industry": industry or "General",
                "jurisdiction": jurisdiction or "United States",
                "version": version,
                "last_updated": last_updated.strftime('%Y-%m-%d'),
                "content": content
            }
    
    return None

def render_esg_form():
    """Render ESG assessment form - mobile optimized"""
    st.markdown("## 🌱 ESG Assessment")
    
    with st.form("esg_form", clear_on_submit=False):
        # Single column layout
        organization = st.text_input(
            "Organization Name:",
            placeholder="e.g., Acme Industries",
            key="esg_org"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            industry = st.selectbox(
                "Industry Sector:",
                [
                    "Manufacturing",
                    "Energy & Utilities",
                    "Technology",
                    "Financial Services",
                    "Healthcare",
                    "Retail",
                    "Transportation",
                    "Other"
                ],
                key="esg_industry"
            )
        
        with col2:
            period = st.text_input(
                "Reporting Period:",
                placeholder="e.g., FY 2024",
                key="esg_period"
            )
        
        framework = st.multiselect(
            "Reporting Framework:",
            [
                "GRI Standards",
                "SASB",
                "TCFD",
                "CDP",
                "UN Global Compact",
                "Other"
            ],
            default=["GRI Standards"],
            key="esg_framework"
        )
        
        st.markdown("### Performance Data")
        
        # Stack ESG data inputs vertically on mobile
        environmental = st.text_area(
            "**Environmental Data:**",
            height=80,
            placeholder="GHG emissions, energy use, water consumption, waste generation...",
            key="esg_env"
        )
        
        social = st.text_area(
            "**Social Data:**",
            height=80,
            placeholder="Safety stats, diversity metrics, employee satisfaction...",
            key="esg_social"
        )
        
        governance = st.text_area(
            "**Governance Data:**",
            height=80,
            placeholder="Board composition, ethics program, risk management...",
            key="esg_gov"
        )
        
        st.markdown("---")
        
        # Mobile buttons
        submit_col, preview_col = st.columns(2)
        
        with submit_col:
            submit = st.form_submit_button(
                "🚀 Generate Assessment",
                type="primary",
                use_container_width=True
            )
        
        with preview_col:
            preview = st.form_submit_button(
                "👁️ Preview Sample",
                use_container_width=True
            )
        
        if preview:
            return {"preview": True}
        
        if submit:
            if not st.session_state.demo_mode and not st.session_state.api_key:
                st.error("⚠️ Please enter API key or switch to Demo mode")
                return None
            
            if not organization:
                st.warning("⚠️ Please enter organization name")
                return None
            
            return {
                "type": "esg",
                "organization": organization,
                "industry": industry,
                "period": period or "FY 2024",
                "framework": ", ".join(framework) if framework else "GRI Standards",
                "environmental": environmental or "Basic environmental data",
                "social": social or "Basic social data",
                "governance": governance or "Basic governance data"
            }
    
    return None

def render_analysis_result(result: Dict[str, Any], input_data: Dict[str, Any]):
    """Render analysis results - mobile optimized"""
    
    if not result.get("success"):
        st.error(f"❌ Analysis Failed: {result.get('analysis', 'Unknown error')}")
        
        with st.expander("🔍 Troubleshooting"):
            st.markdown("""
            **Common Issues:**
            
            1. **Invalid API Key**: Verify your DeepSeek API key
            2. **Network Error**: Check internet connection
            3. **Rate Limit**: Wait 60 seconds and try again
            4. **Timeout**: Simplify input or try again
            
            **Solutions:**
            - Switch to Demo Mode to test
            - Verify API key at platform.deepseek.com
            - Check API credits balance
            """)
        return
    
    # Update statistics
    st.session_state.usage_stats['total_reports'] += 1
    st.session_state.usage_stats['total_cost'] += result.get('cost', 0.0)
    st.session_state.usage_stats['total_tokens'] += result.get('tokens_used', 0)
    
    # Add to history
    st.session_state.analysis_history.append({
        "timestamp": datetime.now().isoformat(),
        "type": input_data.get('type', 'unknown'),
        "cost": result.get('cost', 0.0),
        "tokens": result.get('tokens_used', 0),
        "model": result.get('model', 'N/A')
    })
    
    # Success message - stacked on mobile
    st.success("✅ Analysis Complete!")
    
    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
    with metrics_col1:
        st.metric("Tokens", f"{result.get('tokens_used', 0):,}")
    with metrics_col2:
        st.metric("Cost", f"${result.get('cost', 0):.4f}")
    with metrics_col3:
        st.metric("Model", result.get('model', 'N/A')[:10])
    
    # Tabs - optimized for mobile
    tab1, tab2, tab3 = st.tabs(["📄 Report", "📊 Analytics", "💾 Export"])
    
    with tab1:
        st.markdown("### Analysis Report")
        # Add scrollable container for report
        report_container = st.container(height=500)
        with report_container:
            st.markdown(result.get('analysis', 'No analysis available'))
    
    with tab2:
        render_analytics_tab()
    
    with tab3:
        render_export_tab(result, input_data)

def render_analytics_tab():
    """Render analytics dashboard - mobile optimized"""
    
    st.markdown("### 📊 Usage Analytics")
    
    if not st.session_state.analysis_history:
        st.info("📈 No analysis history yet. Generate reports to see analytics!")
        return
    
    df = pd.DataFrame(st.session_state.analysis_history)
    
    # Summary metrics - stacked on mobile
    metrics_col1, metrics_col2 = st.columns(2)
    
    with metrics_col1:
        st.metric("Total Reports", len(df))
        st.metric("Avg Cost", f"${df['cost'].mean():.4f}")
    
    with metrics_col2:
        st.metric("Total Cost", f"${df['cost'].sum():.2f}")
        st.metric("Total Tokens", f"{df['tokens'].sum():,}")
    
    st.markdown("---")
    
    # Charts - full width on mobile
    st.markdown("#### Reports by Type")
    type_counts = df['type'].value_counts()
    fig1 = px.pie(
        values=type_counts.values, 
        names=type_counts.index, 
        title='Analysis Type Distribution'
    )
    fig1.update_layout(height=300)
    st.plotly_chart(fig1, use_container_width=True)
    
    st.markdown("#### Cost by Type")
    cost_by_type = df.groupby('type')['cost'].sum()
    fig2 = px.bar(
        x=cost_by_type.index, 
        y=cost_by_type.values, 
        title='Total Cost by Type',
        labels={'x': 'Type', 'y': 'Cost ($)'}
    )
    fig2.update_layout(height=300)
    st.plotly_chart(fig2, use_container_width=True)
    
    # History table
    st.markdown("---")
    st.markdown("#### Recent Reports")
    
    display_df = df.copy()
    display_df['timestamp'] = pd.to_datetime(display_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
    display_df['cost'] = display_df['cost'].apply(lambda x: f"${x:.4f}")
    
    # Use container for scrollable table on mobile
    table_container = st.container(height=300)
    with table_container:
        st.dataframe(
            display_df[['timestamp', 'type', 'tokens', 'cost']].tail(10),
            use_container_width=True,
            hide_index=True
        )

def render_export_tab(result: Dict[str, Any], input_data: Dict[str, Any]):
    """Render export options - mobile optimized"""
    
    st.markdown("### 💾 Export Options")
    
    # Text export
    export_text = f"""
================================================================================
COMPLIANCE SENTINEL - {input_data.get('type', 'ANALYSIS').upper()} REPORT
================================================================================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Model: {result.get('model', 'N/A')}

--------------------------------------------------------------------------------
METADATA
--------------------------------------------------------------------------------
Tokens Used: {result.get('tokens_used', 0):,}
Analysis Cost: ${result.get('cost', 0):.4f}

================================================================================
ANALYSIS REPORT
================================================================================

{result.get('analysis', 'No analysis available')}

================================================================================
END OF REPORT
================================================================================
"""
    
    # Stack download buttons vertically on mobile
    st.download_button(
        label="📥 Download TXT Report",
        data=export_text,
        file_name=f"{input_data.get('type', 'report')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain",
        use_container_width=True
    )
    
    # JSON export
    json_data = {
        "metadata": {
            "generated": datetime.now().isoformat(),
            "tokens": result.get('tokens_used', 0),
            "cost": result.get('cost', 0),
            "type": input_data.get('type', 'unknown')
        },
        "input": input_data,
        "analysis": result.get('analysis', '')
    }
    
    st.download_button(
        label="📥 Download JSON Data",
        data=json.dumps(json_data, indent=2),
        file_name=f"{input_data.get('type', 'report')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        use_container_width=True
    )
    
    # Preview
    st.markdown("---")
    with st.expander("👁️ Preview Export", expanded=False):
        preview_container = st.container(height=200)
        with preview_container:
            st.code(export_text[:500] + "..." if len(export_text) > 500 else export_text)

# =============================================================================
# MAIN APPLICATION - Mobile optimized
# =============================================================================

def main():
    """Main application with mobile optimization"""
    
    # Initialize
    init_session_state()
    
    # Initialize mobile menu state
    if 'show_menu' not in st.session_state:
        st.session_state.show_menu = False
    
    # Main layout
    if st.session_state.show_menu:
        # Show sidebar as main content on mobile
        with st.container():
            analysis_type = render_sidebar()
    else:
        # Show header and main content
        render_header()
        
        # Get analysis type from URL params or default
        analysis_type = st.selectbox(
            "Select Analysis Type:",
            [
                "🚨 Incident Investigation",
                "📋 Compliance Audit",
                "📜 Policy Review",
                "🌱 ESG Assessment"
            ],
            label_visibility="collapsed"
        )
    
    # Show menu toggle on mobile
    if not st.session_state.show_menu:
        col1, col2 = st.columns([6, 1])
        with col2:
            if st.button("⚙️", key="show_menu_btn", help="Open Settings"):
                st.session_state.show_menu = True
                st.rerun()
    
    # Main content - route to appropriate form
    if not st.session_state.show_menu:
        if "Incident" in analysis_type:
            form_data = render_incident_form()
            prompt_type = "incident"
        
        elif "Audit" in analysis_type:
            form_data = render_audit_form()
            prompt_type = "audit"
        
        elif "Policy" in analysis_type:
            form_data = render_policy_form()
            prompt_type = "policy"
        
        elif "ESG" in analysis_type:
            form_data = render_esg_form()
            prompt_type = "esg"
        
        else:
            form_data = None
            prompt_type = "incident"
        
        # Process form submission
        if form_data:
            if form_data.get("preview"):
                st.info(f"### 📋 Sample {analysis_type} Preview")
                
                client = DeepSeekClient("demo")
                result = client.get_demo_response(prompt_type, form_data)
                
                with st.expander("👁️ View Sample Report", expanded=True):
                    preview_container = st.container(height=400)
                    with preview_container:
                        st.markdown(result.get('analysis', '')[:2000] + "\n\n*[Truncated for preview]*")
            
            else:
                with st.spinner(f"🔍 Generating {analysis_type}..."):
                    api_key = st.session_state.api_key if not st.session_state.demo_mode else "demo"
                    client = DeepSeekClient(api_key)
                    
                    result = client.analyze(prompt_type, form_data)
                    
                    render_analysis_result(result, form_data)
    
    # Footer
    if not st.session_state.show_menu:
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; padding: 1rem; color: #666; font-size: 0.9rem;'>
            <p><strong>Compliance Sentinel</strong> | Professional HSE & Compliance Analysis</p>
            <p>Powered by DeepSeek AI | v2.0 Mobile</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
