import streamlit as st
import os
import json
from datetime import datetime
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import re

# Set page config FIRST
st.set_page_config(
    page_title="Compliance Sentinel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# MINIMAL CSS - Only fix what's broken
st.markdown("""
<style>
    /* FIX: Make all text visible */
    * {
        color: #000000 !important;
    }
    
    /* FIX: Input fields */
    .stTextArea textarea,
    .stTextInput input,
    input[type="text"],
    input[type="password"],
    textarea {
        background-color: white !important;
        color: black !important;
    }
    
    /* FIX: Placeholder text */
    ::placeholder {
        color: #666666 !important;
        opacity: 1 !important;
    }
    
    /* FIX: Labels */
    label, .stMarkdown, p, div, span {
        color: black !important;
    }
    
    /* FIX: Select boxes */
    .stSelectbox div[data-baseweb="select"] {
        background-color: white !important;
    }
    
    /* FIX: Checkboxes */
    .stCheckbox label {
        color: black !important;
    }
    
    /* FIX: Radio buttons */
    .stRadio label {
        color: black !important;
    }
    
    /* Simple styling for better UI */
    .main-header {
        text-align: center;
        padding: 20px 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        margin-bottom: 30px;
        border-radius: 10px;
    }
    
    .metric-card {
        background: #3B82F6;
        padding: 20px;
        border-radius: 10px;
        color: white !important;
        margin: 10px 0;
    }
    
    .info-box {
        background: #DBEAFE;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #3B82F6;
    }
    
    .warning-box {
        background: #FEF3C7;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        border-left: 4px solid #F59E0B;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'api_key' not in st.session_state:
    st.session_state.api_key = None
if 'analysis_history' not in st.session_state:
    st.session_state.analysis_history = []
if 'usage_stats' not in st.session_state:
    st.session_state.usage_stats = {
        'total_reports': 0,
        'total_cost': 0.0,
        'total_tokens': 0
    }
if 'demo_mode' not in st.session_state:
    st.session_state.demo_mode = True
if 'current_analysis' not in st.session_state:
    st.session_state.current_analysis = None

# ==================== SIMPLE DEEPSEEK CLIENT ====================
class DeepSeekClient:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com"
    
    def analyze(self, prompt_type, data):
        """Simple analysis method"""
        if not self.api_key or self.api_key == "demo":
            return self.get_demo_response()
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            system_prompt = self.get_system_prompt(prompt_type)
            user_prompt = self.get_user_prompt(prompt_type, data)
            
            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "max_tokens": 2000,
                "temperature": 0.1
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis = result["choices"][0]["message"]["content"]
                
                # Simple token estimation
                tokens = len(analysis) // 4
                cost = tokens / 1000000 * 0.21
                
                return {
                    "success": True,
                    "analysis": analysis,
                    "tokens_used": tokens,
                    "cost": round(cost, 4),
                    "model": "deepseek-chat"
                }
            else:
                return {
                    "success": False,
                    "analysis": f"API Error: {response.status_code}",
                    "tokens_used": 0,
                    "cost": 0.0,
                    "model": "deepseek-chat"
                }
                
        except Exception as e:
            return {
                "success": False,
                "analysis": f"Error: {str(e)}",
                "tokens_used": 0,
                "cost": 0.0,
                "model": "deepseek-chat"
            }
    
    def get_system_prompt(self, prompt_type):
        """Get system prompt based on type"""
        prompts = {
            "incident": """You are a senior HSE consultant at PricewaterhouseCoopers (PwC). 
            Provide institutional-grade incident analysis with:
            1. Executive summary
            2. Root cause analysis (5 Whys)
            3. Regulatory implications
            4. Risk assessment
            5. Recommendations (prioritized)
            6. Cost-benefit analysis
            Use professional business language.""",
            
            "audit": """You are an ISO Lead Auditor at PwC. Analyze compliance gaps.""",
            
            "policy": """You are a policy compliance expert at PwC. Review policy documents.""",
            
            "esg": """You are an ESG Sustainability Director at PwC. Analyze ESG performance."""
        }
        return prompts.get(prompt_type, prompts["incident"])
    
    def get_user_prompt(self, prompt_type, data):
        """Get user prompt based on type"""
        if prompt_type == "incident":
            return f"""INCIDENT ANALYSIS REQUEST:
            
            Description: {data.get('description', 'N/A')}
            Severity: {data.get('severity', 'N/A')}
            Location: {data.get('location', 'N/A')}
            Date: {data.get('date', 'N/A')}
            Time: {data.get('time', 'N/A')}
            
            Provide comprehensive PwC-style analysis."""
        
        return "Please analyze this data."
    
    def get_demo_response(self):
        """Return demo response"""
        demo_report = f"""# 🏢 COMPLIANCE SENTINEL - INCIDENT ANALYSIS REPORT

## 📋 Executive Summary
A slip incident occurred due to an unremediated oil leak, requiring immediate containment and process improvements. Risk level: HIGH.

## 🔍 Root Cause Analysis
1. Why slip? Oil on floor
2. Why oil? Leak from machine
3. Why not fixed? Maintenance delay (48h)
4. Why no control? Missing procedure
5. Why no procedure? System gap

## ⚖️ Regulatory Implications
- OSHA 1910.22(a)(1): Non-compliance
- ISO 45001:2018 Clause 8.1.2: Gap identified

## 📈 Risk Assessment
- Likelihood: Probable (4/5)
- Severity: Major (4/5)
- Risk Rating: HIGH (16/25)

## 🎯 Recommendations
### P1 - Immediate (24h):
1. Isolate area with barriers
2. Clean spill immediately
3. Issue safety alert

### P2 - Short-term (1 week):
4. Audit maintenance backlog
5. Implement interim controls
6. Conduct training

### P3 - Systemic (1 month):
7. Update safety procedures
8. Implement predictive maintenance
9. Review management system

## 💰 Cost-Benefit
- Investment: $22,500
- Annual Savings: $120,000
- ROI: 5.3:1

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*"""
        
        return {
            "success": True,
            "analysis": demo_report,
            "tokens_used": 450,
            "cost": 0.01,
            "model": "deepseek-chat-demo"
        }

# ==================== SIMPLE UI COMPONENTS ====================
def render_header():
    """Simple header"""
    st.markdown("""
    <div class="main-header">
        <h1>🤖 Compliance Sentinel</h1>
        <h3>Institutional-Grade HSE, ESG & Compliance Analysis</h3>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    """Simple sidebar"""
    with st.sidebar:
        st.markdown("## 🔐 Configuration")
        
        # Mode selection
        mode = st.radio("Select Mode:", ["🎯 Demo Mode", "🔑 API Mode"])
        st.session_state.demo_mode = (mode == "🎯 Demo Mode")
        
        if not st.session_state.demo_mode:
            api_key = st.text_input(
                "DeepSeek API Key:",
                type="password",
                placeholder="Enter your API key",
                value=st.session_state.api_key or ""
            )
            if api_key:
                st.session_state.api_key = api_key
        
        st.markdown("---")
        st.markdown("## 📊 Statistics")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Reports", st.session_state.usage_stats['total_reports'])
        with col2:
            st.metric("Cost", f"${st.session_state.usage_stats['total_cost']:.2f}")
        
        st.markdown("---")
        st.markdown("## 📋 Analysis Type")
        
        analysis_type = st.selectbox(
            "Choose:",
            ["🚨 Incident Report", "📋 Compliance Audit", "📜 Policy Review", "🌱 ESG Assessment"]
        )
        
        return analysis_type

def render_incident_form():
    """Simple incident form"""
    st.markdown("## 🚨 Incident Analysis Report")
    
    with st.form("incident_form"):
        # Description
        description = st.text_area(
            "**Incident Description:**",
            height=150,
            placeholder="Describe what happened in detail...",
            help="Include what, where, when, who was involved"
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            severity = st.selectbox(
                "**Severity Level:**",
                ["1 - Minor", "2 - Moderate", "3 - Serious", "4 - Severe", "5 - Critical"]
            )
            
            location = st.text_input(
                "**Location:**",
                placeholder="e.g., Manufacturing Plant B"
            )
        
        with col2:
            date = st.date_input("**Date:**", datetime.now())
            time = st.time_input("**Time:**", datetime.now())
            reported_by = st.text_input("**Reported By:** (Optional)", placeholder="Name/Department")
        
        # Submit buttons
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submit = st.form_submit_button("🚀 Generate Report", type="primary", use_container_width=True)
        with col_btn2:
            preview = st.form_submit_button("👁️ Preview Sample", use_container_width=True)
        
        if preview:
            return {"preview": True}
        
        if submit:
            if not st.session_state.demo_mode and not st.session_state.api_key:
                st.error("⚠️ Please enter your API key in the sidebar")
                return None
            
            if not description or not location:
                st.warning("⚠️ Please fill in all required fields")
                return None
            
            return {
                "type": "incident",
                "description": description,
                "severity": severity,
                "location": location,
                "date": date.strftime('%Y-%m-%d'),
                "time": time.strftime('%H:%M'),
                "reported_by": reported_by
            }
    
    return None

def render_analysis_result(result, input_data):
    """Simple result display"""
    
    if result["success"]:
        # Update stats
        st.session_state.usage_stats['total_reports'] += 1
        st.session_state.usage_stats['total_cost'] += result['cost']
        st.session_state.usage_stats['total_tokens'] += result['tokens_used']
        
        # Save to history
        st.session_state.analysis_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": input_data.get("type", "incident"),
            "cost": result["cost"],
            "tokens": result["tokens_used"]
        })
    
    # Display result
    if result["success"]:
        st.success(f"✅ Analysis complete! (Cost: ${result['cost']:.4f})")
        
        # Create tabs
        tab1, tab2, tab3 = st.tabs(["📄 Report", "📊 Analytics", "💾 Export"])
        
        with tab1:
            # Show the analysis
            st.markdown("### Analysis Report")
            st.markdown(result["analysis"])
            
            # Show metadata
            col1, col2, col3 = st.columns(3)
            with col1:
                st.info(f"**Tokens:** {result['tokens_used']:,}")
            with col2:
                st.info(f"**Cost:** ${result['cost']:.4f}")
            with col3:
                st.info(f"**Model:** {result['model']}")
        
        with tab2:
            render_simple_analytics()
        
        with tab3:
            render_simple_export(result)
    
    else:
        st.error(f"❌ Error: {result['analysis']}")

def render_simple_analytics():
    """Simple analytics"""
    if st.session_state.analysis_history:
        df = pd.DataFrame(st.session_state.analysis_history)
        
        st.markdown("### 📈 Usage Analytics")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Reports", len(df))
            st.metric("Total Cost", f"${df['cost'].sum():.2f}")
        
        with col2:
            avg_cost = df['cost'].mean() if len(df) > 0 else 0
            st.metric("Avg Cost/Report", f"${avg_cost:.3f}")
            st.metric("Total Tokens", f"{df['tokens'].sum():,}")
        
        # Simple chart
        if len(df) > 1:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            daily = df.groupby('date')['cost'].sum().reset_index()
            
            fig = px.line(daily, x='date', y='cost', title='Daily Cost Trend')
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No analysis history yet.")

def render_simple_export(result):
    """Simple export options"""
    st.markdown("### 💾 Export Options")
    
    export_text = f"""COMPLIANCE SENTINEL REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Tokens Used: {result['tokens_used']:,}
Cost: ${result['cost']:.4f}

{result['analysis']}
"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📥 Download Text",
            data=export_text,
            file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col2:
        if st.button("📋 Show for Copying", use_container_width=True):
            st.code(export_text[:1000])

# ==================== MAIN APP ====================
def main():
    # Render header
    render_header()
    
    # Get analysis type
    analysis_type = render_sidebar()
    
    # Main content
    if "Incident" in analysis_type:
        form_data = render_incident_form()
        
        if form_data:
            if form_data.get("preview"):
                st.info("### Sample Report Preview")
                client = DeepSeekClient("demo")
                result = client.get_demo_response()
                render_analysis_result(result, {"preview": True})
            
            else:
                with st.spinner("Analyzing..."):
                    client = DeepSeekClient(
                        st.session_state.api_key if not st.session_state.demo_mode else "demo"
                    )
                    result = client.analyze("incident", form_data)
                
                render_analysis_result(result, form_data)
    
    else:
        st.info(f"**{analysis_type}** analysis coming soon!")
        st.markdown("""
        ### Current Features:
        - 🚨 **Incident Analysis** - Full PwC-style reporting
        - 🤖 **AI-Powered** - DeepSeek AI integration
        - 💰 **Cost Effective** - ~$0.01 per report
        - 📊 **Analytics** - Usage tracking
        - 💾 **Export** - Download reports
        """)

# Run the app
if __name__ == "__main__":
    main()
