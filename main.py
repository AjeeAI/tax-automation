from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel, EmailStr
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import gspread
from google.oauth2.service_account import Credentials
import logging
from datetime import datetime

# Configure a standard logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Automated Tax Workflow Engine")

# Define the scopes required by Google's API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# 1. Data Model: Validates the incoming webhook payload from your form
class FormEntry(BaseModel):
    name: str
    email: EmailStr
    salary: float

# 2. Logic Node (The Expressions/Switch Node)
def evaluate_tax_status(salary: float) -> str:
    """
    Evaluates the input and returns a routing classification.
    """
    if salary <= 300000:
        return "EXEMPT"
    elif salary <= 3000000:
        return "TIER_1"
    else:
        return "TIER_2"

# 3. Action Node: Google Sheets
def append_to_sheets(data: FormEntry):
    """
    Authenticates with Google Workspace and appends a new row to the target sheet.
    """
    try:
        creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
        client = gspread.authorize(creds)
        
        # FIXED: Just the ID string, no "https://..." or "/edit"
        SPREADSHEET_ID = "1GFwkuKwNL_n2v5tG4oTwsUirYG3K73RGZI2tom0bZdM"
        
        worksheet = client.open_by_key(SPREADSHEET_ID).sheet1  # Targets the first tab
        
        # Serialize the data into a flat list (representing a row)
        timestamp = datetime.now().isoformat()
        row_data = [timestamp, data.name, data.email, data.salary]
        
        # Append the data
        worksheet.append_row(row_data)
        logger.info(f"[Sheets Node] Successfully saved {data.name}'s data.")
        
    except Exception as e:
        logger.error(f"[Sheets Node] Failed to save data for {data.name}. Error: {str(e)}")
        
# 4. Action Node: Email Dispatch
def dispatch_email(data: FormEntry, tax_status: str):
    """
    Constructs a personalized email based on the calculated tax tier and 
    dispatches it via Gmail's SMTP server.
    """
    SENDER_EMAIL = "ajeeaidev@gmail.com" 
    SENDER_PASSWORD = "afrx pwcn izjd afup" # Put your newly generated app password here!

    # Dictionary acting as our "Switch Node" for personalized templates
    templates = {
        "EXEMPT": f"Hello {data.name},\n\nGood news! Based on your declared salary of ₦{data.salary:,.2f}, you are exempt from filing this period.\n\nBest,\nTax Automation Bot",
        "TIER_1": f"Hello {data.name},\n\nBased on your declared salary of ₦{data.salary:,.2f}, the standard tax tier applies. Please proceed to the portal to file your returns.\n\nBest,\nTax Automation Bot",
        "TIER_2": f"Hello {data.name},\n\nBased on your declared salary of ₦{data.salary:,.2f}, the upper tax tier applies. Please consult your financial advisor and proceed to the portal to file.\n\nBest,\nTax Automation Bot"
    }
    
    email_body = templates.get(tax_status, f"Hello {data.name}, your tax status is {tax_status}.")
    
    # Construct the email payload
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = data.email
    msg['Subject'] = f"Your Automated Tax Assessment: {tax_status}"
    msg.attach(MIMEText(email_body, 'plain'))
    
    try:
        # Connect to Gmail's SMTP server, encrypt the connection, and send
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"[Email Node] Successfully dispatched '{tax_status}' email to {data.email}.")
        
    except Exception as e:
        logger.error(f"[Email Node] Failed to send email to {data.email}. Error: {str(e)}")

# 5. The Orchestrator
def execute_pipeline(data: FormEntry):
    """Runs the workflow sequence outside the main request thread."""
    append_to_sheets(data)
    tax_status = evaluate_tax_status(data.salary)
    dispatch_email(data, tax_status)

# 6. Webhook Trigger
@app.post("/webhook/tax-assessment")
async def trigger_workflow(entry: FormEntry, background_tasks: BackgroundTasks):
    """
    Receives the form payload and instantly hands it off to the background engine.
    """
    background_tasks.add_task(execute_pipeline, entry)
    return {"status": "success", "message": "Workflow triggered successfully."}