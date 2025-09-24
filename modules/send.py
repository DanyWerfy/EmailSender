import base64
import requests
import asyncio
from email.message import Message

def extract_html_body(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            charset = part.get_content_charset() or "utf-8"
            return part.get_payload(decode=True).decode(charset)
    return None

async def send_email(access_token: str, content, recipient_email: str, subject: str):
    body = ""
    attachments = []

    # Check if the content is a MIME object or raw HTML
    if isinstance(content, Message):
        subject = content.get("Subject", "")
        body = extract_html_body(content)

        # Collect attachments from the MIME object
        for part in content.walk():
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

    elif isinstance(content, str):
        # Handle raw HTML string
        body = content
            
    else:
        print("Error: Invalid content type. Must be a MIME object or an HTML string.")
        return

    if not body:
        print("Warning: No HTML body found, email not sent")
        return

    # Build payload
    print(subject)
    message_payload = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": body},
        "toRecipients": [{"emailAddress": {"address": recipient_email}}],
        "attachments": attachments
    }

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    response = requests.post("https://graph.microsoft.com/v1.0/me/messages",
                             headers=headers, json=message_payload)

    if response.status_code == 201:
        print(f"Email created successfully for {recipient_email}")
    elif response.status_code == 429:
        wait_time = int(response.headers.get("Retry-After", 5))
        print(f"Throttled, waiting {wait_time} seconds...")
        await asyncio.sleep(wait_time)
        return await send_email(access_token, content, recipient_email)
    else:
        print(f"Error: {response.status_code} - {response.text}")
