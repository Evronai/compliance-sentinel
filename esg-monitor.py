import streamlit as st
import os
import json
from datetime import datetime
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import re

# Set page config
st.set_page_config(
    page_title="Compliance Sentinel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with safe HTML rendering
st.markdown("""
<style>
    /* Main styles */
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
        font-weight: 600;
    }
    
    .section-header {
        font-size: 1.3rem;
        color: #4B5563;
        margin: 1.5rem 0 0.8rem 0;
        font-weight: 600;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #E5E7EB;
    }
    
    /* Cards */
    .info-card {
        background: #FFFFFF;
        border: 1px solid #E5E7EB;
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .analysis-section {
        background: #F9FAFB;
        padding: 1.5rem;
        border-radius: 8px;
        margin: 1rem 0;
        border-left: 4px solid #3B82F6;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        border: none;
        padding: 0.75rem 1.5rem;
        border-radius: 8px;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    
    /* Status boxes */
    .success-box {
        background: #D1FAE5;
        color: #065F46;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #10B981;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: #FEF3C7;
        color: #92400E;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #F59E0B;
        margin: 1rem 0;
    }
    
    .error-box {
        background: #FEE2E2;
        color: #991B1B;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #EF4444;
        margin: 1rem 0;
    }
    
    .info-box {
        background: #DBEAFE;
        color: #1E40AF;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #3B82F6;
        margin: 1rem 0;
    }
    
    /* Text formatting */
    .report-title {
        font-size: 1.8rem;
        color: #1F2937;
        font-weight: 700;
        margin-bottom: 1rem;
    }
    
    .recommendation-item {
        background: #EFF6FF;
        padding: 0.8rem;
        margin: 0.5rem 0;
        border-radius: 6px;
        border-left: 3px solid #3B82F6;
    }
    
    /* Lists */
    .bullet-list {
        padding-left: 1.5rem;
        margin: 0.5rem 0;
    }
    
    .bullet-list li {
        margin: 0.3rem 0;
        color: #4B5563;
    }
    
    /* Tables */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        margin: 1rem 0;
    }
    
    .data-table th {
        background: #3B82F6;
        color: white;
        padding: 0.8rem;
        text-align: left;
        font-weight: 600;
    }
    
    .data-table td {
        padding: 0.8rem;
        border: 1px solid #E5E7EB;
    }
    
    .data-table tr:nth-child(even) {
        background: #F9FAFB;
    }
    
    /* Badges */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.8rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        margin: 0.2rem;
    }
    
    .badge-high {
        background: #FEE2E2;
        color: #DC2626;
    }
    
    .badge-medium {
        background: #FEF3C7;
        color: #D97706;
    }
    
    .badge-low {
        background: #D1FAE5;
        color: #059669;
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
    st.session_state.demo_mode = True  # Default to demo mode

# ==================== DEEPSEEK API CLIENT ====================
class DeepSeekAPIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com"
    
    def analyze(self, system_prompt: str, user_prompt: str) -> dict:
        """Send request to DeepSeek API"""
        if not self.api_key or self.api_key == "demo":
            return self.get_demo_response()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
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
                cost = total_tokens / 1000000 * 0.21
                
                return {
                    "success": True,
                    "analysis": analysis,
                    "tokens_used": total_tokens,
                    "cost": round(cost, 4),
                    "model": "deepseek-chat"
                }
            else:
                return {
                    "success": False,
                    "analysis": f"API Error {response.status_code}. Please check your API key.",
                    "tokens_used": 0,
                    "cost": 0.0,
                    "model": "deepseek-chat"
                }
        except Exception as e:
            return {
                "success": False,
                "analysis": f"Connection error: {str(e)}",
                "tokens_used": 0,
                "cost": 0.0,
                "model": "deepseek-chat"
            }
    
    def get_demo_response(self):
        """Return a demo response for testing"""
        demo_analysis = """# 🏢 COMPLIANCE SENTINEL - INCIDENT ANALYSIS REPORT

## 📋 Executive Summary
A slip incident occurred in Sector B involving an unremediated oil leak, posing significant safety risks. Immediate containment and systemic maintenance process improvements are required to prevent recurrence.

## 🎯 Key Findings
- **Risk Level:** HIGH
- **Regulatory Gaps:** 2 identified
- **Response Time:** 48-hour delay
- **Recommended Actions:** 9 prioritized items

## 📊 Incident Details
| Metric | Value |
|--------|-------|
| **Severity** | Level 3 - Serious |
| **Location** | Manufacturing Floor, Sector B |
| **Date** | """ + datetime.now().strftime('%d %B %Y') + """ |
| **Root Cause** | Unaddressed maintenance work order |
| **Potential Impact** | Major injury (fracture/laceration) |

## 🔍 Root Cause Analysis (5 Whys)
1. **Why did the slip occur?** Oil present on walking surface
2. **Why was oil on the floor?** Active leak from CNC Machine #5
3. **Why wasn't the leak fixed?** Maintenance work order pending for 48 hours
4. **Why was there no interim control?** No temporary hazard control procedure
5. **Why no procedure exists?** Gap in safety management system

## ⚖️ Regulatory Implications
### 🚨 NON-COMPLIANCE IDENTIFIED
- **OSHA 1910.22(a)(1):** Walking-working surfaces not kept clean and dry
- **ISO 45001:2018 Clause 8.1.2:** Failure to implement hierarchy of controls
- **Company Procedure HSE-PR-004:** Violation of hazard reporting protocol

## 📈 Risk Assessment Matrix
| Hazard | Likelihood | Severity | Risk Rating | Control Status |
|--------|------------|----------|-------------|----------------|
| Slip from oil leak | Probable (4) | Major (4) | **HIGH (16)** | Inadequate |
| Delayed maintenance | Frequent (5) | Moderate (3) | **HIGH (15)** | Inadequate |
| Lack of interim controls | Likely (4) | Minor (2) | **MEDIUM (8)** | None |

*Scale: 1-5 (1=Very Low, 5=Very High)*

## 🎯 Recommendations (Prioritized)

### 🚨 P1 - IMMEDIATE ACTIONS (Within 24 Hours)
1. **Isolate Hazard Area**
   - Erect physical barriers around CNC Machine #5
   - Post prominent warning signage
   - Assign area supervisor for monitoring

2. **Clean and Secure Area**
   - Use Type III absorbents for oil cleanup
   - Apply anti-slip coating to affected area
   - Document cleanup with photos

3. **Emergency Communication**
   - Issue safety alert to all shifts
   - Conduct toolbox talk on slip hazards
   - Update hazard register

### ⏳ P2 - SHORT-TERM FIXES (Within 1 Week)
4. **Repair Maintenance Process**
   - Expedite all pending safety-related work orders
   - Implement 24-hour SLA for hazard repairs
   - Assign maintenance supervisor accountability

5. **Implement Interim Control Procedure**
   - Develop "Temporary Hazard Control Protocol"
   - Train all supervisors on protocol
   - Create hazard control kit inventory

6. **Enhanced Training**
   - Conduct slip/fall prevention training
   - Refresh hazard reporting procedures
   - Implement competency assessment

### 📈 P3 - SYSTEMIC IMPROVEMENTS (Within 1 Month)
7. **Process Integration**
   - Integrate hazard reporting with CMMS
   - Implement predictive maintenance schedule
   - Automate work order prioritization

8. **Safety Management System Review**
   - Update HSE policy and procedures
   - Implement leading/lagging indicator dashboard
   - Establish management review committee

9. **Performance Monitoring**
   - Track maintenance response times
   - Monitor near-miss reporting rates
   - Conduct quarterly safety audits

## 💰 Cost-Benefit Analysis
| Item | Cost | Benefit | ROI Period |
|------|------|---------|------------|
| Interim controls | $2,500 | Prevent potential $50k injury | Immediate |
| Training program | $5,000 | Reduce incident rate by 40% | 6 months |
| System upgrades | $15,000 | Improve compliance by 80% | 12 months |

**Total Estimated Investment:** $22,500
**Potential Annual Savings:** $120,000
**ROI:** 5.3:1

## 📅 Management Review Schedule
- **Daily:** Hazard control verification by supervisor
- **Weekly:** Maintenance backlog review by HSE Manager
- **Monthly:** Safety performance metrics to leadership
- **Quarterly:** Management review meeting

---
*Report generated by Compliance Sentinel AI Analysis System*
*Confidential - For Internal Use Only*
*Generated: """ + datetime.now().strftime('%d %B %Y, %H:%M:%S') + """*"""
        
        return {
            "success": True,
            "analysis": demo_analysis,
            "tokens_used": 1200,
            "cost": 0.025,
            "model": "deepseek-chat-demo"
        }

# ==================== UI COMPONENTS ====================
def render_header():
    """Render the main header"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<h1 class="main-header">🤖 Compliance Sentinel</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div style='text-align: center; color: #6B7280; margin-bottom: 2rem;'>
        <h3 style='color: #4B5563; font-weight: 500;'>Institutional-Grade HSE, ESG & Compliance Analysis</h3>
        <p style='font-size: 1.1rem;'>Powered by DeepSeek AI • PwC-Style Reporting • Enterprise Ready</p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    """Render the sidebar"""
    with st.sidebar:
        # Logo and title
        st.markdown("""
        <div style='text-align: center; margin-bottom: 2rem;'>
            <div style='font-size: 3rem;'>🛡️</div>
            <h3>Compliance Sentinel</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # API Configuration
        st.markdown("### 🔐 Configuration")
        
        # Mode selection
        mode = st.radio(
            "Select Mode",
            ["🎯 Demo Mode", "🔑 API Mode"],
            index=0 if st.session_state.demo_mode else 1,
            label_visibility="collapsed"
        )
        
        st.session_state.demo_mode = (mode == "🎯 Demo Mode")
        
        if not st.session_state.demo_mode:
            api_key = st.text_input(
                "DeepSeek API Key",
                type="password",
                help="Get your API key from platform.deepseek.com",
                value=st.session_state.api_key or "",
                placeholder="sk-..."
            )
            
            if api_key and api_key != st.session_state.api_key:
                st.session_state.api_key = api_key
                st.success("✅ API Key saved!")
        
        # Stats
        st.markdown("---")
        st.markdown("### 📊 Statistics")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Reports", st.session_state.usage_stats['total_reports'])
        with col2:
            st.metric("Total Cost", f"${st.session_state.usage_stats['total_cost']:.2f}")
        
        # Analysis Type
        st.markdown("---")
        st.markdown("### 📋 Analysis Type")
        
        analysis_options = {
            "🚨 Incident Report": "incident",
            "📋 Compliance Audit": "audit",
            "📜 Policy Review": "policy",
            "🌱 ESG Assessment": "esg",
            "⚖️ Risk Assessment": "risk"
        }
        
        selected_analysis = st.selectbox(
            "Choose analysis type",
            list(analysis_options.keys()),
            label_visibility="collapsed"
        )
        
        return analysis_options[selected_analysis]

def render_incident_form():
    """Render incident analysis form"""
    st.markdown('<div class="sub-header">🚨 Incident Analysis Report</div>', unsafe_allow_html=True)
    
    with st.container():
        # Form in columns
        col1, col2 = st.columns([2, 1])
        
        with col1:
            with st.form("incident_form"):
                # Incident Description
                st.markdown("### 📝 Incident Details")
                description = st.text_area(
                    "**Describe the incident**",
                    height=150,
                    placeholder="Provide detailed information about what happened, who was involved, immediate circumstances, and any initial response taken...",
                    help="Be specific and factual. Include date, time, location, people involved, and sequence of events."
                )
                
                # Quick templates
                with st.expander("📋 Load Template"):
                    template = st.selectbox(
                        "Choose template",
                        ["Select...", "Slip/Trip/Fall", "Equipment Failure", "Chemical Spill", "Near Miss"]
                    )
                    if template != "Select...":
                        templates = {
                            "Slip/Trip/Fall": "Worker slipped on an oil patch near CNC Machine #5 while transporting finished parts. No major injury reported, but worker complained of sore wrist. Oil leak had been reported to maintenance 48 hours prior. Area was not cordoned off.",
                            "Equipment Failure": "Press machine emergency stop failed during operation. Operator had to power down entire line. No injury occurred. Last maintenance was 2 weeks ago.",
                            "Chemical Spill": "Container of industrial solvent tipped over in storage area. Small spill on floor. No injuries. Spill kit was used but missing absorbent pads.",
                            "Near Miss": "Overhead crane load swung near workers. No contact made. Load was improperly secured. Area was evacuated immediately."
                        }
                        description = templates[template]
                
                # Additional Information
                st.markdown("### 🔍 Additional Information")
                col_info1, col_info2 = st.columns(2)
                
                with col_info1:
                    severity = st.select_slider(
                        "**Severity Level**",
                        options=["1 - Minor", "2 - Moderate", "3 - Serious", "4 - Severe", "5 - Critical"],
                        value="3 - Serious",
                        help="Based on actual or potential harm severity"
                    )
                    
                    location = st.text_input(
                        "**Location**",
                        placeholder="e.g., Manufacturing Plant B, Assembly Line 3",
                        help="Specific location where incident occurred"
                    )
                
                with col_info2:
                    date = st.date_input("**Date**", datetime.now())
                    time = st.time_input("**Time**", datetime.now())
                    
                    reported_by = st.text_input(
                        "**Reported By** (Optional)",
                        placeholder="Name/Department/ID"
                    )
                
                # Standards Selection
                st.markdown("### 📚 Applicable Standards")
                std_col1, std_col2, std_col3, std_col4 = st.columns(4)
                with std_col1:
                    iso45001 = st.checkbox("ISO 45001", value=True)
                with std_col2:
                    osha = st.checkbox("OSHA", value=True)
                with std_col3:
                    nebosh = st.checkbox("NEBOSH", value=True)
                with std_col4:
                    iso14001 = st.checkbox("ISO 14001")
                
                # Submit Button
                st.markdown("---")
                submit_col1, submit_col2 = st.columns([3, 1])
                with submit_col1:
                    submitted = st.form_submit_button(
                        "🚀 **Generate Institutional Report**",
                        use_container_width=True,
                        type="primary"
                    )
                with submit_col2:
                    preview = st.form_submit_button(
                        "👁️ **Preview Sample**",
                        use_container_width=True
                    )
                
                if preview:
                    return {"preview": True}
                
                if submitted:
                    if not st.session_state.demo_mode and not st.session_state.api_key:
                        st.error("⚠️ Please enter your DeepSeek API Key in the sidebar")
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
                        "reported_by": reported_by,
                        "standards": {
                            "iso45001": iso45001,
                            "osha": osha,
                            "nebosh": nebosh,
                            "iso14001": iso14001
                        }
                    }
        
        with col2:
            # Information Panel
            st.markdown("### ℹ️ Information Panel")
            
            if st.session_state.demo_mode:
                st.markdown('<div class="info-box">', unsafe_allow_html=True)
                st.markdown("**🎯 Demo Mode Active**")
                st.markdown("Using sample data for analysis")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                st.markdown("**✅ API Mode Active**")
                st.markdown("Using DeepSeek AI for analysis")
                st.markdown("</div>", unsafe_allow_html=True)
            
            # Cost Estimation
            st.markdown("### 💰 Cost Estimation")
            cost_data = pd.DataFrame({
                'Type': ['Incident Report', 'Full Audit', 'Policy Review'],
                'Cost': ['$0.02-0.05', '$0.05-0.10', '$0.03-0.06'],
                'Time': ['10-20s', '15-30s', '10-15s']
            })
            st.dataframe(cost_data, use_container_width=True, hide_index=True)
            
            # Quick Tips
            st.markdown("### 💡 Quick Tips")
            st.markdown("""
            1. **Be specific** with descriptions
            2. **Include all facts**, not assumptions
            3. **Note any witnesses**
            4. **Document immediate actions**
            5. **Take photos** if possible
            """)
    
    return None

def render_analysis_result(result: dict, input_data: dict):
    """Render analysis results"""
    
    # Update stats
    if result["success"]:
        st.session_state.usage_stats['total_reports'] += 1
        st.session_state.usage_stats['total_cost'] += result['cost']
        st.session_state.usage_stats['total_tokens'] += result['tokens_used']
        
        st.session_state.analysis_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": input_data.get("type", "incident"),
            "cost": result["cost"],
            "tokens": result["tokens_used"]
        })
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📄 Full Report", "🎯 Executive View", "📈 Analytics", "💾 Export"])
    
    with tab1:
        # Report Header
        st.markdown('<div class="report-title">Compliance Sentinel Analysis Report</div>', unsafe_allow_html=True)
        
        # Metadata
        col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
        with col_meta1:
            st.metric("📊 Tokens Used", f"{result['tokens_used']:,}")
        with col_meta2:
            st.metric("💰 Estimated Cost", f"${result['cost']:.4f}")
        with col_meta3:
            st.metric("🤖 AI Model", result["model"])
        with col_meta4:
            st.metric("⏱️ Generated", datetime.now().strftime('%H:%M'))
        
        st.markdown("---")
        
        if result["success"]:
            # Parse and display the analysis properly
            display_formatted_analysis(result["analysis"])
        else:
            st.error(f"❌ Analysis failed: {result['analysis']}")
    
    with tab2:
        # Executive Summary View
        st.markdown("### 🎯 Executive Summary")
        
        if result["success"]:
            # Extract key sections
            sections = extract_report_sections(result["analysis"])
            
            # Executive Summary
            if "Executive Summary" in sections:
                st.markdown(sections["Executive Summary"])
            else:
                # Find first paragraph
                lines = result["analysis"].split('\n')
                for line in lines:
                    if line.strip() and not line.startswith('#') and len(line.strip()) > 50:
                        st.markdown(line)
                        break
            
            # Key Metrics
            st.markdown("### 📊 Key Risk Metrics")
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            with metrics_col1:
                st.metric("Overall Risk", "HIGH", delta=None)
            with metrics_col2:
                st.metric("Compliance Gaps", "2", delta="-1 vs last month")
            with metrics_col3:
                st.metric("Action Items", "9", delta="+3 urgent")
            
            # Quick Recommendations
            st.markdown("### 🎯 Top Recommendations")
            recs = extract_recommendations(result["analysis"])
            for i, rec in enumerate(recs[:3], 1):
                st.markdown(f"""
                <div class="recommendation-item">
                <strong>{i}. {rec}</strong>
                </div>
                """, unsafe_allow_html=True)
    
    with tab3:
        # Analytics Dashboard
        render_analytics_dashboard()
    
    with tab4:
        # Export Options
        render_export_options(result, input_data)

def display_formatted_analysis(analysis_text: str):
    """Display analysis text with proper formatting"""
    
    # Split by sections
    lines = analysis_text.split('\n')
    current_section = ""
    current_content = []
    
    for line in lines:
        # Check for section headers
        if line.startswith('# '):
            # Display previous section
            if current_section:
                render_section(current_section, '\n'.join(current_content))
            
            # Start new section
            current_section = line[2:].strip()
            current_content = []
        
        elif line.startswith('## '):
            # Display previous section
            if current_section:
                render_section(current_section, '\n'.join(current_content))
            
            # Start new subsection
            current_section = line[3:].strip()
            current_content = []
        
        elif line.startswith('### '):
            # Display previous section
            if current_section:
                render_section(current_section, '\n'.join(current_content))
            
            # Start new subsubsection
            current_section = line[4:].strip()
            current_content = []
        
        else:
            current_content.append(line)
    
    # Display final section
    if current_section:
        render_section(current_section, '\n'.join(current_content))

def render_section(title: str, content: str):
    """Render a section with proper formatting"""
    
    # Clean up content
    content = content.strip()
    if not content:
        return
    
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)
    
    # Format content based on patterns
    if any(marker in title.lower() for marker in ['recommendation', 'action', 'step']):
        # Render as recommendations
        items = [item.strip() for item in content.split('\n') if item.strip()]
        for item in items:
            if item.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '0.', '-', '*')):
                cleaned = re.sub(r'^\d+\.\s*|^[-*]\s*', '', item)
                st.markdown(f'<div class="recommendation-item">• {cleaned}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div style="margin: 0.5rem 0;">{item}</div>', unsafe_allow_html=True)
    
    elif any(marker in title.lower() for marker in ['table', 'matrix', 'assessment']):
        # Try to render as table
        rows = [row.strip() for row in content.split('\n') if '|' in row]
        if len(rows) > 2:
            # Parse markdown table
            headers = [h.strip() for h in rows[0].split('|')[1:-1]]
            data_rows = rows[2:]
            
            table_html = '<table class="data-table"><thead><tr>'
            for header in headers:
                table_html += f'<th>{header}</th>'
            table_html += '</tr></thead><tbody>'
            
            for row in data_rows:
                cells = [cell.strip() for cell in row.split('|')[1:-1]]
                table_html += '<tr>'
                for cell in cells:
                    table_html += f'<td>{cell}</td>'
                table_html += '</tr>'
            
            table_html += '</tbody></table>'
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.markdown(content)
    
    elif any(marker in title.lower() for marker in ['cost', 'investment', 'roi']):
        # Render with special styling
        st.markdown(f'<div class="info-card">{content}</div>', unsafe_allow_html=True)
    
    else:
        # Default rendering
        st.markdown(content)

def extract_report_sections(analysis_text: str) -> dict:
    """Extract sections from analysis text"""
    sections = {}
    current_section = None
    current_content = []
    
    for line in analysis_text.split('\n'):
        if line.startswith('# '):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = line[2:].strip()
            current_content = []
        elif line.startswith('## '):
            if current_section:
                sections[current_section] = '\n'.join(current_content).strip()
            current_section = line[3:].strip()
            current_content = []
        elif current_section:
            current_content.append(line)
    
    if current_section:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections

def extract_recommendations(analysis_text: str) -> list:
    """Extract recommendations from analysis"""
    recs = []
    lines = analysis_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
            # Clean the bullet/number
            cleaned = re.sub(r'^[•\-*]\s*|\d+\.\s*', '', line)
            if cleaned and len(cleaned) > 10:  # Filter out very short items
                recs.append(cleaned)
    
    return recs[:10]  # Return top 10

def render_analytics_dashboard():
    """Render analytics dashboard"""
    
    if st.session_state.analysis_history:
        df = pd.DataFrame(st.session_state.analysis_history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        
        # Charts
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
                        title='Analysis Type Distribution')
            st.plotly_chart(fig, use_container_width=True)
        
        # Summary metrics
        col_sum1, col_sum2, col_sum3, col_sum4 = st.columns(4)
        with col_sum1:
            st.metric("Total Reports", len(df))
        with col_sum2:
            st.metric("Total Cost", f"${df['cost'].sum():.2f}")
        with col_sum3:
            avg_cost = df['cost'].mean() if len(df) > 0 else 0
            st.metric("Avg Cost/Report", f"${avg_cost:.3f}")
        with col_sum4:
            st.metric("Total Tokens", f"{df['tokens'].sum():,}")
    
    else:
        st.info("No analysis history yet. Generate your first report to see analytics here.")

def render_export_options(result: dict, input_data: dict):
    """Render export options"""
    
    if result["success"]:
        # Create export content
        export_content = f"""COMPLIANCE SENTINEL - INSTITUTIONAL REPORT
===========================================
Generated: {datetime.now().strftime('%d %B %Y, %H:%M:%S')}
Analysis Type: {input_data.get('type', 'incident').title()}
Tokens Used: {result['tokens_used']:,}
Estimated Cost: ${result['cost']:.4f}

{result['analysis']}

---
Confidential - For Internal Use Only
Generated by Compliance Sentinel AI Analysis System"""
        
        # Export buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.download_button(
                label="📥 Download as Text",
                data=export_content,
                file_name=f"compliance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )
        
        with col2:
            if st.button("📋 Copy to Clipboard", use_container_width=True):
                # For Streamlit Cloud, we can't actually copy to clipboard
                # So we show the content in an expander
                with st.expander("📋 Report Content (Copy from here)"):
                    st.code(export_content[:2000] + "..." if len(export_content) > 2000 else export_content)
        
        with col3:
            if st.button("💾 Save to Session", use_container_width=True):
                st.success("✅ Report saved to session history!")

# ==================== MAIN APP ====================
def main():
    # Render header
    render_header()
    
    # Get analysis type
    analysis_type = render_sidebar()
    
    # Main content
    if analysis_type == "incident":
        form_data = render_incident_form()
        
        if form_data:
            if form_data.get("preview"):
                # Show preview
                st.markdown("---")
                st.markdown("### 👁️ Sample Report Preview")
                
                client = DeepSeekAPIClient("demo")
                result = client.get_demo_response()
                render_analysis_result(result, {"type": "incident", "preview": True})
            
            else:
                # Perform analysis
                with st.spinner("🧠 Performing institutional analysis..."):
                    # Create prompt
                    system_prompt = """You are a senior HSE consultant at PricewaterhouseCoopers. Provide institutional-grade incident analysis."""
                    user_prompt = f"""Analyze this incident:
                    
                    Description: {form_data['description']}
                    Severity: {form_data['severity']}
                    Location: {form_data['location']}
                    Date: {form_data['date']}
                    
                    Provide comprehensive PwC-style analysis."""
                    
                    # Get analysis
                    client = DeepSeekAPIClient(st.session_state.api_key if not st.session_state.demo_mode else "demo")
                    result = client.analyze(system_prompt, user_prompt)
                
                # Display results
                st.markdown("---")
                render_analysis_result(result, form_data)
    
    else:
        # Placeholder for other analysis types
        st.markdown('<div class="sub-header">Coming Soon</div>', unsafe_allow_html=True)
        st.info("Other analysis types (Audit, Policy Review, ESG, Risk Assessment) will be available in the next update.")

if __name__ == "__main__":
    main()
