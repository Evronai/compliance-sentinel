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
    initial_sidebar_state="expanded"
)

# =============================================================================
# CUSTOM CSS - Mobile optimized
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
        
        /* Stack columns on mobile */
        [data-testid="column"] {
            width: 100% !important;
            margin-bottom: 1rem;
        }
        
        /* Make buttons full width on mobile */
        .stButton > button {
            width: 100% !important;
        }
        
        /* Form elements mobile optimization */
        .stTextInput input, 
        .stTextArea textarea,
        .stSelectbox select {
            font-size: 16px !important; /* Prevents zoom on iOS */
        }
        
        /* Better spacing for mobile */
        .stForm {
            padding: 1rem !important;
        }
        
        /* Adjust sidebar for mobile */
        [data-testid="stSidebar"] {
            min-width: 100% !important;
            max-width: 100% !important;
        }
        
        /* Metric cards spacing */
        .stMetric {
            margin: 5px 0 !important;
            padding: 0.75rem !important;
        }
    }
    
    /* Keep all original styles and add mobile-friendly adjustments */
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
    
    /* Better textarea sizing for mobile */
    .stTextArea textarea {
        min-height: 100px !important;
        resize: vertical !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# SESSION STATE INITIALIZATION - Keep original
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
# DEEPSEEK API CLIENT - Keep original (truncated for brevity, but keep all original code)
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
        
        prompts = {
            "incident": """You are a Senior HSE (Health, Safety & Environment) Consultant with 15+ years of experience.

Provide a comprehensive incident analysis with this structure:

# INCIDENT ANALYSIS REPORT
## 1. EXECUTIVE SUMMARY
## 2. INCIDENT DETAILS
## 3. ROOT CAUSE ANALYSIS (5 Whys)
## 4. REGULATORY IMPLICATIONS
## 5. RISK ASSESSMENT
## 6. RECOMMENDATIONS (P1/P2/P3)
## 7. COST-BENEFIT ANALYSIS
## 8. LESSONS LEARNED

Use professional language with specific regulatory citations.""",

            "audit": """You are an ISO Lead Auditor with expertise in ISO 9001, 14001, 45001, and 27001.

Provide a comprehensive audit report with this structure:

# COMPLIANCE AUDIT REPORT
## 1. EXECUTIVE SUMMARY
## 2. AUDIT SCOPE & OBJECTIVES
## 3. METHODOLOGY
## 4. FINDINGS SUMMARY
## 5. DETAILED FINDINGS (by standard clause)
## 6. NON-CONFORMITIES (Major/Minor/Observations)
## 7. CORRECTIVE ACTION PLAN
## 8. RECOMMENDATIONS
## 9. FOLLOW-UP SCHEDULE

Use ISO audit terminology and cite specific clauses.""",

            "policy": """You are a Policy & Compliance Director with expertise in regulatory compliance.

Provide a comprehensive policy review with this structure:

# POLICY REVIEW REPORT
## 1. EXECUTIVE SUMMARY
## 2. POLICY OVERVIEW
## 3. REGULATORY ALIGNMENT ANALYSIS
## 4. GAP ANALYSIS
## 5. BEST PRACTICES COMPARISON
## 6. RECOMMENDATIONS
## 7. IMPLEMENTATION ROADMAP
## 8. REVIEW SCHEDULE

Cite specific regulations and industry standards.""",

            "esg": """You are an ESG (Environmental, Social, Governance) Director with expertise in GRI, SASB, and TCFD frameworks.

Provide a comprehensive ESG assessment with this structure:

# ESG PERFORMANCE ASSESSMENT
## 1. EXECUTIVE SUMMARY
## 2. ENVIRONMENTAL PERFORMANCE
## 3. SOCIAL PERFORMANCE
## 4. GOVERNANCE PERFORMANCE
## 5. MATERIALITY ASSESSMENT
## 6. BENCHMARKING & SCORING
## 7. RECOMMENDATIONS
## 8. REPORTING ALIGNMENT

Use recognized ESG frameworks and provide scoring."""
        }
        
        return prompts.get(prompt_type, prompts["incident"])
    
    def get_user_prompt(self, prompt_type: str, data: Dict[str, Any]) -> str:
        """Generate user prompt based on type and data"""
        
        if prompt_type == "incident":
            return f"""INCIDENT ANALYSIS REQUEST

**Incident Description:** {data.get('description', 'N/A')}

**Details:**
- Severity: {data.get('severity', 'N/A')}
- Location: {data.get('location', 'N/A')}
- Date: {data.get('date', 'N/A')}
- Time: {data.get('time', 'N/A')}

Provide comprehensive analysis."""

        elif prompt_type == "audit":
            return f"""COMPLIANCE AUDIT REQUEST

**Organization:** {data.get('organization', 'N/A')}
**Standards:** {data.get('standards', 'N/A')}
**Scope:** {data.get('scope', 'N/A')}
**Areas Reviewed:** {data.get('areas', 'N/A')}
**Findings:** {data.get('findings', 'N/A')}

Provide comprehensive audit report."""

        elif prompt_type == "policy":
            return f"""POLICY REVIEW REQUEST

**Policy Name:** {data.get('policy_name', 'N/A')}
**Policy Type:** {data.get('policy_type', 'N/A')}
**Industry:** {data.get('industry', 'N/A')}
**Jurisdiction:** {data.get('jurisdiction', 'N/A')}

**Policy Content:**
{data.get('content', 'N/A')}

Provide comprehensive review."""

        elif prompt_type == "esg":
            return f"""ESG ASSESSMENT REQUEST

**Organization:** {data.get('organization', 'N/A')}
**Industry:** {data.get('industry', 'N/A')}
**Reporting Period:** {data.get('period', 'N/A')}
**Framework:** {data.get('framework', 'N/A')}

**Environmental Data:** {data.get('environmental', 'N/A')}
**Social Data:** {data.get('social', 'N/A')}
**Governance Data:** {data.get('governance', 'N/A')}

Provide comprehensive ESG assessment."""

        return "Please analyze this data."
    
    def get_demo_response(self, prompt_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate demo response based on analysis type"""
        
        if prompt_type == "incident":
            report = self._generate_incident_demo(data)
        elif prompt_type == "audit":
            report = self._generate_audit_demo(data)
        elif prompt_type == "policy":
            report = self._generate_policy_demo(data)
        elif prompt_type == "esg":
            report = self._generate_esg_demo(data)
        else:
            report = "# Analysis Report\n\nDemo report generated."
        
        return {
            "success": True,
            "analysis": report,
            "tokens_used": len(report) // 4,
            "cost": 0.01,
            "model": "deepseek-chat-demo",
            "timestamp": datetime.now().isoformat()
        }
    
    def _generate_incident_demo(self, data: Dict[str, Any]) -> str:
        """Generate incident demo report"""
        description = data.get('description', 'workplace incident')
        severity = data.get('severity', '3 - Serious')
        location = data.get('location', 'Facility')
        
        return f"""# 🛡️ INCIDENT ANALYSIS REPORT

## 1. EXECUTIVE SUMMARY

A {severity.split('-')[1].strip().lower()} severity incident occurred at {location}. {description[:200]}

**Key Findings:**
- Root Cause: Procedural gap in safety protocols
- Risk Level: HIGH
- Immediate Action Required: Yes
- Estimated Implementation Cost: $22,500
- Projected Annual Savings: $120,000

## 2. INCIDENT DETAILS

- **Date:** {data.get('date', 'N/A')}
- **Time:** {data.get('time', 'N/A')}
- **Location:** {location}
- **Severity:** {severity}
- **Reported By:** {data.get('reported_by', 'Site personnel')}
- **Witnesses:** {data.get('witnesses', 'None listed')}

## 3. ROOT CAUSE ANALYSIS (5 Whys)

1. **Why did the incident occur?** → Hazardous condition present
2. **Why was hazard present?** → Maintenance backlog
3. **Why was there backlog?** → Inadequate prioritization
4. **Why inadequate prioritization?** → Missing procedures
5. **Why no procedures?** → **ROOT CAUSE: Systematic gap in safety management**

## 4. REGULATORY IMPLICATIONS

**OSHA 1910.22(a)(1)** - Walking-Working Surfaces
- Status: Potential non-compliance
- Citation Risk: High
- Penalty: $7,000-$14,000

**ISO 45001:2018** - OH&S Management
- Clause 8.1.2: Gap in hazard elimination
- Clause 6.1.2.3: Risk assessment needs update

## 5. RISK ASSESSMENT

- **Likelihood:** 4/5 (Probable)
- **Severity:** 4/5 (Major)
- **Risk Score:** 16/25 (HIGH RISK)

## 6. RECOMMENDATIONS

### Priority 1 - Immediate (0-24h) - $1,500
1. Physical containment and barriers
2. Emergency cleanup/remediation
3. Safety alert distribution

### Priority 2 - Short-term (1-7 days) - $9,500
4. Safety audit and inspection
5. Interim control measures
6. Training program deployment
7. Procedure review and update

### Priority 3 - Long-term (1-3 months) - $11,500
8. Engineering controls installation
9. Management system enhancement
10. Safety culture program

**Total Investment: $22,500**

## 7. COST-BENEFIT ANALYSIS

**Implementation Costs:** $22,500

**Annual Savings:**
- Avoided injuries: $35,000
- Prevented damage: $25,000
- Avoided penalties: $10,000
- Reduced insurance: $12,000
- Efficiency gains: $18,000
- Reduced downtime: $10,000
- **Total: $120,000**

**ROI:** 433% | **Payback:** 2.25 months

## 8. LESSONS LEARNED

1. Procedural gaps have real consequences
2. Early intervention is cost-effective
3. Communication is critical
4. Proactive risk assessment essential
5. Training is an investment, not a cost

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Report ID:** INC-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(description.encode()).hexdigest()[:6].upper()}
"""

    def _generate_audit_demo(self, data: Dict[str, Any]) -> str:
        """Generate audit demo report"""
        org = data.get('organization', 'Organization')
        standards = data.get('standards', 'ISO 45001:2018')
        
        return f"""# 📋 COMPLIANCE AUDIT REPORT

## 1. EXECUTIVE SUMMARY

Compliance audit conducted for **{org}** against **{standards}** standard(s).

**Audit Results:**
- Total Findings: 12
- Major Non-Conformities: 2
- Minor Non-Conformities: 5
- Observations: 5
- Overall Compliance: 78%

**Recommendation:** Certification recommended pending closure of major NCs within 90 days.

## 2. AUDIT SCOPE & OBJECTIVES

**Organization:** {org}
**Standards Audited:** {standards}
**Audit Type:** {data.get('scope', 'Full System Audit')}
**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Lead Auditor:** Compliance Sentinel AI
**Audit Team:** 3 auditors

**Objectives:**
1. Assess conformity to standard requirements
2. Evaluate effectiveness of management system
3. Identify improvement opportunities
4. Verify corrective actions from previous audit

**Areas Covered:** {data.get('areas', 'All operational areas')}

## 3. METHODOLOGY

**Audit Approach:**
- Document review (policies, procedures, records)
- On-site inspections and walkthroughs
- Personnel interviews (25 staff members)
- Process observations
- Records sampling (150 documents)

**Standards Used:**
- ISO 45001:2018 - OH&S Management Systems
- ISO 19011:2018 - Auditing Guidelines
- ANSI/ASQ Z1.13 - Sampling Procedures

## 4. FINDINGS SUMMARY

| Category | Count | % of Total |
|----------|-------|------------|
| Major NC | 2 | 17% |
| Minor NC | 5 | 42% |
| Observations | 5 | 41% |
| **Total** | **12** | **100%** |

**Compliance Score:** 78% (Target: >85%)

## 5. DETAILED FINDINGS

### MAJOR NON-CONFORMITIES

**NC-001: Risk Assessment Process (Clause 6.1.2)**
- **Finding:** Risk assessments not conducted for new equipment installations
- **Evidence:** 3 out of 5 new machines installed without documented risk assessment
- **Impact:** HIGH - Unidentified hazards may exist
- **Root Cause:** Procedure gap in change management process
- **Requirement:** ISO 45001:2018 Clause 6.1.2.1

**NC-002: Emergency Preparedness (Clause 8.2)**
- **Finding:** Emergency drills not conducted as per schedule
- **Evidence:** Last fire drill conducted 8 months ago (requirement: quarterly)
- **Impact:** HIGH - Emergency response capability unknown
- **Root Cause:** Lack of drill coordination and scheduling
- **Requirement:** ISO 45001:2018 Clause 8.2

### MINOR NON-CONFORMITIES

**NC-003: Training Records (Clause 7.2)**
- **Finding:** Incomplete training records for 12% of workforce
- **Evidence:** 15 out of 125 employees missing training completion documentation
- **Impact:** MEDIUM
- **Corrective Action:** Update training matrix and complete missing records

**NC-004: Incident Investigation (Clause 10.2)**
- **Finding:** Incident investigations not completed within required timeframe
- **Evidence:** 3 out of 8 incidents exceeded 7-day investigation deadline
- **Impact:** MEDIUM
- **Corrective Action:** Implement investigation tracking system

**NC-005: Management Review (Clause 9.3)**
- **Finding:** Management review agenda incomplete
- **Evidence:** Review did not cover all required inputs per Clause 9.3.2
- **Impact:** MEDIUM
- **Corrective Action:** Update review template

**NC-006: Document Control (Clause 7.5)**
- **Finding:** Obsolete documents found in work area
- **Evidence:** 2 superseded procedures still in circulation
- **Impact:** LOW
- **Corrective Action:** Strengthen document control process

**NC-007: Contractor Management (Clause 8.1.4.2)**
- **Finding:** Contractor OH&S performance not monitored
- **Evidence:** No tracking of contractor incidents or near-misses
- **Impact:** MEDIUM
- **Corrective Action:** Implement contractor monitoring system

### OBSERVATIONS

**OBS-001:** Internal audit frequency could be increased for high-risk areas
**OBS-002:** Safety suggestion program has low participation (8%)
**OBS-003:** PPE inspection records could be more detailed
**OBS-004:** Near-miss reporting trending downward (possible under-reporting)
**OBS-005:** Preventive maintenance tracking could be digitized

## 6. NON-CONFORMITIES BY STANDARD CLAUSE

| Clause | Requirement | Major | Minor | Obs |
|--------|-------------|-------|-------|-----|
| 6.1.2 | Risk Assessment | 1 | 0 | 0 |
| 7.2 | Competence | 0 | 1 | 0 |
| 7.5 | Documented Info | 0 | 1 | 1 |
| 8.1.4.2 | Contractors | 0 | 1 | 0 |
| 8.2 | Emergency Prep | 1 | 0 | 1 |
| 9.3 | Mgmt Review | 0 | 1 | 0 |
| 10.2 | Incident Inv. | 0 | 1 | 2 |

## 7. CORRECTIVE ACTION PLAN

### Major NC-001: Risk Assessment Process

**Required Actions:**
1. Conduct risk assessments for 3 machines (by Week 2)
2. Update change management procedure (by Week 3)
3. Train relevant personnel (by Week 4)
4. Verify implementation (by Week 6)

**Responsible:** Safety Manager
**Target Completion:** 6 weeks
**Verification Method:** Document review + on-site verification

### Major NC-002: Emergency Preparedness

**Required Actions:**
1. Schedule and conduct fire drill (by Week 2)
2. Create annual drill schedule (by Week 3)
3. Assign drill coordinator role (by Week 3)
4. Implement drill tracking system (by Week 4)

**Responsible:** Facilities Manager
**Target Completion:** 4 weeks
**Verification Method:** Drill records + observation

### Minor NCs (NC-003 through NC-007)

**Timeline:** 8-12 weeks
**Approach:** Standard CAR process
**Review:** Monthly progress tracking

## 8. RECOMMENDATIONS

### Immediate Priorities (0-30 days)
1. Close both major non-conformities
2. Initiate corrective actions for minor NCs
3. Assign responsibility and resources
4. Establish monitoring mechanisms

### Short-term Improvements (1-3 months)
5. Enhance risk assessment methodology
6. Digitize safety management processes
7. Strengthen contractor oversight
8. Improve safety culture engagement

### Long-term Excellence (3-12 months)
9. Implement predictive analytics for risks
10. Achieve ISO 45001 certification
11. Benchmark against industry leaders
12. Pursue continuous improvement initiatives

## 9. FOLLOW-UP SCHEDULE

**30-Day Review:**
- Verify major NC corrective actions initiated
- Review minor NC progress
- Assess resource allocation

**60-Day Review:**
- Verify major NC effectiveness
- Complete minor NC closures
- Assess observation responses

**90-Day Closure Audit:**
- Formal verification of all major NCs
- Re-assessment of affected areas
- Certification recommendation decision

**6-Month Surveillance:**
- Verify sustained compliance
- Monitor continuous improvement
- Plan next full audit

## 10. AUDIT CONCLUSION

**Overall Assessment:** The organization demonstrates a functional OH&S management system with opportunities for improvement.

**Strengths:**
- Strong management commitment
- Good hazard identification processes
- Effective incident response
- Engaged workforce

**Areas for Improvement:**
- Risk assessment for change management
- Emergency preparedness scheduling
- Record keeping consistency
- Contractor oversight

**Certification Recommendation:** CONDITIONAL - Subject to closure of major non-conformities within 90 days.

**Next Audit:** Scheduled in 12 months (or upon major NC closure)

---

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Report ID:** AUD-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(org.encode()).hexdigest()[:6].upper()}
**Lead Auditor:** Compliance Sentinel AI System
**Audit Standard:** {standards}
"""

    def _generate_policy_demo(self, data: Dict[str, Any]) -> str:
        """Generate policy review demo report"""
        policy_name = data.get('policy_name', 'Safety Policy')
        policy_type = data.get('policy_type', 'Health & Safety')
        
        return f"""# 📜 POLICY REVIEW REPORT

