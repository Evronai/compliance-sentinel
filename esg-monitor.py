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
# PAGE CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Compliance Sentinel",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================================================================
# CUSTOM CSS
# =============================================================================

st.markdown("""
<style>
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
    }
    
    .main-header p {
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
        opacity: 0.95;
    }
    
    /* Metric cards */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 1rem;
    }
    
    /* Success/Error messages */
    .stAlert {
        border-radius: 8px;
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
    }
    
    /* Form styling */
    .stTextInput>div>div>input,
    .stTextArea>div>div>textarea,
    .stSelectbox>div>div>select {
        border-radius: 6px;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px 6px 0 0;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    
    /* Info boxes */
    .info-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2196f3;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: #fff3e0;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #ff9800;
        margin: 1rem 0;
    }
    
    /* Export section */
    .export-section {
        background: #f5f5f5;
        padding: 1.5rem;
        border-radius: 8px;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE INITIALIZATION
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
            'reports_by_type': {},
            'last_7_days': []
        },
        'demo_mode': True,
        'current_analysis': None,
        'saved_reports': [],
        'settings': {
            'temperature': 0.1,
            'max_tokens': 2000,
            'auto_save': True
        }
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# =============================================================================
# DEEPSEEK API CLIENT
# =============================================================================

class DeepSeekClient:
    """Enhanced DeepSeek API client with better error handling and features"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com"
        self.timeout = 60
        
    def analyze(self, prompt_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze data using DeepSeek API
        
        Args:
            prompt_type: Type of analysis (incident, audit, policy, esg)
            data: Input data dictionary
            
        Returns:
            Dictionary with analysis results
        """
        # Demo mode
        if not self.api_key or self.api_key == "demo":
            return self.get_demo_response(prompt_type, data)
        
        # Validate API key
        if not self._validate_api_key():
            return {
                "success": False,
                "analysis": "Invalid API key format",
                "tokens_used": 0,
                "cost": 0.0,
                "model": "deepseek-chat"
            }
        
        try:
            # Prepare request
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
                "max_tokens": st.session_state.settings.get('max_tokens', 2000),
                "temperature": st.session_state.settings.get('temperature', 0.1)
            }
            
            # Make API call
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            # Handle response
            if response.status_code == 200:
                result = response.json()
                analysis = result["choices"][0]["message"]["content"]
                
                # Calculate usage
                usage = result.get("usage", {})
                tokens = usage.get("total_tokens", len(analysis) // 4)
                cost = self._calculate_cost(tokens)
                
                return {
                    "success": True,
                    "analysis": analysis,
                    "tokens_used": tokens,
                    "cost": round(cost, 4),
                    "model": result.get("model", "deepseek-chat"),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_msg = self._parse_error_response(response)
                return {
                    "success": False,
                    "analysis": error_msg,
                    "tokens_used": 0,
                    "cost": 0.0,
                    "model": "deepseek-chat"
                }
                
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "analysis": "Request timed out. Please try again.",
                "tokens_used": 0,
                "cost": 0.0,
                "model": "deepseek-chat"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "analysis": f"Network error: {str(e)}",
                "tokens_used": 0,
                "cost": 0.0,
                "model": "deepseek-chat"
            }
        except Exception as e:
            return {
                "success": False,
                "analysis": f"Unexpected error: {str(e)}",
                "tokens_used": 0,
                "cost": 0.0,
                "model": "deepseek-chat"
            }
    
    def _validate_api_key(self) -> bool:
        """Validate API key format"""
        if not self.api_key or len(self.api_key) < 10:
            return False
        return True
    
    def _calculate_cost(self, tokens: int) -> float:
        """Calculate cost based on token usage"""
        # DeepSeek pricing: ~$0.21 per 1M tokens
        return (tokens / 1_000_000) * 0.21
    
    def _parse_error_response(self, response: requests.Response) -> str:
        """Parse error response from API"""
        try:
            error_data = response.json()
            error_msg = error_data.get("error", {}).get("message", "Unknown error")
            return f"API Error ({response.status_code}): {error_msg}"
        except:
            return f"API Error: Status {response.status_code}"
    
    def get_system_prompt(self, prompt_type: str) -> str:
        """Get system prompt based on analysis type"""
        prompts = {
            "incident": """You are a Senior HSE (Health, Safety & Environment) Consultant at PricewaterhouseCoopers (PwC) with 15+ years of experience in incident investigation and compliance analysis.

Your analysis must be institutional-grade and follow this exact structure:

# INCIDENT ANALYSIS REPORT

## 1. EXECUTIVE SUMMARY
Provide a 3-4 sentence overview covering what happened, severity, immediate impacts, and key recommendation.

## 2. INCIDENT DETAILS
- Date & Time:
- Location:
- Severity Level:
- People Involved:
- Immediate Response:

## 3. ROOT CAUSE ANALYSIS (5 Whys Method)
Systematically identify the root cause using the 5 Whys technique.

## 4. REGULATORY IMPLICATIONS
Identify specific regulations, standards, or compliance frameworks affected:
- OSHA regulations (with specific citations)
- ISO standards (e.g., ISO 45001:2018)
- Industry-specific requirements
- Potential violations and consequences

## 5. RISK ASSESSMENT
- Likelihood: [1-5 scale with justification]
- Severity: [1-5 scale with justification]
- Risk Rating: [Calculated]
- Potential Recurrence:

## 6. RECOMMENDATIONS (Prioritized)
### Priority 1 - Immediate (0-24 hours):
### Priority 2 - Short-term (1-7 days):
### Priority 3 - Long-term (1-3 months):

## 7. COST-BENEFIT ANALYSIS
- Estimated implementation cost:
- Potential loss prevention:
- ROI calculation:
- Timeline to positive ROI:

## 8. LESSONS LEARNED & PREVENTIVE MEASURES

Use professional business language, be specific with numbers and timelines, and maintain objectivity.""",

            "audit": """You are an ISO Lead Auditor and Compliance Expert at PwC, specializing in management systems audits (ISO 9001, 14001, 45001, 27001).

Provide a structured compliance gap analysis following ISO audit methodology:

# COMPLIANCE AUDIT REPORT

## 1. AUDIT SCOPE & OBJECTIVES
## 2. METHODOLOGY
## 3. FINDINGS SUMMARY
## 4. DETAILED FINDINGS (by clause/requirement)
## 5. NON-CONFORMITIES
   - Major NCs
   - Minor NCs
   - Observations
## 6. CORRECTIVE ACTION PLAN
## 7. TIMELINE & FOLLOW-UP

Use ISO audit terminology and maintain professional audit standards.""",

            "policy": """You are a Policy & Regulatory Compliance Director at PwC with expertise in corporate governance, legal compliance, and policy development.

Analyze policy documents for:

# POLICY REVIEW REPORT

## 1. EXECUTIVE SUMMARY
## 2. POLICY OVERVIEW
## 3. REGULATORY ALIGNMENT
   - Federal regulations
   - State/local requirements
   - Industry standards
## 4. GAP ANALYSIS
## 5. RECOMMENDATIONS FOR IMPROVEMENT
## 6. IMPLEMENTATION ROADMAP
## 7. REVIEW SCHEDULE

Ensure legal precision and regulatory accuracy.""",

            "esg": """You are an ESG (Environmental, Social, Governance) Sustainability Director at PwC, specializing in ESG reporting frameworks (GRI, SASB, TCFD).

Provide comprehensive ESG analysis:

# ESG PERFORMANCE ASSESSMENT

## 1. EXECUTIVE SUMMARY
## 2. ENVIRONMENTAL PERFORMANCE
   - Carbon footprint
   - Resource efficiency
   - Waste management
## 3. SOCIAL PERFORMANCE
   - Labor practices
   - Community impact
   - Health & safety
## 4. GOVERNANCE PERFORMANCE
   - Board diversity
   - Ethics & compliance
   - Transparency
## 5. MATERIALITY ASSESSMENT
## 6. RECOMMENDATIONS
## 7. ESG SCORE & BENCHMARKING

Align with recognized ESG frameworks and provide data-driven insights."""
        }
        
        return prompts.get(prompt_type, prompts["incident"])
    
    def get_user_prompt(self, prompt_type: str, data: Dict[str, Any]) -> str:
        """Generate user prompt based on type and data"""
        
        if prompt_type == "incident":
            return f"""INCIDENT ANALYSIS REQUEST

**Incident Description:**
{data.get('description', 'N/A')}

**Incident Details:**
- Severity Level: {data.get('severity', 'N/A')}
- Location: {data.get('location', 'N/A')}
- Date: {data.get('date', 'N/A')}
- Time: {data.get('time', 'N/A')}
- Reported By: {data.get('reported_by', 'N/A')}

Please provide a comprehensive PwC-style incident analysis report following the structured format. Include specific regulatory citations, quantified risk assessments, and actionable recommendations with clear timelines."""

        elif prompt_type == "audit":
            return f"""COMPLIANCE AUDIT REQUEST

**Audit Scope:**
{data.get('scope', 'N/A')}

**Standards/Frameworks:**
{data.get('standards', 'N/A')}

**Areas to Review:**
{data.get('areas', 'N/A')}

Conduct a thorough compliance gap analysis."""

        elif prompt_type == "policy":
            return f"""POLICY REVIEW REQUEST

**Policy Name:** {data.get('policy_name', 'N/A')}
**Policy Type:** {data.get('policy_type', 'N/A')}
**Current Version:** {data.get('version', 'N/A')}

**Policy Content:**
{data.get('content', 'N/A')}

Review for regulatory compliance and best practices."""

        elif prompt_type == "esg":
            return f"""ESG ASSESSMENT REQUEST

**Organization:** {data.get('organization', 'N/A')}
**Reporting Period:** {data.get('period', 'N/A')}
**Focus Areas:** {data.get('focus_areas', 'N/A')}

**Data Provided:**
{data.get('esg_data', 'N/A')}

Provide comprehensive ESG analysis and recommendations."""

        return "Please analyze the provided data."
    
    def get_demo_response(self, prompt_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate realistic demo response"""
        
        if prompt_type == "incident":
            description = data.get('description', 'workplace incident')
            severity = data.get('severity', '3 - Serious')
            location = data.get('location', 'Facility')
            
            demo_report = f"""# 🛡️ INCIDENT ANALYSIS REPORT

## 1. EXECUTIVE SUMMARY

{description[:200]}... This incident has been classified as **{severity}** severity. Immediate containment measures have been identified, and a comprehensive corrective action plan is outlined below. Primary root cause identified as procedural gap in maintenance protocols. Estimated implementation cost for corrective measures: $22,500 with projected annual savings of $120,000.

---

## 2. INCIDENT DETAILS

- **Date & Time:** {data.get('date', 'N/A')} at {data.get('time', 'N/A')}
- **Location:** {location}
- **Severity Level:** {severity}
- **People Involved:** {data.get('reported_by', 'Site personnel')}
- **Immediate Response:** Area secured, first aid administered, incident reported to management
- **Current Status:** Under investigation, interim controls in place

---

## 3. ROOT CAUSE ANALYSIS (5 Whys Method)

**Problem Statement:** Incident occurred resulting in potential injury and operational disruption.

1. **Why did the incident occur?**
   → Hazardous condition was present in the work area

2. **Why was the hazardous condition present?**
   → Maintenance backlog led to equipment deterioration over 48-hour period

3. **Why was there a maintenance backlog?**
   → Insufficient priority assignment in work order system

4. **Why was priority assignment inadequate?**
   → Lack of clear procedure for urgent maintenance requests

5. **Why was there no procedure?**
   → **ROOT CAUSE:** Systematic gap in maintenance management protocols and risk assessment procedures

---

## 4. REGULATORY IMPLICATIONS

### Federal Regulations:
- **OSHA 1910.22(a)(1)** - Walking-Working Surfaces: Non-compliance identified
  - *Citation Risk:* High
  - *Potential Penalty:* $7,000 - $14,000 per violation
  
- **OSHA 1904** - Recordkeeping: Incident must be recorded if medical treatment beyond first aid

### ISO Standards:
- **ISO 45001:2018 Clause 8.1.2** - Eliminating hazards and reducing OH&S risks
  - Gap identified in hazard control hierarchy implementation
  
- **ISO 45001:2018 Clause 6.1.2.3** - Action plans not adequately addressing identified risks

### Compliance Status:
⚠️ **IMMEDIATE ACTION REQUIRED** to prevent regulatory enforcement action

---

## 5. RISK ASSESSMENT

### Likelihood Analysis:
**Rating: 4/5 (Probable)**
- Recurring conditions observed
- Similar incidents recorded in past 12 months (3 occurrences)
- Current controls ineffective
- High exposure frequency

### Severity Analysis:
**Rating: 4/5 (Major)**
- Potential for serious injury (days away from work)
- Significant property damage possible ($10,000+)
- Regulatory exposure
- Reputational impact

### Risk Rating Matrix:
**RISK SCORE: 16/25 (HIGH RISK)**

```
Likelihood (4) × Severity (4) = Risk Rating 16
```

**Risk Category:** HIGH - Requires immediate executive attention and resource allocation

### Potential for Recurrence:
- **Without intervention:** 85% probability within next 90 days
- **With interim controls:** 40% probability
- **With full implementation:** <5% probability

---

## 6. RECOMMENDATIONS (Prioritized)

### Priority 1 - IMMEDIATE (0-24 hours):
**Objective: Contain immediate hazards and prevent recurrence**

1. **Physical Containment** [$500]
   - Install barrier systems around affected area
   - Deploy hazard warning signage
   - Implement mandatory PPE requirements
   - Assign dedicated safety monitor

2. **Emergency Cleanup** [$1,200]
   - Professional cleaning crew deployment
   - Hazardous material removal (if applicable)
   - Surface decontamination
   - Air quality testing

3. **Safety Alert** [$0]
   - Issue facility-wide safety bulletin
   - Conduct toolbox talk with all affected departments
   - Update daily pre-shift briefings
   - Notify management team

**P1 Subtotal: $1,700**

---

### Priority 2 - SHORT-TERM (1-7 days):
**Objective: Address systemic issues and strengthen controls**

4. **Maintenance Audit** [$2,500]
   - Review entire maintenance backlog (500+ work orders)
   - Re-prioritize based on risk assessment
   - Identify critical items requiring immediate attention
   - Implement emergency maintenance protocol

5. **Interim Control Measures** [$5,000]
   - Install temporary safety systems
   - Deploy additional monitoring equipment
   - Increase inspection frequency (daily → hourly)
   - Assign dedicated oversight personnel

6. **Training Program** [$3,000]
   - Hazard recognition training (40 employees)
   - Emergency response procedures
   - Proper reporting protocols
   - Documentation requirements

**P2 Subtotal: $10,500**

---

### Priority 3 - LONG-TERM (1-3 months):
**Objective: Implement permanent solutions and prevent recurrence**

7. **Procedure Development** [$1,500]
   - Create comprehensive maintenance prioritization matrix
   - Develop risk-based inspection schedules
   - Establish escalation procedures for urgent issues
   - Implement management of change (MOC) protocol

8. **Preventive Maintenance Program** [$6,000]
   - Implement predictive maintenance technologies
   - Install real-time monitoring systems
   - Deploy IoT sensors for critical equipment
   - Establish automated alert system

9. **Management System Review** [$2,800]
   - Conduct gap analysis against ISO 45001:2018
   - Update safety management system documentation
   - Implement continuous improvement processes
   - Schedule regular management reviews

**P3 Subtotal: $10,300**

---

**TOTAL INVESTMENT REQUIRED: $22,500**

---

## 7. COST-BENEFIT ANALYSIS

### Implementation Costs:
| Category | Cost |
|----------|------|
| Immediate Actions (P1) | $1,700 |
| Short-term Actions (P2) | $10,500 |
| Long-term Actions (P3) | $10,300 |
| **TOTAL** | **$22,500** |

### Loss Prevention Benefits (Annual):
| Category | Savings |
|----------|---------|
| Avoided injury costs | $45,000 |
| Prevented property damage | $25,000 |
| Avoided OSHA penalties | $14,000 |
| Reduced insurance premiums | $18,000 |
| Operational efficiency gains | $12,000 |
| Reduced downtime | $6,000 |
| **TOTAL ANNUAL SAVINGS** | **$120,000** |

### Financial Metrics:
- **Net Annual Benefit:** $97,500
- **Return on Investment (ROI):** 433%
- **Payback Period:** 2.25 months
- **5-Year NPV (7% discount):** $468,500

**RECOMMENDATION:** Immediate approval justified based on strong financial case and regulatory compliance requirements.

---

## 8. LESSONS LEARNED & PREVENTIVE MEASURES

### Key Lessons:
1. **Procedural Gaps Have Real Consequences** - Lack of formal maintenance prioritization procedures created unnecessary risk
2. **Early Intervention is Cost-Effective** - Minor issues escalate to major incidents when not addressed promptly
3. **Communication is Critical** - Better reporting mechanisms could have prevented this incident
4. **Risk Assessment Must Be Dynamic** - Static annual assessments insufficient for operational environments

### Preventive Measures:
- ✅ Implement real-time hazard reporting mobile app
- ✅ Establish daily safety huddles with cross-functional teams
- ✅ Deploy predictive analytics for maintenance scheduling
- ✅ Create near-miss reporting incentive program
- ✅ Conduct quarterly safety culture assessments
- ✅ Implement behavioral-based safety observations

### Knowledge Sharing:
- Distribute lessons learned across all facilities
- Update corporate safety training materials
- Present case study at next quarterly safety meeting
- Include in annual HSE report

---

## 9. IMPLEMENTATION TIMELINE

**Week 1:**
- ✓ P1 actions completed
- ✓ P2 actions initiated
- ✓ Project team assembled

**Week 2-4:**
- ✓ P2 actions completed
- ✓ P3 planning and design
- ✓ Procurement initiated

**Month 2-3:**
- ✓ P3 implementation
- ✓ Training programs delivered
- ✓ System testing and validation

**Month 4:**
- ✓ Post-implementation review
- ✓ Effectiveness verification
- ✓ Closure documentation

---

## 10. MONITORING & VERIFICATION

**KPIs to Track:**
- Maintenance backlog reduction (target: <48 hours for critical items)
- Near-miss reporting rate (target: increase by 200%)
- Lost time injury frequency rate (target: 0)
- Regulatory compliance score (target: 100%)
- Employee safety perception survey scores (target: >90%)

**Review Schedule:**
- Daily: Safety metrics dashboard review
- Weekly: Progress against action plan
- Monthly: KPI performance review
- Quarterly: Management system effectiveness audit

---

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Report ID:** INC-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(description.encode()).hexdigest()[:6].upper()}  
**Prepared By:** Compliance Sentinel AI | PwC HSE Consulting Division  
**Classification:** Internal - Management Review  

---

*This report is AI-generated and should be reviewed by qualified HSE professionals before implementation.*
"""

        elif prompt_type == "audit":
            demo_report = """# 📋 COMPLIANCE AUDIT REPORT

## 1. AUDIT SCOPE & OBJECTIVES
Comprehensive compliance audit against ISO 45001:2018 requirements...

[Demo audit report content]
"""

        else:
            demo_report = f"""# {prompt_type.upper()} ANALYSIS REPORT

Demo analysis report for {prompt_type} type analysis.
This is a placeholder for the full report.
"""

        return {
            "success": True,
            "analysis": demo_report,
            "tokens_used": len(demo_report) // 4,
            "cost": 0.01,
            "model": "deepseek-chat-demo",
            "timestamp": datetime.now().isoformat()
        }

# =============================================================================
# UI COMPONENTS
# =============================================================================

def render_header():
    """Render application header"""
    st.markdown("""
    <div class="main-header">
        <h1>🛡️ Compliance Sentinel</h1>
        <p>Institutional-Grade HSE, ESG & Compliance Analysis Platform</p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    """Render sidebar with configuration and navigation"""
    with st.sidebar:
        st.markdown("## ⚙️ Configuration")
        
        # Mode selection
        mode = st.radio(
            "Operating Mode:",
            ["🎯 Demo Mode (Free)", "🔑 API Mode (Live)"],
            help="Demo mode uses simulated responses. API mode requires DeepSeek API key."
        )
        st.session_state.demo_mode = (mode == "🎯 Demo Mode (Free)")
        
        # API key input
        if not st.session_state.demo_mode:
            st.markdown("### 🔐 API Authentication")
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
                st.info("🔗 API Connected")
        else:
            st.info("💡 Demo mode active - using simulated responses")
        
        st.markdown("---")
        
        # Usage statistics
        st.markdown("## 📊 Usage Statistics")
        stats = st.session_state.usage_stats
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Reports", stats['total_reports'])
            st.metric("Total Tokens", f"{stats['total_tokens']:,}")
        with col2:
            st.metric("Total Cost", f"${stats['total_cost']:.2f}")
            avg_cost = stats['total_cost'] / max(stats['total_reports'], 1)
            st.metric("Avg/Report", f"${avg_cost:.3f}")
        
        st.markdown("---")
        
        # Analysis type selection
        st.markdown("## 📋 Analysis Type")
        analysis_type = st.selectbox(
            "Select Analysis:",
            [
                "🚨 Incident Investigation",
                "📋 Compliance Audit",
                "📜 Policy Review",
                "🌱 ESG Assessment"
            ],
            help="Choose the type of analysis to perform"
        )
        
        st.markdown("---")
        
        # Advanced settings
        with st.expander("⚙️ Advanced Settings"):
            st.session_state.settings['temperature'] = st.slider(
                "Temperature",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.settings.get('temperature', 0.1),
                step=0.1,
                help="Lower = more focused, Higher = more creative"
            )
            
            st.session_state.settings['max_tokens'] = st.slider(
                "Max Tokens",
                min_value=500,
                max_value=4000,
                value=st.session_state.settings.get('max_tokens', 2000),
                step=100,
                help="Maximum length of generated report"
            )
            
            st.session_state.settings['auto_save'] = st.checkbox(
                "Auto-save Reports",
                value=st.session_state.settings.get('auto_save', True)
            )
        
        # Quick actions
        st.markdown("---")
        st.markdown("## ⚡ Quick Actions")
        
        if st.button("📊 View Analytics", use_container_width=True):
            st.session_state.show_analytics = True
        
        if st.button("💾 Export History", use_container_width=True):
            export_history()
        
        if st.button("🗑️ Clear History", use_container_width=True):
            if st.session_state.analysis_history:
                st.session_state.analysis_history = []
                st.success("History cleared")
            else:
                st.info("No history to clear")
        
        # Footer
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; opacity: 0.6; font-size: 0.8rem;'>
            Powered by DeepSeek AI<br>
            v2.0.0 | PwC Standard
        </div>
        """, unsafe_allow_html=True)
        
        return analysis_type

def render_incident_form():
    """Render incident analysis form"""
    st.markdown("## 🚨 Incident Investigation Report")
    st.markdown("Complete the form below for comprehensive incident analysis following PwC HSE standards.")
    
    with st.form("incident_form", clear_on_submit=False):
        
        # Description
        st.markdown("### 📝 Incident Description")
        description = st.text_area(
            "Detailed Description:",
            height=200,
            placeholder="""Describe the incident in detail including:
- What happened?
- Where did it occur?
- Who was involved?
- What were the immediate consequences?
- What actions were taken?

Example: "At approximately 14:30, an employee slipped on an oil spill near Machine #7 in the production area. The employee sustained a minor ankle injury. The spill originated from a hydraulic leak that had been reported 48 hours prior but not yet addressed..."
            """,
            help="Provide comprehensive details for accurate analysis"
        )
        
        st.markdown("---")
        
        # Incident details
        st.markdown("### 📋 Incident Details")
        
        col1, col2, col3 = st.columns(3)
        
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
                help="Select based on actual or potential severity"
            )
            
            date = st.date_input(
                "Incident Date:",
                value=datetime.now(),
                max_value=datetime.now()
            )
        
        with col2:
            location = st.text_input(
                "Location:",
                placeholder="e.g., Production Floor, Building A",
                help="Specific location where incident occurred"
            )
            
            time = st.time_input(
                "Incident Time:",
                value=datetime.now().time()
            )
        
        with col3:
            reported_by = st.text_input(
                "Reported By:",
                placeholder="Name / Department",
                help="Person reporting the incident"
            )
            
            witnesses = st.text_input(
                "Witnesses:",
                placeholder="Names (optional)"
            )
        
        st.markdown("---")
        
        # Additional information
        with st.expander("➕ Additional Information (Optional)"):
            col1, col2 = st.columns(2)
            
            with col1:
                injury_type = st.multiselect(
                    "Injury Type:",
                    ["Slip/Trip/Fall", "Struck By", "Caught In/Between", 
                     "Chemical Exposure", "Ergonomic", "Other"]
                )
                
                equipment_involved = st.text_input(
                    "Equipment Involved:",
                    placeholder="Machine/tool/vehicle"
                )
            
            with col2:
                immediate_cause = st.text_area(
                    "Immediate Cause:",
                    placeholder="What directly caused the incident?",
                    height=100
                )
                
                corrective_action = st.text_area(
                    "Immediate Actions Taken:",
                    placeholder="What was done immediately after?",
                    height=100
                )
        
        st.markdown("---")
        
        # Submit buttons
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            submit = st.form_submit_button(
                "🚀 Generate Full Analysis",
                type="primary",
                use_container_width=True,
                help="Generate comprehensive PwC-style analysis report"
            )
        
        with col2:
            preview = st.form_submit_button(
                "👁️ Preview Sample Report",
                use_container_width=True,
                help="See an example of the analysis format"
            )
        
        with col3:
            clear = st.form_submit_button(
                "🔄 Clear",
                use_container_width=True
            )
        
        # Form validation and submission
        if preview:
            return {"preview": True}
        
        if clear:
            st.rerun()
        
        if submit:
            # Validation
            if not st.session_state.demo_mode and not st.session_state.api_key:
                st.error("⚠️ Please enter your DeepSeek API key in the sidebar to use API mode, or switch to Demo mode.")
                return None
            
            if not description or len(description.strip()) < 20:
                st.warning("⚠️ Please provide a detailed incident description (minimum 20 characters)")
                return None
            
            if not location:
                st.warning("⚠️ Please specify the incident location")
                return None
            
            # Build data dictionary
            return {
                "type": "incident",
                "description": description,
                "severity": severity,
                "location": location,
                "date": date.strftime('%Y-%m-%d'),
                "time": time.strftime('%H:%M'),
                "reported_by": reported_by or "Not specified",
                "witnesses": witnesses,
                "injury_type": ", ".join(injury_type) if injury_type else "Not specified",
                "equipment_involved": equipment_involved or "None specified",
                "immediate_cause": immediate_cause,
                "corrective_action": corrective_action
            }
    
    return None

def render_other_analysis_forms(analysis_type: str):
    """Render forms for other analysis types"""
    
    if "Audit" in analysis_type:
        st.markdown("## 📋 Compliance Audit")
        st.info("🚧 Compliance Audit module coming soon! This will include ISO 9001, 14001, 45001, 27001 audit capabilities.")
        
        with st.expander("Preview Features"):
            st.markdown("""
            **Planned Features:**
            - ISO standard gap analysis
            - Non-conformity tracking
            - Corrective action planning
            - Audit report generation
            - Finding categorization
            - Timeline management
            """)
    
    elif "Policy" in analysis_type:
        st.markdown("## 📜 Policy Review")
        st.info("🚧 Policy Review module coming soon! This will provide comprehensive policy analysis and compliance checking.")
        
        with st.expander("Preview Features"):
            st.markdown("""
            **Planned Features:**
            - Regulatory alignment check
            - Best practice comparison
            - Gap identification
            - Update recommendations
            - Version control
            - Stakeholder review workflow
            """)
    
    elif "ESG" in analysis_type:
        st.markdown("## 🌱 ESG Assessment")
        st.info("🚧 ESG Assessment module coming soon! This will cover Environmental, Social, and Governance performance analysis.")
        
        with st.expander("Preview Features"):
            st.markdown("""
            **Planned Features:**
            - GRI/SASB/TCFD framework alignment
            - Carbon footprint analysis
            - Social impact assessment
            - Governance scoring
            - Materiality assessment
            - Benchmarking against industry
            - ESG reporting generation
            """)

def render_analysis_result(result: Dict[str, Any], input_data: Dict[str, Any]):
    """Render analysis results with enhanced UI"""
    
    if not result.get("success"):
        st.error(f"❌ Analysis Failed: {result.get('analysis', 'Unknown error')}")
        
        with st.expander("🔍 Troubleshooting Help"):
            st.markdown("""
            **Common Issues:**
            
            1. **Invalid API Key**: Verify your DeepSeek API key in sidebar
            2. **Network Error**: Check your internet connection
            3. **Rate Limit**: You may have exceeded API rate limits
            4. **Timeout**: Request took too long, try again
            
            **Need Help?**
            - Switch to Demo Mode to test functionality
            - Check DeepSeek API status
            - Verify API key has sufficient credits
            """)
        return
    
    # Update statistics
    st.session_state.usage_stats['total_reports'] += 1
    st.session_state.usage_stats['total_cost'] += result.get('cost', 0.0)
    st.session_state.usage_stats['total_tokens'] += result.get('tokens_used', 0)
    
    # Track by type
    report_type = input_data.get('type', 'unknown')
    if report_type not in st.session_state.usage_stats['reports_by_type']:
        st.session_state.usage_stats['reports_by_type'][report_type] = 0
    st.session_state.usage_stats['reports_by_type'][report_type] += 1
    
    # Add to history
    history_entry = {
        "timestamp": result.get('timestamp', datetime.now().isoformat()),
        "type": report_type,
        "cost": result.get('cost', 0.0),
        "tokens": result.get('tokens_used', 0),
        "model": result.get('model', 'unknown'),
        "severity": input_data.get('severity', 'N/A'),
        "location": input_data.get('location', 'N/A'),
        "preview": result.get('analysis', '')[:500]
    }
    st.session_state.analysis_history.append(history_entry)
    
    # Auto-save if enabled
    if st.session_state.settings.get('auto_save', True):
        st.session_state.saved_reports.append({
            **history_entry,
            "full_analysis": result.get('analysis', ''),
            "input_data": input_data
        })
    
    # Success message with metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.success("✅ Analysis Complete!")
    with col2:
        st.info(f"📊 {result.get('tokens_used', 0):,} tokens")
    with col3:
        st.info(f"💰 ${result.get('cost', 0):.4f}")
    with col4:
        st.info(f"🤖 {result.get('model', 'N/A')}")
    
    # Create tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs([
        "📄 Analysis Report",
        "📊 Analytics Dashboard",
        "💾 Export Options",
        "🔍 Report History"
    ])
    
    with tab1:
        render_report_tab(result, input_data)
    
    with tab2:
        render_analytics_tab()
    
    with tab3:
        render_export_tab(result, input_data)
    
    with tab4:
        render_history_tab()

