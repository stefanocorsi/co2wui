import webbrowser
import threading
import tempfile
import schedula as sh
from co2mpas import __version__
import click
from flask import Flask, render_template, current_app, url_for, request, send_file
from flask import Response
from flask import Flask, redirect
from flask.cli import FlaskGroup
from os import listdir
from os.path import isfile, join
import requests
import json
import io
import os
import os.path as osp
from werkzeug import secure_filename
import logging
import logging.config


def create_app(configfile=None):

    logging.config.fileConfig("logging.conf")
    log = logging.getLogger(__name__)

    app = Flask(__name__)
    CO2MPAS_VERSION = "3"

    @app.route("/")
    def index():
        return render_template(
            "layout.html",
            action="dashboard",
            data={
                "breadcrumb": ["Co2mpas"],
                "props": {"active": {"run": "", "doc": "", "expert": ""}},
            },
        )

    @app.route("/run/download-template-form")
    def download_template_form():
        return render_template(
            "layout.html",
            action="template_download_form",
            data={
                "breadcrumb": ["Co2mpas", "Download template"],
                "props": {"active": {"run": "active", "doc": "", "expert": ""}},
            },
        )

    @app.route("/run/download-template")
    def download_template():

        # Temp file name
        of = next(tempfile._get_candidate_names())

        # Input parameters
        inputs = {"output_file": of, "template_type": "input"}

        # Dispatcher
        d = dsp.register()
        ret = d.dispatch(inputs, ["template", "done"])

        # Read from file
        data = None
        with open(of, "rb") as xlsx:
            data = xlsx.read()

        # Delete files
        os.remove(of)

        # Output xls file
        iofile = io.BytesIO(data)
        iofile.seek(0)
        return send_file(
            iofile,
            attachment_filename="co2mpas-input-template.xlsx",
            as_attachment=True,
        )

    @app.route("/run/simulation-form")
    def simulation_form():
        inputs = [f for f in listdir("input") if isfile(join("input", f))]
        return render_template(
            "layout.html",
            action="simulation_form",
            data={
                "breadcrumb": ["Co2mpas", "Run simulation"],
                "props": {"active": {"run": "active", "doc": "", "expert": ""}},
                "inputs": inputs,
            },
        )

    def run_process():

        thread = threading.current_thread()
        files = ["input/" + f for f in listdir("input") if isfile(join("input", f))]

        # Input parameters
        kwargs = {
            "output_folder": "output",
            "only_summary": False,
            "hard_validation": False,
            "declaration_mode": False,
            "enable_selector": False,
            "type_approval_mode": False,
        }
        inputs = dict(
            plot_workflow=False,
            host="127.0.0.1",
            port=4999,
            cmd_flags=kwargs,
            input_files=files,
        )

        # Dispatcher
        d = dsp.register()
        ret = d.dispatch(inputs, ["done", "run"])
        return ""

    # Run
    @app.route("/run/simulation")
    def simulation_run():

        thread = threading.Thread(target=run_process, args=())
        thread.daemon = False
        thread.start()
        id = thread.ident
        return redirect("/run/progress?id=" + str(thread.ident), code=302)

    @app.route("/run/progress")
    def simulation_progress():

        done = True
        thread_id = request.args.get("id")
        for thread in threading.enumerate():
            if (thread.ident == int(thread_id)) and thread.is_alive():
                done = False

        page = "run_complete" if done else "run_progress"
        title = "Simulation complete" if done else "Simulation in progress..."
        return render_template(
            "layout.html",
            action=page,
            data={
                "breadcrumb": ["Co2mpas", title],
                "props": {"active": {"run": "active", "doc": "", "expert": ""}},
            },
        )

    @app.route("/run/add-file", methods=["POST"])
    def add_file():
        f = request.files["file"]
        f.save("input/" + secure_filename(f.filename))
        files = {"file": f.read()}
        return redirect("/run/simulation-form", code=302)

    @app.route("/run/delete-file", methods=["GET"])
    def delete_file():
        fn = request.args.get("fn")
        inputs = [f for f in listdir("input") if isfile(join("input", f))]
        os.remove("input/" + inputs[int(fn) - 1])
        return redirect("/run/simulation-form", code=302)

    @app.route("/run/view-results")
    def view_results():
        return render_template(
            "layout.html",
            action="view_results",
            data={
                "breadcrumb": ["Co2mpas", "View results"],
                "props": {"active": {"run": "active", "doc": "", "expert": ""}},
            },
        )

    return app


@click.group(cls=FlaskGroup, create_app=create_app)
def cli():
    """Management script for the Wiki application."""


if __name__ == "__main__":
    create_app().run(debug=True)
