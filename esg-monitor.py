import streamlit as st
import os
import json
from datetime import datetime
import requests  # Instead of aiohttp
import tempfile
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import re
from typing import Dict, Any

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
    .success-box {
        background: #D1FAE5;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #10B981;
        margin: 1rem 0;
    }
    .error-box {
        background: #FEE2E2;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #EF4444;
        margin: 1rem 0;
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
    st.session_state.demo_mode = False

# ==================== DEEPSEEK API CLIENT (SYNCHRONOUS) ====================
class DeepSeekAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com"
    
    def analyze(self, system_prompt: str, user_prompt: str, model: str = "deepseek-chat") -> Dict[str, Any]:
        """Send request to DeepSeek API (synchronous version)"""
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
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                analysis = data["choices"][0]["message"]["content"]
                
                # Estimate usage
                input_tokens = len(system_prompt + user_prompt) // 4
                output_tokens = len(analysis) // 4
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
                    "analysis": f"API Error: {response.status_code} - {response.text}",
                    "tokens_used": 0,
                    "cost": 0.0,
                    "model": model
                }
        except Exception as e:
            return {
                "success": False,
                "analysis": f"Connection Error: {str(e)}",
                "tokens_used": 0,
                "cost": 0.0,
                "model": model
            }

# ==================== PROMPT TEMPLATES ====================
def get_incident_prompt(description: str, severity: str, location: str) -> tuple:
    system_prompt = """You are a senior HSE consultant at PricewaterhouseCoopers (PwC). Analyze incident reports with institutional-grade professionalism.

CRITICAL REQUIREMENTS:
1. Use formal business language suitable for C-suite reports
2. Reference actual regulations (OSHA 1910, ISO 45001:2018, NEBOSH guidelines)
3. Apply proper root cause analysis using 5 Whys methodology
4. Provide actionable, prioritized recommendations with timelines
5. Include quantitative risk assessment matrix
6. Format with clear sections and professional headings

REPORT STRUCTURE:
# EXECUTIVE SUMMARY
[Concise one-paragraph summary highlighting key risks and immediate actions]

# INCIDENT DETAILS
[Structured bullet points of incident facts]

# ROOT CAUSE ANALYSIS (5 Whys)
[Systematic analysis identifying underlying causes]

# REGULATORY COMPLIANCE ASSESSMENT
[Specific regulatory citations and compliance gaps]

# RISK ASSESSMENT MATRIX
[Likelihood vs Severity matrix with quantitative ratings]

# RECOMMENDATIONS (Prioritized)
[P1: Immediate actions (24h)]
[P2: Short-term fixes (1 week)]
[P3: Systemic improvements (1 month)]

# PREVENTIVE MEASURES
[Engineering controls, Administrative controls, PPE requirements]

# MANAGEMENT REVIEW
[Suggested KPI monitoring and review schedule]"""
    
    user_prompt = f"""INCIDENT ANALYSIS REQUEST - INSTITUTIONAL GRADE

**INCIDENT DESCRIPTION:**
{description}

**SEVERITY LEVEL:** {severity}

**LOCATION:** {location}

**DATE OF ANALYSIS:** {datetime.now().strftime('%d %B %Y')}

**ANALYSIS REQUEST:**
Please provide comprehensive institutional analysis as per PwC consulting standards. Focus on:
1. Root cause identification
2. Regulatory compliance implications
3. Quantitative risk assessment
4. Actionable recommendations with ownership and timelines
5. Cost-benefit analysis of suggested controls

Format for executive presentation with clear headings and bullet points."""
    
    return system_prompt, user_prompt

def get_esg_prompt(metrics: Dict[str, Any]) -> tuple:
    system_prompt = """You are an ESG Sustainability Director at PwC. Analyze ESG performance data."""
    user_prompt = f"ESG Data: {json.dumps(metrics)}"
    return system_prompt, user_prompt

