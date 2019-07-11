import re
import glob
from stat import S_ISREG, S_ISDIR, ST_CTIME, ST_MODE
import webbrowser
import threading
import tempfile
import logging
import logging.config
import time
import io
import os
from os import path
from os import listdir
from os import path as osp
from stat import S_ISDIR, S_ISREG, ST_CTIME, ST_MODE

import click
import requests
import schedula as sh
import syncing
import gettext
import pickle
import zipfile
import shutil
from babel import Locale
from babel.support import Translations
from co2mpas import __version__, dsp
from flask import (
    Flask,
    Response,
    current_app,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask.cli import FlaskGroup
from flask_babel import Babel
from jinja2 import Environment, PackageLoader
from ruamel import yaml
from werkzeug.utils import secure_filename

_ = gettext.gettext

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)


def listdir_inputs(path):
    """Only allow for excel files as input
    """
    return map(lambda x: os.path.basename(x), glob.glob(osp.join(path, "*.xls*")))


def listdir_outputs(path):
    """Only allow for excel files as output
    """
    return map(
        lambda x: os.path.basename(x),
        glob.glob(osp.join(path, "*.xls*")) + glob.glob(osp.join(path, "*.zip*")),
    )


def listdir_conf(path):
    """Only allow for conf.yaml files
    """
    return map(lambda x: os.path.basename(x), glob.glob(osp.join(path, "conf.yaml")))


def listdir_enc_keys(path):
    """Only allow for conf.yaml files
    """
    return map(
        lambda x: os.path.basename(x), glob.glob(osp.join(path, "dice.co2mpas.keys"))
    )


def listdir_key_pass(path):
    """Only allow for conf.yaml files
    """
    return map(
        lambda x: os.path.basename(x), glob.glob(osp.join(path, "secret.passwords"))
    )


def listdir_key_sign(path):
    """Only allow for conf.yaml files
    """
    return map(
        lambda x: os.path.basename(x), glob.glob(osp.join(path, "sign.co2mpas.key"))
    )


def get_summary(runid):
    """Read a summary saved file and returns it as a dict
    """
    summary = None
    if os.path.exists(osp.join("output", runid, "result.dat")):

        with open(osp.join("output", runid, "result.dat"), "rb") as summary_file:
            try:
                summary = pickle.load(summary_file)
            except:
                return None

    return summary


def humanised(summary):

    formatted = {"params": {}}
    for k in summary.keys():
        if k not in ("base", "id"):
            try:
                formatted["params"][k[3]][".".join(k)] = (
                    round(summary[k], 3)
                    if isinstance(summary[k], float)
                    else summary[k]
                )
            except:
                formatted["params"][k[3]] = {}

    return formatted


def ta_enabled():
    """Return true if all conditions for TA mode are met
    """
    if not os.path.exists("keys/dice.co2mpas.keys"):
        return False

    if not os.path.exists("keys/sign.co2mpas.key"):
        return False

    return True


