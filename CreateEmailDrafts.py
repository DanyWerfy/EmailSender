import os
import sys
import base64
import asyncio
import glob
import csv
import requests
import re
import time

import configparser
from msg_parser import MsOxMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.parser import BytesParser
from email import policy
from azure.identity import InteractiveBrowserCredential

# input paths
CSV_FILE_PATH = os.path.join("data", "Montreal Market Data 2025(Sheet1).csv")
CONFIG_FILE_PATH = os.path.join("data", "config.cfg")
EMAIL_TEMPLATE_PATH = os.path.join("data", "template", "emailTemplate.msg")
MARKETING_FLYER_PATH = os.path.join("data", "inputs", "Hotelrez_Marketing flyer.pdf")
LOGO_PATH = os.path.join("data", "inputs", "Logo.png")
ATTACHMENTS_INPUT_DIR = os.path.join("data", "attachements")
output_emails_dir = "./data/emails/" 

# app entry point
def main():
    greetUser()
    accessToken = connectToAPI()
    print("Starting to create email drafts!")
    emailTemplate = convertMsgToMime() 
    
    with open(CSV_FILE_PATH, "r", newline='', encoding='utf-8') as data:
        csv_reader = csv.DictReader(data)
        all_rows = list(csv_reader) 
        max_rows = len(all_rows)
        i = 0
        for row in enumerate(all_rows):
            # grab info
            recipientName = row["Name of recipient"]
            companyName = row["Company name"]
            recipientEmail = row["Email"]
            # create the bytes for the email
            newMsg = createEmailBytes(emailTemplate,recipientName,recipientEmail, companyName)
            # send the email bytes
            asyncio.run(sendEmail(accessToken, newMsg, recipientEmail))
            i += 1
            print(f"completed {i}/{max_rows} drafts!")
        print("\nAll emails processed.")

def greetUser():
        try:
            username = os.getlogin()
            print(f"Hello, {username}!")
        except OSError:
            print("Hello there! - I couldn't find your name :(")
        print("Welcome to this mass email drafting tool, please let Dany know if you run into any issues!")
def createEmailBytes(emailTemplate: str, recipientName: str, recipientEmail: str, companyName: str):
    # replace vars in the email
    body, subject = replaceVariablesInEmail(emailTemplate, recipientName, companyName)
    # create the email
    newMsg = createNewEmail(body, subject, recipientEmail)
    # add an attachment
    attachement_path = find_matching_attachment(company_name=companyName, search_dir=ATTACHMENTS_INPUT_DIR)
    if attachement_path:
        attach_file_to_email(newMsg, attachement_path)
    else:
        print(f"\nWarning: No company-specific PDF found for {companyName} in {ATTACHMENTS_INPUT_DIR}.")
    
    if os.path.exists(MARKETING_FLYER_PATH):
        attach_file_to_email(newMsg, MARKETING_FLYER_PATH)
    
    os.makedirs(output_emails_dir, exist_ok=True) 
    output_path = os.path.join(output_emails_dir, f"{subject}.eml")
    # write the byte steam
    with open(output_path, "wb") as f:
        f.write(newMsg.as_bytes())
    return newMsg
def convertMsgToMime():
    final_eml_template_name = "WERFY_Email_Template.eml"
    msg = MsOxMessage(EMAIL_TEMPLATE_PATH)
    
    os.makedirs(output_emails_dir, exist_ok=True) 
    
    msg.save_email_file(output_emails_dir) 
    
    saved_files = glob.glob(os.path.join(output_emails_dir, "*.eml"))
    saved_files.sort(key=os.path.getmtime, reverse=True) 
    
    original_saved_path = None
    if saved_files:
        original_saved_path = saved_files[0]
    else:
        print("Warning: No .eml file found after saving MSG template. Assuming 'message.eml'.")
        original_saved_path = os.path.join(output_emails_dir, "message.eml")

    final_eml_template_path = os.path.join(output_emails_dir, final_eml_template_name)

    if os.path.exists(original_saved_path) and original_saved_path != final_eml_template_path:
        try:
            os.rename(original_saved_path, final_eml_template_path)
            print(f"Renamed email template from {os.path.basename(original_saved_path)} to {os.path.basename(final_eml_template_path)}")
        except OSError as e:
            print(f"Error renaming email template file from {original_saved_path} to {final_eml_template_path}: {e}")
            return original_saved_path
    elif not os.path.exists(original_saved_path):
        print(f"Error: Original saved EML template not found at {original_saved_path}.")
        return None

    return final_eml_template_path