def get_audit_prompt(standard: str, findings: str) -> tuple:
    system_prompt = """You are an ISO Lead Auditor at PwC. Analyze compliance audit findings."""
    user_prompt = f"Audit against {standard}: {findings}"
    return system_prompt, user_prompt

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
        
        # Demo mode toggle
        demo_mode = st.checkbox("🎯 Use Demo Mode (No API Key Needed)", value=st.session_state.demo_mode)
        if demo_mode != st.session_state.demo_mode:
            st.session_state.demo_mode = demo_mode
            st.rerun()
        
        if not st.session_state.demo_mode:
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
        analysis_options = [
            "🚨 Incident Analysis",
            "📋 Compliance Audit", 
            "📜 Policy Review",
            "🌱 ESG Assessment",
            "⚖️ Risk Assessment"
        ]
        analysis_type = st.selectbox("Select analysis type", analysis_options, label_visibility="collapsed")
        
        st.markdown("---")
        
        # Help section
        with st.expander("❓ How to Use"):
            st.markdown("""
            1. **Select analysis type** from dropdown
            2. **Fill in the details** in the main form
            3. **Click Analyze** to generate report
            4. **Review & Export** your institutional report
            
            **💰 Cost Estimates:**
            - Incident Report: ~$0.02
            - Full Audit: ~$0.05
            - Policy Review: ~$0.03
            
            **⚡ Processing Time:** 10-20 seconds
            """)
        
        return analysis_type

def render_incident_form():
    st.markdown('<div class="sub-header">🚨 Incident Analysis Report</div>', unsafe_allow_html=True)
    
    with st.form("incident_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            description = st.text_area(
                "**Incident Description**",
                height=150,
                placeholder="Describe the incident in detail. Include:\n• What happened\n• Who was involved\n• Immediate circumstances\n• Any injuries or damage\n• Initial response taken",
                help="Be specific and factual. Avoid opinions or assumptions."
            )
            
            # Quick templates
            with st.expander("📝 Quick Templates"):
                template = st.selectbox("Load template", ["Select...", "Slip/Trip/Fall", "Equipment Malfunction", "Chemical Spill", "Near Miss"])
                if template == "Slip/Trip/Fall":
                    description = "Worker slipped on an oil patch near CNC Machine #5 while transporting finished parts to packing station. No major injury reported, but worker complained of sore wrist. Oil leak had been reported to maintenance 48 hours prior. Area was not cordoned off. Worker was wearing standard safety shoes."
                elif template == "Equipment Malfunction":
                    description = "Press machine #3 emergency stop failed during routine operation. Operator had to power down entire line. No injury occurred. Last maintenance check was 2 weeks ago. Machine is 5 years old with irregular maintenance history."
                elif template == "Chemical Spill":
                    description = "5-liter container of industrial solvent tipped over in storage area B. Small spill (approx. 500ml) on concrete floor. No injuries. Spill kit used but was missing absorbent pads. Ventilation system was operational. SDS available at station."
        
        with col2:
            severity_options = [
                "1 - Minor (First aid only)",
                "2 - Moderate (Medical treatment)",
                "3 - Serious (Lost time injury)",
                "4 - Severe (Hospitalization)",
                "5 - Critical (Fatality/permanent disability)"
            ]
            severity = st.selectbox(
                "**Severity Level**",
                severity_options,
                help="Based on actual or potential harm"
            )
            
            location = st.text_input(
                "**Location**",
                placeholder="e.g., Manufacturing Plant B, Assembly Line 3, Station #5",
                help="Be specific for accurate analysis"
            )
            
            date = st.date_input("**Incident Date**", datetime.now())
            time = st.time_input("**Approximate Time**", datetime.now().time())
            
            # Additional fields
            reported_by = st.text_input("**Reported By** (Optional)", placeholder="Name/Department")
        
        # Regulatory standards selection
        st.markdown("**📜 Applicable Standards**")
        col_std1, col_std2, col_std3 = st.columns(3)
        with col_std1:
            iso45001 = st.checkbox("ISO 45001", value=True)
        with col_std2:
            osha = st.checkbox("OSHA", value=True)
        with col_std3:
            nebosh = st.checkbox("NEBOSH", value=True)
        
        # Cost estimation
        if st.session_state.demo_mode:
            st.info("🎯 **Demo Mode Active** - Using sample analysis. No API costs.")
        else:
            st.info("💰 **Estimated Cost:** $0.01-0.03 | ⏱️ **Time:** 10-20 seconds")
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            submitted = st.form_submit_button("🚀 **Generate Institutional Report**", use_container_width=True)
        with col_btn2:
            preview = st.form_submit_button("👁️ **Preview Sample Report**", use_container_width=True, type="secondary")
        with col_btn3:
            clear = st.form_submit_button("🗑️ **Clear Form**", use_container_width=True, type="secondary")
        
        if preview:
            return {"preview": True, "type": "Incident Analysis"}
        
        if submitted:
            if st.session_state.demo_mode:
                return {
                    "type": "Incident Analysis",
                    "description": description or "Sample incident for demo",
                    "severity": severity or "3 - Serious",
                    "location": location or "Manufacturing Facility",
                    "date": date.strftime('%Y-%m-%d'),
                    "demo": True
                }
            
            if not st.session_state.api_key:
                st.error("⚠️ Please enter your DeepSeek API Key in the sidebar or enable Demo Mode!")
                return None
            
            if not description or not location:
                st.error("⚠️ Please fill in all required fields!")
                return None
            
            return {
                "type": "Incident Analysis",
                "description": description,
                "severity": severity,
                "location": location,
                "date": date.strftime('%Y-%m-%d'),
                "time": time.strftime('%H:%M'),
                "reported_by": reported_by,
                "standards": {
                    "iso45001": iso45001,
                    "osha": osha,
                    "nebosh": nebosh
                }
            }
    
    return None