def render_report_tab(result: Dict[str, Any], input_data: Dict[str, Any]):
    """Render the analysis report tab"""
    
    # Report header
    st.markdown("### 📄 Full Analysis Report")
    
    # Metadata
    with st.expander("ℹ️ Report Metadata", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            **Report Details:**
            - Type: {input_data.get('type', 'N/A').title()}
            - Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            - Model: {result.get('model', 'N/A')}
            """)
        with col2:
            st.markdown(f"""
            **Usage:**
            - Tokens: {result.get('tokens_used', 0):,}
            - Cost: ${result.get('cost', 0):.4f}
            - Temperature: {st.session_state.settings.get('temperature', 0.1)}
            """)
        with col3:
            st.markdown(f"""
            **Incident Details:**
            - Severity: {input_data.get('severity', 'N/A')}
            - Location: {input_data.get('location', 'N/A')}
            - Date: {input_data.get('date', 'N/A')}
            """)
    
    st.markdown("---")
    
    # Display the analysis
    st.markdown(result.get('analysis', 'No analysis available'))
    
    # Quick actions
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🖨️ Print Report", use_container_width=True):
            st.info("Use your browser's print function (Ctrl+P / Cmd+P)")
    
    with col2:
        if st.button("📧 Email Report", use_container_width=True):
            st.info("Copy the report and paste into your email client")
    
    with col3:
        if st.button("💾 Save to Reports", use_container_width=True):
            if input_data not in st.session_state.saved_reports:
                st.session_state.saved_reports.append({
                    **input_data,
                    "analysis": result.get('analysis', ''),
                    "timestamp": datetime.now().isoformat()
                })
                st.success("✅ Report saved!")
            else:
                st.info("Already saved")

def render_analytics_tab():
    """Render analytics dashboard tab"""
    
    st.markdown("### 📊 Usage Analytics Dashboard")
    
    if not st.session_state.analysis_history:
        st.info("📈 No analysis history yet. Generate your first report to see analytics!")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(st.session_state.analysis_history)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    
    # Summary metrics
    st.markdown("#### 📈 Summary Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Reports",
            len(df),
            delta=f"+1 today" if len(df) > 0 else None
        )
    
    with col2:
        total_cost = df['cost'].sum()
        st.metric(
            "Total Spend",
            f"${total_cost:.2f}",
            delta=f"${df.iloc[-1]['cost']:.4f} last" if len(df) > 0 else None
        )
    
    with col3:
        avg_cost = df['cost'].mean()
        st.metric(
            "Avg Cost/Report",
            f"${avg_cost:.4f}",
            delta="Well optimized" if avg_cost < 0.02 else None
        )
    
    with col4:
        total_tokens = df['tokens'].sum()
        st.metric(
            "Total Tokens",
            f"{total_tokens:,}",
            delta=f"{df.iloc[-1]['tokens']:,} last" if len(df) > 0 else None
        )
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📅 Reports Over Time")
        daily_reports = df.groupby('date').size().reset_index(name='count')
        fig1 = px.bar(
            daily_reports,
            x='date',
            y='count',
            title='Daily Report Generation',
            labels={'count': 'Number of Reports', 'date': 'Date'}
        )
        fig1.update_layout(showlegend=False)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("#### 💰 Cost Breakdown")
        if 'type' in df.columns:
            cost_by_type = df.groupby('type')['cost'].sum().reset_index()
            fig2 = px.pie(
                cost_by_type,
                values='cost',
                names='type',
                title='Cost by Analysis Type'
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("Type information not available")
    
    # Detailed table
    st.markdown("---")
    st.markdown("#### 📋 Detailed History")
    
    # Format DataFrame for display
    display_df = df.copy()
    display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
    display_df['cost'] = display_df['cost'].apply(lambda x: f"${x:.4f}")
    display_df['tokens'] = display_df['tokens'].apply(lambda x: f"{x:,}")
    
    st.dataframe(
        display_df[['timestamp', 'type', 'severity', 'location', 'tokens', 'cost', 'model']],
        use_container_width=True,
        hide_index=True
    )

def render_export_tab(result: Dict[str, Any], input_data: Dict[str, Any]):
    """Render export options tab"""
    
    st.markdown("### 💾 Export Options")
    
    # Prepare export content
    export_text = f"""
================================================================================
COMPLIANCE SENTINEL - INCIDENT ANALYSIS REPORT
================================================================================

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Report Type: {input_data.get('type', 'N/A').upper()}
Model: {result.get('model', 'N/A')}

--------------------------------------------------------------------------------
METADATA
--------------------------------------------------------------------------------
Tokens Used: {result.get('tokens_used', 0):,}
Analysis Cost: ${result.get('cost', 0):.4f}
Temperature: {st.session_state.settings.get('temperature', 0.1)}

--------------------------------------------------------------------------------
INCIDENT DETAILS
--------------------------------------------------------------------------------
Date: {input_data.get('date', 'N/A')}
Time: {input_data.get('time', 'N/A')}
Location: {input_data.get('location', 'N/A')}
Severity: {input_data.get('severity', 'N/A')}
Reported By: {input_data.get('reported_by', 'N/A')}

Description:
{input_data.get('description', 'N/A')}

================================================================================
ANALYSIS REPORT
================================================================================

{result.get('analysis', 'No analysis available')}

================================================================================
END OF REPORT
================================================================================

This report was generated using Compliance Sentinel AI-powered analysis platform.
For questions or support, please contact your HSE administrator.

Disclaimer: This AI-generated report should be reviewed by qualified HSE 
professionals before implementation of recommendations.
"""
    
    # Export options
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📄 Text Format")
        st.download_button(
            label="📥 Download as TXT",
            data=export_text,
            file_name=f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
        
        st.markdown("#### 📊 JSON Format")
        json_data = {
            "metadata": {
                "generated": datetime.now().isoformat(),
                "report_type": input_data.get('type', 'N/A'),
                "model": result.get('model', 'N/A'),
                "tokens": result.get('tokens_used', 0),
                "cost": result.get('cost', 0)
            },
            "incident": input_data,
            "analysis": result.get('analysis', '')
        }
        
        st.download_button(
            label="📥 Download as JSON",
            data=json.dumps(json_data, indent=2),
            file_name=f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    with col2:
        st.markdown("#### 📋 Markdown Format")
        markdown_content = f"""# Incident Analysis Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Incident Details

- **Date:** {input_data.get('date', 'N/A')}
- **Time:** {input_data.get('time', 'N/A')}
- **Location:** {input_data.get('location', 'N/A')}
- **Severity:** {input_data.get('severity', 'N/A')}
- **Reported By:** {input_data.get('reported_by', 'N/A')}

### Description

{input_data.get('description', 'N/A')}

---

## Analysis

{result.get('analysis', '')}

---

*Report generated by Compliance Sentinel | Tokens: {result.get('tokens_used', 0):,} | Cost: ${result.get('cost', 0):.4f}*
"""
        
        st.download_button(
            label="📥 Download as MD",
            data=markdown_content,
            file_name=f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
            mime="text/markdown",
            use_container_width=True
        )
        
        st.markdown("#### 📊 CSV Export (History)")
        if st.session_state.analysis_history:
            df = pd.DataFrame(st.session_state.analysis_history)
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download History as CSV",
                data=csv,
                file_name=f"analysis_history_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.info("No history to export")
    
    # Preview section
    st.markdown("---")
    st.markdown("#### 👁️ Preview")
    
    with st.expander("Show Export Preview (first 1000 chars)"):
        st.code(export_text[:1000] + "..." if len(export_text) > 1000 else export_text)

def render_history_tab():
    """Render report history tab"""
    
    st.markdown("### 🔍 Report History")
    
    if not st.session_state.analysis_history:
        st.info("📚 No report history yet. Your completed analyses will appear here.")
        return
    
    # Sort by timestamp (newest first)
    history = sorted(
        st.session_state.analysis_history,
        key=lambda x: x.get('timestamp', ''),
        reverse=True
    )
    
    # Display each report
    for idx, report in enumerate(history):
        with st.expander(
            f"📄 Report #{len(history)-idx} - {report.get('type', 'Unknown').title()} - "
            f"{pd.to_datetime(report.get('timestamp')).strftime('%Y-%m-%d %H:%M') if report.get('timestamp') else 'Unknown date'}"
        ):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"""
                **Details:**
                - Type: {report.get('type', 'N/A').title()}
                - Severity: {report.get('severity', 'N/A')}
                - Location: {report.get('location', 'N/A')}
                """)
            
            with col2:
                st.markdown(f"""
                **Metrics:**
                - Tokens: {report.get('tokens', 0):,}
                - Cost: ${report.get('cost', 0):.4f}
                - Model: {report.get('model', 'N/A')}
                """)
            
            with col3:
                st.markdown(f"""
                **Timestamp:**
                - {pd.to_datetime(report.get('timestamp')).strftime('%Y-%m-%d %H:%M:%S') if report.get('timestamp') else 'Unknown'}
                """)
            
            if report.get('preview'):
                st.markdown("**Preview:**")
                st.text(report['preview'] + "...")

def export_history():
    """Export analysis history"""
    if not st.session_state.analysis_history:
        st.warning("No history to export")
        return
    
    df = pd.DataFrame(st.session_state.analysis_history)
    csv = df.to_csv(index=False)
    
    st.download_button(
        label="📥 Download History CSV",
        data=csv,
        file_name=f"compliance_sentinel_history_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )

# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main():
    """Main application entry point"""
    
    # Initialize session state
    init_session_state()
    
    # Render header
    render_header()
    
    # Render sidebar and get analysis type
    analysis_type = render_sidebar()
    
    # Main content area
    if "Incident" in analysis_type:
        # Render incident form
        form_data = render_incident_form()
        
        if form_data:
            if form_data.get("preview"):
                # Show preview
                st.info("### 📋 Sample Report Preview")
                st.markdown("This is an example of the analysis you'll receive:")
                
                client = DeepSeekClient("demo")
                result = client.get_demo_response("incident", {
                    "description": "Sample incident for preview purposes",
                    "severity": "3 - Serious",
                    "location": "Sample Location"
                })
                
                with st.expander("👁️ View Sample Report", expanded=True):
                    st.markdown(result.get('analysis', '')[:2000] + "\n\n*[Report truncated for preview]*")
                
                st.info("💡 **Tip:** Fill out the form above and click 'Generate Full Analysis' to create a custom report based on your incident details.")
            
            else:
                # Generate actual analysis
                with st.spinner("🔍 Analyzing incident... This may take 30-60 seconds..."):
                    # Initialize client
                    api_key = st.session_state.api_key if not st.session_state.demo_mode else "demo"
                    client = DeepSeekClient(api_key)
                    
                    # Perform analysis
                    result = client.analyze("incident", form_data)
                    
                    # Display results
                    render_analysis_result(result, form_data)
    
    else:
        # Render other analysis type forms
        render_other_analysis_forms(analysis_type)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 2rem; color: #666;'>
        <p><strong>Compliance Sentinel</strong> | Institutional-Grade HSE Analysis Platform</p>
        <p style='font-size: 0.9rem;'>
            Powered by DeepSeek AI | Designed for PwC Standards<br>
            Version 2.0.0 | © 2024
        </p>
        <p style='font-size: 0.8rem; margin-top: 1rem;'>
            ⚠️ <em>AI-generated reports should be reviewed by qualified professionals before implementation</em>
        </p>
    </div>
    """, unsafe_allow_html=True)

# =============================================================================
# RUN APPLICATION
# =============================================================================

if __name__ == "__main__":
    main()
