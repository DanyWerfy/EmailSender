import base64
import requests
import asyncio

def extract_html_body(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            charset = part.get_content_charset() or "utf-8"
            return part.get_payload(decode=True).decode(charset)
    return None

async def send_email(access_token, msg, recipient_email):
    subject = msg["Subject"]
    body = extract_html_body(msg)
    
    if not body:
        print("Warning: No HTML body found, email not sent")
        return

    # Collect attachments
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

    # Build payload
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
        return await send_email(access_token, msg, recipient_email)
    else:
        print(f"Error: {response.status_code} - {response.text}")

