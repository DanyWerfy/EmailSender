import os
import csv
import asyncio

from modules.auth import connect_to_api
from modules.send import send_email
from modules.template import replace_variables_in_email, create_new_email
from modules.attachments import find_matching_attachment, attach_file_to_email

CONFIG_FILE_PATH = "data/config.cfg"
CSV_FILE_PATH = "data/recipients.csv"
EMAIL_TEMPLATE_PATH = "data/template/emailTemplate.eml"
ATTACHMENTS_INPUT_DIR = "data/attachments"
GLOBAL_FLYER_PATH = "data/inputs/Marketing_Flyer.pdf"
SENDER_EMAIL = "YOUR_EMAIL@domain.com"

def main():
    # 1. Authenticate
    print("Connecting to Microsoft Graph...")
    token = connect_to_api(CONFIG_FILE_PATH)

    # 2. Read recipients from CSV
    with open(CSV_FILE_PATH, newline='', encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} recipients in {CSV_FILE_PATH}.")

    # 3. Loop over recipients
    for i, row in enumerate(rows, start=1):
        recipient_name = row["Name"]
        company_name = row["Company"]
        recipient_email = row["Email"]

        print(f"\n[{i}/{len(rows)}] Preparing email for {recipient_name} ({recipient_email})...")

        # 3a. Generate email body + subject from template
        body, subject = replace_variables_in_email(
            EMAIL_TEMPLATE_PATH,
            recipient_name,
            company_name
        )

        msg = create_new_email(body, subject, recipient_email, SENDER_EMAIL)

        company_pdf = find_matching_attachment(company_name, ATTACHMENTS_INPUT_DIR)
        if company_pdf:
            attach_file_to_email(msg, company_pdf)
            print(f"Attached company PDF: {os.path.basename(company_pdf)}")
        else:
            print(f"No specific PDF found for {company_name}")

        if os.path.exists(GLOBAL_FLYER_PATH):
            attach_file_to_email(msg, GLOBAL_FLYER_PATH)
            print(f"Attached global flyer: {os.path.basename(GLOBAL_FLYER_PATH)}")

        asyncio.run(send_email(token, msg, recipient_email))

if __name__ == "__main__":
    main()
