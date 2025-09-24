import configparser
from azure.identity import InteractiveBrowserCredential

def connect_to_api(config_file_path: str):
    config = configparser.ConfigParser()
    config.read(config_file_path) 
    client_id = config["azure"]["ClientId"]
    credential = InteractiveBrowserCredential(client_id=client_id)
    token = credential.get_token("Mail.ReadWrite")
    return token.token