def replaceVariablesInEmail(emailToEdit, recipientName, companyName):
    with open(emailToEdit, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)
    # find subject and replace variable
    subject = msg["subject"]
    subject = subject.replace("[Company name]", companyName)
    
    body = None
    # walk through the message parts
    for part in msg.walk():
        content_type = part.get_content_type()
        # if the content is not html or plain text, retrn None
        if not(content_type == "text/html" or content_type == "text/plain"):
            print("Warning: No text body found in email template")
            return None
        # get char set
        charset = part.get_content_charset() or "utf-8"
        # decode
        body = part.get_payload(decode=True).decode(charset)
        if content_type == "text/plain":
            # convert plain text into html to be eaier to work with
            body = convert_plain_to_html(body)

    # replace variables
    body = body.replace("[Company name]", companyName)
    body = body.replace("[Name of recipient]", recipientName)
    body = fix_html_formatting(body)
    return body, subject

# helper function to convert plain text into html
def convert_plain_to_html(plain_text):
    if not plain_text:
        return ""
    
    html = plain_text.replace('\r\n', '\n').replace('\r', '\n')
    
    paragraphs = html.split('\n\n')
    
    html_paragraphs = []
    for para in paragraphs:
        if para.strip():
            para = para.replace('\n', '<br>\n')
            html_paragraphs.append(f'<p>{para}</p>')
    
    return '\n'.join(html_paragraphs)

# helper function to fix the html formatting
def fix_html_formatting(html_body):
    if not html_body:
        return html_body
    
    html_body = re.sub(r'<p>', '<p style="margin: 0 0 12pt 0;">', html_body)
    
    gds_section = create_gds_table()
    gds_pattern = r'GDS Codes HTO28824\s*(.*?)(?=Best regards|$)'
    html_body = re.sub(gds_pattern, gds_section, html_body, flags=re.DOTALL | re.IGNORECASE)
    
    signature_section = create_signature_section()
    signature_pattern = r'Best regards,?\s*(.*?)'
    html_body = re.sub(signature_pattern, signature_section, html_body, flags=re.DOTALL | re.IGNORECASE)
    return html_body

def createNewEmail(body, subject, recipientEmail):
    new_msg = MIMEMultipart()
    new_msg["Subject"] = subject
    new_msg["From"] = "WERFY EMAIL HERE"
    new_msg["To"] = recipientEmail
    
    full_html = f'''
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                font-size: 11pt;
                line-height: 1.4;
                color: #000000;
                margin: 0;
                padding: 20pt;
            }}
            p {{
                margin: 0 0 12pt 0;
            }}
            table {{
                border-collapse: collapse;
            }}
            strong {{
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        {body}
    </body>
    </html>
    '''
    
    new_msg.attach(MIMEText(full_html, _subtype='html', _charset='utf-8'))
    return new_msg


# helper function to finds an attachment using the company name
def find_matching_attachment(company_name, search_dir):
    normalized_name = company_name.lower().replace(" ", "").replace("-", "").replace("_", "")
    pdf_files = glob.glob(os.path.join(search_dir, "*.pdf"))
    for pdf in pdf_files:
        filename = os.path.basename(pdf).lower().replace(" ", "").replace("-", "").replace("_", "")
        if normalized_name in filename:
            return pdf
    return None

