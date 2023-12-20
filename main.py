from flask import Flask, render_template, redirect, session, request, abort, jsonify
from flask_wtf.form import _Auto
import requests
from google.oauth2 import id_token
from pip._vendor import cachecontrol
from google_auth_oauthlib.flow import Flow
import google.auth.transport.requests
import os
from loggerfile import logger
import config
from functools import wraps
import base64
import db
from helper import upload_image, cleaner, divide_chunks, dtnow, date_to_timestamp
from from_classes import *

app = Flask(__name__)
app.config["SECRET_KEY"] = config.client_secret
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = (
    config.client_id
)
client_secrets_file = "client_secret.json"

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "openid",
    ],
    redirect_uri=f"{config.domain}/callback",
)

def auth_required(fn):
    @wraps(fn)
    def decorated_view(*args, **kwargs):
        if not "google_id" in session:
            return redirect("/")
        return app.ensure_sync(fn)(*args, **kwargs)

    return decorated_view

@app.context_processor
def inject_dict_for_all_templates():
    return dict(login_details=session.get("login_details", {}))

@app.route("/login")
async def login():
    auth_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(auth_url)

@app.route("/callback")
async def callback():
    flow.fetch_token(authorization_response=request.url)

    if not session["state"] == request.args["state"]:
        abort(500)  # State does not match!

    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)

    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token, request=token_request, audience=GOOGLE_CLIENT_ID
    )
    if not "@iitgn.ac.in" in id_info["email"]:
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

    user = db.sgetuser(id_info["sub"])
    if not user:
        user = await db.insert_user(
            id_info["sub"], id_info["name"], id_info["email"], id_info["picture"]
        )
    return redirect("/home")

@app.route("/logout")
async def logout():
    session.clear()
    return redirect("/")

@app.route("/")
async def home():
    if "google_id" in session:
        return redirect("/home")
    return render_template("home.html")

@app.route("/home")
@auth_required
async def auth_home():
    recent_lost = divide_chunks(
        await cleaner(await db.get_all_lost_items(includes_found=False, length=12)), 3
    )

    recent_found = divide_chunks(
        await cleaner(await db.get_all_found_items(claimed=False, length=12)), 3
    )

    return render_template(
        "auth_home.html", recent_lost=recent_lost, recent_found=recent_found
    )

@app.route("/report_a_lost_item", methods=["GET", "POST"])
@auth_required
async def report_a_lost_item():
    name, description, picture, abnum, roomnum, location, date_of_loss = [None] * 7
    form = ReportLostItemForm()
    form.category.choices = db.list_categories()
    if form.validate_on_submit():
        name = form.name.data
        form.name.data = ""
        description = form.description.data
        form.description.data = ""
        picture = form.picture.data
        if picture:
            picture: FileStorage
            picture = base64.b64encode(picture.stream.read()).decode("utf-8")

        abnum = form.abnum.data
        form.abnum.data = 0
        roomnum = form.roomnum.data
        form.roomnum.data = 0
        location = form.location.data
        form.location.data = ""
        date_of_loss = form.date_of_loss.data.strftime("%d-%m-%Y")
        form.date_of_loss.data = ""

        if abnum != 0 and roomnum != 0:
            if abnum <= 0 or roomnum <= 0:
                return redirect("/report_a_lost_item")

            location_lost = (int(abnum), int(roomnum))
        else:
            location_lost = location

        category = form.category.data
        form.category.data = ""

        await db.insert_lost_item(
            await upload_image(picture),
            name,
            description,
            location_lost,
            category,
            date_of_loss,
            time=None,
            semantic_time=None,
            uid=session["google_id"],
        )

    if form.errors != {}:
        return jsonify(form.errors)

    return render_template(
        "report_a_lost_item.html",
        name=name,
        description=description,
        form=form,
        picture=picture,
        abnum=abnum,
        roomnum=roomnum,
        date_of_loss=date_of_loss,
        location=location,
    )