## 1. EXECUTIVE SUMMARY

Comprehensive review of **{policy_name}** ({policy_type}) conducted.

**Review Results:**
- Regulatory Alignment: 85%
- Best Practice Compliance: 78%
- Gaps Identified: 8
- Recommendations: 15
- Overall Grade: B+ (Good, needs minor improvements)

**Key Findings:**
- Policy generally compliant with current regulations
- Some sections require updating for recent regulatory changes
- Industry best practices not fully incorporated
- Implementation guidance could be strengthened

## 2. POLICY OVERVIEW

**Policy Name:** {policy_name}
**Policy Type:** {policy_type}
**Industry:** {data.get('industry', 'Manufacturing')}
**Jurisdiction:** {data.get('jurisdiction', 'United States')}
**Current Version:** {data.get('version', '2.1')}
**Last Updated:** {data.get('last_updated', '2023-01-15')}
**Review Date:** {datetime.now().strftime('%Y-%m-%d')}

**Scope:** This policy applies to all employees, contractors, and visitors at all company facilities.

**Purpose:** To establish requirements and responsibilities for maintaining a safe and healthy workplace.

**Policy Owner:** {data.get('owner', 'HSE Director')}

## 3. REGULATORY ALIGNMENT ANALYSIS

### Federal Regulations

