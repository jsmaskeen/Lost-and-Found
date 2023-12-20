db_uri = "mongodb+srv://blahblahblah.mongodb.net/?retryWrites=true&w=majority" 
domain = "http://localhost:5100"
import json
client_secret = json.loads(open("client_secret.json").read())["web"]["client_secret"]

ibb_api_key = 'hehe'
client_id = json.loads(open("client_secret.json").read())["web"]["client_id"]

allow_all_emails = True

sacreds_file = 'sa_creds.json'
brevo_api = ''
