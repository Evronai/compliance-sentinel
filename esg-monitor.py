import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

# Core dependencies
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
import aiohttp
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import aiofiles
import hashlib
import re
from dataclasses import dataclass
from decimal import Decimal

# Enhanced logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('compliance_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==================== CONFIGURATION ====================
class AnalysisType(Enum):
    INCIDENT = "incident"
    AUDIT = "audit"
    POLICY = "policy"
    ESG = "esg"
    RISK = "risk"
    COMPLIANCE = "compliance"

class SeverityLevel(Enum):
    CRITICAL = "5 - Critical"
    SEVERE = "4 - Severe"
    SERIOUS = "3 - Serious"
    MODERATE = "2 - Moderate"
    MINOR = "1 - Minor"

class ReportFormat(Enum):
    PDF = "pdf"
    TEXT = "text"
    EXECUTIVE = "executive"
    DETAILED = "detailed"

# ==================== DEEPSEEK API INTEGRATION ====================
class DeepSeekAPIClient:
    """Client for DeepSeek AI API with cost optimization"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = None
        self.model_pricing = {
            "deepseek-chat": {"input": 0.14, "output": 0.28},  # per 1M tokens (example pricing)
            "deepseek-coder": {"input": 0.14, "output": 0.28},
        }
        self.default_model = "deepseek-chat"
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def estimate_cost(self, input_tokens: int, output_tokens: int, model: str = None) -> Decimal:
        """Estimate cost for API call"""
        model = model or self.default_model
        if model not in self.model_pricing:
            model = self.default_model
            
        pricing = self.model_pricing[model]
        cost = (Decimal(input_tokens) / Decimal(1_000_000) * Decimal(pricing["input"]) +
                Decimal(output_tokens) / Decimal(1_000_000) * Decimal(pricing["output"]))
        return cost
    
    async def analyze(self, system_prompt: str, user_prompt: str, 
                      model: str = None, max_tokens: int = 4000,
                      temperature: float = 0.1) -> Dict[str, Any]:
        """Send analysis request to DeepSeek API"""
        
        model = model or self.default_model
        
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
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            ) as response:
                
                if response.status == 200:
                    data = await response.json()
                    
                    # Estimate tokens and cost
                    input_tokens = data.get("usage", {}).get("prompt_tokens", len(system_prompt + user_prompt) // 4)
                    output_tokens = data.get("usage", {}).get("completion_tokens", len(data["choices"][0]["message"]["content"]) // 4)
                    cost = self.estimate_cost(input_tokens, output_tokens, model)
                    
                    return {
                        "analysis": data["choices"][0]["message"]["content"],
                        "tokens_used": input_tokens + output_tokens,
                        "cost": float(cost),
                        "model": model,
                        "success": True
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"DeepSeek API error: {response.status} - {error_text}")
                    return {
                        "analysis": f"API Error: {response.status}. Please check your API key and try again.",
                        "tokens_used": 0,
                        "cost": 0.0,
                        "model": model,
                        "success": False
                    }
                    
        except aiohttp.ClientError as e:
            logger.error(f"DeepSeek connection error: {e}")
            return {
                "analysis": f"Connection error: {str(e)}. Please try again later.",
                "tokens_used": 0,
                "cost": 0.0,
                "model": model,
                "success": False
            }

# ==================== CORE BOT CLASS ====================
class ComplianceSentinelBot:
    """Main bot class with DeepSeek AI integration"""
    
    def __init__(self):
        self.deepseek_client = None
        self.user_api_keys = {}  # Store user API keys temporarily
        self.conversation_cache = {}
        self.report_templates = {}
        self.setup_templates()
        
    def setup_templates(self):
        """Initialize analysis prompt templates"""
        self.report_templates = {
            AnalysisType.INCIDENT: self._create_incident_prompt,
            AnalysisType.AUDIT: self._create_audit_prompt,
            AnalysisType.POLICY: self._create_policy_prompt,
            AnalysisType.ESG: self._create_esg_prompt,
            AnalysisType.RISK: self._create_risk_prompt,
            AnalysisType.COMPLIANCE: self._create_compliance_prompt,
        }
    
    # Prompt template methods
    def _create_incident_prompt(self, data: Dict[str, Any]) -> Tuple[str, str]:
        system_prompt = """You are a senior HSE consultant at a top-tier firm. Analyze incident reports with professional rigor.
        
        CRITICAL INSTRUCTIONS:
        1. Use formal, professional language suitable for corporate reports
        2. Base analysis on actual HSE regulations (OSHA, ISO, NEBOSH)
        3. Never invent or guess regulations - be specific
        4. Structure analysis with clear sections
        5. Provide actionable, prioritized recommendations
        
        RESPONSE FORMAT:
        # EXECUTIVE SUMMARY
        [1 paragraph summary]
        
        # ROOT CAUSE ANALYSIS
        [Use 5 Whys methodology]
        
        # REGULATORY IMPLICATIONS
        [Specific regulations violated with citations]
        
        # RECOMMENDATIONS
        [Numbered, prioritized by impact/cost]
        
        # RISK ASSESSMENT
        [Likelihood, Severity, Overall Risk Rating]
        """
        
        user_prompt = f"""INCIDENT ANALYSIS REQUEST
        Description: {data.get('description', 'N/A')}
        Severity: {data.get('severity', 'N/A')}
        Location: {data.get('location', 'N/A')}
        Date/Time: {data.get('date_time', 'Not specified')}
        
        Please provide comprehensive analysis."""
        
        return system_prompt, user_prompt
    
    def _create_audit_prompt(self, data: Dict[str, Any]) -> Tuple[str, str]:
        system_prompt = """You are an ISO/NEBOSH audit expert. Analyze findings against specified standards."""
        # ... similar structure for other templates
        return system_prompt, ""
    
    # ... other template methods

# ==================== TELEGRAM BOT HANDLERS ====================
class TelegramBotHandlers:
    """Telegram bot conversation handlers"""
    
    def __init__(self, compliance_bot: ComplianceSentinelBot):
        self.bot = compliance_bot
        self.conversation_states = {}
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with API key setup"""
        
        # Check if user has API key configured
        user_id = update.effective_user.id
        
        if user_id not in self.bot.user_api_keys:
            # Show API key setup menu
            keyboard = [
                [InlineKeyboardButton("🔑 Set API Key", callback_data="setup_api_key")],
                [InlineKeyboardButton("ℹ️ How to Get API Key", callback_data="api_help")],
                [InlineKeyboardButton("🚀 Try Demo (Limited)", callback_data="demo_mode")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            welcome_text = """
🤖 *Welcome to Compliance Sentinel*

I'm your institutional-grade HSE, ESG, and compliance analysis assistant powered by DeepSeek AI.

📋 *Before we start, you need to:*
1. Get a DeepSeek API key from [platform.deepseek.com](https://platform.deepseek.com)
2. Set your API key using the button below
3. Start analyzing incidents, audits, and policies

💡 *Free Tier Available:* DeepSeek offers generous free tiers for testing!
            """
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup,
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
        else:
            # User has API key, show main menu
            await self.show_main_menu(update, context)
    
    async def show_main_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show main analysis menu"""
        
        keyboard = [
            [InlineKeyboardButton("🚨 Incident Report", callback_data="analysis_incident")],
            [InlineKeyboardButton("📋 Compliance Audit", callback_data="analysis_audit")],
            [InlineKeyboardButton("📜 Policy Analysis", callback_data="analysis_policy")],
            [InlineKeyboardButton("🌱 ESG Assessment", callback_data="analysis_esg")],
            [InlineKeyboardButton("⚙️ Settings", callback_data="settings")],
            [InlineKeyboardButton("📊 Usage Stats", callback_data="usage_stats")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        menu_text = """
📊 *Compliance Sentinel - Main Menu*

Select an analysis type:

• 🚨 *Incident Report* - Analyze safety incidents
• 📋 *Compliance Audit* - Review against ISO/NEBOSH
• 📜 *Policy Analysis* - Evaluate documents
• 🌱 *ESG Assessment* - Sustainability analysis

⚙️ *Settings* - Manage API key & preferences
        """
        
        if isinstance(update, Update) and update.message:
            await update.message.reply_text(
                menu_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.callback_query.message.reply_text(
                menu_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def setup_api_key(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle API key setup"""
        query = update.callback_query
        await query.answer()
        
        await query.message.reply_text(
            "🔑 *Set Your DeepSeek API Key*\n\n"
            "Please send your API key in the format:\n"
            "`/api_key YOUR_API_KEY_HERE`\n\n"
            "*Example:* `/api_key sk-123456789abcdef`\n\n"
            "⚠️ *Security Note:* Your API key is stored temporarily "
            "and only used for your analyses.",
            parse_mode='Markdown'
        )
    
    async def api_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show API key help"""
        query = update.callback_query
        await query.answer()
        
        help_text = """
📖 *How to Get DeepSeek API Key:*

1. Visit [platform.deepseek.com](https://platform.deepseek.com)
2. Sign up for an account
3. Go to API Keys section
4. Create a new API key
5. Copy the key (starts with `sk-`)

💰 *Pricing:*
• Very cost-effective compared to other AI APIs
• Generous free tier for testing
• Pay-per-use with no monthly commitments

⚡ *Benefits:*
• Fast response times
• Strong reasoning capabilities
• Excellent for compliance analysis

🔒 *Security:* Your API key is only stored in this chat session and is never logged.
        """
        
        await query.message.reply_text(
            help_text,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
    
    async def set_api_key_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /api_key command"""
        user_id = update.effective_user.id
        
        if not context.args:
            await update.message.reply_text(
                "❌ Please provide your API key. Usage: `/api_key YOUR_KEY_HERE`",
                parse_mode='Markdown'
            )
            return
        
        api_key = context.args[0].strip()
        
        # Basic validation
        if not api_key.startswith('sk-'):
            await update.message.reply_text(
                "❌ Invalid API key format. Should start with 'sk-'. "
                "Please check your key and try again."
            )
            return
        
        # Store API key (in production, use secure storage)
        self.bot.user_api_keys[user_id] = api_key
        
        # Test the API key
        await update.message.reply_text("🔍 Testing your API key...")
        
        try:
            async with DeepSeekAPIClient(api_key) as client:
                test_result = await client.analyze(
                    system_prompt="You are a test assistant.",
                    user_prompt="Say 'API test successful' if you can read this.",
                    max_tokens=10
                )
                
                if test_result["success"]:
                    await update.message.reply_text(
                        "✅ *API Key Verified Successfully!*\n\n"
                        "Your DeepSeek API key is now configured and ready to use.\n\n"
                        "💰 *Estimated Cost Per Analysis:* ~$0.01-0.03\n"
                        "⚡ *Response Time:* ~5-15 seconds\n\n"
                        "Use /menu to start analyzing!",
                        parse_mode='Markdown'
                    )
                    
                    # Show main menu
                    await self.show_main_menu(update, context)
                else:
                    await update.message.reply_text(
                        f"❌ API Key Test Failed: {test_result['analysis']}\n"
                        "Please check your key and try again."
                    )
                    del self.bot.user_api_keys[user_id]
                    
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error testing API key: {str(e)}\n"
                "Please try again or check your network connection."
            )
            del self.bot.user_api_keys[user_id]
    
    async def start_incident_report(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start incident report conversation"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        
        # Check if user has API key
        if user_id not in self.bot.user_api_keys:
            await query.message.reply_text(
                "❌ *API Key Required*\n\n"
                "Please set your DeepSeek API key first using /api_key command.\n\n"
                "Get your free key from [platform.deepseek.com](https://platform.deepseek.com)",
                parse_mode='Markdown',
                disable_web_page_preview=True
            )
            return
        
        # Initialize conversation
        self.conversation_states[user_id] = {
            'type': AnalysisType.INCIDENT,
            'step': 'description',
            'data': {}
        }
        
        await query.message.reply_text(
            "🚨 *Incident Report Analysis*\n\n"
            "Let's document and analyze a safety incident.\n\n"
            "*Step 1 of 3:* Please describe what happened in detail:\n"
            "- What was the incident?\n"
            "- Who was involved?\n"
            "- What were the immediate circumstances?\n\n"
            "*Example:* 'A worker slipped on an oil patch near machine #5 while...'",
            parse_mode='Markdown'
        )
    
    async def handle_incident_description(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incident description input"""
        user_id = update.effective_user.id
        
        if user_id not in self.conversation_states:
            return
        
        description = update.message.text
        self.conversation_states[user_id]['data']['description'] = description
        self.conversation_states[user_id]['step'] = 'severity'
        
        # Show severity keyboard
        keyboard = [
            [InlineKeyboardButton(level.value, callback_data=f"severity_{level.name}")]
            for level in SeverityLevel
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "✅ *Description recorded*\n\n"
            "*Step 2 of 3:* Select the incident severity level:\n\n"
            "5️⃣ Critical - Fatality or permanent disability\n"
            "4️⃣ Severe - Major injury, hospitalization\n"
            "3️⃣ Serious - Lost time injury\n"
            "2️⃣ Moderate - Medical treatment needed\n"
            "1️⃣ Minor - First aid only",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def handle_incident_severity(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle severity selection"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        severity = query.data.replace('severity_', '')
        
        try:
            severity_level = SeverityLevel[severity]
            self.conversation_states[user_id]['data']['severity'] = severity_level.value
            self.conversation_states[user_id]['step'] = 'location'
            
            await query.message.reply_text(
                f"✅ Severity set to: *{severity_level.value}*\n\n"
                "*Step 3 of 3:* Please specify the location:\n"
                "- Facility name\n"
                "- Department/area\n"
                "- Specific location if known\n\n"
                "*Example:* 'Manufacturing Plant B, Assembly Line 3, Near Station #5'",
                parse_mode='Markdown'
            )
        except KeyError:
            await query.message.reply_text("Invalid severity selection. Please try again.")
    
    async def handle_incident_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle location input and start analysis"""
        user_id = update.effective_user.id
        
        location = update.message.text
        self.conversation_states[user_id]['data']['location'] = location
        self.conversation_states[user_id]['data']['date_time'] = datetime.now().isoformat()
        
        # Confirm before analysis
        data = self.conversation_states[user_id]['data']
        
        summary = f"""
📋 *Incident Details Summary*

*Description:* {data['description'][:100]}...
*Severity:* {data['severity']}
*Location:* {data['location']}

💰 *Estimated Cost:* ~$0.02
⏱️ *Estimated Time:* 10-20 seconds

Proceed with AI analysis?
        """
        
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Analyze", callback_data="confirm_analysis")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_analysis")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            summary,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def confirm_analysis(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Confirm and start AI analysis"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        conversation = self.conversation_states.get(user_id)
        
        if not conversation:
            await query.message.reply_text("Session expired. Please start again.")
            return
        
        await query.message.reply_text(
            "🧠 *Starting DeepSeek AI Analysis...*\n\n"
            "🤖 Querying AI model...\n"
            "📊 Generating professional report...\n"
            "⏳ This may take 10-20 seconds\n\n"
            "_You'll receive a detailed PDF report when complete._",
            parse_mode='Markdown'
        )
        
        # Get API key
        api_key = self.bot.user_api_keys.get(user_id)
        if not api_key:
            await query.message.reply_text("API key not found. Please set it again.")
            return
        
        # Perform analysis
        try:
            async with DeepSeekAPIClient(api_key) as client:
                analysis_type = conversation['type']
                data = conversation['data']
                
                # Get appropriate prompt
                system_prompt, user_prompt = self.bot.report_templates[analysis_type](data)
                
                # Call DeepSeek API
                result = await client.analyze(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=3000,
                    temperature=0.1
                )
                
                if result["success"]:
                    # Generate PDF report
                    pdf_path = await self.generate_pdf_report(
                        analysis=result["analysis"],
                        title=f"Incident Analysis Report",
                        user_data=data
                    )
                    
                    # Send report with cost info
                    cost_info = (
                        f"💰 *Cost Breakdown:*\n"
                        f"• Tokens Used: {result['tokens_used']:,}\n"
                        f"• Estimated Cost: ${result['cost']:.4f}\n"
                        f"• AI Model: {result['model']}\n\n"
                    )
                    
                    await query.message.reply_text(
                        f"✅ *Analysis Complete!*\n\n{cost_info}"
                        f"📄 *Report Generated Successfully*",
                        parse_mode='Markdown'
                    )
                    
                    # Send PDF
                    with open(pdf_path, 'rb') as pdf_file:
                        await query.message.reply_document(
                            document=pdf_file,
                            caption=f"📊 Incident Analysis Report\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        )
                    
                    # Clean up
                    os.remove(pdf_path)
                    
                else:
                    await query.message.reply_text(
                        f"❌ Analysis failed: {result['analysis']}\n"
                        f"Please check your API key and try again."
                    )
                
                # Clear conversation state
                if user_id in self.conversation_states:
                    del self.conversation_states[user_id]
                    
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            await query.message.reply_text(
                f"❌ Analysis error: {str(e)}\nPlease try again."
            )
    
    async def generate_pdf_report(self, analysis: str, title: str, user_data: Dict[str, Any]) -> str:
        """Generate PDF report from analysis"""
        # Create HTML template
        html_template = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
            <style>
                body {{ font-family: 'Arial', sans-serif; line-height: 1.6; margin: 40px; color: #333; }}
                .header {{ text-align: center; border-bottom: 2px solid #2c3e50; padding-bottom: 20px; margin-bottom: 30px; }}
                .logo {{ font-size: 28px; font-weight: bold; color: #3498db; margin-bottom: 10px; }}
                .subtitle {{ color: #7f8c8d; font-style: italic; }}
                .section {{ margin: 30px 0; }}
                h1 {{ color: #2c3e50; }}
                h2 {{ color: #34495e; border-left: 4px solid #3498db; padding-left: 10px; }}
                h3 {{ color: #7f8c8d; }}
                .info-box {{ background: #f8f9fa; border: 1px solid #e9ecef; padding: 15px; border-radius: 5px; margin: 15px 0; }}
                .footer {{ margin-top: 50px; text-align: center; font-size: 12px; color: #95a5a6; border-top: 1px solid #eee; padding-top: 20px; }}
                .recommendation {{ background: #e8f4fc; border-left: 4px solid #3498db; padding: 10px 15px; margin: 10px 0; }}
                .risk-high {{ color: #e74c3c; font-weight: bold; }}
                .risk-medium {{ color: #f39c12; font-weight: bold; }}
                .risk-low {{ color: #27ae60; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="logo">COMPLIANCE SENTINEL</div>
                <div class="subtitle">Institutional-Grade HSE & ESG Analysis</div>
                <h1>{title}</h1>
                <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="info-box">
                <h3>Incident Details</h3>
                <p><strong>Severity:</strong> {user_data.get('severity', 'N/A')}</p>
                <p><strong>Location:</strong> {user_data.get('location', 'N/A')}</p>
                <p><strong>Date:</strong> {datetime.now().strftime('%Y-%m-%d')}</p>
            </div>
            
            <div class="section">
                {analysis.replace('#', '<h2>').replace('\n#', '</h2>\n<h2>').replace('\n\n', '</p><p>')}
            </div>
            
            <div class="footer">
                <p>This report was generated by Compliance Sentinel AI Analysis Bot using DeepSeek AI.</p>
                <p>Confidential - For internal use only | Not a substitute for professional advice</p>
            </div>
        </body>
        </html>
        """
        
        # Create temp file
        import tempfile
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        temp_path = temp_file.name
        temp_file.close()
        
        # Generate PDF
        HTML(string=html_template).write_pdf(temp_path)
        
        return temp_path

# ==================== MAIN APPLICATION ====================
def main():
    """Main application entry point"""
    
    # Get configuration
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN environment variable not set")
        return
    
    # Initialize bot components
    compliance_bot = ComplianceSentinelBot()
    handlers = TelegramBotHandlers(compliance_bot)
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("menu", handlers.show_main_menu))
    application.add_handler(CommandHandler("api_key", handlers.set_api_key_command))
    
    # Add callback handlers
    application.add_handler(CallbackQueryHandler(handlers.setup_api_key, pattern="^setup_api_key$"))
    application.add_handler(CallbackQueryHandler(handlers.api_help, pattern="^api_help$"))
    application.add_handler(CallbackQueryHandler(handlers.start_incident_report, pattern="^analysis_incident$"))
    application.add_handler(CallbackQueryHandler(handlers.handle_incident_severity, pattern="^severity_"))
    application.add_handler(CallbackQueryHandler(handlers.confirm_analysis, pattern="^confirm_analysis$"))
    
    # Add conversation handler for incident reporting
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handlers.start_incident_report, pattern="^analysis_incident$")],
        states={
            'description': [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_incident_description)],
            'severity': [CallbackQueryHandler(handlers.handle_incident_severity, pattern="^severity_")],
            'location': [MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_incident_location)],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
    )
    
    application.add_handler(conv_handler)
    
    # Start the bot
    logger.info("Starting Compliance Sentinel Bot with DeepSeek AI...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
