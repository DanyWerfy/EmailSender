import os
import re
import glob
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.parser import BytesParser
from email import policy
from msg_parser import MsOxMessage

# Example: convert .msg -> .eml file path
def convert_msg_to_eml(msg_path: str, output_dir: str) -> str:
    msg = MsOxMessage(msg_path)
    os.makedirs(output_dir, exist_ok=True)
    msg.save_email_file(output_dir)

    saved_files = glob.glob(os.path.join(output_dir, "*.eml"))
    saved_files.sort(key=os.path.getmtime, reverse=True)

    if saved_files:
        return saved_files[0]
    return None

def replace_variables_in_email(eml_path: str, recipient_name: str, company_name: str):
    with open(eml_path, "rb") as f:
        msg = BytesParser(policy=policy.default).parse(f)

    subject = msg["subject"].replace("[Company name]", company_name)

    body = None
    for part in msg.walk():
        if part.get_content_type() in ("text/html", "text/plain"):
            charset = part.get_content_charset() or "utf-8"
            body = part.get_payload(decode=True).decode(charset)
            if part.get_content_type() == "text/plain":
                body = convert_plain_to_html(body)

    body = body.replace("[Company name]", company_name)
    body = body.replace("[Name of recipient]", recipient_name)
    body = fix_html_formatting(body)

    return body, subject

def convert_plain_to_html(text: str) -> str:
    paragraphs = text.split("\n\n")
    return "".join(f"<p>{p.replace('\n', '<br>')}</p>" for p in paragraphs if p.strip())

def fix_html_formatting(html: str) -> str:
    # Example: tweak <p> styling
    html = re.sub(r"<p>", '<p style="margin: 0 0 12pt 0;">', html)
    return html

def create_new_email(body: str, subject: str, recipient_email: str, sender: str) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient_email

    full_html = f"""<html><body>{body}</body></html>"""
    msg.attach(MIMEText(full_html, "html", "utf-8"))
    return msg