**OSHA Standards (29 CFR)**

| Regulation | Requirement | Policy Coverage | Gap |
|------------|-------------|----------------|-----|
| 1910.132 | PPE Requirements | ✅ Covered | None |
| 1910.147 | LOTO | ✅ Covered | Minor update needed |
| 1910.1200 | HazCom | ✅ Covered | None |
| 1904 | Recordkeeping | ⚠️ Partial | Clarification needed |
| 1910.38 | Emergency Plans | ✅ Covered | None |

**Overall OSHA Alignment:** 90%

### State/Local Regulations

**California Cal/OSHA (Example):**
- Heat Illness Prevention: ⚠️ Not addressed (if applicable)
- Workplace Violence: ⚠️ Limited coverage
- COVID-19 Requirements: ✅ Recently updated

**State Alignment:** 75%

### Industry Standards

**ANSI/ASSP Standards:**
- Z10 (OH&S Management): ✅ Well aligned
- Z15.1 (Fleet Safety): ⚠️ Not covered (if fleet operations exist)
- Z490.1 (Training): ✅ Covered

**ISO Standards:**
- ISO 45001:2018: ✅ 85% aligned
- ISO 14001:2015: ⚠️ Environmental aspects limited

**Industry Alignment:** 80%

## 4. GAP ANALYSIS

