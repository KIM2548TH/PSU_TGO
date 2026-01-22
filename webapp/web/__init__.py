import os
import optparse
import json
from flask import Flask
from . import views
from .. import models
from .utils.error_handling import init_error_handling
from .utils import acl
from dotenv import load_dotenv


def load_config(app):
    app.config.from_object("webapp.default_settings")
    app.config.from_envvar("APP_SETTINGS")
    load_dotenv()

    for k, v in os.environ.items():
        if v in ["True", "TRUE", "False", "FALSE"]:
            v = v.lower()
        try:
            app.config[k] = json.loads(v)
        except Exception as e:
            app.config[k] = v


def create_app():
    app = Flask(__name__)
    load_config(app)
    
    # เพิ่มขนาดไฟล์สูงสุดที่รับได้ (100 MB)
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB

    views.register_blueprint(app)
    views.init_htmx(app)
    views.register_context_processors(app)  # ✅ เพิ่มตรงนี้

    models.init_db(app)
    acl.init_acl(app)
    init_error_handling(app)

    return app


def get_program_options(default_host="127.0.0.1", default_port="8080"):
    parser = optparse.OptionParser()
    parser.add_option("-H", "--host", default=default_host)
    parser.add_option("-P", "--port", default=default_port)
    parser.add_option("-c", "--config", dest="config", default=None)
    parser.add_option("-d", "--debug", action="store_true", dest="debug")
    parser.add_option("-p", "--profile", action="store_true", dest="profile")
    options, _ = parser.parse_args()
    return options
