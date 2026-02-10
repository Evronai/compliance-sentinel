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
# CUSTOM CSS - FIXED
# =============================================================================

st.markdown("""
<style>
    /* Remove white background from sidebar */
    [data-testid="stSidebar"] {
        background-color: transparent;
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
    }
    
    .stSelectbox label {
        color: inherit !important;
    }
    
    /* Metric cards */
    .stMetric {
        background: rgba(255, 255, 255, 0.05);
        padding: 1rem;
        border-radius: 8px;
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 6px;
        font-weight: 500;
    }
    
    /* Info boxes */
    .info-box {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2196f3;
        margin: 1rem 0;
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
# DEEPSEEK API CLIENT
# =============================================================================

class DeepSeekClient:
    """DeepSeek API client for analysis"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.deepseek.com"
        self.timeout = 60
        
    def analyze(self, prompt_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze data using DeepSeek API"""
        
        # Demo mode
        if not self.api_key or self.api_key == "demo":
            return self.get_demo_response(prompt_type, data)
        
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
                "max_tokens": st.session_state.settings.get('max_tokens', 2000),
                "temperature": st.session_state.settings.get('temperature', 0.1)
            }
            
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                analysis = result["choices"][0]["message"]["content"]
                
                usage = result.get("usage", {})
                tokens = usage.get("total_tokens", len(analysis) // 4)
                cost = (tokens / 1_000_000) * 0.21
                
                return {
                    "success": True,
                    "analysis": analysis,
                    "tokens_used": tokens,
                    "cost": round(cost, 4),
                    "model": result.get("model", "deepseek-chat"),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                error_data = response.json() if response.text else {}
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                return {
                    "success": False,
                    "analysis": f"API Error: {error_msg}",
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
        except Exception as e:
            return {
                "success": False,
                "analysis": f"Error: {str(e)}",
                "tokens_used": 0,
                "cost": 0.0,
                "model": "deepseek-chat"
            }
    
    def get_system_prompt(self, prompt_type: str) -> str:
        """Get system prompt based on analysis type"""
        
        if prompt_type == "incident":
            return """You are a Senior HSE (Health, Safety & Environment) Consultant with 15+ years of experience in incident investigation and compliance analysis.

Provide a comprehensive incident analysis report with the following structure:

# INCIDENT ANALYSIS REPORT

## 1. EXECUTIVE SUMMARY
Provide a 3-4 sentence overview covering what happened, severity, immediate impacts, and key recommendation.

## 2. INCIDENT DETAILS
- Date & Time
- Location
- Severity Level
- People Involved
- Immediate Response

## 3. ROOT CAUSE ANALYSIS (5 Whys Method)
Use the 5 Whys technique to systematically identify the root cause.

## 4. REGULATORY IMPLICATIONS
Identify specific regulations and standards affected:
- OSHA regulations (with specific citations)
- ISO standards (e.g., ISO 45001:2018)
- Industry-specific requirements
- Potential violations and consequences

## 5. RISK ASSESSMENT
- Likelihood (1-5 scale with justification)
- Severity (1-5 scale with justification)
- Risk Rating (calculated)
- Potential for recurrence

## 6. RECOMMENDATIONS (Prioritized)
### Priority 1 - Immediate (0-24 hours)
### Priority 2 - Short-term (1-7 days)
### Priority 3 - Long-term (1-3 months)

## 7. COST-BENEFIT ANALYSIS
- Estimated implementation cost
- Potential loss prevention
- ROI calculation
- Timeline to positive ROI

## 8. LESSONS LEARNED & PREVENTIVE MEASURES

Use professional business language, be specific with numbers and timelines, and maintain objectivity."""

        return "Analyze the provided data professionally."
    
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

Please provide a comprehensive incident analysis report following the structured format."""

        return "Please analyze this data."
    
    def get_demo_response(self, prompt_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate demo response"""
        
        description = data.get('description', 'workplace incident')
        severity = data.get('severity', '3 - Serious')
        location = data.get('location', 'Facility')
        incident_date = data.get('date', 'N/A')
        incident_time = data.get('time', 'N/A')
        
        demo_report = f"""# 🛡️ INCIDENT ANALYSIS REPORT

## 1. EXECUTIVE SUMMARY

A {severity.split('-')[1].strip().lower()} severity incident occurred at {location} on {incident_date} at {incident_time}. {description[:150]}... 

Immediate containment measures have been identified, and a comprehensive corrective action plan is outlined below. Primary root cause identified as procedural gap in safety protocols. Estimated implementation cost for corrective measures: $22,500 with projected annual savings of $120,000.

**Risk Level:** HIGH  
**Immediate Action Required:** Yes  
**Regulatory Impact:** Moderate

---

## 2. INCIDENT DETAILS

- **Date & Time:** {incident_date} at {incident_time}
- **Location:** {location}
- **Severity Level:** {severity}
- **People Involved:** {data.get('reported_by', 'Site personnel')}
- **Immediate Response:** Area secured, first aid administered (if applicable), incident reported to management
- **Current Status:** Under investigation, interim controls in place

**Witnesses:** {data.get('witnesses', 'None listed')}  
**Equipment Involved:** {data.get('equipment_involved', 'Not specified')}

---

## 3. ROOT CAUSE ANALYSIS (5 Whys Method)

**Problem Statement:** {description[:100]}...

**Analysis:**

1. **Why did the incident occur?**
   → Hazardous condition was present in the work area

2. **Why was the hazardous condition present?**
   → Maintenance backlog led to equipment/environmental deterioration

3. **Why was there a maintenance backlog?**
   → Insufficient priority assignment in work order system

4. **Why was priority assignment inadequate?**
   → Lack of clear procedure for urgent safety-related requests

5. **Why was there no procedure?**
   → **ROOT CAUSE:** Systematic gap in safety management protocols and risk assessment procedures

**Contributing Factors:**
- Communication breakdown between departments
- Inadequate hazard recognition training
- Missing pre-task safety assessments
- Insufficient supervision during high-risk activities

---

## 4. REGULATORY IMPLICATIONS

### Federal Regulations

**OSHA 1910.22(a)(1) - Walking-Working Surfaces**
- **Status:** Potential non-compliance identified
- **Citation Risk:** High
- **Potential Penalty:** $7,000 - $14,000 per violation
- **Required Action:** Immediate hazard correction and documentation

**OSHA 1904 - Recordkeeping**
- **Requirement:** Incident must be recorded if medical treatment required
- **Status:** Pending injury classification
- **Action:** Complete OSHA 300 log entry within 7 days

### ISO Standards

**ISO 45001:2018 - Occupational Health & Safety Management**
- **Clause 8.1.2:** Eliminating hazards and reducing OH&S risks
  - Gap identified in hazard control hierarchy implementation
- **Clause 6.1.2.3:** Assessment of OH&S risks
  - Risk assessment procedures need updating

### Industry Standards
- ANSI Z10 - Occupational Health and Safety Management Systems
- NFPA standards (if fire/electrical hazards involved)
- Industry-specific safety requirements

**Compliance Status:** ⚠️ **IMMEDIATE ACTION REQUIRED** to prevent regulatory enforcement

---

## 5. RISK ASSESSMENT

### Likelihood Analysis
**Rating: 4/5 (Probable)**

**Justification:**
- Similar conditions observed in other areas
- Previous incidents of similar nature (check historical data)
- Current controls ineffective
- High exposure frequency
- Lack of preventive maintenance

### Severity Analysis
**Rating: 4/5 (Major)**

**Justification:**
- Potential for serious injury (lost time/restricted duty)
- Significant property damage possible
- Regulatory exposure
- Reputational impact
- Multiple people potentially affected

### Risk Rating Matrix
```
Likelihood (4) × Severity (4) = Risk Score: 16/25
```

**Risk Category:** **HIGH RISK** - Requires immediate senior management attention and resource allocation

### Potential for Recurrence
- **Without intervention:** 75-85% probability within next 90 days
- **With interim controls:** 30-40% probability
- **With full implementation of recommendations:** <5% probability

---

## 6. RECOMMENDATIONS (Prioritized)

### Priority 1 - IMMEDIATE (0-24 hours)
**Objective: Prevent immediate recurrence**

1. **Physical Containment** [$500]
   - Install barriers/warning signs around affected area
   - Deploy hazard warning signage
   - Restrict access to authorized personnel only
   - Assign dedicated safety monitor if operations must continue

2. **Emergency Response** [$1,000]
   - Address immediate hazard (cleanup, repair, isolation)
   - Conduct air quality/environmental testing if needed
   - Provide appropriate PPE to affected workers
   - Brief all shift personnel on incident and precautions

3. **Safety Communication** [$0]
   - Issue facility-wide safety alert
   - Conduct toolbox talk with affected departments
   - Update daily pre-shift safety briefings
   - Notify management team and safety committee

**P1 Subtotal: $1,500**

---

### Priority 2 - SHORT-TERM (1-7 days)
**Objective: Address systemic vulnerabilities**

4. **Safety Audit** [$2,000]
   - Conduct comprehensive workplace inspection
   - Identify similar hazards in other areas
   - Review maintenance backlog (all high-risk items)
   - Assess adequacy of current controls

5. **Interim Controls** [$4,000]
   - Install temporary safety systems
   - Deploy additional monitoring equipment
   - Increase inspection frequency
   - Implement enhanced supervision

6. **Training & Awareness** [$2,500]
   - Hazard recognition training (all affected personnel)
   - Emergency response procedures review
   - Proper reporting protocols
   - Near-miss reporting encouragement

7. **Procedure Review** [$1,000]
   - Update relevant safety procedures
   - Create job safety analyses (JSAs) for high-risk tasks
   - Develop incident-specific safe work practices
   - Implement permit-to-work system if needed

**P2 Subtotal: $9,500**

---

### Priority 3 - LONG-TERM (1-3 months)
**Objective: Sustainable risk reduction**

8. **Engineering Controls** [$8,000]
   - Install permanent safety systems
   - Upgrade equipment/machinery guards
   - Implement automated safety interlocks
   - Improve facility design/layout

9. **Management System Enhancement** [$2,000]
   - Implement preventive maintenance software
   - Deploy real-time safety monitoring dashboard
   - Establish safety performance indicators (KPIs)
   - Create management review process

10. **Culture & Behavior** [$1,500]
    - Behavioral-based safety program launch
    - Near-miss reporting incentive system
    - Safety recognition program
    - Regular safety leadership walkthroughs

**P3 Subtotal: $11,500**

---

**TOTAL INVESTMENT REQUIRED: $22,500**

---

## 7. COST-BENEFIT ANALYSIS

### Implementation Costs

| Category | Investment |
|----------|-----------|
| Immediate Actions (P1) | $1,500 |
| Short-term Actions (P2) | $9,500 |
| Long-term Actions (P3) | $11,500 |
| **TOTAL** | **$22,500** |

### Loss Prevention Benefits (Annual)

| Category | Savings |
|----------|---------|
| Avoided injury costs (direct) | $35,000 |
| Avoided workers' compensation claims | $20,000 |
| Prevented property damage | $15,000 |
| Avoided OSHA penalties | $10,000 |
| Reduced insurance premiums | $12,000 |
| Operational efficiency gains | $18,000 |
| Avoided downtime | $10,000 |
| **TOTAL ANNUAL SAVINGS** | **$120,000** |

### Financial Metrics

- **Net Annual Benefit:** $97,500
- **Return on Investment (ROI):** 433%
- **Payback Period:** 2.25 months
- **5-Year NPV (7% discount rate):** $468,500
- **Benefit-Cost Ratio:** 5.3:1

**Financial Recommendation:** ✅ **IMMEDIATE APPROVAL JUSTIFIED**

Strong financial case with rapid payback. Additional intangible benefits include:
- Enhanced regulatory compliance posture
- Improved employee morale and safety culture
- Reduced liability exposure
- Better corporate reputation

---

## 8. LESSONS LEARNED & PREVENTIVE MEASURES

### Key Lessons

1. **Procedural Gaps Have Real Consequences**
   - Lack of formal safety procedures creates unnecessary risk
   - Written procedures must be clear, accessible, and enforced

2. **Early Intervention is Critical**
   - Minor issues escalate to major incidents when ignored
   - "See something, say something" culture essential

3. **Communication Saves Lives**
   - Better reporting mechanisms could have prevented this incident
   - Multiple communication channels needed (formal + informal)

4. **Risk Assessment Must Be Proactive**
   - Reactive safety management is insufficient
   - Regular workplace inspections and hazard assessments required

5. **Training is an Investment, Not a Cost**
   - Proper training prevents incidents and saves money
   - Ongoing refresher training necessary

### Preventive Measures

**Immediate Implementation:**
- ✅ Daily safety briefings with hazard focus
- ✅ Enhanced hazard reporting hotline/app
- ✅ Weekly safety committee walkthroughs
- ✅ Near-miss reporting with no-blame culture

**Ongoing Programs:**
- ✅ Quarterly safety culture assessments
- ✅ Monthly safety training modules
- ✅ Behavioral-based safety observations
- ✅ Safety suggestion box with recognition

**Systematic Improvements:**
- ✅ Integrated safety management system (SMS)
- ✅ Predictive analytics for maintenance
- ✅ Real-time safety performance dashboard
- ✅ Regular management safety reviews

### Knowledge Sharing

**Internal:**
- Distribute lessons learned to all facilities
- Update corporate safety training materials
- Present case study at quarterly safety meeting
- Include in annual HSE performance report

**External:**
- Share anonymized case study with industry peers
- Contribute to industry safety database
- Participate in safety consortium discussions

---

## 9. IMPLEMENTATION TIMELINE

**Week 1:**
- ✓ All P1 actions completed
- ✓ P2 actions initiated
- ✓ Project team assembled
- ✓ Budget approved

**Week 2-4:**
- ✓ P2 actions in progress
- ✓ Training programs launched
- ✓ P3 planning and design
- ✓ Procurement initiated

**Month 2:**
- ✓ P2 actions completed
- ✓ P3 implementation begins
- ✓ Interim controls verified
- ✓ Mid-point review

**Month 3:**
- ✓ P3 implementation completed
- ✓ System testing and validation
- ✓ Final training delivery
- ✓ Performance monitoring active

**Month 4:**
- ✓ Post-implementation effectiveness review
- ✓ KPI measurement and reporting
- ✓ Closure documentation
- ✓ Continuous improvement planning

---

## 10. MONITORING & VERIFICATION

### Key Performance Indicators (KPIs)

**Safety Metrics:**
- Lost Time Injury Frequency Rate (LTIFR): Target = 0
- Total Recordable Incident Rate (TRIR): Target < industry average
- Near-miss reporting rate: Target = increase by 200%
- Safety observation completion: Target = 100% weekly

**Compliance Metrics:**
- Regulatory compliance score: Target = 100%
- Audit findings closure rate: Target = 100% on-time
- Training completion rate: Target = 100%
- Procedure compliance rate: Target > 95%

**Operational Metrics:**
- Maintenance backlog (critical items): Target < 24 hours
- Safety work order completion: Target = 100% on-time
- Incident investigation closure: Target < 7 days
- Corrective action effectiveness: Target > 90%

### Review Schedule

**Daily:**
- Safety metrics dashboard review
- Hazard reports reviewed and actioned
- High-risk work permits approved

**Weekly:**
- Progress against action plan
- Safety committee meeting
- Management walkthrough

**Monthly:**
- KPI performance review
- Trend analysis
- Management safety meeting
- Training effectiveness assessment

**Quarterly:**
- Management system effectiveness audit
- Safety culture survey
- External regulatory compliance review

---

## APPENDICES

### A. Incident Classification
- **Type:** {data.get('injury_type', 'To be determined')}
- **OSHA Recordability:** Pending medical determination
- **Root Cause Category:** Procedural/Administrative

### B. Regulatory References
- OSHA 1910.22(a)(1) - Walking-Working Surfaces
- OSHA 1904 - Recording and Reporting Occupational Injuries
- ISO 45001:2018 - OH&S Management Systems
- ANSI Z10 - Occupational Health and Safety Management Systems

### C. Related Documents
- Site Safety Manual (current version)
- Emergency Response Procedures
- Incident Investigation Procedure
- Corrective Action Tracking System

---

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Report ID:** INC-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(description.encode()).hexdigest()[:6].upper()}  
**Prepared By:** Compliance Sentinel AI | HSE Analysis System  
**Classification:** Internal - Management Review  
**Distribution:** HSE Manager, Site Manager, Safety Committee, Operations Director

---

*This is an AI-generated report and should be reviewed by qualified HSE professionals before implementation of recommendations. All regulatory citations should be verified against current requirements.*

**DISCLAIMER:** This analysis is based on the information provided and general industry best practices. Site-specific conditions, local regulations, and organizational policies may require additional considerations. Consult with qualified safety professionals and legal counsel as appropriate.
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
        <p>Professional HSE & Compliance Analysis Platform</p>
    </div>
    """, unsafe_allow_html=True)

def render_sidebar():
    """Render sidebar with configuration"""
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
        
        # Usage statistics
        st.markdown("## 📊 Statistics")
        stats = st.session_state.usage_stats
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Reports", stats['total_reports'])
        with col2:
            st.metric("Cost", f"${stats['total_cost']:.2f}")
        
        if stats['total_reports'] > 0:
            st.metric("Tokens", f"{stats['total_tokens']:,}")
        
        st.markdown("---")
        
        # Analysis type selection
        st.markdown("## 📋 Analysis Type")
        analysis_type = st.selectbox(
            "Select Type:",
            [
                "🚨 Incident Investigation",
                "📋 Compliance Audit (Coming Soon)",
                "📜 Policy Review (Coming Soon)",
                "🌱 ESG Assessment (Coming Soon)"
            ]
        )
        
        # Advanced settings
        if st.session_state.demo_mode == False:
            st.markdown("---")
            with st.expander("⚙️ Advanced Settings"):
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
                    step=100
                )
        
        return analysis_type

def render_incident_form():
    """Render incident analysis form"""
    st.markdown("## 🚨 Incident Investigation Report")
    
    with st.form("incident_form", clear_on_submit=False):
        
        # Description
        description = st.text_area(
            "Incident Description:",
            height=150,
            placeholder="Describe what happened in detail...\n\nExample: At approximately 14:30, an employee slipped on an oil spill near Machine #7 in the production area. The employee sustained a minor ankle injury. The spill originated from a hydraulic leak that had been reported 48 hours prior but not yet addressed...",
            help="Include what, where, when, who was involved, and immediate consequences"
        )
        
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
                ]
            )
            
            location = st.text_input(
                "Location:",
                placeholder="e.g., Production Floor, Building A"
            )
            
            date = st.date_input("Date:", datetime.now())
        
        with col2:
            time = st.time_input("Time:", datetime.now().time())
            
            reported_by = st.text_input(
                "Reported By:",
                placeholder="Name / Department (optional)"
            )
            
            witnesses = st.text_input(
                "Witnesses:",
                placeholder="Names (optional)"
            )
        
        # Additional info
        with st.expander("➕ Additional Information (Optional)"):
            injury_type = st.text_input("Injury Type:", placeholder="e.g., Slip/Trip/Fall")
            equipment_involved = st.text_input("Equipment Involved:", placeholder="e.g., Machine #7")
        
        st.markdown("---")
        
        # Submit buttons
        col1, col2 = st.columns(2)
        
        with col1:
            submit = st.form_submit_button(
                "🚀 Generate Analysis",
                type="primary",
                use_container_width=True
            )
        
        with col2:
            preview = st.form_submit_button(
                "👁️ Preview Sample",
                use_container_width=True
            )
        
        if preview:
            return {"preview": True}
        
        if submit:
            if not st.session_state.demo_mode and not st.session_state.api_key:
                st.error("⚠️ Please enter your API key in the sidebar or switch to Demo mode")
                return None
            
            if not description or len(description.strip()) < 20:
                st.warning("⚠️ Please provide a detailed description (minimum 20 characters)")
                return None
            
            if not location:
                st.warning("⚠️ Please specify the location")
                return None
            
            return {
                "type": "incident",
                "description": description,
                "severity": severity,
                "location": location,
                "date": date.strftime('%Y-%m-%d'),
                "time": time.strftime('%H:%M'),
                "reported_by": reported_by or "Not specified",
                "witnesses": witnesses,
                "injury_type": injury_type,
                "equipment_involved": equipment_involved
            }
    
    return None

def render_analysis_result(result: Dict[str, Any], input_data: Dict[str, Any]):
    """Render analysis results"""
    
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
        "type": input_data.get('type', 'incident'),
        "severity": input_data.get('severity', 'N/A'),
        "location": input_data.get('location', 'N/A'),
        "cost": result.get('cost', 0.0),
        "tokens": result.get('tokens_used', 0),
        "model": result.get('model', 'N/A')
    })
    
    # Success message
    col1, col2, col3 = st.columns(3)
    with col1:
        st.success("✅ Analysis Complete!")
    with col2:
        st.info(f"📊 {result.get('tokens_used', 0):,} tokens")
    with col3:
        st.info(f"💰 ${result.get('cost', 0):.4f}")
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📄 Report", "📊 Analytics", "💾 Export"])
    
    with tab1:
        st.markdown("### Analysis Report")
        st.markdown(result.get('analysis', 'No analysis available'))
    
    with tab2:
        render_analytics_tab()
    
    with tab3:
        render_export_tab(result, input_data)

def render_analytics_tab():
    """Render analytics dashboard"""
    
    st.markdown("### 📊 Usage Analytics")
    
    if not st.session_state.analysis_history:
        st.info("📈 No analysis history yet. Generate reports to see analytics!")
        return
    
    df = pd.DataFrame(st.session_state.analysis_history)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Reports", len(df))
    
    with col2:
        st.metric("Total Cost", f"${df['cost'].sum():.2f}")
    
    with col3:
        avg_cost = df['cost'].mean()
        st.metric("Avg Cost", f"${avg_cost:.4f}")
    
    with col4:
        st.metric("Total Tokens", f"{df['tokens'].sum():,}")
    
    st.markdown("---")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Reports Over Time")
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['date'] = df['timestamp'].dt.date
        daily = df.groupby('date').size().reset_index(name='count')
        
        fig1 = px.bar(daily, x='date', y='count', title='Daily Report Generation')
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("#### Cost Breakdown")
        fig2 = px.pie(df, names='severity', values='cost', title='Cost by Severity')
        st.plotly_chart(fig2, use_container_width=True)
    
    # History table
    st.markdown("---")
    st.markdown("#### Recent Reports")
    
    display_df = df.copy()
    display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
    display_df['cost'] = display_df['cost'].apply(lambda x: f"${x:.4f}")
    
    st.dataframe(
        display_df[['timestamp', 'severity', 'location', 'tokens', 'cost']].tail(10),
        use_container_width=True,
        hide_index=True
    )

def render_export_tab(result: Dict[str, Any], input_data: Dict[str, Any]):
    """Render export options"""
    
    st.markdown("### 💾 Export Options")
    
    # Text export
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

--------------------------------------------------------------------------------
INCIDENT DETAILS
--------------------------------------------------------------------------------
Date: {input_data.get('date', 'N/A')}
Time: {input_data.get('time', 'N/A')}
Location: {input_data.get('location', 'N/A')}
Severity: {input_data.get('severity', 'N/A')}

Description:
{input_data.get('description', 'N/A')}

================================================================================
ANALYSIS REPORT
================================================================================

{result.get('analysis', 'No analysis available')}

================================================================================
END OF REPORT
================================================================================
"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📥 Download TXT",
            data=export_text,
            file_name=f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col2:
        # JSON export
        json_data = {
            "metadata": {
                "generated": datetime.now().isoformat(),
                "tokens": result.get('tokens_used', 0),
                "cost": result.get('cost', 0)
            },
            "incident": input_data,
            "analysis": result.get('analysis', '')
        }
        
        st.download_button(
            label="📥 Download JSON",
            data=json.dumps(json_data, indent=2),
            file_name=f"incident_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    # Preview
    st.markdown("---")
    with st.expander("👁️ Preview Export"):
        st.code(export_text[:1000] + "..." if len(export_text) > 1000 else export_text)

# =============================================================================
# MAIN APPLICATION
# =============================================================================

def main():
    """Main application"""
    
    # Initialize
    init_session_state()
    
    # Header
    render_header()
    
    # Sidebar
    analysis_type = render_sidebar()
    
    # Main content
    if "Incident" in analysis_type:
        form_data = render_incident_form()
        
        if form_data:
            if form_data.get("preview"):
                st.info("### 📋 Sample Report Preview")
                
                client = DeepSeekClient("demo")
                result = client.get_demo_response("incident", {
                    "description": "Sample incident for preview",
                    "severity": "3 - Serious",
                    "location": "Sample Location",
                    "date": datetime.now().strftime('%Y-%m-%d'),
                    "time": datetime.now().strftime('%H:%M')
                })
                
                with st.expander("👁️ View Sample Report", expanded=True):
                    st.markdown(result.get('analysis', '')[:2000] + "\n\n*[Truncated for preview]*")
            
            else:
                with st.spinner("🔍 Analyzing incident..."):
                    api_key = st.session_state.api_key if not st.session_state.demo_mode else "demo"
                    client = DeepSeekClient(api_key)
                    
                    result = client.analyze("incident", form_data)
                    
                    render_analysis_result(result, form_data)
    
    else:
        st.info(f"**{analysis_type}** - Feature coming soon!")
        st.markdown("""
        ### Available Now:
        - 🚨 **Incident Investigation** - Full analysis with root cause, recommendations, and cost-benefit
        
        ### Coming Soon:
        - 📋 **Compliance Audit** - ISO standard gap analysis
        - 📜 **Policy Review** - Regulatory alignment checking
        - 🌱 **ESG Assessment** - Environmental, Social, Governance analysis
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 1rem; color: #666;'>
        <p><strong>Compliance Sentinel</strong> | Professional HSE Analysis Platform</p>
        <p style='font-size: 0.9rem;'>Powered by DeepSeek AI | Version 2.0</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
