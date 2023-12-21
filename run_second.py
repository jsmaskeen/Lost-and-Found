from config import db_uri

import pymongo

from certifi import where

client = pymongo.MongoClient(db_uri, tlsCAFile=where())

my_db = client["iitgn_lafs"]
lost_items_db = my_db["lost_items_db"]
found_items_db = my_db["found_items_db"]
users_db = my_db["users_db"]
category_db = my_db["category_db"]
claims_db = my_db["claims_queue_db"]
admins_db = my_db["admins_db"]

admins_db.delete_one({"_id": "01", "admin": False})

category_db.delete_one({"_id": "02", "name": None})

claims_db.delete_one(
{
            "_id": "03",
            "item_id": "1",
            "claimed_by": "1",
            "proof": "1",
            "stage": "1",
            "name": "1",
            "rollnum": "1",
            "additional_information": "",
            "claimed_at": 1,
            "otp": "1",
        }

)

found_items_db.delete_one(
        {
            "_id": "04",
            "picture": "1",
            "name": "1",
            "description": "1",
            "category": "1",
            "date": "1",
            "time": None,
            "found_by_uid": "1",
            "claimed": False,
            "time_inserted": 1,
            "AB": 1,
            "room_num": 1,
            "location_found": "1",
            "date_as_ts": 1,
        }
)

lost_items_db.delete_one(
        {
            "_id": '05',
            "picture": "1",
            "name": "1",
            "description": "1",
            "category": "1",
            "date": "1",
            "time": None,
            "semantic_time": None,
            "lost_by_uid": "1",
            "found": False,
            "time_inserted": 1,
            "AB": 1,
            "room_num": 1,
            "location_lost": "1",
            "date_as_ts": 1,
        }
)

users_db.delete_one({
  "_id": "1",
  "name": "1",
  "email": "1",
  "picture": "1",
  "lost_items": 1,
  "found_items_of_others": 1,
  "found_lost_items": 1
})

def add_category(cat):
    category_db.insert_one({'name':cat})
    return

add_category('Electronics')
add_category('Money (Cash/Wallet/Card)')
add_category('Other')
add_category('Keys')
add_category('Bag')
add_category('Cycle')
add_category('Clothes')
add_category('Bottle')
add_category('Watch')
add_category('Accessories')
add_category('Umbrella')


from flask import Flask,session,abort,request,redirect
import requests

from config import domain,client_secret,client_id, allow_all_emails
from db import sgetuser,insert_user,add_admin
import os
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
app = Flask(__name__)
app.config["SECRET_KEY"] = client_secret
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

GOOGLE_CLIENT_ID = client_id
client_secrets_file = "client_secret.json"

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    ],
    redirect_uri=f"{domain}/callback",
)

@app.route("/")
async def login():
    auth_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(auth_url)


@app.route("/callback")
async def callback():
    flow.fetch_token(authorization_response=request.url)

    try:
        if not session["state"] == request.args["state"]:
            abort(500)  # State does not match!
    except KeyError:
        return redirect('/')

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID,
        clock_skew_in_seconds=20,
    )
    if not allow_all_emails:
        if not "@iitgn.ac.in" in id_info["email"]:
            print("Only @iitgn.ac.in emails are allowed.")
            return redirect("/")

    session["google_id"] = id_info.get("sub")
    session["name"] = id_info.get("name")
    session["picture"] = id_info.get("picture")
    session["email"] = id_info.get("email")
    session["login_details"] = {
        "google_id": id_info.get("sub"),
        "name": id_info.get("name"),
        "picture": id_info.get("picture"),
        "email": id_info.get("email"),
    }

    user = sgetuser(id_info["sub"])
    if not user:
        user = await insert_user(
            id_info["sub"], id_info["name"], id_info["email"], id_info["picture"]
        )

    await add_admin(id_info['sub'])
    
    return 'All good, you are now an admin. Now you can continue to deploy and add other admins via mail id'


@app.route("/logout")
async def logout():
    session.clear()
    return redirect("/")

app.run(port=5100,debug=True)