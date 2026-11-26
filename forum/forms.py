from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import SelectField, StringField, TextAreaField
from wtforms.fields.choices import SelectChoice
from wtforms.validators import InputRequired, Length, Optional

CATEGORIES = {
    "study": "勉強",
    "school": "学校生活",
    "career": "進路",
    "hobby": "趣味",
    "chat": "雑談",
}


def strip_text(value):
    return value.strip() if isinstance(value, str) else value


class JapaneseForm(FlaskForm):
    class Meta(FlaskForm.Meta):
        locales = ("ja",)


class CommentForm(JapaneseForm):
    nickname = StringField(
        "ニックネーム（任意）", filters=[strip_text], validators=[Optional(), Length(max=20)]
    )
    body = TextAreaField(
        "コメント", filters=[strip_text], validators=[InputRequired(), Length(min=1, max=500)]
    )


class PostForm(JapaneseForm):
    nickname = StringField(
        "ニックネーム（任意）", filters=[strip_text], validators=[Optional(), Length(max=20)]
    )
    title = StringField(
        "タイトル", filters=[strip_text], validators=[InputRequired(), Length(min=1, max=80)]
    )
    body = TextAreaField(
        "本文", filters=[strip_text], validators=[InputRequired(), Length(min=1, max=2000)]
    )
    category = SelectField(
        "カテゴリ",
        choices=[SelectChoice(key, label) for key, label in CATEGORIES.items()],
        validators=[InputRequired()],
    )
    image = FileField("添付画像（任意）")
