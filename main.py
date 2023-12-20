import asyncio
import base64
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from functools import wraps

import google.auth.transport.requests
import requests
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
from werkzeug.utils import secure_filename

import config
import db
from from_classes import *
from helper import (
    cleaner,
    date_to_timestamp,
    divide_chunks,
    generateOTP,
    getIdFromUrl,
    send_approve,
    send_reject,
    upload_image,
    upload_pdf,
)

app = Flask(__name__)
app.config["SECRET_KEY"] = config.client_secret
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

GOOGLE_CLIENT_ID = config.client_id
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
            flash("You must login to access the endpoint")
            return redirect("/")
        return app.ensure_sync(fn)(*args, **kwargs)

    return decorated_view


def is_admin(fn):
    @wraps(fn)
    def decorated_view(*args, **kwargs):
        if not "google_id" in session:
            flash("You must login to access the endpoint")
            return redirect("/")
        if session["google_id"] not in db.list_admins():
            flash("You must have admin access to access the endpoint")
            return redirect("/")
        return app.ensure_sync(fn)(*args, **kwargs)

    return decorated_view


@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = timedelta(minutes=45)


@app.context_processor
def inject_dict_for_all_templates():
    return dict(
        login_details=session.get("login_details", {}),
        isadmin=session.get("isadmin", False),
        request=request,
    )


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
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID,
        clock_skew_in_seconds=20,
    )
    if not config.allow_all_emails:
        if not "@iitgn.ac.in" in id_info["email"]:
            flash("Only @iitgn.ac.in emails are allowed.")
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

    if str(id_info.get("sub")) in db.list_admins():
        session["isadmin"] = True
    else:
        session["isadmin"] = False

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
            if not picture.mimetype.startswith("image"):
                flash("The uploaded file is not a picture")
                return redirect(f"/report_a_lost_item")
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
                flash("Academic Block Number or Room Number cannot be negative")
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
        flash("Reported Sucessfully")
        return redirect("/report_a_lost_item")

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
            if not picture.mimetype.startswith("image"):
                flash("The uploaded file is not a picture")
                return redirect(f"/report_a_found_item")
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
                flash("Academic Block Number or Room Number cannot be negative")
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
        flash("Successfully Reported")
        return redirect("/report_a_found_item")

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


@app.route("/claim_item/<string:_id>", methods=["GET", "POST"])
@auth_required
async def claim_item(_id):
    item = await cleaner([await db.get_found_item_by_id(_id)])
    item = item[0]

    name, rollnum, proofs, additional_information = [None] * 4

    form = ClaimForm()

    if form.validate_on_submit():
        name = form.name.data
        form.name.data = ""
        rollnum = form.rollnum.data
        form.rollnum.data = ""
        additional_information = form.additional_information.data
        form.additional_information.data = ""
        proofs = form.proofs.data
        if proofs:
            proofs: FileStorage
            if proofs.mimetype != "application/pdf":
                flash("The upload file should be of the type pdf")
                return redirect(f"/claim_item/{_id}")

            fname = secure_filename(f"proofs_{_id}.pdf")
            proofs.save(f"/tmp/{fname}")

            with ThreadPoolExecutor() as pool:
                res = await asyncio.get_event_loop().run_in_executor(
                    pool, upload_pdf, f"/tmp/{fname}"
                )

            proofs_link = res
        else:
            proofs_link = None

        await db.add_to_claim_queue(
            _id,
            session["google_id"],
            proofs_link,
            name,
            rollnum,
            additional_information,
        )
        flash("Claim request sent for approval")
        return redirect("/all_found_items")

    if form.errors != {}:
        return jsonify(form.errors)

    return render_template(
        "claim_item.html",
        item=item,
        form=form,
        name=name,
        rollnum=rollnum,
        proofs=proofs,
        additional_information=additional_information,
    )


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
            flash("Academic Block Number or Room Number cannot be negative")
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
                        "text": {"query": description.lower(), "path": "description"},
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
                            "path": "location_found",
                        },
                    }
                }
            )

        search_params |= {"claimed": {"$eq": False}}

        pipeline.append({"$match": search_params})

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
            flash("Academic Block Number or Room Number cannot be negative")
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
                        "text": {"query": description.lower(), "path": "description"},
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
                            "path": "location_lost",
                        },
                    }
                }
            )

        search_params |= {"found": {"$eq": False}}

        pipeline.append({"$match": search_params})

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