# hepler function to attach attachment to message
def attach_file_to_email(msg, file_path):
    with open(file_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
        msg.attach(part)

# take in a message and convert it to html
def extract_html_body(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            charset = part.get_content_charset() or "utf-8"
            html = part.get_payload(decode=True).decode(charset)
            
            if "<html" not in html.lower():
                html = f"<html><body>{html}</body></html>"
            
            return html
    return None

# take in a message and send the email (or create draft in this case)
async def sendEmail(accessToken, msg, recipientEmail):
    subject = msg["Subject"]
    body = extract_html_body(msg)
    
    if body is None:
        print("Warning: No HTML body found, email not sent")
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
    
    if response.status_code == 201:
        print(f"Email created successfully for {recipientEmail}")
    # if we got throttled by the API
    elif response.status_code == 429:
        timeToWait = int(response.headers.get("Retry-After"))
        print(f"too many requests have been sent, attemping to await {timeToWait} seconds")
        await asyncio.sleep(timeToWait)
        try: 
            response = requests.post(
                "https://graph.microsoft.com/v1.0/me/messages",
                headers=headers,
                json=message_payload
            )
            print(f"Email created successfully for {recipientEmail}")
        except:
            print(f"\nError creating email : {response.status_code} - {response.text} for {recipientEmail}")
    else:
        print(f"\nError creating email: {response.status_code} - {response.text} for {recipientEmail}")

def connectToAPI():
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE_PATH) 
    clientId = config["azure"]["ClientId"]
    credential = InteractiveBrowserCredential(client_id=clientId)
    token = credential.get_token("Mail.ReadWrite")
    access_token = token.token
    return access_token

# helper function to create the table at the bottom fo the email
def create_gds_table():
    return '''
    <p style="margin: 20pt 0 12pt 0;"><strong>GDS Codes HTO28824</strong></p>
    
    <table style="border-collapse: collapse; margin: 0 0 20pt 0; font-size: 11pt;">
        <tr>
            <td style="padding: 2pt 40pt 2pt 0; vertical-align: top;">Apollo / Galileo Chain: HO</td>
            <td style="padding: 2pt 0; vertical-align: top;">Apollo / Galileo Code: I3317</td>
        </tr>
        <tr>
            <td style="padding: 2pt 40pt 2pt 0; vertical-align: top;">Worldspan Chain: HO</td>
            <td style="padding: 2pt 0; vertical-align: top;">Worldspan Code: YULWL</td>
        </tr>
        <tr>
            <td style="padding: 2pt 40pt 2pt 0; vertical-align: top;">Amadeus Chain: HO</td>
            <td style="padding: 2pt 0; vertical-align: top;">Amadeus Code: YMQWLA</td>
        </tr>
        <tr>
            <td style="padding: 2pt 40pt 2pt 0; vertical-align: top;">Sabre Chain: HO</td>
            <td style="padding: 2pt 0; vertical-align: top;">Sabre Code: 606012</td>
        </tr>
        <tr>
            <td style="padding: 2pt 40pt 2pt 0; vertical-align: top;">ODD Chain: HO</td>
            <td style="padding: 2pt 0; vertical-align: top;">ODD Code: 46333</td>
        </tr>
    </table>
    '''

# helper function to create the signature at the bottom of the email
def create_signature_section():
    logo_base64 = get_image_base64(LOGO_PATH)

    logo_html = f'<img src="{logo_base64}" alt="WERFY Logo" style="width:120px; height:auto; display:block;">' if logo_base64 else ''

    return f'''
    <p style="margin: 20pt 0 12pt 0;">Best regards,</p>
    
    <table style="border-collapse: collapse; font-size: 11pt; margin: 12pt 0 0 0;">
        <tr>
            <td style="vertical-align: top; padding-right: 30pt;">
                <strong>HANI BEITINJANEH, MBA</strong><br>
                <span style="color: #666666;">PRÉSIDENT - FONDATEUR</span><br>
                <span style="color: #666666;">PRESIDENT - FOUNDER</span><br>
                <br>
                (514)309-3739 #106 | WERFY.COM<br>
                202-60 RUE SAINT-JACQUES, MONTRÉAL
            </td>
            <td style="vertical-align: top;">
                <div style="width: 120px; height: 60px; text-align: center; line-height: 60px; font-size: 10pt; color: #666;">
                    {logo_html}
                </div>
            </td>
        </tr>
    </table>
    '''

# take an image and convert to base64 encoding
def get_image_base64(image_path):
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return f"data:image/png;base64,{encoded_string}" 
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return ""

if __name__ == "__main__":
    main()