@app.route("/report_a_found_item", methods=["GET", "POST"])
@auth_required
async def report_a_found_item():
    name, description, picture, abnum, roomnum, location, date_found = [None] * 7
    form = ReportFoundForm()
    form.category.choices = db.list_categories()
    if form.validate_on_submit():
        name = form.name.data
        form.name.data = ""
        description = form.description.data
        form.description.data = ""
        picture = form.picture.data
        if picture:
            picture: FileStorage
            picture = base64.b64encode(picture.stream.read()).decode("utf-8")

        abnum = form.abnum.data
        form.abnum.data = 0
        roomnum = form.roomnum.data
        form.roomnum.data = 0
        location = form.location.data
        form.location.data = ""
        date_found = form.date_found.data.strftime("%d-%m-%Y")
        form.date_found.data = ""

        if abnum != 0 and roomnum != 0:
            if abnum <= 0 or roomnum <= 0:
                return redirect("/report_a_found_item")

            location_found = (int(abnum), int(roomnum))
        else:
            location_found = location

        category = form.category.data
        form.category.data = ""

        await db.insert_found_item(
            await upload_image(picture),
            name,
            description,
            location_found,
            category,
            date_found,
            time=None,
            uid=session["google_id"],
        )

    if form.errors != {}:
        return jsonify(form.errors)

    return render_template(
        "report_a_found_item.html",
        name=name,
        description=description,
        form=form,
        picture=picture,
        abnum=abnum,
        roomnum=roomnum,
        date_of_loss=date_found,
        location=location,
    )

@app.route("/claim_item/<string:_id>")
@auth_required
async def claim_item(_id):
    return render_template("claim_item.html", _id=_id)

@app.route("/all_found_items", methods=["GET", "POST"])
@auth_required
async def all_found_items():
    items = None
    description, category, from_date, to_date, acadblock, roomnum, location = [None] * 7
    form = SearchFoundItems()
    form.category.choices = ["All"] + db.list_categories()
    if form.validate_on_submit():
        description = form.description.data
        form.description.data = ""
        acadblock = form.acadblock.data
        form.acadblock.data = 0
        roomnum = form.roomnum.data
        form.roomnum.data = 0

        location = form.location.data
        form.location.data = ""
        from_date = form.from_date.data
        to_date = form.to_date.data
        form.from_date.data = ""
        form.to_date.data = ""

        if acadblock < 0 or roomnum < 0:
            return redirect("/all_found_items")

        if acadblock != 0 and roomnum == 0 and not location:
            location_found = f"search only in AB {acadblock}"
        elif acadblock == 0 and roomnum == 0 and location:
            location_found = location
        elif acadblock != 0 and roomnum != 0:
            location_found = f"AB {acadblock}/{roomnum}"
        else:
            location_found = location

        category = form.category.data
        if category == "All":
            category = ""
        form.category.data = ""

        # print((description,category,from_date,to_date,acadblock,roomnum,location_found))

        search_params = {}

        search_params |= {
            "date_as_ts": {  # done
                "$gte": date_to_timestamp(from_date.strftime("%d-%m-%Y")),
                "$lte": date_to_timestamp(to_date.strftime("%d-%m-%Y")),
            }
        }
        fuzzy_loc = False
        if category != "":  # done
            search_params |= {"category": {"$eq": category}}

        if acadblock != 0 and roomnum == 0 and not location:  # done
            search_params |= {"AB": {"$eq": acadblock}}
        else:
            if location_found != "" and acadblock != 0 and roomnum != 0:
                search_params |= {"location_found": {"$eq": location_found}}
            else:
                if location_found != "":  # fuzzy location
                    fuzzy_loc = True

        # pipeline.append(search_params)

        pipeline = []

        if description and fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "found_items_search_index",
                        "compound": {
                            "should": [
                                {
                                    "text": {
                                        "query": description.lower(),
                                        "path": "description",
                                        "score": {"boost": {"value": 9}},
                                    }
                                },
                                {
                                    "text": {
                                        "query": location_found.lower(),
                                        "path": "location_found",
                                        "score": {"boost": {"value": 4}},
                                    }
                                },
                            ]
                        },
                    }
                }
            )
        elif description and not fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "found_items_search_index",
                        "text": {
                            "query": description.lower(),
                            "path": "description"
                        },
                    }
                }
            )
        elif not description and fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "found_items_search_index",
                        "text": {
                            "query": location_found.lower(),
                            "path": "location_found"
                        },
                    }
                }
            )

        search_params|={
            'claimed':{'$eq':False}
        }
        

        pipeline.append(
            {"$match": search_params})


        m = db.found_items_db.aggregate(pipeline)
        items = await cleaner(await m.to_list(length=100))


    if items == None:
        items = await cleaner(await db.get_all_found_items(claimed=False))

    if form.errors != {}:
        return jsonify(form.errors)

    return render_template(
        "all_found_items.html",
        items=items,
        form=form,
        description=description,
        category=category,
        from_date=from_date,
        to_date=to_date,
        acadblock=acadblock,
        roomnum=roomnum,
        location=location,
    )

