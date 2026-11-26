import os
from datetime import UTC
from zoneinfo import ZoneInfo

from azure.core.exceptions import AzureError
from dotenv import load_dotenv
from flask import Flask, render_template
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError

csrf = CSRFProtect()


def create_app(config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY"),
        AZURE_STORAGE_ACCOUNT_NAME=os.getenv("AZURE_STORAGE_ACCOUNT_NAME"),
        AZURE_STORAGE_CONNECTION_STRING=os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        MAX_CONTENT_LENGTH=6 * 1024 * 1024,
        MAX_FORM_MEMORY_SIZE=64 * 1024,
        SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "true").lower() != "false",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("SECRET_KEY must be configured")
    csrf.init_app(app)
    from forum.routes import bp

    app.register_blueprint(bp)

    @app.template_filter("jst")
    def jst(value):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(ZoneInfo("Asia/Tokyo")).strftime("%Y/%m/%d %H:%M")

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' blob:; style-src 'self'; "
            "script-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.errorhandler(AzureError)
    def storage_error(error):
        # Do not log SDK exception strings, request URLs or credentials.
        app.logger.error("Storage operation failed (%s)", type(error).__name__)
        return render_template(
            "error.html", message="保存先に接続できません。時間をおいて再度お試しください。"
        ), 503

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        return render_template(
            "error.html", message="フォームの有効期限が切れました。画面を開き直してください。"
        ), 400

    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", message="お探しの投稿・画像が見つかりません。"), 404

    @app.errorhandler(413)
    def too_large(error):
        return render_template(
            "error.html", message="送信サイズが大きすぎます。画像は5 MiB以下にしてください。"
        ), 413

    @app.errorhandler(500)
    def unexpected_error(error):
        return render_template(
            "error.html", message="処理に失敗しました。時間をおいて再度お試しください。"
        ), 500

    return app
