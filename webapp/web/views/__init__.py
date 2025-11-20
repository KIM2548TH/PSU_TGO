import importlib
import logging
import pathlib
from flask_htmx import HTMX
from flask import session
from ..utils import template_filters
from ..utils.translations import translations  # ✅ แก้ path ให้ถูก



logger = logging.getLogger(__name__)
htmx = HTMX()


def get_subblueprints(directory):
    blueprints = []
    package = directory.parts[len(pathlib.Path.cwd().parts) :]
    parent_module = None
    try:
        pymod_file = f"{'.'.join(package)}"
        pymod = importlib.import_module(pymod_file)
        if "module" in dir(pymod):
            parent_module = pymod.module
            blueprints.append(parent_module)
    except Exception as e:
        logger.exception(e)
        return blueprints

    subblueprints = []
    for module in directory.iterdir():
        if module.name[:2] == "__":
            continue
        if module.match("*.py"):
            try:
                pymod_file = f"{'.'.join(package)}.{module.stem}"
                pymod = importlib.import_module(pymod_file)
                if "module" in dir(pymod):
                    subblueprints.append(pymod.module)
            except Exception as e:
                logger.exception(e)
        elif module.is_dir():
            subblueprints.extend(get_subblueprints(module))

    for module in subblueprints:
        if parent_module:
            parent_module.register_blueprint(module)
        else:
            blueprints.append(module)

    return blueprints


def register_blueprint(app):
    app.add_template_filter(template_filters.static_url)
    parent = pathlib.Path(__file__).parent
    blueprints = get_subblueprints(parent)
    for blueprint in blueprints:
        app.register_blueprint(blueprint)


def init_htmx(app):
    htmx.init_app(app)


def register_context_processors(app):
    @app.context_processor
    def inject_translation():
        lang = session.get("lang", "th")
        t = translations.get(lang, translations["th"])
        return dict(t=t, lang=lang)