@app.route("/my_lost_items", methods=["GET", "POST"])
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
            flash("Academic Block Number or Room Number cannot be negative")
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

        search_params = {"lost_by_uid": {"$eq": session["google_id"]}}

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
                        "text": {"query": description.lower(), "path": "description"},
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
                            "path": "location_lost",
                        },
                    }
                }
            )

        search_params |= {"found": {"$eq": False}}

        pipeline.append({"$match": search_params})

        m = db.lost_items_db.aggregate(pipeline)
        items = await cleaner(await m.to_list(length=100))

    if items == None:
        items = await cleaner(
            await db.get_all_lost_items_for_user(
                session["google_id"], includes_found=False
            )
        )

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


@app.route("/my_found_items", methods=["GET", "POST"])
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
            flash("Academic Block Number or Room Number cannot be negative")
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

        search_params = {"found_by_uid": {"$eq": session["google_id"]}}

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
                        "text": {"query": description.lower(), "path": "description"},
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
                            "path": "location_found",
                        },
                    }
                }
            )

        search_params |= {"claimed": {"$eq": False}}

        pipeline.append({"$match": search_params})

        m = db.found_items_db.aggregate(pipeline)
        items = await cleaner(await m.to_list(length=100))

    if items == None:
        items = await cleaner(
            await db.get_all_found_items_for_user(session["google_id"], claimed=False)
        )

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


@app.route("/mark_found/<string:_id>", methods=["GET", "POST"])
@auth_required
async def mark_found(_id):
    item = await cleaner([await db.get_lost_item_by_id(_id)])
    item = item[0]
    question = None
    form = MarkFound()

    if form.validate_on_submit():
        question = form.question.data
        form.question.data = False
        if question == True:
            await db.mark_item_as_found(_id)
        flash("Marked Item as Found")
        return redirect("/my_lost_items")

    return render_template("mark_found.html", item=item, form=form, question=question)


@app.route("/admin", methods=["GET"])
@auth_required
@is_admin
async def admin():
    ls = {
        "num_of_lost_items": len(await db.get_all_lost_items(includes_found=False)),
        "num_of_claim_requests_under_processing": len(
            await db.claims_db.find({"stage": "approved"}).to_list(length=None)
        ),
        "num_of_claim_requests": len(
            await db.claims_db.find({"stage": "requested"}).to_list(length=None)
        ),
        "num_of_users": len(await db.users_db.find().to_list(length=None)),
        "num_of_found_items": len(await db.get_all_found_items(claimed=False)),
    }
    return render_template("adminpanel.html", **ls)


@app.route("/new_claim_requests", methods=["GET"])
@auth_required
@is_admin
async def new_claim_requests():
    claim_reqs = await db.list_new_claims()

    ls = []

    ls = [db.get_found_item_by_id(i["item_id"]) for i in claim_reqs]
    ls = await asyncio.gather(*ls)
    ls = await cleaner(ls)

    for i in claim_reqs:
        i["_id"] = str(i["_id"])
    data = list(zip(ls, claim_reqs))
    # for i in data:
    #     print(i)
    # print(data)
    return render_template("new_claim_requests.html", data=data)


@app.route("/delete/<path:theurl>/<string:dbname>/<string:_id>")
@auth_required
@is_admin
async def delete_from_db(theurl, dbname, _id):
    # print(theurl,dbname,_id)

    await db.delete_item(dbname, item_id=_id)
    flash("Deleted the item")
    return redirect(f"/{theurl}")
    # await db.delete_item()


@app.route("/review_claim_item/<string:_id>", methods=["GET", "POST"])
@auth_required
@is_admin
async def review_claim_item(_id):
    approve_these, reject_these = [None] * 2
    form = ReviewClaimItemForm()
    item = await cleaner([await db.get_found_item_by_id(_id)])
    item = item[0]
    reqs = await db.get_claims_by_id(_id)
    for i in reqs:
        i["_id"] = str(i["_id"])
        i["spcl"] = i["name"] + "|" + str(i["rollnum"])
        if i["proof"]:
            i["proof_id"] = getIdFromUrl(i["proof"])
    choices = [i["spcl"] for i in reqs]
    form.approve_these.choices = choices
    form.reject_these.choices = choices

    if form.validate_on_submit():
        approve_these = form.approve_these.data
        reject_these = form.reject_these.data
        if len(approve_these) == 0 and len(reject_these) == 0:
            flash("You must select atleast one user to approve or reject")
            return redirect(f"/review_claim_item/{_id}")

        to_approve = list(set(approve_these) - set(reject_these))

        for i in reqs:
            if i["spcl"] in to_approve:
                otp = generateOTP()
                await db.approve_claim_stage2(i["_id"], otp)
                uid = i["claimed_by"]
                user = await db.get_user(uid)
                print(otp)
                await send_approve(
                    user["name"], user["email"], url_for("view", _id=item["_id"]), otp
                )
            else:
                await db.reject_claim_stage2(i["_id"])
                uid = i["claimed_by"]
                user = await db.get_user(uid)
                await send_reject(
                    user["name"], user["email"], url_for("view", _id=item["_id"])
                )
        flash("Approved and Rejected respective users for the claim")
        return redirect("/new_claim_requests")

    return render_template(
        "review_claim_item.html",
        reqs=reqs,
        item=item,
        form=form,
        approve_these=approve_these,
        reject_these=reject_these,
    )