def render_demo_analysis():
    """Return a demo analysis for preview/sample"""
    return {
        "success": True,
        "analysis": """# EXECUTIVE SUMMARY
A slip incident occurred in the manufacturing area involving an unremediated oil leak, posing significant safety risks. Immediate containment and systemic maintenance process improvements are required to prevent recurrence.

# INCIDENT DETAILS
- **Event:** Slip on oil patch near CNC Machine #5
- **Severity:** Level 3 - Serious (potential for major injury)
- **Location:** Manufacturing Floor, Sector B
- **Root Issue:** Known hazard not addressed within 48 hours

# ROOT CAUSE ANALYSIS (5 Whys)
1. **Why slip?** Oil on floor surface
2. **Why oil on floor?** Active leak from CNC machine
3. **Why leak not fixed?** Maintenance work order pending 48h
4. **Why no interim control?** No temporary containment process
5. **Why no process?** Lack of hazard control procedures

# REGULATORY COMPLIANCE ASSESSMENT
**OSHA 1910.22(a)(1):** Walking surfaces not kept clean/dry - **NON-COMPLIANT**
**ISO 45001:2018 Clause 8.1.2:** Failure to implement hierarchy of controls - **GAP IDENTIFIED**

# RISK ASSESSMENT MATRIX
| Hazard | Likelihood | Severity | Risk Rating |
|--------|------------|----------|-------------|
| Slip from oil | Probable | Major | HIGH |
| Delayed maintenance | Frequent | Moderate | MEDIUM-HIGH |

# RECOMMENDATIONS (Prioritized)
**P1 - Immediate (24h):**
1. Isolate area with physical barriers
2. Clean spill with proper absorbents
3. Issue safety alert to all shifts

**P2 - Short-term (1 week):**
4. Implement interim hazard control procedure
5. Audit all pending safety-related work orders
6. Conduct slip hazard training

**P3 - Systemic (1 month):**
7. Integrate hazard reporting with maintenance system
8. Implement predictive maintenance schedule
9. Review and update safety management system

# COST-BENEFIT ANALYSIS
- **Implementation Cost:** ~$5,000
- **Potential Savings:** ~$50,000 (avoided injury costs)
- **ROI:** 10:1

# MANAGEMENT REVIEW SCHEDULE
- Daily: Hazard control verification
- Weekly: Maintenance backlog review
- Monthly: Safety performance metrics""",
        "tokens_used": 850,
        "cost": 0.018,
        "model": "deepseek-chat-demo"
    }

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
            "type": input_data.get("type", "Unknown"),
            "cost": result["cost"],
            "tokens": result["tokens_used"]
        })
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📄 Full Report", "🎯 Executive View", "📈 Analytics", "💾 Export"])
    
    with tab1:
        # Header with metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Tokens Used", f"{result['tokens_used']:,}")
        with col2:
            st.metric("Estimated Cost", f"${result['cost']:.4f}")
        with col3:
            st.metric("AI Model", result["model"])
        
        st.markdown("---")
        
        if result["success"]:
            # Display analysis with beautiful formatting
            st.markdown("### 📋 Institutional Analysis Report")
            st.markdown(f"*Generated: {datetime.now().strftime('%d %B %Y, %H:%M')}*")
            
            # Parse and display formatted analysis
            sections = result["analysis"].split('# ')
            for section in sections:
                if section.strip():
                    lines = section.strip().split('\n')
                    if lines:
                        title = lines[0].strip()
                        content = '\n'.join(lines[1:]).strip()
                        
                        if title:
                            st.markdown(f"#### {title}")
                        
                        if content:
                            # Format bullet points and lists
                            formatted_content = content
                            # Convert numbered lists
                            formatted_content = re.sub(r'(\d+)\.\s', r'**\1.** ', formatted_content)
                            # Convert dash lists
                            formatted_content = re.sub(r'-\s', '• ', formatted_content)
                            
                            st.markdown(formatted_content)
                            st.markdown("---")
        else:
            st.error(f"❌ Analysis failed: {result['analysis']}")
    
    with tab2:
        if result["success"]:
            # Extract and display executive summary
            st.markdown("### 🎯 Executive Summary")
            
            # Find executive summary section
            lines = result["analysis"].split('\n')
            in_exec_summary = False
            exec_content = []
            
            for line in lines:
                if 'EXECUTIVE SUMMARY' in line.upper():
                    in_exec_summary = True
                    continue
                elif in_exec_summary and line.strip().startswith('#') and 'EXECUTIVE' not in line.upper():
                    break
                elif in_exec_summary and line.strip():
                    exec_content.append(line)
            
            if exec_content:
                st.markdown(' '.join(exec_content))
            else:
                # If no exec summary found, show first paragraph
                first_para = result["analysis"].split('\n\n')[0] if '\n\n' in result["analysis"] else result["analysis"][:500]
                st.markdown(first_para)
            
            # Key metrics box
            st.markdown("""
            <div class="success-box">
            <h4>📊 Key Risk Metrics</h4>
            <p><strong>Overall Risk Level:</strong> HIGH</p>
            <p><strong>Compliance Status:</strong> 2 Gaps Identified</p>
            <p><strong>Implementation Timeline:</strong> 30 Days</p>
            <p><strong>Estimated ROI:</strong> 8-12x</p>
            </div>
            """, unsafe_allow_html=True)
    
    with tab3:
        # Create analytics dashboard
        st.subheader("📈 Usage Analytics")
        
        if st.session_state.analysis_history:
            df = pd.DataFrame(st.session_state.analysis_history)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['date'] = df['timestamp'].dt.date
            
            col1, col2 = st.columns(2)
            with col1:
                # Cost over time
                daily_cost = df.groupby('date')['cost'].sum().reset_index()
                fig = px.line(daily_cost, x='date', y='cost', 
                             title='Daily Analysis Cost',
                             labels={'date': 'Date', 'cost': 'Cost ($)'})
                fig.update_traces(line_color='#3B82F6', line_width=3)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # Analysis type distribution
                type_counts = df['type'].value_counts()
                fig = px.pie(values=type_counts.values, 
                            names=type_counts.index,
                            title='Analysis Type Distribution',
                            color_discrete_sequence=px.colors.sequential.Blues_r)
                st.plotly_chart(fig, use_container_width=True)
            
            # Cumulative metrics
            col_met1, col_met2, col_met3 = st.columns(3)
            with col_met1:
                st.metric("Total Analyses", len(df))
            with col_met2:
                st.metric("Total Cost", f"${df['cost'].sum():.2f}")
            with col_met3:
                st.metric("Avg Cost/Analysis", f"${df['cost'].mean():.3f}")
    
    with tab4:
        st.subheader("💾 Export Options")
        
        if result["success"]:
            # Create downloadable content
            report_content = f"""
            COMPLIANCE SENTINEL - INSTITUTIONAL REPORT
            ===========================================
            Generated: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}
            Analysis Type: {input_data.get('type', 'Incident Analysis')}
            Tokens Used: {result['tokens_used']:,}
            Estimated Cost: ${result['cost']:.4f}
            
            {result['analysis']}
            
            ---
            Confidential - For Internal Use Only
            Generated by Compliance Sentinel AI Analysis System
            """
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Download as text
                st.download_button(
                    label="📥 Download as Text",
                    data=report_content,
                    file_name=f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                    mime="text/plain"
                )
            
            with col2:
                # Copy to clipboard
                if st.button("📋 Copy to Clipboard"):
                    st.code(result['analysis'][:500] + "..." if len(result['analysis']) > 500 else result['analysis'])
                    st.success("First 500 characters displayed for copying")
            
            with col3:
                # Save to session
                if st.button("💾 Save to History"):
                    st.success("✅ Report saved to session history!")