def create_app(configfile=None):

    app = Flask(__name__)
    babel = Babel(app)
    CO2MPAS_VERSION = "3"

    app.jinja_env.globals.update(humanised=humanised)

    with open("locale/texts-en.yaml", "r") as stream:
        co2wui_texts = yaml.safe_load(stream)

    @app.route("/")
    def index():

        nohints = False
        if "nohints" in request.cookies:
            nohints = True
        return render_template(
            "layout.html",
            action="dashboard",
            data={
                "breadcrumb": ["Co2mpas"],
                "props": {"active": {"run": "", "sync": "", "doc": "", "expert": ""}},
                "nohints": nohints,
                "texts": co2wui_texts,
            },
        )

    @app.route("/run/download-template-form")
    def download_template_form():
        return render_template(
            "layout.html",
            action="template_download_form",
            data={
                "breadcrumb": ["Co2mpas", _("Download template")],
                "props": {
                    "active": {"run": "active", "sync": "", "doc": "", "expert": ""}
                },
                "texts": co2wui_texts,
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
        inputs = [
            f for f in listdir_inputs("input") if osp.isfile(osp.join("input", f))
        ]
        return render_template(
            "layout.html",
            action="simulation_form",
            data={
                "breadcrumb": ["Co2mpas", _("Run simulation")],
                "props": {
                    "active": {"run": "active", "sync": "", "doc": "", "expert": ""}
                },
                "inputs": inputs,
                "ta_enabled": ta_enabled(),
                "texts": co2wui_texts,
            },
        )

    def run_process(args):

        thread = threading.current_thread()
        files = [
            osp.join("input", f)
            for f in listdir_inputs("input")
            if osp.isfile(osp.join("input", f))
        ]

        # Create output directory for this execution
        output_folder = osp.join("output", str(thread.ident))
        os.makedirs(output_folder or ".", exist_ok=True)

        # Dedicated logging for this run
        fileh = logging.FileHandler(
            osp.join("output", str(thread.ident), "logfile.txt"), "a"
        )
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        frmt = "%(asctime)-15s:%(levelname)5.5s:%(name)s:%(message)s"
        logging.basicConfig(level=logging.INFO, format=frmt)
        logger.addHandler(fileh)

        # Input parameters
        kwargs = {
            "output_folder": output_folder,
            "only_summary": bool(args.get("only_summary")),
            "hard_validation": bool(args.get("hard_validation")),
            "declaration_mode": bool(args.get("declaration_mode")),
            "encryption_keys": "keys/dice.co2mpas.keys"
            if os.path.exists("keys/dice.co2mpas.keys")
            else "",
            "sign_key": "keys/sign.co2mpas.key"
            if os.path.exists("keys/sign.co2mpas.key")
            else "",
            "encryption_keys_passwords": "",
            "enable_selector": False,
            "type_approval_mode": bool(args.get("tamode")),
        }

        with open(
            osp.join("output", str(thread.ident), "header.dat"), "wb"
        ) as header_file:
            pickle.dump(kwargs, header_file)

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
        with open(
            osp.join("output", str(thread.ident), "result.dat"), "wb"
        ) as summary_file:
            pickle.dump(ret["summary"], summary_file)
        return ""

    @app.route("/run/view-summary/<runid>")
    def view_summary(runid):
        """Show a modal dialog with a execution's summary formatted in a table
        """

        # Read the header containing run information
        header = {}
        with open(osp.join("output", runid, "header.dat"), "rb") as header_file:
            try:
                header = pickle.load(header_file)
            except:
                return None

        summaries = get_summary(runid)

        if summaries is not None:
            return render_template(
                "ajax.html",
                action="summary",
                title=_("Summary of your Co2mpas execution"),
                data={"thread_id": runid, "summaries": summaries, "header": header},
            )
        else:
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

        done = False

        thread_id = request.args.get("id")
        layout = request.args.get("layout")

        # Done if there's a result file
        if os.path.exists(osp.join("output", thread_id, "result.dat")):
            done = True

        # See if done or still running
        page = "run_complete" if done else "run_progress"
        title = _("Simulation complete") if done else _("Simulation in progress...")

        # Read the header containing run information
        header = {}
        with open(osp.join("output", thread_id, "header.dat"), "rb") as header_file:
            try:
                header = pickle.load(header_file)
            except:
                return None

        # Get the summary of the execution (if ready)
        summary = get_summary(thread_id)
        result = "KO" if (summary is None or len(summary[0].keys()) <= 2) else "OK"

        # Get the log ile
        log = ""
        loglines = []
        with open(osp.join("output", thread_id, "logfile.txt")) as f:
            loglines = f.readlines()

        for logline in reversed(loglines):
            if not re.search("- INFO -", logline):
                log += logline

        # Collect result files
        results = []
        if not (summary is None or len(summary[0].keys()) <= 2):
            output_files = [
                f
                for f in listdir_outputs(os.path.join("output", thread_id))
                if osp.isfile(os.path.join("output", thread_id, f))
            ]
            results.append({"name": thread_id, "files": output_files})

        # Render page progress/complete
        return render_template(
            "layout.html" if layout == "layout" else "ajax.html",
            action=page,
            data={
                "breadcrumb": ["Co2mpas", title],
                "props": {
                    "active": {"run": "active", "sync": "", "doc": "", "expert": ""}
                },
                "thread_id": thread_id,
                "log": log,
                "result": result,
                "summary": summary[0] if summary is not None else None,
                "results": results if results is not None else None,
                "header": header,
            },
        )

    @app.route("/run/add-file", methods=["POST"])
    def add_file():
        f = request.files["file"]
        f.save(osp.join("input", secure_filename(f.filename)))
        files = {"file": f.read()}
        return redirect("/run/simulation-form", code=302)

    @app.route("/run/delete-file", methods=["GET"])
    def delete_file():
        fn = request.args.get("fn")
        inputs = [
            f for f in listdir_inputs("input") if osp.isfile(osp.join("input", f))
        ]
        os.remove(osp.join("input", inputs[int(fn) - 1]))
        return redirect("/run/simulation-form", code=302)

    @app.route("/run/view-results")
    def view_results():

        dirpath = r"output"
        entries = (osp.join(dirpath, fn) for fn in os.listdir(dirpath))
        entries = ((os.stat(path), path) for path in entries)
        entries = (
            (stat[ST_CTIME], path) for stat, path in entries if S_ISDIR(stat[ST_MODE])
        )

        results = []
        for cdate, path in sorted(entries):
            dirname = os.path.basename(path)
            output_files = [
                f
                for f in listdir_outputs(osp.join("output", dirname))
                if osp.isfile(osp.join("output", dirname, f))
            ]
            summary = get_summary(dirname)
            outcome = "KO" if (summary is None or len(summary[0].keys()) <= 2) else "OK"
            results.append(
                {
                    "datetime": time.ctime(cdate),
                    "name": dirname,
                    "files": output_files,
                    "outcome": outcome,
                }
            )

        return render_template(
            "layout.html",
            action="view_results",
            data={
                "breadcrumb": ["Co2mpas", _("View results")],
                "props": {
                    "active": {"run": "active", "sync": "", "doc": "", "expert": ""}
                },
                "results": reversed(results),
                "texts": co2wui_texts,
            },
        )

    @app.route("/run/download-result/<runid>/<fnum>")
    def download_result(runid, fnum):

        files = list(listdir_outputs(osp.join("output", runid)))
        rf = osp.join("output", runid, files[int(fnum) - 1])

        # Read from file
        data = None
        with open(rf, "rb") as result:
            data = result.read()

        # Output xls file
        iofile = io.BytesIO(data)
        iofile.seek(0)
        return send_file(
            iofile, attachment_filename=files[int(fnum) - 1], as_attachment=True
        )

    @app.route("/run/delete-results", methods=["POST"])
    def delete_results():

        for k in request.form.keys():
            if re.match(r"select-[0-9]+", k):
                runid = k.rpartition("-")[2]
                shutil.rmtree(osp.join("output", runid))

        return redirect("/run/view-results", code=302)

    @app.route("/run/download-log/<runid>")
    def download_log(runid):

        rf = osp.join("output", runid, "logfile.txt")

        # Read from file
        data = None
        with open(rf, "rb") as xlsx:
            data = xlsx.read()

        # Output xls file
        iofile = io.BytesIO(data)
        iofile.seek(0)
        return send_file(iofile, attachment_filename="logfile.txt", as_attachment=True)

    @app.route("/sync/template-form")
    def sync_template_form():
        return render_template(
            "layout.html",
            action="synchronisation_template_form",
            data={
                "breadcrumb": ["Co2mpas", _("Data synchronisation")],
                "props": {
                    "active": {"run": "", "sync": "active", "doc": "", "expert": ""}
                },
                "title": "Data synchronisation",
            },
        )

    @app.route("/sync/template-download")
    def sync_template_download():

        # Parameters from request
        cycle_type = request.args.get("cycle")
        gear_box_type = request.args.get("gearbox")
        wltp_class = request.args.get("wltpclass")

        # Output temp file
        output_file = next(tempfile._get_candidate_names()) + ".xlsx"

        # Generate template
        import pandas as pd
        from co2mpas.core.model.physical import dsp

        theoretical = sh.selector(
            ["times", "velocities"],
            dsp(
                inputs=dict(
                    cycle_type=cycle_type.upper(),
                    gear_box_type=gear_box_type,
                    wltp_class=wltp_class,
                    downscale_factor=0,
                ),
                outputs=["times", "velocities"],
                shrink=True,
            ),
        )
        base = dict.fromkeys(
            (
                "times",
                "velocities",
                "target gears",
                "engine_speeds_out",
                "engine_coolant_temperatures",
                "co2_normalization_references",
                "alternator_currents",
                "battery_currents",
                "target fuel_consumptions",
                "target co2_emissions",
                "target engine_powers_out",
            ),
            [],
        )
        data = dict(theoretical=theoretical, dyno=base, obd=base)

        with pd.ExcelWriter(output_file) as writer:
            for k, v in data.items():
                pd.DataFrame(v).to_excel(writer, k, index=False)

        # Read from generated file
        data = None
        with open(output_file, "rb") as xlsx:
            data = xlsx.read()

        # Delete files
        os.remove(output_file)

        # Output xls file
        iofile = io.BytesIO(data)
        iofile.seek(0)
        return send_file(
            iofile, attachment_filename="datasync.xlsx", as_attachment=True
        )

    @app.route("/sync/synchronisation-form")
    def synchronisation_form():
        inputs = [
            f
            for f in listdir_inputs("sync/input")
            if osp.isfile(osp.join("sync/input", f))
        ]
        return render_template(
            "layout.html",
            action="synchronisation_form",
            data={
                "breadcrumb": ["Co2mpas", _("Run synchronisation")],
                "props": {
                    "active": {"run": "", "sync": "active", "doc": "", "expert": ""}
                },
                "interpolation_methods": [
                    "linear",
                    "nearest",
                    "zero",
                    "slinear",
                    "quadratic",
                    "cubic",
                    "pchip",
                    "akima",
                    "integral",
                    "polynomial0",
                    "polynomial1",
                    "polynomial2",
                    "polynomial3",
                    "polynomial4",
                    "spline5",
                    "spline7",
                    "spline9",
                ],
                "inputs": inputs,
                "texts": co2wui_texts,
            },
        )

    @app.route("/sync/add-sync-file", methods=["POST"])
    def add_sync_file():
        inputs = [f for f in listdir_inputs("sync") if osp.isfile(osp.join("sync", f))]

        for file in inputs:
            os.remove(osp.join("sync/input", file))

        f = request.files["file"]
        f.save(osp.join("sync/input", secure_filename(f.filename)))
        files = {"file": f.read()}
        return redirect("/sync/synchronisation-form", code=302)

    @app.route("/sync/run-synchronisation", methods=["POST"])
    def run_synchronisation():

        # Dedicated logging for this run
        fileh = logging.FileHandler("sync/logfile.txt", "w")
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        frmt = "%(asctime)-15s:%(levelname)5.5s:%(name)s:%(message)s"
        logging.basicConfig(level=logging.INFO, format=frmt)
        logger.addHandler(fileh)

        # Input and output files
        inputs = [
            f
            for f in listdir_inputs("sync/input")
            if osp.isfile(osp.join("sync/input", f))
        ]
        input_file = osp.join("sync", "input", inputs[0])
        output_file = osp.join("sync", "output", "datasync.sync.xlsx")

        # Arguments
        kwargs = {
            "x_label": request.form.get("x_label")
            if request.form.get("x_label")
            else "times",
            "y_label": request.form.get("y_label")
            if request.form.get("y_label")
            else "velocities",
            "interpolation_method": request.form.get("interpolation_method"),
            "header": request.form.get("header"),
            "reference_name": request.form.get("reference_name")
            if request.form.get("reference_name")
            else "theoretical",
        }
        kwargs = {k: v for k, v in kwargs.items() if v}

        try:

            # Dispatcher
            _process = sh.SubDispatch(syncing.dsp, ["written"], output_type="value")
            ret = _process(
                dict(input_fpath=input_file, output_fpath=output_file, **kwargs)
            )
            fileh.close()
            logger.removeHandler(fileh)
            return "OK"

        except Exception as e:
            logger.error(_("Synchronisation failed: ") + str(e))
            fileh.close()
            logger.removeHandler(fileh)
            return "KO"

    @app.route("/sync/delete-file", methods=["GET"])
    def delete_sync_file():
        inputs = [
            f
            for f in listdir_inputs("sync/input")
            if osp.isfile(osp.join("sync/input", f))
        ]

        for file in inputs:
            os.remove(osp.join("sync/input", file))

        return redirect("/sync/synchronisation-form", code=302)

    @app.route("/sync/load-log", methods=["GET"])
    def load_sync_log():
        log = ""
        loglines = []
        with open("sync/logfile.txt") as f:
            loglines = f.readlines()

        for logline in loglines:
            log += logline

        return log

    @app.route("/sync/download-result")
    def sync_download_result():

        resfile = "sync/output/datasync.sync.xlsx"

        # Read from file
        data = None
        with open(resfile, "rb") as xlsx:
            data = xlsx.read()

        # Output xls file
        iofile = io.BytesIO(data)
        iofile.seek(0)
        return send_file(
            iofile, attachment_filename="datasync.sync.xlsx", as_attachment=True
        )

    # Demo/download
    @app.route("/demo/download")
    def demo_download():

        # Temporary output folder
        of = next(tempfile._get_candidate_names())

        # Input parameters
        inputs = {"output_folder": of}

        # Dispatcher
        d = dsp.register()
        ret = d.dispatch(inputs, ["demo", "done"])

        # List of demo files created
        demofiles = [f for f in listdir(of) if osp.isfile(osp.join(of, f))]

        # Create zip archive on the fly
        zip_subdir = of
        iofile = io.BytesIO()
        zf = zipfile.ZipFile(iofile, mode="w", compression=zipfile.ZIP_DEFLATED)

        # Adds demo files to archive
        for f in demofiles:
            # Add file, at correct path
            zf.write(os.path.abspath(osp.join(of, f)), f)

        # Close archive
        zf.close()

        # Remove temporary files
        shutil.rmtree(of)

        # Output zip file
        iofile.seek(0)
        return send_file(
            iofile, attachment_filename="co2mpas-demo.zip", as_attachment=True
        )

    @app.route("/plot/launched")
    def plot_launched():
        return render_template(
            "content.html",
            action="launch_plot",
            data={
                "breadcrumb": ["Co2mpas", "Plot launched"],
                "props": {
                    "active": {"run": "", "sync": "", "doc": "", "expert": "active"}
                },
                "title": "Plot launched",
            },
        )

    @app.route("/plot/model-graph")
    def plot_model_graph():
        dsp(
            dict(plot_model=True, cache_folder="cache", host="127.0.0.1", port=4999),
            ["plot", "done"],
        )
        return ""

    @app.route("/conf/configuration-form")
    def configuration_form():
        files = [f for f in listdir_conf(".") if osp.isfile(osp.join(".", f))]
        return render_template(
            "layout.html",
            action="configuration_form",
            data={
                "breadcrumb": ["Co2mpas", _("Configuration file")],
                "props": {
                    "active": {
                        "run": "",
                        "sync": "active",
                        "doc": "",
                        "expert": "active",
                    }
                },
                "title": "Configuration form",
                "inputs": files,
                "texts": co2wui_texts,
            },
        )

    @app.route("/conf/add-conf-file", methods=["POST"])
    def add_conf_file():
        if os.path.exists("conf.yaml"):
            os.remove("conf.yaml")

        f = request.files["file"]
        f.save("conf.yaml")
        return redirect("/conf/configuration-form", code=302)

    @app.route("/conf/delete-file", methods=["GET"])
    def delete_conf_file():
        os.remove("conf.yaml")
        return redirect("/conf/configuration-form", code=302)

    @app.route("/keys/keys-form")
    def keys_form():

        enc_keys = [
            f for f in listdir_enc_keys("keys") if osp.isfile(osp.join("keys", f))
        ]
        key_pass = [
            f for f in listdir_key_pass("keys") if osp.isfile(osp.join("keys", f))
        ]
        key_sign = [
            f for f in listdir_key_sign("keys") if osp.isfile(osp.join("keys", f))
        ]

        return render_template(
            "layout.html",
            action="keys_form",
            data={
                "breadcrumb": ["Co2mpas", _("Load keys")],
                "props": {
                    "active": {"run": "", "sync": "", "doc": "", "expert": "active"}
                },
                "enc_keys": enc_keys,
                "key_pass": key_pass,
                "key_sign": key_sign,
                "texts": co2wui_texts,
            },
        )

    @app.route("/keys/add-key-file", methods=["POST"])
    def add_key_file():

        upload_type = request.form.get("upload_type")
        filenames = {
            "enc_keys": "dice.co2mpas.keys",
            "key_pass": "secret.passwords",
            "key_sign": "sign.co2mpas.key",
        }

        filename = filenames.get(upload_type)
        if os.path.exists(filename):
            os.remove(filename)

        f = request.files["file"]
        f.save(osp.join("keys", filename))
        return redirect("/keys/keys-form", code=302)

    @app.route("/keys/delete-file", methods=["GET"])
    def delete_key_file():

        upload_type = request.args.get("upload_type")
        filenames = {
            "enc_keys": "dice.co2mpas.keys",
            "key_pass": "secret.passwords",
            "key_sign": "sign.co2mpas.key",
        }
        filename = filenames.get(upload_type)

        os.remove(osp.join("keys", filename))
        return redirect("/keys/keys-form", code=302)

    @app.route("/not-implemented")
    def not_implemented():
        return render_template(
            "layout.html",
            action="generic_message",
            data={
                "breadcrumb": ["Co2mpas", _("Feature not implemented")],
                "props": {"active": {"run": "", "sync": "", "doc": "", "expert": ""}},
                "title": "Feature not implemented",
                "message": "Please refer to future versions of the application or contact xxxxxxx@xxxxxx.europa.eu for information.",
            },
        )

    @app.route("/conf/generate")
    def conf_generate():

        # Conf file name
        of = "conf.yaml"

        # Input parameters
        inputs = {"output_file": of}

        # Dispatcher
        d = dsp.register()
        ret = d.dispatch(inputs, ["conf", "done"])

        return redirect("/conf/configuration-form", code=302)

    # Demo/download
    @app.route("/conf/download")
    def conf_download():

        # Conf file name
        of = "conf.yaml"

        # Read from file
        data = None
        with open(of, "rb") as conf_yaml:
            data = conf_yaml.read()

        # Output xls file
        iofile = io.BytesIO(data)
        iofile.seek(0)
        return send_file(iofile, attachment_filename="conf.yaml", as_attachment=True)

    @app.route("/contact-us")
    def contact_us():
        return render_template(
            "layout.html",
            action="contact_us",
            data={
                "breadcrumb": ["Co2mpas", "Contact us"],
                "props": {
                    "active": {"run": "", "sync": "", "doc": "active", "expert": ""}
                },
                "title": "Contact us",
                "texts": co2wui_texts,
            },
        )

    return app


@click.group(cls=FlaskGroup, create_app=create_app)
def cli():
    """Management script for the Co2gui application."""
    # FIXME: read port from cli/configs
    # TODO: option for the user to skip opening browser
    webbrowser.open("http:localhost:5000")


if __name__ == "__main__":
    create_app().run(debug=True)
