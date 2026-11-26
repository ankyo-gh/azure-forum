import re
from io import BytesIO

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from forum.forms import CATEGORIES, CommentForm, PostForm
from forum.images import sanitize_image
from forum.storage import get_storage

bp = Blueprint("board", __name__)
POST_ID = re.compile(r"\d{13}-[0-9a-f]{32}\Z")
BLOB_NAME = re.compile(r"[0-9a-f]{32}\.(jpg|png|webp)\Z")


@bp.app_context_processor
def categories():
    return {"categories": CATEGORIES}


def find_post(post_id):
    if not POST_ID.fullmatch(post_id):
        abort(404)
    post = get_storage().get_post(post_id)
    if not post:
        abort(404)
    return post


@bp.get("/health")
def health():
    return jsonify(status="ok")


@bp.get("/")
def index():
    category = request.args.get("category", "")
    if category and category not in CATEGORIES:
        abort(404)
    return render_template(
        "index.html", posts=get_storage().list_posts(category), selected=category
    )


@bp.get("/posts/new")
def new_post():
    return render_template("new_post.html", form=PostForm())


@bp.post("/posts")
def create_post():
    form = PostForm()
    valid = form.validate_on_submit()
    image = None
    files = request.files.getlist("image")
    if len([f for f in files if f.filename]) > 1:
        form.image.errors = [*form.image.errors, "添付できる画像は1枚です。"]
        valid = False
    if valid and form.image.data:
        try:
            image = sanitize_image(form.image.data)
        except ValueError as error:
            form.image.errors = [str(error)]
            valid = False
    if not valid:
        return render_template("new_post.html", form=form), 400
    post_id = get_storage().create_post(
        {
            "nickname": form.nickname.data or "匿名",
            "title": form.title.data,
            "body": form.body.data,
            "category": form.category.data,
        },
        image,
    )
    flash("投稿しました。")
    return redirect(url_for("board.post_detail", post_id=post_id), code=303)


@bp.get("/posts/<post_id>")
def post_detail(post_id):
    post = find_post(post_id)
    return render_template(
        "post_detail.html",
        post=post,
        comments=get_storage().list_comments(post_id),
        form=CommentForm(),
    )


@bp.post("/posts/<post_id>/comments")
def create_comment(post_id):
    post = find_post(post_id)
    form = CommentForm()
    if not form.validate_on_submit():
        return render_template(
            "post_detail.html", post=post, comments=get_storage().list_comments(post_id), form=form
        ), 400
    get_storage().create_comment(
        post_id,
        {
            "nickname": form.nickname.data or "匿名",
            "body": form.body.data,
        },
    )
    flash("コメントを投稿しました。")
    return redirect(url_for("board.post_detail", post_id=post_id, _anchor="comments"), code=303)


@bp.get("/images/<blob_name>")
def image(blob_name):
    if not BLOB_NAME.fullmatch(blob_name):
        abort(404)
    result = get_storage().get_image(blob_name)
    if result is None:
        abort(404)
    data, content_type = result
    return send_file(BytesIO(data), mimetype=content_type, max_age=3600)
