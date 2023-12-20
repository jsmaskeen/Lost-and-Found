import certifi
from config import db_uri
from loggerfile import logger
import json
import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorCollection
from bson.objectid import ObjectId
ca = certifi.where()
import asyncio

from helper import date_to_timestamp


from helper import make_timestamp

client = motor.motor_asyncio.AsyncIOMotorClient(db_uri,tlsCAFile=ca)
client.get_io_loop = asyncio.get_event_loop


my_db = client["iitgn_lafs"]
lost_items_db:motor.motor_asyncio.AsyncIOMotorCollection = my_db['lost_items_db']
found_items_db:motor.motor_asyncio.AsyncIOMotorCollection = my_db['found_items_db']
users_db:motor.motor_asyncio.AsyncIOMotorCollection = my_db['users_db']
category_db:motor.motor_asyncio.AsyncIOMotorCollection = my_db['category_db']
claims_db:motor.motor_asyncio.AsyncIOMotorCollection = my_db['claims_queue_db']
admins_db:motor.motor_asyncio.AsyncIOMotorCollection = my_db['admins_db']



async def get_user(uid):
    uid = str(uid)
    x = await users_db.find_one({'_id':uid})
    return x

async def insert_user(uid,name,email,picture):
    d= {
        '_id':uid,
        'name':name,
        'email':email,
        'picture':picture,
        'lost_items':0,
        'found_items_of_others':0,
        'found_lost_items':0
    }
    await users_db.insert_one(d)
    return d


async def increment(kind,uid):
    """ lost_items found_lost_items found_items_of_others """
    x =await get_user(uid)
    x[kind]+=1

    await users_db.replace_one({'_id':uid},x)

async def decrement(uid,kind='lost_items'):
    """lost_items"""
    x= await get_user(uid)
    v = x[kind]
    v = max(v,v-1)
    x[kind] = v

    await users_db.replace_one({'_id':uid},x)


async def insert_lost_item(picture_url,name,description,location_lost,category,date,time,semantic_time,uid,found=False): # user inserts their lost item
    d = {
        'picture':picture_url,
        'name':name,
        'description':description,
        'category':category,
        'date':date,
        'date_as_ts':date_to_timestamp(date),
        'time':time,
        'semantic_time':semantic_time,
        'lost_by_uid':uid,
        'found':found,
        'time_inserted':make_timestamp()
    }

    if isinstance(location_lost,tuple):
        d.update({
            'AB':location_lost[0],
            'room_num':location_lost[1],
            'location_lost':f'AB {"/".join(map(str,location_lost))}'
        })
    else:
        d.update({
            'location_lost':location_lost,
            'AB':None,
            'room_num':None
        })



    await lost_items_db.insert_one(d)
    await increment('lost_items',uid)
    return d

async def edit_lost_item(item_id,picture_url,name,description,location_lost,category,date,time,semantic_time,uid,found,time_inserted): # user edits their lost item
    if isinstance(item_id,str):
        item_id = ObjectId(item_id)
    
    d = {
        'picture':picture_url,
        'name':name,
        'description':description,
        'category':category,
        'date':date,
        'date_as_ts':date_to_timestamp(date),
        'time':time,
        'semantic_time':semantic_time,
        'lost_by_uid':uid,
        'found':found,
        'time_inserted':time_inserted,
        'time_edited':make_timestamp()
    }

    if isinstance(location_lost,tuple):
        d.update({
            'AB':location_lost[0],
            'room_num':location_lost[1],
            'location_lost':f'AB {"/".join(map(str,location_lost))}'
        })
    else:
        d.update({
            'location_lost':location_lost,
            'AB':None,
            'room_num':None
        })

    await lost_items_db.replace_one({'_id':item_id},d)
    
async def get_all_lost_items(includes_found=True,length=None):
    if includes_found:
        m = lost_items_db.find().sort('time_inserted',-1)
        return await m.to_list(length=length)
    m = lost_items_db.find({'found':False})
    return await m.to_list(length=length)

async def get_all_lost_items_for_user(uid,includes_found=True):
    if includes_found:
        m = lost_items_db.find({'lost_by_uid':uid}).sort('time_inserted',1)
        return await m.to_list(length=None)
    m = lost_items_db.find({'lost_by_uid':uid,'found':False})
    return await m.to_list(length=None)

async def mark_item_as_found(item_id): # user marks their lost item as found
    if isinstance(item_id,str):
        item_id = ObjectId(item_id)

    await lost_items_db.update_one({'_id':item_id},{'$set':{
        'found':True
    }})

    x = await lost_items_db.find_one({'_id':item_id})
    uid = x['lost_by_uid']
    await decrement(uid)
    await increment('found_lost_items',uid)


async def insert_found_item(picture_url,name,description,location_found,category,date,time,uid,claimed=False): # user inserts someone elses lost item which they found
    d = {
        'picture':picture_url,
        'name':name,
        'description':description,
        'category':category,
        'date':date,
        'date_as_ts':date_to_timestamp(date),
        'time':time,
        'found_by_uid':uid,
        'claimed':claimed,
        'time_inserted':make_timestamp()
    }

    if isinstance(location_found,tuple):
        d.update({
            'AB':location_found[0],
            'room_num':location_found[1],
            'location_found':f'AB {"/".join(map(str,location_found))}'
        })
    else:
        d.update({
            'location_found':location_found,
            'AB':None,
            'room_num':None
        })



    await found_items_db.insert_one(d)
    await increment('found_items_of_others',uid)
    return d

