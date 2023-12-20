from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import (
    StringField,
    SubmitField,
    PasswordField,
    BooleanField,
    IntegerField,
    DateField,
    TextAreaField,
    SelectField,
    SelectMultipleField
)
from wtforms.validators import DataRequired
from werkzeug.datastructures import FileStorage

from datetime import date
from helper import dtnow


class ReportLostItemForm(FlaskForm):
    name = StringField("Short Name of item", validators=[DataRequired()])
    description = TextAreaField("Describe the item", validators=[DataRequired()])
    picture = FileField("Upload a picture of the item")
    abnum = IntegerField("Academic Block Number", default=0)
    roomnum = IntegerField("Room Number", default=0)
    location = StringField("Location [If item was not lost in academic block]")
    date_of_loss = DateField("Date Lost", validators=[DataRequired()])
    category = SelectField("Select a category", validators=[DataRequired()])
    submit = SubmitField("Submit")


class ReportFoundForm(FlaskForm):
    name = StringField("Short Name of item", validators=[DataRequired()])
    description = TextAreaField("Describe the item", validators=[DataRequired()])
    picture = FileField("Upload a picture of the item")
    abnum = IntegerField("Academic Block Number", default=0)
    roomnum = IntegerField("Room Number", default=0)
    location = StringField("Location [If item was not found in academic block]")
    date_found = DateField("Date Found", validators=[DataRequired()])
    category = SelectField("Select a category", validators=[DataRequired()])
    submit = SubmitField("Submit")

class ClaimForm(FlaskForm):
    name = StringField("Enter your name", validators=[DataRequired()])
    rollnum = StringField("Roll number/Employee code/NA", validators=[DataRequired()])
    proofs = FileField("Upload a single PDF of images of proof(s).")
    additional_information = TextAreaField(
        "Any additional information you would like to provide ?"
    )
    submit = SubmitField("Submit")


class SearchFoundItems(FlaskForm):
    description = StringField("Description of the item")
    category = SelectField("Category")
    from_date = DateField(
        "From:", validators=[DataRequired()], default=date(2023, 12, 18)
    )
    to_date = DateField("To:", validators=[DataRequired()], default=dtnow())
    acadblock = IntegerField("Academic Block Number", default=0)
    roomnum = IntegerField("Room Number", default=0)
    location = StringField("Location. Eg: tea post")
    submit = SubmitField("Submit")

class SearchLostItems(FlaskForm):
    description = StringField("Description of the item")
    category = SelectField("Category")
    from_date = DateField(
        "From:", validators=[DataRequired()], default=date(2023, 12, 18)
    )
    to_date = DateField("To:", validators=[DataRequired()], default=dtnow())
    acadblock = IntegerField("Academic Block Number", default=0)
    roomnum = IntegerField("Room Number", default=0)
    location = StringField("Location. Eg: tea post")
    submit = SubmitField("Submit")


class MarkFound(FlaskForm):
    question = BooleanField('Are you sure you want to mark this item as found ?',validators=[DataRequired()],default=True)
    submit = SubmitField('Submit')


class ReviewClaimItemForm(FlaskForm):
    approve_these = SelectMultipleField('Select claims to approve.')
    reject_these = SelectMultipleField('Select these claims to reject.')
    submit = SubmitField('Submit')


class FinaliseClaimItem(FlaskForm):
    otp = StringField('Enter the OTP',validators=[DataRequired(),])
    submit = SubmitField('Submit')


class CategoryForm(FlaskForm):
    name = StringField('Enter the name of new category',validators=[DataRequired(),])
    submit = SubmitField('Submit')