@app.route("/all_lost_items", methods=["GET", "POST"])
@auth_required
async def all_lost_items():
    items = None
    description, category, from_date, to_date, acadblock, roomnum, location = [None] * 7
    form = SearchLostItems()
    form.category.choices = ["All"] + db.list_categories()
    if form.validate_on_submit():
        description = form.description.data
        form.description.data = ""
        acadblock = form.acadblock.data
        form.acadblock.data = 0
        roomnum = form.roomnum.data
        form.roomnum.data = 0

        location = form.location.data
        form.location.data = ""
        from_date = form.from_date.data
        to_date = form.to_date.data
        form.from_date.data = ""
        form.to_date.data = ""

        if acadblock < 0 or roomnum < 0:
            return redirect("/all_lost_items")

        if acadblock != 0 and roomnum == 0 and not location:
            location_lost = f"search only in AB {acadblock}"
        elif acadblock == 0 and roomnum == 0 and location:
            location_lost = location
        elif acadblock != 0 and roomnum != 0:
            location_lost = f"AB {acadblock}/{roomnum}"
        else:
            location_lost = location

        category = form.category.data
        if category == "All":
            category = ""
        form.category.data = ""

        # print((description,category,from_date,to_date,acadblock,roomnum,location_found))

        search_params = {}

        search_params |= {
            "date_as_ts": {  # done
                "$gte": date_to_timestamp(from_date.strftime("%d-%m-%Y")),
                "$lte": date_to_timestamp(to_date.strftime("%d-%m-%Y")),
            }
        }
        fuzzy_loc = False
        if category != "":  # done
            search_params |= {"category": {"$eq": category}}

        if acadblock != 0 and roomnum == 0 and not location:  # done
            search_params |= {"AB": {"$eq": acadblock}}
        else:
            if location_lost != "" and acadblock != 0 and roomnum != 0:
                search_params |= {"location_lost": {"$eq": location_lost}}
            else:
                if location_lost != "":  # fuzzy location
                    fuzzy_loc = True

        # pipeline.append(search_params)

        pipeline = []

        if description and fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "lost_items_search_index",
                        "compound": {
                            "should": [
                                {
                                    "text": {
                                        "query": description.lower(),
                                        "path": "description",
                                        "score": {"boost": {"value": 9}},
                                    }
                                },
                                {
                                    "text": {
                                        "query": location_lost.lower(),
                                        "path": "location_lost",
                                        "score": {"boost": {"value": 4}},
                                    }
                                },
                            ]
                        },
                    }
                }
            )
        elif description and not fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "lost_items_search_index",
                        "text": {
                            "query": description.lower(),
                            "path": "description"
                        },
                    }
                }
            )
        elif not description and fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "lost_items_search_index",
                        "text": {
                            "query": location_lost.lower(),
                            "path": "location_lost"
                        },
                    }
                }
            )

        search_params|={
            'found':{'$eq':False}
        }
        

        pipeline.append(
            {"$match": search_params})

        m = db.lost_items_db.aggregate(pipeline)
        items = await cleaner(await m.to_list(length=100))


    if items == None:
        items = await cleaner(await db.get_all_lost_items(includes_found=False))

    if form.errors != {}:
        return jsonify(form.errors)

    return render_template(
        "all_lost_items.html",
        items=items,
        form=form,
        description=description,
        category=category,
        from_date=from_date,
        to_date=to_date,
        acadblock=acadblock,
        roomnum=roomnum,
        location=location,
    )

