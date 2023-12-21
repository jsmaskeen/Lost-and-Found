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

admins_db.insert_one({"_id": "01", "admin": False})

category_db.insert_one({"_id": "02", "name": None})

claims_db.insert_one(
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

found_items_db.insert_one(
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

lost_items_db.insert_one(
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

users_db.insert_one({
  "_id": "1",
  "name": "1",
  "email": "1",
  "picture": "1",
  "lost_items": 1,
  "found_items_of_others": 1,
  "found_lost_items": 1
})

