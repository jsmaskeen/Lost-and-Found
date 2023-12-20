import aiohttp
from config import ibb_api_key
import datetime

import pytz

tz_IN = pytz.timezone('Asia/Kolkata')


def date_to_timestamp(date):
    date = datetime.datetime.strptime(date,'%d-%m-%Y')
    localized_date = tz_IN.localize(date)

    # Set the time to 0:0:0
    date_with_time_zero = localized_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert the timezone-aware datetime to a Unix timestamp
    timestamp = int(date_with_time_zero.timestamp())

    return timestamp


def dtnow():
    return datetime.datetime.now(tz_IN).date()

def make_timestamp():
    dtobj = datetime.datetime.now(tz_IN)
    return round(dtobj.timestamp())

def full_time(timestamp):
    dt_object = datetime.datetime.fromtimestamp(timestamp,tz=tz_IN)
    return dt_object.strftime("%H:%M:%S %d-%m-%Y %Z")


async def upload_image(b64=None):
    if not b64:return None
    base = "https://api.imgbb.com/1/upload"

    async with aiohttp.ClientSession() as session:
        async with session.post(base, params={"key": ibb_api_key}, data={"image": b64}) as r:

            d = await r.json()

    return d["data"]["url"]


async def image_url():
    # async with aiohttp.ClientSession() as sess:
    #     async with sess.get('https://meme-api.com/gimme') as r:
    #         d = await r.json()
    #         return d['url']
    
    return 'https://placehold.jp/150x150.png'

async def cleaner(ls):
    l = []

    for i in ls:
        if i['picture'] == None:
            i['picture'] = await image_url()
        i['_id'] = str(i['_id'])
        i['delta'] = time_difference(make_timestamp(),i['time_inserted'])
        l.append(i)

    return l


def divide_chunks(l, n): 
      
    # looping till length l 
    for i in range(0, len(l), n):  
        yield l[i:i + n] 


def time_difference(current, previous):
    current*=1000
    previous*=1000
    ms_per_minute = 60 * 1000
    ms_per_hour = ms_per_minute * 60
    ms_per_day = ms_per_hour * 24
    ms_per_month = ms_per_day * 30
    ms_per_year = ms_per_day * 365

    elapsed = current - previous

    if elapsed < ms_per_minute:
        return str(round(elapsed / 1000)) + ' seconds ago'
    elif elapsed < ms_per_hour:
        return str(round(elapsed / ms_per_minute)) + ' minutes ago'
    elif elapsed < ms_per_day:
        return str(round(elapsed / ms_per_hour)) + ' hours ago'
    elif elapsed < ms_per_month:
        return 'approximately ' + str(round(elapsed / ms_per_day)) + ' days ago'
    elif elapsed < ms_per_year:
        return 'approximately ' + str(round(elapsed / ms_per_month)) + ' months ago'
    else:
        return 'approximately ' + str(round(elapsed / ms_per_year)) + ' years ago'