### High Priority Gaps

**GAP-001: Emergency Response Procedures**
- **Issue:** Policy references but doesn't detail emergency procedures
- **Impact:** HIGH - Regulatory requirement
- **Regulation:** OSHA 1910.38
- **Recommendation:** Add detailed emergency response section
- **Effort:** Medium (2-3 weeks)

**GAP-002: Incident Reporting Timelines**
- **Issue:** No clear timelines for incident reporting
- **Impact:** HIGH - Delays in OSHA reporting possible
- **Regulation:** OSHA 1904.39
- **Recommendation:** Add specific reporting timelines (8-hour, 24-hour)
- **Effort:** Low (1 week)

**GAP-003: Contractor Safety Management**
- **Issue:** Limited guidance on contractor oversight
- **Impact:** MEDIUM - Liability exposure
- **Regulation:** OSHA 1910.119(h) (if applicable)
- **Recommendation:** Expand contractor requirements section
- **Effort:** Medium (2 weeks)

### Medium Priority Gaps

**GAP-004: Mental Health & Wellbeing**
- **Issue:** No coverage of workplace mental health
- **Impact:** MEDIUM - Emerging regulatory focus
- **Trend:** Increasing state-level requirements
- **Recommendation:** Add mental health support section
- **Effort:** Medium (3 weeks)

**GAP-005: Remote Work Safety**
- **Issue:** Policy doesn't address remote/hybrid work
- **Impact:** MEDIUM - Compliance gap for remote workers
- **Recommendation:** Add remote work safety section
- **Effort:** Low (1-2 weeks)

**GAP-006: Environmental Considerations**
- **Issue:** Limited environmental protection guidance
- **Impact:** MEDIUM - Growing stakeholder expectations
- **Recommendation:** Integrate environmental responsibilities
- **Effort:** Medium (2-3 weeks)

### Low Priority Gaps

**GAP-007: Technology & Automation Safety**
- **Issue:** No specific guidance for automated systems
- **Recommendation:** Add robotics/automation safety section
- **Effort:** Low (1 week)

**GAP-008: Workplace Violence Prevention**
- **Issue:** Limited coverage beyond general safety
- **Recommendation:** Expand workplace violence section
- **Effort:** Low (1 week)

## 5. BEST PRACTICES COMPARISON

### Industry Leading Practices

**✅ Policy Includes:**
- Clear accountability structure
- Employee participation mechanisms
- Regular safety training requirements
- Incident investigation procedures
- Continuous improvement commitment

**⚠️ Policy Missing:**
- Behavioral-based safety programs
- Leading indicator metrics
- Safety leadership competencies
- Near-miss reporting incentives
- Predictive analytics for risk

### Benchmark Comparison

| Element | Company | Industry Leader | Gap |
|---------|---------|----------------|-----|
| Policy Scope | Good | Excellent | Minor |
| Accountability | Good | Excellent | Minor |
| Training Req. | Good | Excellent | Medium |
| Measurement | Fair | Excellent | Significant |
| Resources | Good | Excellent | Minor |
| Culture | Good | Excellent | Medium |

**Overall Benchmark Score:** 78% of industry leaders

## 6. RECOMMENDATIONS

### Category A: Compliance (MUST DO)

**REC-001: Update Emergency Response Section** [HIGH]
- Add detailed emergency procedures
- Include evacuation plans reference
- Specify emergency contact protocols
- Timeline: 30 days

**REC-002: Clarify Incident Reporting Timelines** [HIGH]
- Add OSHA reporting requirements (8-hour, 24-hour)
- Include state-specific requirements
- Define internal escalation process
- Timeline: 14 days

**REC-003: Enhance Contractor Safety Requirements** [MEDIUM]
- Add contractor qualification criteria
- Include safety performance monitoring
- Specify oversight responsibilities
- Timeline: 45 days

### Category B: Best Practice (SHOULD DO)

**REC-004: Add Mental Health Provisions** [MEDIUM]
- Include mental health support resources
- Address workplace stress management
- Define available support programs
- Timeline: 60 days

**REC-005: Incorporate Remote Work Safety** [MEDIUM]
- Add home office ergonomics
- Include remote work safety checklist
- Define equipment provision requirements
- Timeline: 45 days

**REC-006: Strengthen Environmental Integration** [MEDIUM]
- Link safety and environmental objectives
- Include waste management responsibilities
- Add environmental incident reporting
- Timeline: 60 days

**REC-007: Implement Leading Indicators** [MEDIUM]
- Add proactive safety metrics
- Include near-miss reporting targets
- Define safety observation goals
- Timeline: 90 days

### Category C: Excellence (NICE TO HAVE)

**REC-008: Behavioral-Based Safety Program** [LOW]
- Add BBS program framework
- Include observation protocols
- Define feedback mechanisms
- Timeline: 120 days

**REC-009: Technology Safety Guidance** [LOW]
- Add automation safety requirements
- Include AI/robotics considerations
- Define human-machine interface standards
- Timeline: 90 days

**REC-010: Enhanced Training Framework** [LOW]
- Add competency-based training
- Include microlearning options
- Define virtual training standards
- Timeline: 120 days

## 7. IMPLEMENTATION ROADMAP

### Phase 1: Compliance (0-60 days)

**Month 1:**
- Week 1-2: Address GAP-002 (Incident Reporting)
- Week 3-4: Address GAP-001 (Emergency Response)

**Month 2:**
- Week 5-6: Address GAP-003 (Contractor Management)
- Week 7-8: Stakeholder review and feedback

**Deliverable:** Compliance-ready policy update v2.2

### Phase 2: Best Practice (60-120 days)

**Month 3:**
- Address GAP-004 (Mental Health)
- Address GAP-005 (Remote Work)

**Month 4:**
- Address GAP-006 (Environmental)
- Implement REC-007 (Leading Indicators)

**Deliverable:** Industry-aligned policy update v2.3

### Phase 3: Excellence (120-180 days)

**Month 5-6:**
- Implement remaining recommendations
- Benchmark against industry leaders
- Continuous improvement planning

**Deliverable:** Best-in-class policy v3.0

## 8. REVIEW SCHEDULE