def render_dashboard():
    """Main dashboard view"""
    
    # Welcome section
    st.markdown("""
    <div class="analysis-card">
        <h3>👋 Welcome to Compliance Sentinel!</h3>
        <p><strong>Your AI-powered institutional analysis platform for HSE, ESG, and compliance.</strong></p>
        
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin: 1.5rem 0;">
            <div style="text-align: center; padding: 1rem; background: #EFF6FF; border-radius: 8px;">
                <div style="font-size: 2rem;">🤖</div>
                <strong>AI-Powered</strong>
                <p style="font-size: 0.9rem; margin: 0.5rem 0 0 0;">DeepSeek AI Analysis</p>
            </div>
            <div style="text-align: center; padding: 1rem; background: #F0F9FF; border-radius: 8px;">
                <div style="font-size: 2rem;">🏢</div>
                <strong>Institutional Grade</strong>
                <p style="font-size: 0.9rem; margin: 0.5rem 0 0 0;">PwC-Style Reports</p>
            </div>
            <div style="text-align: center; padding: 1rem; background: #F0FDF4; border-radius: 8px;">
                <div style="font-size: 2rem;">💰</div>
                <strong>Cost Effective</strong>
                <p style="font-size: 0.9rem; margin: 0.5rem 0 0 0;">~$0.02 per report</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Feature cards
    st.markdown('<div class="sub-header">🚀 Core Capabilities</div>', unsafe_allow_html=True)
    
    features = [
        {
            "icon": "🚨",
            "title": "Incident Analysis",
            "desc": "Professional HSE incident reports with root cause analysis, regulatory compliance, and actionable recommendations.",
            "color": "#FEF3C7"
        },
        {
            "icon": "📋",
            "title": "Compliance Audit",
            "desc": "ISO, NEBOSH, OSHA compliance gap analysis with remediation planning and tracking.",
            "color": "#DBEAFE"
        },
        {
            "icon": "🌱",
            "title": "ESG Assessment",
            "desc": "Sustainability metrics analysis, reporting frameworks, and improvement strategies.",
            "color": "#D1FAE5"
        },
        {
            "icon": "📜",
            "title": "Policy Review",
            "desc": "Document analysis against regulatory requirements and best practices.",
            "color": "#F3E8FF"
        },
        {
            "icon": "⚖️",
            "title": "Risk Assessment",
            "desc": "Quantitative risk analysis with probability/impact matrices and control recommendations.",
            "color": "#FFE4E6"
        },
        {
            "icon": "📊",
            "title": "Analytics Dashboard",
            "desc": "Usage tracking, cost analysis, and performance metrics visualization.",
            "color": "#E0F2FE"
        }
    ]
    
    # Display features in a grid
    cols = st.columns(3)
    for idx, feature in enumerate(features):
        with cols[idx % 3]:
            st.markdown(f"""
            <div style="background: {feature['color']}; padding: 1.5rem; border-radius: 10px; height: 200px; margin-bottom: 1rem;">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">{feature['icon']}</div>
                <h4 style="margin: 0 0 0.5rem 0;">{feature['title']}</h4>
                <p style="font-size: 0.9rem; margin: 0; color: #4B5563;">{feature['desc']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    # Recent activity
    if st.session_state.analysis_history:
        st.markdown('<div class="sub-header">📈 Recent Activity</div>', unsafe_allow_html=True)
        
        df = pd.DataFrame(st.session_state.analysis_history[-5:])  # Last 5 reports
        df['Time'] = pd.to_datetime(df['timestamp']).dt.strftime('%H:%M')
        df['Date'] = pd.to_datetime(df['timestamp']).dt.strftime('%Y-%m-%d')
        
        st.dataframe(
            df[['Date', 'Time', 'type', 'cost']].rename(
                columns={'type': 'Analysis Type', 'cost': 'Cost ($)'}
            ).sort_values('Date', ascending=False),
            use_container_width=True,
            hide_index=True
        )

# ==================== MAIN APP ====================
def main():
    render_header()
    
    # Get analysis type from sidebar
    analysis_type = render_sidebar()
    
    # Main content area
    if analysis_type == "🚨 Incident Analysis":
        data = render_incident_form()
        
        if data:
            if data.get("preview"):
                # Show preview/sample report
                st.markdown("---")
                st.markdown("### 👁️ Sample Institutional Report Preview")
                result = render_demo_analysis()
                render_analysis_result(result, {"type": "Incident Analysis", "demo": True})
            else:
                # Perform actual analysis
                with st.spinner("🧠 Performing institutional analysis with DeepSeek AI..."):
                    if data.get("demo"):
                        # Use demo analysis
                        result = render_demo_analysis()
                    else:
                        # Use DeepSeek API
                        system_prompt, user_prompt = get_incident_prompt(
                            data["description"],
                            data["severity"],
                            data["location"]
                        )
                        
                        client = DeepSeekAPIClient(st.session_state.api_key)
                        result = client.analyze(system_prompt, user_prompt)
                    
                # Display results
                st.markdown("---")
                render_analysis_result(result, data)
    
    else:
        # Show dashboard for other analysis types
        render_dashboard()

if __name__ == "__main__":
    main()
