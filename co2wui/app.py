import re
import glob
from stat import S_ISREG, S_ISDIR, ST_CTIME, ST_MODE
from os import path
import webbrowser
import threading
import tempfile
import schedula as sh
import co2mpas_dice
from co2mpas import dsp as dsp
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
import time
import os.path as osp
from werkzeug import secure_filename
import logging
import logging.config


def listdir_inputs(path):
    """Only allow for excel files as input 
    """
    return map(lambda x: os.path.basename(x), glob.glob(os.path.join(path, "*.xls*")))


def listdir_outputs(path):
    """Only allow for excel files as output 
    """
    return map(lambda x: os.path.basename(x), glob.glob(os.path.join(path, "*.xls*")))


def create_app(configfile=None):

    log_file_path = path.join(path.dirname(path.abspath(__file__)), "../logging.conf")
    logging.config.fileConfig(log_file_path)
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
        inputs = [f for f in listdir_inputs("input") if isfile(join("input", f))]
        return render_template(
            "layout.html",
            action="simulation_form",
            data={
                "breadcrumb": ["Co2mpas", "Run simulation"],
                "props": {"active": {"run": "active", "doc": "", "expert": ""}},
                "inputs": inputs,
            },
        )

    def run_process(args):

        thread = threading.current_thread()
        files = [
            "input/" + f for f in listdir_inputs("input") if isfile(join("input", f))
        ]

        # Create output directory for this execution
        output_folder = "output/" + str(thread.ident)
        os.makedirs(output_folder or ".", exist_ok=True)

        # Dedicated logging for this run
        fileh = logging.FileHandler(
            "output/" + str(thread.ident) + "/" + "logfile.txt", "a"
        )
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fileh.setFormatter(formatter)
        log = logging.getLogger()
        log.setLevel(logging.DEBUG)
        for hdlr in log.handlers[:]:
            log.removeHandler(hdlr)
        log.addHandler(fileh)

        # Input parameters
        kwargs = {
            "output_folder": output_folder,
            "only_summary": bool(args.get("only_summary")),
            "hard_validation": bool(args.get("hard_validation")),
            "declaration_mode": bool(args.get("declaration_mode")),
            "encryption_keys": "",
            "sign_key": "",
            "encryption_keys_passwords": "",
            "enable_selector": False,
            "type_approval_mode": bool(args.get("tamode")),
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
        f = open("output/" + str(thread.ident) + "/result.dat", "w+")
        f.write(str(ret))
        return ""

    # Run
    @app.route("/run/simulation")
    def run_simulation():

        thread = threading.Thread(target=run_process, args=(request.args,))
        thread.daemon = False
        thread.start()
        id = thread.ident
        return redirect("/run/progress?layout=layout&id=" + str(thread.ident), code=302)

    @app.route("/run/progress")
    def run_progress():

        done = True

        thread_id = request.args.get("id")
        layout = request.args.get("layout")

        for thread in threading.enumerate():
            if (thread.ident == int(thread_id)) and thread.is_alive():
                done = False

        page = "run_complete" if done else "run_progress"
        title = "Simulation complete" if done else "Simulation in progress..."

        log = ""
        loglines = []
        with open("output/" + thread_id + "/" + "logfile.txt") as f:
            loglines = f.readlines()

        for logline in reversed(loglines):
            if not re.search("- INFO -", logline):
                log += logline

        return render_template(
            "layout.html" if layout == "layout" else "ajax.html",
            action=page,
            data={
                "breadcrumb": ["Co2mpas", title],
                "props": {"active": {"run": "active", "doc": "", "expert": ""}},
                "thread_id": thread_id,
                "log": log,
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
        inputs = [f for f in listdir_inputs("input") if isfile(join("input", f))]
        os.remove("input/" + inputs[int(fn) - 1])
        return redirect("/run/simulation-form", code=302)

    @app.route("/run/view-results")
    def view_results():

        dirpath = r"output"
        entries = (os.path.join(dirpath, fn) for fn in os.listdir(dirpath))
        entries = ((os.stat(path), path) for path in entries)
        entries = (
            (stat[ST_CTIME], path) for stat, path in entries if S_ISDIR(stat[ST_MODE])
        )

        results = []
        for cdate, path in sorted(entries):
            dirname = os.path.basename(path)
            output_files = [
                f
                for f in listdir_outputs("output/" + dirname)
                if isfile(join("output/" + dirname, f))
            ]
            results.append(
                {"datetime": time.ctime(cdate), "name": dirname, "files": output_files}
            )

        return render_template(
            "layout.html",
            action="view_results",
            data={
                "breadcrumb": ["Co2mpas", "View results"],
                "props": {"active": {"run": "active", "doc": "", "expert": ""}},
                "results": reversed(results),
            },
        )

    @app.route("/run/download-result/<runid>/<fnum>")
    def download_result(runid, fnum):

        files = list(listdir_outputs("output/" + runid))
        rf = "output/" + runid + "/" + files[int(fnum) - 1]

        # Read from file
        data = None
        with open(rf, "rb") as xlsx:
            data = xlsx.read()

        # Output xls file
        iofile = io.BytesIO(data)
        iofile.seek(0)
        return send_file(
            iofile, attachment_filename=files[int(fnum) - 1], as_attachment=True
        )

    @app.route("/run/download-log/<runid>")
    def download_log(runid):

        rf = "output/" + runid + "/logfile.txt"

        # Read from file
        data = None
        with open(rf, "rb") as xlsx:
            data = xlsx.read()

        # Output xls file
        iofile = io.BytesIO(data)
        iofile.seek(0)
        return send_file(iofile, attachment_filename="logfile.txt", as_attachment=True)

    @app.route("/not-implemented")
    def not_implemented():
        return render_template(
            "layout.html",
            action="generic_message",
            data={
                "breadcrumb": ["Co2mpas", "Feature not implemented"],
                "props": {"active": {"run": "", "doc": "", "expert": ""}},
                "title": "Feature not implemented",
                "message": "Please refer to future versions of the application or contact xxxxxxx@xxxxxx.europa.eu for information.",
            },
        )

    return app


@click.group(cls=FlaskGroup, create_app=create_app)
def cli():
    """Management script for the Wiki application."""
    # FIXME: read port from cli/configs
    # TODO: option for the user to skip opening browser
    webbrowser.open("http:localhost:5000")


if __name__ == "__main__":
    create_app().run(debug=True)