### Ongoing Monitoring

**Quarterly Reviews:**
- Regulatory update scanning
- Incident trend analysis
- Effectiveness metrics review

**Annual Full Review:**
- Comprehensive regulatory alignment check
- Industry benchmark comparison
- Stakeholder feedback integration
- Full policy refresh

**Trigger-Based Reviews:**
- Significant regulatory changes
- Major incidents or trends
- Organizational restructuring
- New technology/processes

### Next Scheduled Review

**Date:** {(datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')}
**Type:** Full policy review
**Responsibility:** HSE Director
**Resources Required:** 40 hours

## 9. APPROVAL & DISTRIBUTION

**Review Completed By:** Compliance Sentinel AI
**Review Date:** {datetime.now().strftime('%Y-%m-%d')}

**Recommended Approvers:**
- HSE Director (Policy Owner)
- Legal Counsel (Regulatory Compliance)
- HR Director (Employee Relations)
- Operations Director (Implementation)
- Executive Leadership (Strategic Alignment)

**Distribution:**
- All employees (via LMS/intranet)
- New hire orientation
- Contractor onboarding
- Supplier qualification
- Regulatory submissions (as needed)

## 10. CONCLUSION

The **{policy_name}** is fundamentally sound and demonstrates good regulatory compliance (85%) and reasonable alignment with industry best practices (78%).

**Strengths:**
- Clear structure and accountability
- Good regulatory foundation
- Employee participation focus
- Regular training requirements

**Improvement Areas:**
- Emergency response detail
- Incident reporting timelines
- Contractor oversight
- Emerging topics (mental health, remote work)
- Leading indicator metrics

**Overall Grade: B+ (Good)**

With implementation of the recommended updates, the policy can achieve **A-grade (Excellent)** status within 6 months.

**Risk Assessment:** Current gaps present MEDIUM organizational risk. Compliance gaps (GAP-001, GAP-002) should be addressed immediately.

**Investment Required:**
- Internal resources: 120 hours
- External consultation: $5,000-$8,000 (if needed)
- Training/communication: $3,000-$5,000
- **Total: $8,000-$13,000**

**Expected Benefits:**
- Enhanced regulatory compliance
- Reduced liability exposure
- Improved safety culture
- Better stakeholder confidence
- Industry leadership positioning

---

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Report ID:** POL-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(policy_name.encode()).hexdigest()[:6].upper()}
**Reviewer:** Compliance Sentinel AI System
"""

    def _generate_esg_demo(self, data: Dict[str, Any]) -> str:
        """Generate ESG assessment demo report"""
        org = data.get('organization', 'Organization')
        industry = data.get('industry', 'Manufacturing')
        
        return f"""# 🌱 ESG PERFORMANCE ASSESSMENT

## 1. EXECUTIVE SUMMARY

ESG assessment conducted for **{org}** in the **{industry}** sector.

**Overall ESG Score: 72/100 (B Rating)**

| Pillar | Score | Grade | Trend |
|--------|-------|-------|-------|
| Environmental | 68/100 | C+ | → Stable |
| Social | 75/100 | B | ↗ Improving |
| Governance | 78/100 | B+ | ↗ Improving |

**Key Findings:**
- Strong governance framework in place
- Social performance above industry average
- Environmental performance needs improvement
- Climate transition planning required
- Good stakeholder engagement practices

**Recommendation:** Focus on environmental performance improvements and climate strategy to achieve A-rating.

## 2. ENVIRONMENTAL PERFORMANCE (Score: 68/100)

### Climate Change & Emissions

**Greenhouse Gas Emissions:**
- **Scope 1:** 15,000 tCO2e (Direct emissions)
- **Scope 2:** 8,500 tCO2e (Purchased energy)
- **Scope 3:** 42,000 tCO2e (Value chain) - Limited data
- **Total:** 65,500 tCO2e
- **Intensity:** 12.5 tCO2e per $M revenue

**Performance vs Targets:**
- Current vs. 2020 Baseline: -8% (Target: -15%) ⚠️
- 2030 Target: -50% (Science-based target needed)
- 2050 Goal: Net Zero (pathway unclear)

**Score: 65/100** - Behind reduction targets

### Energy Management

**Energy Consumption:**
- Total: 185,000 MWh annually
- Renewable: 28% (52,000 MWh) ↗
- Non-renewable: 72% (133,000 MWh)
- Energy Intensity: 3.5 MWh per $M revenue

**Initiatives:**
- Solar installation: 15% of facilities
- LED retrofit: 75% complete
- Energy management system: ISO 50001 (2 sites)

**Score: 70/100** - Good progress, increase renewables

### Water Stewardship

**Water Usage:**
- Total withdrawal: 450,000 m³/year
- Water stressed regions: 35% of operations ⚠️
- Recycled/reused: 15%
- Discharge quality: 100% compliant

**Score: 66/100** - Address water-stressed locations

### Waste & Circular Economy

**Waste Generation:**
- Total waste: 8,500 tonnes/year
- Hazardous: 450 tonnes (5.3%)
- Recycling rate: 58%
- Landfill diversion: 72%
- Zero waste sites: 2 out of 12

**Score: 70/100** - Good recycling, increase circularity

### Biodiversity & Land Use

**Impact Assessment:**
- Facilities in sensitive areas: 1 site
- Biodiversity action plans: Limited
- Land restoration: Not applicable
- Habitat protection: Basic measures

**Score: 60/100** - Strengthen biodiversity strategy

### Environmental Compliance

**Regulatory Performance:**
- Environmental violations: 2 (minor)
- Fines/penalties: $15,000
- Spill incidents: 1 (contained, no impact)
- Audit findings: 8 (all closed)

**Score: 75/100** - Generally compliant

## 3. SOCIAL PERFORMANCE (Score: 75/100)

### Employee Health & Safety

**Safety Performance:**
- LTIFR (Lost Time Injury Frequency): 0.8 (Industry avg: 1.2) ✅
- TRIFR (Total Recordable Injury): 2.1 (Industry avg: 3.5) ✅
- Fatalities: 0
- Near-miss reporting: 450 reports (strong culture)
- Safety training hours: 12,500 hours/year

**Score: 85/100** - Excellent safety performance

### Labor Practices

**Workforce Demographics:**
- Total employees: 2,500
- Temporary/contract: 18%
- Union representation: 45%
- Turnover rate: 12% (Industry: 15%) ✅
- Employee satisfaction: 72%

**Diversity & Inclusion:**
- Women in workforce: 32%
- Women in leadership: 28%
- Ethnic diversity: 42%
- Pay equity ratio: 0.98 (M/F)
- D&I training: 95% completion

**Score: 78/100** - Good, improve gender diversity in leadership

### Human Rights

**Human Rights Due Diligence:**
- Policy in place: ✅
- Supplier assessments: 65% of spend
- Grievance mechanism: ✅ Active
- Child labor risk: Low (verified)
- Forced labor risk: Low (verified)
- Modern Slavery Statement: ✅ Published

**Score: 80/100** - Strong framework

### Community Engagement

**Community Investment:**
- Community spend: $850,000 (0.5% of profit)
- Employee volunteering: 3,200 hours
- Local hiring: 78%
- Community complaints: 8 (all resolved)
- Stakeholder satisfaction: 76%

**Score: 72/100** - Good engagement, increase investment

### Supply Chain Responsibility

**Supplier Management:**
- Supplier code of conduct: ✅ 100% coverage
- Supplier audits: 45% (target: 80%)
- Critical suppliers assessed: 90%
- Supplier ESG training: 60%
- Conflict minerals: Compliant (3TG)

**Score: 70/100** - Increase audit coverage

### Product Responsibility

**Product Safety & Quality:**
- Product recalls: 0
- Customer complaints: <0.1%
- Product certifications: ISO 9001
- Sustainable products: 35% of revenue
- Product lifecycle assessments: 15% of products

**Score: 75/100** - Strong quality, expand sustainability

## 4. GOVERNANCE PERFORMANCE (Score: 78/100)

### Board Composition & Independence

**Board Structure:**
- Board size: 9 directors
- Independent directors: 67% ✅
- Women on board: 33% (Target: 40%)
- Average tenure: 6 years
- Board diversity: Improving

**Committees:**
- Audit Committee: ✅ Independent chair
- Compensation Committee: ✅
- Sustainability Committee: ✅ (Added 2023)

**Score: 80/100** - Strong independence

### Business Ethics

**Ethics & Compliance:**
- Code of conduct: ✅ 100% training
- Anti-corruption policy: ✅
- Whistleblower hotline: ✅ Active
- Ethics training: 98% completion
- Violations reported: 12 (all investigated)
- Disciplinary actions: 3

**Score: 82/100** - Excellent ethics culture

### Risk Management

**ERM Framework:**
- Risk management system: ✅ Mature
- Climate risk assessment: ⚠️ Limited
- Cybersecurity program: ✅ Strong
- Business continuity: ✅ Tested
- Insurance coverage: ✅ Adequate

**Score: 75/100** - Strengthen climate risk

### Stakeholder Engagement

**Engagement Practices:**
- Shareholder engagement: Regular
- Annual materiality assessment: ✅
- Stakeholder advisory panel: ✅
- Community consultation: Active
- Investor ESG calls: Quarterly

**Score: 78/100** - Good engagement

### Transparency & Reporting

**Disclosure Quality:**
- Sustainability report: ✅ Annual (GRI Standards)
- TCFD alignment: Partial (50%)
- SASB disclosure: ⚠️ Not yet
- CDP reporting: Climate (B), Water (B-)
- External assurance: Limited

**Score: 70/100** - Improve disclosure frameworks

### Executive Compensation

**Compensation Structure:**
- ESG metrics in compensation: 15% weighting
- Clawback provisions: ✅
- Say-on-pay approval: 92%
- CEO pay ratio: 85:1 (Industry: 120:1) ✅
- Long-term incentives: 60% of package

**Score: 80/100** - Well structured

## 5. MATERIALITY ASSESSMENT

**Top Material Topics (Stakeholder Impact × Business Impact):**

### High Priority (Score >8.0)
1. **Climate Change** (9.2) - Emissions reduction & transition
2. **Employee Safety** (9.0) - Zero harm culture
3. **Business Ethics** (8.8) - Compliance & integrity
4. **Energy Management** (8.5) - Renewable transition
5. **Diversity & Inclusion** (8.3) - Workforce equity

### Medium Priority (Score 6.0-8.0)
6. **Water Management** (7.8)
7. **Waste & Circularity** (7.5)
8. **Supply Chain Labor** (7.2)
9. **Community Impact** (7.0)
10. **Product Sustainability** (6.8)

### Monitoring (Score <6.0)
11. Biodiversity (5.8)
12. Political Contributions (5.2)
13. Tax Transparency (5.0)

## 6. BENCHMARKING & SCORING

### Industry Comparison

| Metric | Company | Industry Avg | Best-in-Class | Gap |
|--------|---------|-------------|---------------|-----|
| Overall ESG | 72 | 68 | 85 | -13 |
| Environmental | 68 | 65 | 82 | -14 |
| Social | 75 | 70 | 88 | -13 |
| Governance | 78 | 72 | 90 | -12 |

**Position:** Above average, gap to leaders

### Rating Agency Comparison

**Current Ratings:**
- MSCI ESG: A (Industry leader: AA)
- Sustainalytics: 22.5 (Medium risk)
- CDP Climate: B (Target: A)
- CDP Water: B- (Target: A-)
- EcoVadis: Silver (Target: Gold)

**Rating Outlook:** Stable to positive with improvements

### SDG Alignment

**Primary SDG Contributions:**
- SDG 7 (Clean Energy): Moderate impact
- SDG 8 (Decent Work): Strong impact
- SDG 12 (Responsible Consumption): Moderate impact
- SDG 13 (Climate Action): Limited impact ⚠️

## 7. RECOMMENDATIONS

### Priority 1: Environmental Acceleration (0-12 months)

**REC-001: Science-Based Targets Initiative (SBTi)**
- Set validated science-based emissions targets
- Develop detailed decarbonization roadmap
- Allocate capital for transition ($15M)
- **Impact:** Improve Environmental score by 10 points

**REC-002: Renewable Energy Acceleration**
- Target: 50% renewable by 2025 (from 28%)
- Execute 20MW solar installation program
- Sign virtual PPAs for 30,000 MWh
- **Investment:** $12M | **Payback:** 6 years

**REC-003: Water Stewardship in Stressed Regions**
- Implement water recycling (target: 40%)
- Conduct water risk assessments
- Set site-specific reduction targets
- **Investment:** $3M

### Priority 2: Social Excellence (6-18 months)

**REC-004: Diversity Leadership Target**
- Women in leadership: 40% by 2026
- Launch mentorship program
- Strengthen inclusive hiring
- **Investment:** $500K/year

**REC-005: Supply Chain Transparency**
- Increase supplier audits to 80%
- Implement blockchain traceability (pilot)
- Publish supplier diversity metrics
- **Investment:** $1.5M

### Priority 3: Governance Enhancement (12-24 months)

**REC-006: Climate Governance**
- Full TCFD alignment by 2025
- Enhance climate risk disclosure
- Scenario analysis (1.5°C, 2°C, 3°C)
- **Investment:** $250K

**REC-007: ESG Reporting Framework**
- Adopt SASB standards
- Obtain limited assurance on key metrics
- Enhance digital ESG data platform
- **Investment:** $400K

**REC-008: Increase ESG Compensation Weighting**
- Increase ESG metrics to 25% (from 15%)
- Add specific climate targets
- Include diversity metrics
- **Investment:** Neutral

## 8. REPORTING ALIGNMENT

### Current Framework Usage

**Global Reporting Initiative (GRI):**
- Coverage: 85% of GRI Standards
- Quality: Good
- Gap: Limited sector-specific disclosures

**Task Force on Climate-related Financial Disclosures (TCFD):**
- Governance: ✅ Fully aligned
- Strategy: ⚠️ Partial (50%)
- Risk Management: ✅ Fully aligned
- Metrics & Targets: ⚠️ Partial (60%)
- **Overall:** 75% aligned

**Sustainability Accounting Standards Board (SASB):**
- Coverage: 40% of industry-specific metrics
- **Recommendation:** Adopt fully by 2025

**United Nations Global Compact:**
- Status: Signatory ✅
- Communication on Progress: Published annually

### Recommended Enhancements

1. **Full TCFD compliance** (2025)
2. **SASB adoption** (2025)
3. **Limited assurance** on emissions, safety, diversity (2025)
4. **Reasonable assurance** on emissions (2027)
5. **Integrated reporting** (2026)

## 9. ACTION PLAN & TIMELINE

### Year 1 (2024-2025)

**Q1-Q2:**
- Launch SBTi commitment process
- Begin renewable energy procurement
- Initiate water stewardship program
- Enhance supplier audit program

**Q3-Q4:**
- Submit science-based targets for validation
- Complete TCFD strategy disclosure
- Achieve 40% renewable energy
- Launch diversity mentorship program

**Investment:** $18M
**Expected ESG Score:** 75 (+3)

### Year 2 (2025-2026)

**Full Year:**
- Achieve SBTi validation
- 50% renewable energy
- SASB reporting implementation
- 40% women in leadership
- Limited assurance on key metrics

**Investment:** $12M
**Expected ESG Score:** 78 (+6 from baseline)

### Year 3 (2026-2027)

**Full Year:**
- 65% renewable energy
- 40% water recycling
- Integrated reporting
- Industry ESG leadership

**Investment:** $10M
**Expected ESG Score:** 82 (+10 from baseline, A-rating)

## 10. FINANCIAL IMPLICATIONS

### Investment Summary

| Category | 3-Year Investment | Annual Benefit | Payback |
|----------|------------------|----------------|---------|
| Renewable Energy | $24M | $3.5M | 6.9 years |
| Energy Efficiency | $8M | $2.2M | 3.6 years |
| Water Management | $4M | $0.8M | 5.0 years |
| Social Programs | $3M | (Intangible) | N/A |
| Governance/Reporting | $2M | (Risk reduction) | N/A |
| **Total** | **$41M** | **$6.5M** | **6.3 years** |

### Business Value

**Tangible Benefits:**
- Energy cost savings: $6.5M/year
- Reduced regulatory risk: $2M/year
- Insurance premium reduction: $500K/year
- Improved resource efficiency: $1.5M/year

**Intangible Benefits:**
- Enhanced brand reputation
- Better talent attraction/retention
- Improved investor perception
- Reduced long-term transition risks
- License to operate in restricted markets

**ESG-Linked Financing:**
- Potential 0.25% interest rate reduction on sustainability-linked loans
- Value on $500M debt: $1.25M/year savings

### Risk Mitigation Value

- Regulatory compliance risk: $5M potential exposure
- Reputational risk: $10M+ potential exposure
- Climate transition risk: $50M+ potential exposure
- Stakeholder activism risk: Moderate

**Total Risk Mitigation Value:** $65M+ over 10 years

## CONCLUSION

**{org}** demonstrates solid ESG performance with a score of 72/100 (B rating), positioning above industry average but with clear opportunities for leadership.

**Key Strengths:**
- Strong safety culture and performance
- Robust governance framework
- Good stakeholder engagement
- Ethical business practices

**Critical Improvement Areas:**
- Climate strategy and emissions reduction
- Renewable energy transition
- Enhanced environmental disclosure
- Supplier sustainability oversight

**Path to Excellence:**
With focused investment of $41M over 3 years, the organization can achieve:
- **A-rating (82/100)** ESG score
- Industry leadership position
- Enhanced stakeholder value
- Reduced long-term risks
- Competitive advantage in ESG-conscious markets

**Recommended Next Steps:**
1. Executive leadership review and approval
2. SBTi commitment letter (immediate)
3. Capital allocation for renewables (Q1)
4. Enhanced disclosure roadmap (Q2)
5. Quarterly progress monitoring

---

**Report Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Report ID:** ESG-{datetime.now().strftime('%Y%m%d')}-{hashlib.md5(org.encode()).hexdigest()[:6].upper()}
**Assessment Framework:** GRI, TCFD, SASB, MSCI ESG
**Reporting Period:** {data.get('period', 'FY 2024')}
**Industry Sector:** {industry}
"""

# =============================================================================
# UI COMPONENTS - Minimal mobile optimizations
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
                "📋 Compliance Audit",
                "📜 Policy Review",
                "🌱 ESG Assessment"
            ],
            label_visibility="collapsed"
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
    """Render incident analysis form - mobile optimized"""
    st.markdown("## 🚨 Incident Investigation Report")
    
    with st.form("incident_form", clear_on_submit=False):
        
        description = st.text_area(
            "Incident Description:",
            height=120,  # Reduced for mobile
            placeholder="Describe what happened...",
            help="Include what, where, when, who, and consequences"
        )
        
        # Stack columns vertically on mobile
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
            
            location = st.text_input("Location:", placeholder="e.g., Production Floor")
        
        with col2:
            date = st.date_input("Date:", datetime.now())
            time = st.time_input("Time:", datetime.now().time())
        
        # Additional fields below
        reported_by = st.text_input("Reported By:", placeholder="Optional")
        witnesses = st.text_input("Witnesses:", placeholder="Optional")
        
        st.markdown("---")
        
        # Full width buttons on mobile
        col1, col2 = st.columns(2)
        
        with col1:
            submit = st.form_submit_button("🚀 Generate Analysis", type="primary", use_container_width=True)
        
        with col2:
            preview = st.form_submit_button("👁️ Preview Sample", use_container_width=True)
        
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
        
        organization = st.text_input(
            "Organization Name:",
            placeholder="e.g., Acme Manufacturing Inc."
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
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
                default=["ISO 45001:2018 (OH&S)"]
            )
        
        with col2:
            scope = st.selectbox(
                "Audit Scope:",
                [
                    "Full System Audit",
                    "Surveillance Audit",
                    "Re-certification Audit",
                    "Specific Process Audit",
                    "Supplier Audit"
                ]
            )
        
        areas = st.text_area(
            "Areas Reviewed:",
            height=80,  # Reduced for mobile
            placeholder="e.g., Production, Maintenance, Quality Control..."
        )
        
        findings = st.text_area(
            "Key Findings/Observations:",
            height=80,  # Reduced for mobile
            placeholder="Describe main audit findings..."
        )
        
        st.markdown("---")
        
        # Full width buttons on mobile
        col1, col2 = st.columns(2)
        
        with col1:
            submit = st.form_submit_button("🚀 Generate Report", type="primary", use_container_width=True)
        
        with col2:
            preview = st.form_submit_button("👁️ Preview Sample", use_container_width=True)
        
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
        
        policy_name = st.text_input(
            "Policy Name:",
            placeholder="e.g., Workplace Safety Policy"
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
                ]
            )
        
        with col2:
            industry = st.text_input(
                "Industry:",
                placeholder="e.g., Manufacturing"
            )
        
        jurisdiction = st.text_input(
            "Jurisdiction:",
            placeholder="e.g., United States, California"
        )
        
        col3, col4 = st.columns(2)
        
        with col3:
            version = st.text_input(
                "Current Version:",
                placeholder="e.g., 2.1"
            )
        
        with col4:
            last_updated = st.date_input(
                "Last Updated:",
                datetime.now() - timedelta(days=365)
            )
        
        content = st.text_area(
            "Policy Content/Summary:",
            height=150,  # Reduced for mobile
            placeholder="Paste policy content or provide summary of key provisions..."
        )
        
        st.markdown("---")
        
        # Full width buttons on mobile
        col1, col2 = st.columns(2)
        
        with col1:
            submit = st.form_submit_button("🚀 Generate Review", type="primary", use_container_width=True)
        
        with col2:
            preview = st.form_submit_button("👁️ Preview Sample", use_container_width=True)
        
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
        
        organization = st.text_input(
            "Organization Name:",
            placeholder="e.g., Acme Industries"
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
                ]
            )
        
        with col2:
            period = st.text_input(
                "Reporting Period:",
                placeholder="e.g., FY 2024"
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
            default=["GRI Standards"]
        )
        
        st.markdown("### Performance Data")
        
        # Stack ESG data vertically on mobile
        environmental = st.text_area(
            "**Environmental Data:**",
            height=80,  # Reduced for mobile
            placeholder="GHG emissions, energy use, water consumption, waste generation..."
        )
        
        social = st.text_area(
            "**Social Data:**",
            height=80,  # Reduced for mobile
            placeholder="Safety stats, diversity metrics, employee satisfaction..."
        )
        
        governance = st.text_area(
            "**Governance Data:**",
            height=80,  # Reduced for mobile
            placeholder="Board composition, ethics program, risk management..."
        )
        
        st.markdown("---")
        
        # Full width buttons on mobile
        col1, col2 = st.columns(2)
        
        with col1:
            submit = st.form_submit_button("🚀 Generate Assessment", type="primary", use_container_width=True)
        
        with col2:
            preview = st.form_submit_button("👁️ Preview Sample", use_container_width=True)
        
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
    
    # Success message - stack metrics on mobile
    st.success("✅ Analysis Complete!")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Tokens", f"{result.get('tokens_used', 0):,}")
    with col2:
        st.metric("Cost", f"${result.get('cost', 0):.4f}")
    with col3:
        st.metric("Model", result.get('model', 'N/A'))
    
    # Tabs
    tab1, tab2, tab3 = st.tabs(["📄 Report", "📊 Analytics", "💾 Export"])
    
    with tab1:
        st.markdown("### Analysis Report")
        # Use container for better mobile scrolling
        report_container = st.container()
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
    
    # Summary metrics - stack on mobile
    metrics_col1, metrics_col2 = st.columns(2)
    
    with metrics_col1:
        st.metric("Total Reports", len(df))
        if len(df) > 0:
            st.metric("Avg Cost", f"${df['cost'].mean():.4f}")
    
    with metrics_col2:
        st.metric("Total Cost", f"${df['cost'].sum():.2f}")
        st.metric("Total Tokens", f"{df['tokens'].sum():,}")
    
    st.markdown("---")
    
    # Charts - full width on mobile
    st.markdown("#### Reports by Type")
    type_counts = df['type'].value_counts()
    fig1 = px.pie(values=type_counts.values, names=type_counts.index, title='Analysis Type Distribution')
    fig1.update_layout(height=300)  # Fixed height for mobile
    st.plotly_chart(fig1, use_container_width=True)
    
    st.markdown("#### Cost by Type")
    cost_by_type = df.groupby('type')['cost'].sum()
    fig2 = px.bar(x=cost_by_type.index, y=cost_by_type.values, title='Total Cost by Type')
    fig2.update_layout(height=300)  # Fixed height for mobile
    st.plotly_chart(fig2, use_container_width=True)
    
    # History table
    st.markdown("---")
    st.markdown("#### Recent Reports")
    
    display_df = df.copy()
    display_df['timestamp'] = pd.to_datetime(display_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
    display_df['cost'] = display_df['cost'].apply(lambda x: f"${x:.4f}")
    
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
    col1, col2 = st.columns(2)
    
    with col1:
        st.download_button(
            label="📥 Download TXT",
            data=export_text,
            file_name=f"{input_data.get('type', 'report')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col2:
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
            label="📥 Download JSON",
            data=json.dumps(json_data, indent=2),
            file_name=f"{input_data.get('type', 'report')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    
    # Preview
    st.markdown("---")
    with st.expander("👁️ Preview Export"):
        st.code(export_text[:1000] + "..." if len(export_text) > 1000 else export_text)

# =============================================================================
# MAIN APPLICATION - Minimal changes
# =============================================================================

def main():
    """Main application"""
    
    # Initialize
    init_session_state()
    
    # Header
    render_header()
    
    # Sidebar
    analysis_type = render_sidebar()
    
    # Main content - route to appropriate form
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
                st.markdown(result.get('analysis', '')[:3000] + "\n\n*[Truncated for preview]*")
        
        else:
            with st.spinner(f"🔍 Generating {analysis_type}..."):
                api_key = st.session_state.api_key if not st.session_state.demo_mode else "demo"
                client = DeepSeekClient(api_key)
                
                result = client.analyze(prompt_type, form_data)
                
                render_analysis_result(result, form_data)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 1rem; color: #666;'>
        <p><strong>Compliance Sentinel</strong> | Professional HSE & Compliance Analysis</p>
        <p style='font-size: 0.9rem;'>Powered by DeepSeek AI | v2.0 | Mobile Optimized</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