@app.route("/claims_under_processing")
@auth_required
@is_admin
async def claims_under_processing():
    claim_reqs = await db.list_under_processing()

    ls = []

    ls = [db.get_found_item_by_id(i["item_id"]) for i in claim_reqs]
    ls = await asyncio.gather(*ls)
    ls = await cleaner(ls)

    for i in claim_reqs:
        i["_id"] = str(i["_id"])
    data = list(zip(ls, claim_reqs))
    # for i in data:
    #     print(i)
    # print(data)
    return render_template("claims_under_processing.html", data=data)


@app.route("/finalise_claim_item/<string:_id>", methods=["GET", "POST"])
@auth_required
@is_admin
async def finalise_claim_item(_id):
    req = await db.get_stage2claim_by_id(_id)

    item = await cleaner([await db.get_found_item_by_id(req["item_id"])])
    item = item[0]
    item_id = item["_id"]

    req["_id"] = str(req["_id"])
    if req["proof"]:
        req["proof_id"] = getIdFromUrl(req["proof"])

    otp = None
    form = FinaliseClaimItem()
    item = await cleaner([await db.get_found_item_by_id(item_id)])
    item = item[0]

    mine_otp = req["otp"]

    if form.validate_on_submit():
        otp = form.otp.data
        form.otp.data = ""

        if str(mine_otp) != str(otp):
            flash("Error: Incorrect OTP provided")
            return redirect(f"/finalise_claim_item/{_id}")

        await db.complete_claim(_id)
        await db.claim_item(item_id, req["claimed_by"])

        for i in await db.claims_db.find({"item_id": item_id}).to_list(length=None):
            if str(i["_id"]) != _id and i["stage"] != "rejected":
                if i["stage"] == "approved":
                    user = await db.get_user(i["claimed_by"])
                    await send_reject(
                        user["name"], user["email"], url_for("view", _id=item["_id"])
                    )
                await db.claims_db.find_one_and_update(
                    {"_id": i["_id"]}, {"$set": {"stage": "rejected"}}
                )
        flash("Completed Claim")
        return redirect("/claims_under_processing")

    return render_template(
        "finalise_claim_item.html", item=item, req=req, form=form, otp=None
    )


@app.route("/view/<string:_id>")
@auth_required
async def view(_id):
    l = await db.get_found_item_by_id(_id)
    if not l:
        l = await db.get_lost_item_by_id(_id)
    l = await cleaner([l])
    l = l[0]

    return render_template("view.html", item=l)


@app.route("/add_category", methods=["GET", "POST"])
@auth_required
@is_admin
async def add_category():
    name = None
    form = CategoryForm()
    if form.validate_on_submit():
        name = form.name.data
        form.name.data = ""
        await db.add_category(name)
        flash("Added the category")
        return redirect("add_category")
    existing = await db.category_db.find({}, {"name": 1}).to_list(length=None)
    return render_template(
        "add_category.html",
        name=name,
        form=form,
        existing=" | ".join([i["name"] for i in existing]),
    )


@app.route("/old_claims")
@auth_required
@is_admin
async def old_claims():
    # rejected and completed

    reqs = await db.claims_db.find(
        {"stage": {"$in": ["completed", "rejected"]}}
    ).to_list(length=None)
    for i in reqs:
        i["_id"] = str(i["_id"])

    return render_template("old_claims.html", reqs=reqs)


@app.errorhandler(500)
def int_ser_err(err):
    return render_template('error.html',err=err)


app.run(port=5100, debug=True)