@app.route('/my_lost_items',methods=["GET","POST"])
@auth_required
async def my_lost_items():
    items = None
    description, category, from_date, to_date, acadblock, roomnum, location = [None] * 7
    form = SearchLostItems()
    form.category.choices = ["All"] + db.list_categories()
    if form.validate_on_submit():
        description = form.description.data
        form.description.data = ""
        acadblock = form.acadblock.data
        form.acadblock.data = 0
        roomnum = form.roomnum.data
        form.roomnum.data = 0

        location = form.location.data
        form.location.data = ""
        from_date = form.from_date.data
        to_date = form.to_date.data
        form.from_date.data = ""
        form.to_date.data = ""

        if acadblock < 0 or roomnum < 0:
            return redirect("/my_lost_items")

        if acadblock != 0 and roomnum == 0 and not location:
            location_lost = f"search only in AB {acadblock}"
        elif acadblock == 0 and roomnum == 0 and location:
            location_lost = location
        elif acadblock != 0 and roomnum != 0:
            location_lost = f"AB {acadblock}/{roomnum}"
        else:
            location_lost = location

        category = form.category.data
        if category == "All":
            category = ""
        form.category.data = ""

        # print((description,category,from_date,to_date,acadblock,roomnum,location_found))

        search_params = {'lost_by_uid':{
            '$eq':session['google_id']
        }}

        search_params |= {
            "date_as_ts": {  # done
                "$gte": date_to_timestamp(from_date.strftime("%d-%m-%Y")),
                "$lte": date_to_timestamp(to_date.strftime("%d-%m-%Y")),
            }
        }
        fuzzy_loc = False
        if category != "":  # done
            search_params |= {"category": {"$eq": category}}

        if acadblock != 0 and roomnum == 0 and not location:  # done
            search_params |= {"AB": {"$eq": acadblock}}
        else:
            if location_lost != "" and acadblock != 0 and roomnum != 0:
                search_params |= {"location_lost": {"$eq": location_lost}}
            else:
                if location_lost != "":  # fuzzy location
                    fuzzy_loc = True

        # pipeline.append(search_params)

        pipeline = []

        if description and fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "lost_items_search_index",
                        "compound": {
                            "should": [
                                {
                                    "text": {
                                        "query": description.lower(),
                                        "path": "description",
                                        "score": {"boost": {"value": 9}},
                                    }
                                },
                                {
                                    "text": {
                                        "query": location_lost.lower(),
                                        "path": "location_lost",
                                        "score": {"boost": {"value": 4}},
                                    }
                                },
                            ]
                        },
                    }
                }
            )
        elif description and not fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "lost_items_search_index",
                        "text": {
                            "query": description.lower(),
                            "path": "description"
                        },
                    }
                }
            )
        elif not description and fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "lost_items_search_index",
                        "text": {
                            "query": location_lost.lower(),
                            "path": "location_lost"
                        },
                    }
                }
            )

        search_params|={
            'found':{'$eq':False}
        }
        

        pipeline.append(
            {"$match": search_params})

        m = db.lost_items_db.aggregate(pipeline)
        items = await cleaner(await m.to_list(length=100))


    if items == None:
        items = await cleaner(await db.get_all_lost_items_for_user(session['google_id'],includes_found=False))
    

    if form.errors != {}:
        return jsonify(form.errors)

    return render_template(
        "my_lost_items.html",
        items=items,
        form=form,
        description=description,
        category=category,
        from_date=from_date,
        to_date=to_date,
        acadblock=acadblock,
        roomnum=roomnum,
        location=location,
    )

