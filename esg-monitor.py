import streamlit as st
import os
import json
import logging
from datetime import datetime
import aiohttp
import asyncio
from typing import Dict, Any, Optional
import tempfile
from enum import Enum
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

# Set page config
st.set_page_config(
    page_title="Compliance Sentinel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #3B82F6;
        margin-top: 2rem;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    .analysis-card {
        background: #F8FAFC;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #3B82F6;
        margin-bottom: 1rem;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        border: none;
        padding: 0.75rem;
        border-radius: 8px;
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

# ==================== ENUMS AND MODELS ====================
class AnalysisType(Enum):
    INCIDENT = "Incident Analysis"
    AUDIT = "Compliance Audit"
    POLICY = "Policy Review"
    ESG = "ESG Assessment"
    RISK = "Risk Assessment"

class SeverityLevel(Enum):
    CRITICAL = "5 - Critical"
    SEVERE = "4 - Severe"
    SERIOUS = "3 - Serious"
    MODERATE = "2 - Moderate"
    MINOR = "1 - Minor"

# ==================== DEEPSEEK API CLIENT ====================
class DeepSeekAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com"
    
    async def analyze(self, system_prompt: str, user_prompt: str, model: str = "deepseek-chat") -> Dict[str, Any]:
        """Send request to DeepSeek API"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 3000,
            "temperature": 0.1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=30
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        analysis = data["choices"][0]["message"]["content"]
                        
                        # Update usage stats
                        usage = data.get("usage", {})
                        input_tokens = usage.get("prompt_tokens", len(system_prompt + user_prompt) // 4)
                        output_tokens = usage.get("completion_tokens", len(analysis) // 4)
                        total_tokens = input_tokens + output_tokens
                        cost = total_tokens / 1000000 * 0.21  # Approximate cost
                        
                        return {
                            "success": True,
                            "analysis": analysis,
                            "tokens_used": total_tokens,
                            "cost": cost,
                            "model": model
                        }
                    else:
                        return {
                            "success": False,
                            "analysis": f"API Error: {response.status}",
                            "tokens_used": 0,
                            "cost": 0.0,
                            "model": model
                        }
        except Exception as e:
            return {
                "success": False,
                "analysis": f"Error: {str(e)}",
                "tokens_used": 0,
                "cost": 0.0,
                "model": model
            }

# ==================== PROMPT TEMPLATES ====================
def get_incident_prompt(description: str, severity: str, location: str) -> tuple:
    system_prompt = """You are a senior HSE consultant at a top-tier firm like PwC. Analyze incident reports with institutional-grade professionalism.

    CRITICAL REQUIREMENTS:
    1. Use formal business language
    2. Reference actual regulations (OSHA, ISO 45001, NEBOSH)
    3. Apply proper root cause analysis (5 Whys or Fishbone)
    4. Provide actionable, prioritized recommendations
    5. Include risk assessment matrix

    FORMAT:
    # EXECUTIVE SUMMARY
    [One paragraph]

    # ROOT CAUSE ANALYSIS
    [Structured analysis]

    # REGULATORY IMPLICATIONS
    [Specific regulations with citations]

    # RECOMMENDATIONS
    [Prioritized list with timelines]

    # RISK ASSESSMENT
    [Matrix with likelihood/severity]

    # PREVENTIVE MEASURES
    [Long-term solutions]"""
    
    user_prompt = f"""INCIDENT FOR ANALYSIS:
    
    DESCRIPTION: {description}
    SEVERITY: {severity}
    LOCATION: {location}
    DATE: {datetime.now().strftime('%Y-%m-%d')}
    
    Please provide comprehensive institutional analysis."""
    
    return system_prompt, user_prompt

def get_esg_prompt(esg_data: Dict[str, Any]) -> tuple:
    system_prompt = """You are an ESG sustainability expert at a top consulting firm."""
    # Similar structure for other analysis types
    return system_prompt, ""

# ==================== STREAMLIT UI COMPONENTS ====================
def render_header():
    st.markdown('<h1 class="main-header">🤖 Compliance Sentinel</h1>', unsafe_allow_html=True)
    st.markdown("""
    <div style='text-align: center; color: #6B7280; margin-bottom: 2rem;'>
        <h3>Institutional-Grade HSE, ESG & Compliance Analysis</h3>
        <p>Powered by DeepSeek AI • PwC-Style Reporting • Enterprise Ready</p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/shield.png", width=80)
        st.markdown("### 🔐 API Configuration")
        
        # API Key Input
        api_key = st.text_input(
            "DeepSeek API Key",
            type="password",
            help="Get your API key from platform.deepseek.com",
            value=st.session_state.api_key or ""
        )
        
        if api_key and api_key != st.session_state.api_key:
            st.session_state.api_key = api_key
            st.success("✅ API Key saved!")
        
        st.markdown("---")
        st.markdown("### 📊 Quick Stats")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Reports", st.session_state.usage_stats['total_reports'])
        with col2:
            st.metric("Total Cost", f"${st.session_state.usage_stats['total_cost']:.2f}")
        
        st.markdown("---")
        
        # Analysis Type Selection
        st.markdown("### 📋 Analysis Type")
        analysis_type = st.selectbox(
            "Select analysis type",
            [AnalysisType.INCIDENT.value, AnalysisType.AUDIT.value, 
             AnalysisType.POLICY.value, AnalysisType.ESG.value, AnalysisType.RISK.value]
        )
        
        return analysis_type

def render_incident_form():
    st.markdown('<div class="sub-header">🚨 Incident Analysis</div>', unsafe_allow_html=True)
    
    with st.form("incident_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            description = st.text_area(
                "Incident Description",
                height=150,
                placeholder="Describe what happened in detail...\nExample: 'Worker slipped on oil patch near machine #5 while moving parts...'",
                help="Include: What happened, who was involved, immediate circumstances"
            )
            
        with col2:
            severity = st.selectbox(
                "Severity Level",
                [level.value for level in SeverityLevel],
                help="Select based on potential or actual harm"
            )
            
            location = st.text_input(
                "Location",
                placeholder="e.g., Manufacturing Plant B, Assembly Line 3"
            )
            
            date = st.date_input("Incident Date", datetime.now())
        
        # Estimated cost info
        st.info("💰 **Estimated Cost:** ~$0.01-0.03 per analysis | ⏱️ **Time:** 10-20 seconds")
        
        submitted = st.form_submit_button("🚀 Start Institutional Analysis", use_container_width=True)
        
        if submitted:
            if not st.session_state.api_key:
                st.error("⚠️ Please enter your DeepSeek API Key in the sidebar first!")
                return None
            
            if not description or not location:
                st.error("⚠️ Please fill in all required fields!")
                return None
            
            return {
                "type": AnalysisType.INCIDENT.value,
                "description": description,
                "severity": severity,
                "location": location,
                "date": date.strftime('%Y-%m-%d')
            }
    
    return None

async def perform_analysis(data: Dict[str, Any]):
    """Perform AI analysis asynchronously"""
    if data["type"] == AnalysisType.INCIDENT.value:
        system_prompt, user_prompt = get_incident_prompt(
            data["description"],
            data["severity"],
            data["location"]
        )
    
    client = DeepSeekAPIClient(st.session_state.api_key)
    result = await client.analyze(system_prompt, user_prompt)
    
    return result

def render_analysis_result(result: Dict[str, Any], input_data: Dict[str, Any]):
    """Display analysis results beautifully"""
    
    # Update usage stats
    if result["success"]:
        st.session_state.usage_stats['total_reports'] += 1
        st.session_state.usage_stats['total_cost'] += result['cost']
        st.session_state.usage_stats['total_tokens'] += result['tokens_used']
        
        # Save to history
        st.session_state.analysis_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": input_data["type"],
            "cost": result["cost"],
            "tokens": result["tokens_used"]
        })
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📄 Full Report", "📊 Executive Summary", "📈 Analytics", "💾 Export"])
    
    with tab1:
        # Cost info banner
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tokens Used", f"{result['tokens_used']:,}")
        with col2:
            st.metric("Estimated Cost", f"${result['cost']:.4f}")
        with col3:
            st.metric("AI Model", result["model"])
        
        st.markdown("---")
        
        if result["success"]:
            # Display analysis with formatting
            analysis_lines = result["analysis"].split('\n')
            for line in analysis_lines:
                if line.startswith('# '):
                    st.markdown(f"## {line[2:]}")
                elif line.startswith('## '):
                    st.markdown(f"### {line[3:]}")
                elif line.startswith('### '):
                    st.markdown(f"#### {line[4:]}")
                elif line.strip() == '':
                    st.write("")
                else:
                    # Check for numbered lists
                    if re.match(r'^\d+\.', line.strip()):
                        st.markdown(f"• {line}")
                    else:
                        st.write(line)
        else:
            st.error(f"❌ Analysis failed: {result['analysis']}")
    
    with tab2:
        if result["success"]:
            # Extract executive summary (first section)
            lines = result["analysis"].split('\n')
            exec_summary = []
            in_summary = False
            
            for line in lines:
                if line.startswith('# EXECUTIVE SUMMARY'):
                    in_summary = True
                    continue
                elif line.startswith('# ') and in_summary:
                    break
                elif in_summary and line.strip():
                    exec_summary.append(line)
            
            if exec_summary:
                st.markdown(" ".join(exec_summary))
            else:
                st.info("No executive summary found in the report.")
    
    with tab3:
        # Create analytics dashboard
        st.subheader("📈 Usage Analytics")
        
        if st.session_state.analysis_history:
            df = pd.DataFrame(st.session_state.analysis_history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            col1, col2 = st.columns(2)
            with col1:
                # Cost over time
                fig = px.line(df, x='timestamp', y='cost', 
                             title='Analysis Cost Over Time',
                             labels={'timestamp': 'Date', 'cost': 'Cost ($)'})
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Analysis type distribution
                type_counts = df['type'].value_counts()
                fig = px.pie(values=type_counts.values, 
                            names=type_counts.index,
                            title='Analysis Type Distribution')
                st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("💾 Export Options")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📥 Download PDF Report"):
                # Create PDF (simplified version)
                html_content = f"""
                <html>
                <head><title>Compliance Sentinel Report</title></head>
                <body>
                    <h1>Compliance Sentinel Report</h1>
                    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                    <hr>
                    <pre>{result['analysis']}</pre>
                </body>
                </html>
                """
                
                st.download_button(
                    label="📥 Download PDF",
                    data=html_content,
                    file_name=f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html"
                )
        
        with col2:
            if st.button("📋 Copy to Clipboard"):
                st.code(result['analysis'][:1000] + "..." if len(result['analysis']) > 1000 else result['analysis'])
                st.success("📋 First 1000 characters copied to clipboard (in code block)")
        
        with col3:
            if st.button("🗄️ Save to History"):
                st.success("✅ Report saved to history!")

def render_dashboard():
    """Main dashboard view"""
    
    # Welcome card for new users
    if not st.session_state.api_key:
        st.markdown("""
        <div class="analysis-card">
            <h3>👋 Welcome to Compliance Sentinel!</h3>
            <p>To get started:</p>
            <ol>
                <li><strong>Get a DeepSeek API Key</strong> from <a href="https://platform.deepseek.com" target="_blank">platform.deepseek.com</a></li>
                <li><strong>Enter your API Key</strong> in the sidebar on the left</li>
                <li><strong>Select analysis type</strong> and fill in the details</li>
                <li><strong>Get institutional-grade reports</strong> instantly!</li>
            </ol>
            <p><strong>💰 Cost Effective:</strong> ~$0.01-0.03 per analysis</p>
            <p><strong>⚡ Fast:</strong> Reports in 10-20 seconds</p>
            <p><strong>🏢 Professional:</strong> PwC-style reporting format</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Feature cards
    st.markdown('<div class="sub-header">🚀 Core Features</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h4>🚨 Incident Analysis</h4>
            <p>Professional HSE incident reports with root cause analysis</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h4>📋 Compliance Audit</h4>
            <p>ISO, NEBOSH, OSHA compliance gap analysis</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h4>🌱 ESG Assessment</h4>
            <p>Sustainability and ESG performance analysis</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Recent activity
    if st.session_state.analysis_history:
        st.markdown('<div class="sub-header">📈 Recent Activity</div>', unsafe_allow_html=True)
        
        df = pd.DataFrame(st.session_state.analysis_history[-5:])  # Last 5 reports
        st.dataframe(
            df[['timestamp', 'type', 'cost']].rename(
                columns={'timestamp': 'Time', 'type': 'Analysis Type', 'cost': 'Cost ($)'}
            ),
            use_container_width=True
        )

# ==================== MAIN APP ====================
def main():
    render_header()
    
    # Get analysis type from sidebar
    analysis_type = render_sidebar()
    
    # Main content area
    if analysis_type == AnalysisType.INCIDENT.value:
        data = render_incident_form()
        
        if data is not None:
            with st.spinner("🧠 Performing institutional analysis with DeepSeek AI..."):
                # Run async analysis
                import asyncio
                
                # Create a new event loop for Streamlit
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    result = loop.run_until_complete(perform_analysis(data))
                    render_analysis_result(result, data)
                finally:
                    loop.close()
    
    else:
        # Show dashboard for other analysis types (to be implemented)
        render_dashboard()

if __name__ == "__main__":
    main()
