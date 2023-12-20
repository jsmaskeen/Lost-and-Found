import aiohttp
from config import ibb_api_key, sacreds_file,brevo_api,domain
import datetime
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

import pytz

tz_IN = pytz.timezone("Asia/Kolkata")


def date_to_timestamp(date):
    date = datetime.datetime.strptime(date, "%d-%m-%Y")
    localized_date = tz_IN.localize(date)

    # Set the time to 0:0:0
    date_with_time_zero = localized_date.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Convert the timezone-aware datetime to a Unix timestamp
    timestamp = int(date_with_time_zero.timestamp())

    return timestamp


def dtnow():
    return datetime.datetime.now(tz_IN).date()


def make_timestamp():
    dtobj = datetime.datetime.now(tz_IN)
    return round(dtobj.timestamp())


def full_time(timestamp):
    dt_object = datetime.datetime.fromtimestamp(timestamp, tz=tz_IN)
    return dt_object.strftime("%H:%M:%S %d-%m-%Y %Z")


async def upload_image(b64=None):
    if not b64:
        return None
    base = "https://api.imgbb.com/1/upload"

    async with aiohttp.ClientSession() as session:
        async with session.post(
            base, params={"key": ibb_api_key}, data={"image": b64}
        ) as r:
            d = await r.json()

    return d["data"]["url"]


async def image_url():
    # async with aiohttp.ClientSession() as sess:
    #     async with sess.get('https://meme-api.com/gimme') as r:
    #         d = await r.json()
    #         return d['url']

    return "https://placehold.jp/150x150.png"


async def cleaner(ls):
    l = []

    for i in ls:
        if i["picture"] == None:
            i["picture"] = await image_url()
        i["_id"] = str(i["_id"])
        i["delta"] = time_difference(make_timestamp(), i["time_inserted"])
        l.append(i)

    return l


def divide_chunks(l, n):
    # looping till length l
    for i in range(0, len(l), n):
        yield l[i : i + n]


def time_difference(current, previous):
    current *= 1000
    previous *= 1000
    ms_per_minute = 60 * 1000
    ms_per_hour = ms_per_minute * 60
    ms_per_day = ms_per_hour * 24
    ms_per_month = ms_per_day * 30
    ms_per_year = ms_per_day * 365

    elapsed = current - previous

    if elapsed < ms_per_minute:
        return str(round(elapsed / 1000)) + " seconds ago"
    elif elapsed < ms_per_hour:
        return str(round(elapsed / ms_per_minute)) + " minutes ago"
    elif elapsed < ms_per_day:
        return str(round(elapsed / ms_per_hour)) + " hours ago"
    elif elapsed < ms_per_month:
        return "approximately " + str(round(elapsed / ms_per_day)) + " days ago"
    elif elapsed < ms_per_year:
        return "approximately " + str(round(elapsed / ms_per_month)) + " months ago"
    else:
        return "approximately " + str(round(elapsed / ms_per_year)) + " years ago"


def login_with_service_account():
    settings = {
        "client_config_backend": "service",
        "service_config": {
            "client_json_file_path": sacreds_file,
        },
    }
    # Create instance of GoogleAuth
    gauth = GoogleAuth(settings=settings)
    # Authenticate
    gauth.ServiceAuth()
    return gauth


gauth = login_with_service_account()

from pydrive2.drive import GoogleDrive


def upload_pdf(path):
    drive = GoogleDrive(gauth)
    f = drive.CreateFile()
    f.SetContentFile(path)
    f.Upload()
    f.InsertPermission({"type": "anyone", "value": "anyone", "role": "reader"})
    return f['alternateLink']

import re

import urllib.parse as urlparse

from urllib.parse import parse_qs

def getIdFromUrl(link: str):
        if "folders" in link or "file" in link:
            regex = r"https://drive\.google\.com/(drive)?/?u?/?\d?/?(mobile)?/?(file)?(folders)?/?d?/([-\w]+)[?+]?/?(w+)?"
            res = re.search(regex, link)
            if res is None:
                raise IndexError("GDrive ID not found.")
            return res.group(5)
        parsed = urlparse.urlparse(link)
        return parse_qs(parsed.query)["id"][0]



import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
configuration = sib_api_v3_sdk.Configuration()
configuration.api_key['api-key'] = brevo_api
api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

def send_email(subject, html, mailid, receiver_username):
    subject = subject
    sender = {"name": "IITGN Lost and Found", "email": "lost.and.found@iitgn.ac.in"}
    html_content = html
    to = [{"email": mailid, "name": receiver_username}]
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(to=to, html_content=html_content, sender=sender, subject=subject)
    api_response = api_instance.send_transac_email(send_smtp_email)
    return

import asyncio
from concurrent.futures import ThreadPoolExecutor

async def send_approve(name,mailid,url,otp):
    subject = 'Claim approved!'
    html = f'Hello {name}<br><br>Your claim request for the <a href = "{domain}{url}">item</a> has been approved.<br><br>Here is the OTP: {otp}.\nYou will need this.<br><br>Regards'
    
    with ThreadPoolExecutor() as pool:
            await asyncio.get_event_loop().run_in_executor(
                pool, send_email,subject,html,mailid,name
            )


async def send_reject(name,mailid,url):
    subject = 'Claim rejected!'
    html = f'Hello {name}<br><br>Your claim request for the <a href = "{domain}{url}">item</a> has been rejected.<br><br>Regards'
    
    with ThreadPoolExecutor() as pool:
            await asyncio.get_event_loop().run_in_executor(
                pool, send_email,subject,html,mailid,name
            )


import math, random
 
# function to generate OTP
def generateOTP() :
 
    # Declare a digits variable  
    # which stores all digits 
    digits = "0123456789"
    OTP = ""
 
   # length of password can be changed
   # by changing value in range
    for i in range(8) :
        OTP += digits[math.floor(random.random() * 10)]
 
    return OTP


# asyncio.run(send_approve('Jaskirat','23110146@iitgn.ac.in','the thing','42523523'))