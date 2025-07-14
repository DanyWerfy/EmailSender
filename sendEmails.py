from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody
from msgraph.generated.models.message import Message
from msgraph.generated.models.recipient import Recipient
from msgraph.generated.models.email_address import EmailAddress
from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.item_body import ItemBody
import os
import configparser
import csv
import fitz
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import re


config = configparser.ConfigParser()
config.read('config.cfg')

tenantId = config["azure"]["TenantId"]
clientId = config["azure"]["ClientId"]
clientSecret = config["azure"]["ClientSecret"]

credential = ClientSecretCredential(client_id=clientId,tenant_id=tenantId,client_secret=clientSecret)
client = GraphServiceClient(credential)

with open("Montreal Market Data 2025(Sheet1).csv", "r") as data:
    csv_reader = csv.DictReader(data)
    for row in csv_reader:
        variables = {}
        # extract data from csv
        recipientName = row["Name of recipient"]
        companyName = row["Company name"]
        email = row["Email"]
        variables["[name of recipient]"] = recipientName
        variables["[company name]"] = companyName
        variables["[email]"] = email

        # open the pdf for editing using fitz
        pdfToEdit = fitz.open('./attachements/EN_WERFY_Corporate Proposal_[Company name].pdf')
        # load the first page
        page = pdfToEdit.load_page(0)
        text = page.get_text().lower()
        changeInstances = re.findall(r'\[.*\]', text)
        for var in changeInstances:
            if var in variables:
                pageInstances = page.search_for(f'{var}')
                for instance in pageInstances:
                    page.add_redact_annot(instance, fill=(1, 1, 1))
                    page.apply_redactions()
                    adjusted_point = fitz.Point((instance.tl + instance.bl) / 2)
                    adjusted_point.y -= 2
                    page.insert_text(adjusted_point, variables[var], color=(0, 0, 0), fontname= "helv", fontsize = 9)
                    page.apply_redactions()
        pdfToEdit.save(f'./output/EN_WERFY_Corporate Proposal_{companyName}.pdf')
        pdfToEdit.close()