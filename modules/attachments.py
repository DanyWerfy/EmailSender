import os
import glob
import base64
from email.mime.application import MIMEApplication

def find_matching_attachment(company_name: str, search_dir: str) -> str | None:
    normalized_name = company_name.lower().replace(" ", "").replace("-", "").replace("_", "")
    pdf_files = glob.glob(os.path.join(search_dir, "*.pdf"))

    for pdf in pdf_files:
        filename = os.path.basename(pdf).lower().replace(" ", "").replace("-", "").replace("_", "")
        if normalized_name in filename:
            return pdf
    return None

def attach_file_to_email(msg, file_path: str):
    with open(file_path, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(file_path))
        part["Content-Disposition"] = f'attachment; filename="{os.path.basename(file_path)}"'
        msg.attach(part)

def get_image_base64(image_path: str) -> str:
    try:
        with open(image_path, "rb") as img:
            encoded = base64.b64encode(img.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"
    except FileNotFoundError:
        print(f"Image not found: {image_path}")
        return ""

