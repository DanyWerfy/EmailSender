from msgraph import GraphServiceClient
import os
import configparser
from msg_parser import MsOxMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.message import EmailMessage
import glob
from email.parser import BytesParser
from email import policy
import base64
import asyncio
from azure.identity import InteractiveBrowserCredential
from msgraph_core import BaseGraphRequestAdapter
from msgraph_core.authentication import AzureIdentityAuthenticationProvider
from msgraph import GraphServiceClient
from azure.identity import InteractiveBrowserCredential
from kiota_http.httpx_request_adapter import HttpxRequestAdapter
from msgraph import GraphServiceClient
from azure.identity import ClientSecretCredential
import csv
import requests

def main():
    emailTemplate = convertMsgToMime()
    with open("Montreal Market Data 2025(Sheet1).csv", "r", newline='', encoding='utf-8') as data:
        csv_reader = csv.DictReader(data)
        for row in csv_reader:
            recipientName = row["Name of recipient"]
            companyName = row["Company name"]
            recipientEmail = row["Email"]
            body,subject = replaceVariablesInEmail(emailTemplate, recipientName, companyName)
            newMsg = createNewEmail(body,subject,recipientEmail)
            attachement = find_matching_attachment(company_name=companyName)
            defaultAttachement = "./inputs/Hotelrez_Marketing flyer.pdf"
            if attachement:
                attach_file_to_email(newMsg, attachement)
            if os.path.exists(defaultAttachement):
                attach_file_to_email(newMsg, defaultAttachement)
            output_path = os.path.join("./emails", f"{subject}.eml")
            with open(output_path, "wb") as f:
                f.write(newMsg.as_bytes())
            accessToken = connectToAPI()
            asyncio.run(sendEmail(accessToken,newMsg,recipientEmail))

def convertMsgToMime():
    msg = MsOxMessage("./template/emailTemplate.msg")
    output_path = "./WERFY Luxury Apart-Hotel - [Company name] - Corporate Proposal for Accommodations .eml"
    msg.save_email_file("./")
    return output_path

def replaceVariablesInEmail(emailToEdit, recipientName, companyName):
    with open(emailToEdit, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    subject = msg["subject"]
    subject = subject.replace("[Company name]", companyName)
    body = None
    html_body = None
    plain_body = None
    
    for part in msg.walk():
        content_type = part.get_content_type()
        
        if content_type == "text/html":
            charset = part.get_content_charset() or "utf-8"
            html_body = part.get_payload(decode=True).decode(charset)
        elif content_type == "text/plain":
            charset = part.get_content_charset() or "utf-8"
            plain_body = part.get_payload(decode=True).decode(charset)
        elif content_type.startswith("image/"):
            # Images are typically embedded or attachments - keep them as they are
            # They don't need text replacement
            continue
        elif content_type == "application/octet-stream":
            # Generic binary data - likely an attachment, skip for body text
            continue
        else:
            # Other content types (application/pdf, etc.) - skip for body text
            continue
    
    # Prefer HTML over plain text
    if html_body:
        body = html_body
    elif plain_body:
        body = plain_body
    else:
        print("Warning: No text body found in email template")
        body = ""
    
    # Check if body is None and handle it
    if body is None:
        print("Warning: No text body found in email template")
        body = ""  # Set to empty string or provide a default body
    
    body = body.replace("[Company name]", companyName)
    body = body.replace("[Name of recipient]", recipientName)
    return body, subject

def createNewEmail(body,subject,recipientEmail):
    new_msg = MIMEMultipart()
    new_msg["Subject"] = subject
    new_msg["From"] = "WERFY EMAIL HERE"
    new_msg["To"] = recipientEmail
    new_msg.attach(MIMEText(body, _subtype='html', _charset='utf-8'))
    return new_msg

def find_matching_attachment(company_name, search_dir="./attachements"):
    normalized_name = company_name.lower().replace(" ", "").replace("-", "").replace("_", "")
    pdf_files = glob.glob(os.path.join(search_dir, "*.pdf"))
    for pdf in pdf_files:
        filename = os.path.basename(pdf).lower().replace(" ", "").replace("-", "").replace("_", "")
        if normalized_name in filename:
            return pdf
    return None

def attach_file_to_email(msg, file_path):
    with open(file_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
        msg.attach(part)

def extract_html_body(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            charset = part.get_content_charset() or "utf-8"
            html = part.get_payload(decode=True).decode(charset)
            if "<html" not in html.lower():
                html = f"<html><body>{html}</body></html>"
            return html
    return None

async def sendEmail(accessToken, msg, recipientEmail):
    subject = msg["Subject"]
    body = extract_html_body(msg)
    print("HTML Preview:\n", body)
    if body is None:
        return
    attachments = []
    for part in msg.walk():
        if part.get_content_disposition() == "attachment":
            filename = part.get_filename()
            content_type = part.get_content_type()
            content_bytes = part.get_payload(decode=True)
            base64_content = base64.b64encode(content_bytes).decode("utf-8")
            attachments.append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": filename,
                "contentType": content_type,
                "contentBytes": base64_content
            })
    message_payload = {
        "subject": subject,
        "body": {
            "contentType": "HTML",
            "content": body
        },
        "toRecipients": [
            {
                "emailAddress": {
                    "address": recipientEmail
                }
            }
        ],
        "attachments": attachments
    }
    headers = {
        "Authorization": f"Bearer {accessToken}",
        "Content-Type": "application/json"
    }
    response = requests.post(
        "https://graph.microsoft.com/v1.0/me/messages",
        headers=headers,
        json=message_payload
    )
    print(response.status_code)

def connectToAPI():
    config = configparser.ConfigParser()
    config.read('config.cfg')
    tenantId = config["azure"]["TenantId"]
    clientId = config["azure"]["ClientId"]
    clientSecret = config["azure"]["ClientSecret"]
    credential = InteractiveBrowserCredential(client_id=clientId)
    token = credential.get_token("Mail.ReadWrite")
    access_token = token.token
    return access_token
    return client

if __name__ == "__main__":
    main()