async def edit_found_item(item_id,picture_url,name,description,location_found,category,date,time,uid,claimed,time_inserted): # user edits someone elses lost item which they found
    if isinstance(item_id,str):
        item_id = ObjectId(item_id)
    
    d = {
        'picture':picture_url,
        'name':name,
        'description':description,
        'category':category,
        'date':date,
        'date_as_ts':date_to_timestamp(date),
        'time':time,
        'found_by_uid':uid,
        'claimed':claimed,
        'time_inserted':time_inserted,
        'time_edited':make_timestamp()
    }

    if isinstance(location_found,tuple):
        d.update({
            'AB':location_found[0],
            'room_num':location_found[1],
            'location_found':f'AB {"/".join(map(str,location_found))}'
        })
    else:
        d.update({
            'location_found':location_found,
            'AB':None,
            'room_num':None
        })

    await found_items_db.replace_one({'_id':item_id},d)
    
async def get_all_found_items(claimed=True,length=None):
    if claimed:
        m = found_items_db.find().sort('time_inserted',-1)
        return await m.to_list(length=length)
    m = found_items_db.find({'claimed':False}).sort('time_inserted',-1)
    return await m.to_list(length=length)

async def get_all_found_items_for_user(uid,claimed=True):
    if claimed:
        m = found_items_db.find({'found_by_uid':uid}).sort('time_inserted',-1)
        return await m.to_list(length=None)
    m = found_items_db.find({'found_by_uid':uid,'claimed':False}).sort('time_inserted',-1)
    return await m.to_list(length=None)

async def find_found_items_with_filter(filter,claimed=True):
    if claimed:
        ...
    m = found_items_db.find(filter).sort('time_inserted',-1)
    return await m.to_list(length=None)


async def mark_item_as_claimed(item_id):
    if isinstance(item_id,str):
        item_id = ObjectId(item_id)

    await found_items_db.update_one({'_id':item_id},{'$set':{
        'claimed':True
    }})

async def claim_item(item_id,uid): # user claims some item from list of found items the above fn is subpart of this
    if isinstance(item_id,str):
        item_id = ObjectId(item_id)

    # item = await found_items_db.find_one({'_id':item_id})

    await found_items_db.update_one({'_id':item_id},{'$set':{
        'claimed_by':uid
    }})

    await mark_item_as_claimed(item_id)
    await increment('found_lost_items',uid)



async def list_new_claims():
    return await claims_db.find({'stage':'requested'}).to_list(length=None)

async def list_under_processing():
    return await claims_db.find({'stage':'approved'}).to_list(length=None)



async def add_to_claim_queue(item_id,uid,proof,name,rollnum,additional_information):
    """stage should be requested , under_processing , processed"""
    await claims_db.insert_one({
        'item_id':item_id,
        'claimed_by':uid,
        'proof':proof,
        'stage':'requested',
        'name':name,
        'rollnum':rollnum,
        'additional_information':additional_information,
        'claimed_at':make_timestamp()
    })


async def approve_claim_stage2(claim_id,otp):
    if isinstance(claim_id,str):
        claim_id = ObjectId(claim_id)

    await claims_db.find_one_and_update({'_id':claim_id},{'$set':{
        'stage':'approved',
        'otp':otp
    }})


async def reject_claim_stage2(claim_id):
    if isinstance(claim_id,str):
        claim_id = ObjectId(claim_id)

    await claims_db.find_one_and_update({'_id':claim_id},{'$set':{
        'stage':'rejected'
    }})
    

async def get_claims_by_id(item_id):
    return await claims_db.find({'item_id':item_id,'stage':'requested'}).to_list(length=None)

async def get_stage2claim_by_id(id):
    if isinstance(id,str):
        id = ObjectId(id)
    return await claims_db.find_one({'_id':id})


async def complete_claim(claim_id):
    if isinstance(claim_id,str):
        claim_id = ObjectId(claim_id)

    await claims_db.find_one_and_update({'_id':claim_id},{'$set':{
        'stage':'completed'
    }})

async def get_found_item_by_id(item_id):
    if isinstance(item_id,str):
        item_id = ObjectId(item_id)
    
    return await found_items_db.find_one({'_id':item_id})

async def get_lost_item_by_id(item_id):
    if isinstance(item_id,str):
        item_id = ObjectId(item_id)
    
    return await lost_items_db.find_one({'_id':item_id})


async def delete_item(dbname,item_id):
    """lost_items_db | found_items_db"""
    if isinstance(item_id,str):
        item_id = ObjectId(item_id)
    if dbname == 'lost_items_db':
        await lost_items_db.delete_one({'_id':item_id})
    if dbname == 'found_items_db':
        await found_items_db.delete_one({'_id':item_id})
    if dbname == 'claims_queue_db':
        await claims_db.delete_one({'_id':item_id})


async def add_admin(uid):
    await admins_db.insert_one({'_id':uid,'admin':True})

# async def list_categories():
#     return [i['name'] for i  in await category_db.find({},{'_id':0,'name':1}).to_list(length=None)]

async def add_category(cat):
    await category_db.insert_one({'name':cat})
    return

# async def m():
#     await add_category('Electronics')
#     await add_category('Money (Cash/Wallet/Card)')
#     await add_category('Other')

# async def m():
#     await add_admin('101697754182408181748')

# asyncio.run(m())

# hearsay

import pymongo
c = pymongo.MongoClient(db_uri,tlsCAFile=ca)
cat_db = c['iitgn_lafs']['category_db']
u_db = c['iitgn_lafs']['users_db']
admn_db = c['iitgn_lafs']['admins_db']
def list_categories():
    return [i['name'] for i  in list(cat_db.find())]


def list_admins():
    return [i['_id'] for i in list(admn_db.find({'admin':True}))]

def sgetuser(uid):
    uid = str(uid)
    x = u_db.find_one({'_id':uid})
    return x



# asyncio.run(m())
    