@app.route('/my_found_items',methods=['GET','POST'])
@auth_required
async def my_found_items():
    items = None
    description, category, from_date, to_date, acadblock, roomnum, location = [None] * 7
    form = SearchFoundItems()
    form.category.choices = ["All"] + db.list_categories()
    if form.validate_on_submit():
        description = form.description.data
        form.description.data = ""
        acadblock = form.acadblock.data
        form.acadblock.data = 0
        roomnum = form.roomnum.data
        form.roomnum.data = 0

        location = form.location.data
        form.location.data = ""
        from_date = form.from_date.data
        to_date = form.to_date.data
        form.from_date.data = ""
        form.to_date.data = ""

        if acadblock < 0 or roomnum < 0:
            return redirect("/all_found_items")

        if acadblock != 0 and roomnum == 0 and not location:
            location_found = f"search only in AB {acadblock}"
        elif acadblock == 0 and roomnum == 0 and location:
            location_found = location
        elif acadblock != 0 and roomnum != 0:
            location_found = f"AB {acadblock}/{roomnum}"
        else:
            location_found = location

        category = form.category.data
        if category == "All":
            category = ""
        form.category.data = ""

        # print((description,category,from_date,to_date,acadblock,roomnum,location_found))

        search_params = {'found_by_uid':{'$eq':session['google_id']}}

        search_params |= {
            "date_as_ts": {  # done
                "$gte": date_to_timestamp(from_date.strftime("%d-%m-%Y")),
                "$lte": date_to_timestamp(to_date.strftime("%d-%m-%Y")),
            }
        }
        fuzzy_loc = False
        if category != "":  # done
            search_params |= {"category": {"$eq": category}}

        if acadblock != 0 and roomnum == 0 and not location:  # done
            search_params |= {"AB": {"$eq": acadblock}}
        else:
            if location_found != "" and acadblock != 0 and roomnum != 0:
                search_params |= {"location_found": {"$eq": location_found}}
            else:
                if location_found != "":  # fuzzy location
                    fuzzy_loc = True

        # pipeline.append(search_params)

        pipeline = []

        if description and fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "found_items_search_index",
                        "compound": {
                            "should": [
                                {
                                    "text": {
                                        "query": description.lower(),
                                        "path": "description",
                                        "score": {"boost": {"value": 9}},
                                    }
                                },
                                {
                                    "text": {
                                        "query": location_found.lower(),
                                        "path": "location_found",
                                        "score": {"boost": {"value": 4}},
                                    }
                                },
                            ]
                        },
                    }
                }
            )
        elif description and not fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "found_items_search_index",
                        "text": {
                            "query": description.lower(),
                            "path": "description"
                        },
                    }
                }
            )
        elif not description and fuzzy_loc:
            pipeline.append(
                {
                    "$search": {
                        "index": "found_items_search_index",
                        "text": {
                            "query": location_found.lower(),
                            "path": "location_found"
                        },
                    }
                }
            )

        search_params|={
            'claimed':{'$eq':False}
        }
        

        pipeline.append(
            {"$match": search_params})


        m = db.found_items_db.aggregate(pipeline)
        items = await cleaner(await m.to_list(length=100))


    if items == None:
        items = await cleaner(await db.get_all_found_items_for_user(session['google_id'],claimed=False))

    if form.errors != {}:
        return jsonify(form.errors)

    return render_template(
        "my_found_items.html",
        items=items,
        form=form,
        description=description,
        category=category,
        from_date=from_date,
        to_date=to_date,
        acadblock=acadblock,
        roomnum=roomnum,
        location=location,
    )

@app.route('/mark_found/<string:_id>',methods=['GET','POST'])
@auth_required
async def mark_found(_id):
    item  = await cleaner([await db.get_lost_item_by_id(_id)])
    item = item[0]
    question = None
    form = MarkFound()

    if form.validate_on_submit():
        question = form.question.data
        form.question.data = False
        if question == True:
            await db.mark_item_as_found(_id)
        return redirect('/my_lost_items')


    return render_template('mark_found.html',item=item,form=form,question=question)


app.run(port=5100, debug=True)
