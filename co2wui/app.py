import itertools
import functools
import re
from stat import S_ISREG, S_ISDIR, ST_CTIME, ST_MODE
import webbrowser
import multiprocessing
import tempfile
import logging
import logging.config
import time
import io
import os
from importlib import resources
from os import path as osp
from pathlib import Path
from stat import S_ISDIR, S_ISREG, ST_CTIME, ST_MODE
from typing import Union, List

import click
import requests
import schedula as sh
import syncing
import gettext
import pickle
import random
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
    session,
    url_for,
)
from flask_session import Session
from flask.cli import FlaskGroup
from flask_babel import Babel
from jinja2 import Environment, PackageLoader
from ruamel import yaml
from werkzeug.utils import secure_filename

_ = gettext.gettext

log = logging.getLogger("werkzeug")
log.setLevel(logging.ERROR)

# The various steps of the progress bar
progress_bar = {
  'open_input_file': 10,
  'parse_excel_file': 13,
  'output.precondition.wltp_p': 15,
  'output.calibration.wltp_h': 30,
  'output.calibration.wltp_l': 50,
  'output.prediction.nedc_h': 60,
  'output.prediction.nedc_l': 75,
  'output.prediction.wltp_h': 85,
  'output.prediction.wltp_l': 90,
  'format_report_output_data': 95,
  'write_to_excel': 99
}

def ensure_working_folders():
    for p in (
        ("keys",),
        ("input",),
        ("output",),
        ("sync", "input"),
        ("sync", "output"),
    ):
        co2wui_fpath(*p).mkdir(parents=True, exist_ok=True)


def _listdir_io(*path: Union[Path, str], patterns=("*",)) -> List[Path]:
    """Only allow for excel files as input """
    folder = co2wui_fpath(*path)
    files = itertools.chain.from_iterable(folder.glob(pat) for pat in patterns)
    return [f for f in files if f.is_file()]


def listdir_inputs(
    *path: Union[Path, str], patterns=("*.[xX][lL][sS]*",)
) -> List[Path]:
    """Only allow for excel files as input """
    return _listdir_io(*path, patterns=patterns)


def input_fpath(*path: Union[Path, str]) -> Path:
    return co2wui_fpath(*path)


def listdir_outputs(
    *path: Union[Path, str], patterns=("*.[xX][lL][sS]*", "*.[zZ][iI][pP]")
) -> List[Path]:
    """Only allow for excel files as output """
    return _listdir_io(*path, patterns=patterns)


def output_fpath(*path: Union[Path, str]) -> Path:
    return co2wui_fpath(*path)


def _home_fpath() -> Path:

    if "CO2WUI_HOME" in os.environ:
        home = Path(os.environ["CO2WUI_HOME"])
    else:
        home = Path.home() / ".co2wui"
    return home

def co2wui_fpath(*path: Union[Path, str]) -> Path:
    return Path(_home_fpath(), *path)

@functools.lru_cache()
def conf_fpath() -> Path:
    return _home_fpath() / "conf.yaml"


@functools.lru_cache()
def enc_keys_fpath() -> Path:
    return co2wui_fpath("keys") / "dice.co2mpas.keys"


@functools.lru_cache()
def key_pass_fpath() -> Path:
    return co2wui_fpath("keys") / "secret.passwords"


@functools.lru_cache()
def key_sign_fpath() -> Path:
    return co2wui_fpath("keys") / "sign.co2mpas.key"


def get_summary(runid):
    """Read a summary saved file and returns it as a dict
    """
    summary = None
    if osp.exists(co2wui_fpath("output", runid, "result.dat")):

        with open(co2wui_fpath("output", runid, "result.dat"), "rb") as summary_file:
            try:
                summary = pickle.load(summary_file)
            except:
                return None

    return summary


def humanised(summary):
    """Return a more readable format of the summary data structure"""

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
    """Return true if all conditions for TA mode are met """
    return enc_keys_fpath().exists() and key_sign_fpath().exists()


def colorize(str):
    str += '<br/>'
    str = str.replace(": done", ': <span style="color: green; font-weight: bold;">done</span>')
    str = re.sub(r"(CO2MPAS output written into) \((.+?)\)", r"\1 (<b>\2</b>)", str)
    return str

# Multi process related functions
def log_phases(dsp):
    """Create a callback in order to log the main phases of the Co2mpas simulation"""

    def createLambda(ph, *args):
      dsp.get_node('CO2MPAS model', node_attr=None)[0]['logger'].info(ph + ": done")

    co2mpas_model = dsp.get_node('CO2MPAS model')[0]
    for k, v in co2mpas_model.dsp.data_nodes.items():
      if k.startswith('output.'):
          v['callback'] = functools.partial(createLambda,k)

    additional_phase = dsp.get_node('load_inputs', 'open_input_file', node_attr=None)[0]
    additional_phase['callback'] = lambda x: additional_phase['logger'].info('open_input_file: done')

    additional_phase = dsp.get_node('load_inputs', 'parse_excel_file', node_attr=None)[0]
    additional_phase['callback'] = lambda x: additional_phase['logger'].info('parse_excel_file: done')

    additional_phase = dsp.get_node('make_report', 'format_report_output_data', node_attr=None)[0]
    additional_phase['callback'] = lambda x: additional_phase['logger'].info('format_report_output_data: done')

    additional_phase = dsp.get_node('write', 'write_to_excel', node_attr=None)[0]
    additional_phase['callback'] = lambda x: additional_phase['logger'].info('write_to_excel: done')

    return dsp

def register_logger(kw):
    """Record the simulation logger into the dispatcher"""

    d, logger = kw['register_core'], kw['pass_logger']

    # Logger for CO2MPAS model
    n = d.get_node('CO2MPAS model', node_attr=None)[0]
    n['logger'] = logger

    for model, phase in [
      ['load_inputs', 'open_input_file'],
      ['load_inputs', 'parse_excel_file'],
      ['make_report', 'format_report_output_data'],
      ['write', 'write_to_excel']
    ]:

      # Logger for open_input_file
      n = d.get_node(model, phase, node_attr=None)[0]
      n['logger'] = logger

    return d

def run_process(args):
    """Run the simulation process in a thread"""

    # Pick current thread
    process = multiprocessing.current_process()

    # Create output directory for this execution
    output_folder = co2wui_fpath("output", str(process.pid))
    os.makedirs(output_folder or ".", exist_ok=True)

    # File list
    files = listdir_inputs("input")
    with open(
        co2wui_fpath("output", str(process.pid), "files.dat"), "wb"
    ) as files_list:
        pickle.dump(files, files_list)

    # Dedicated logging for this run
    fileh = logging.FileHandler(
        co2wui_fpath("output", str(process.pid), "logfile.txt"), "a"
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
        "encryption_keys": str(enc_keys_fpath())
        if enc_keys_fpath().exists()
        else "",
        "sign_key": str(key_sign_fpath()) if key_sign_fpath().exists() else "",
        "encryption_keys_passwords": "",
        "enable_selector": False,
        "type_approval_mode": bool(args.get("tamode")),
    }

    with open(
        co2wui_fpath("output", str(process.pid), "header.dat"), "wb"
    ) as header_file:
        pickle.dump(kwargs, header_file)

    inputs = dict(
        logger=logger,
        plot_workflow=False,
        host="127.0.0.1",
        port=4999,
        cmd_flags=kwargs,
        input_files=[str(f) for f in files],
    )

    # Dispatcher
    d = dsp.register()

    d.add_function('pass_logger', sh.bypass, inputs=['logger'], outputs=['core_model'])
    d.add_data('core_model', function=register_logger, wait_inputs=True)

    n = d.get_node('register_core', node_attr=None)[0]
    n['filters'] = n.get('filters', [])
    n['filters'].append(log_phases)

    ret = d.dispatch(inputs, ["done", "run", "core_model"])
    with open(
        co2wui_fpath("output", str(process.pid), "result.dat"), "wb"
    ) as summary_file:
        pickle.dump(ret["summary"], summary_file)
    return ""

def create_app(configfile=None):
    """Main flask app"""

    from . import i18n

    app = Flask(__name__)
    sess = Session()

    babel = Babel(app)
    CO2MPAS_VERSION = "3"

    hash = random.getrandbits(128)

    app.secret_key = ("%032x" % hash)
    app.config['SESSION_TYPE'] = 'filesystem'

    sess.init_app(app)

    app.jinja_env.globals.update(humanised=humanised)

    with resources.open_text(i18n, "texts-en.yaml") as stream:
        co2wui_texts = yaml.safe_load(stream)

    ensure_working_folders()

    with open(os.path.join(app.root_path, '..', 'VERSION')) as version_file:
      version = version_file.read().strip()
      co2wui_texts["version"] = version

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

        if ('active_pid' in session) and (session['active_pid'] is not None):
          return redirect("/run/progress?layout=layout&counter=999&id=" + str(session['active_pid']), code=302)

        inputs = [f.name for f in listdir_inputs("input")]
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

    @app.route("/run/view-summary/<runid>")
    def view_summary(runid):
        """Show a modal dialog with a execution's summary formatted in a table
        """

        # Read the header containing run information
        header = {}
        with open(co2wui_fpath("output", runid, "header.dat"), "rb") as header_file:
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

        process = multiprocessing.Process(target=run_process, args=(request.args,))
        process.start()
        id = process.pid
        session['active_pid'] = str(id)
        return redirect("/run/progress?layout=layout&counter=0&id=" + str(process.pid), code=302)

    @app.route("/run/progress")
    def run_progress():

        # Flags
        started = False
        done = False
        stopped = True if request.args.get("stopped") else False

        # Num of files processed up to now
        num_processed = 0

        # Process id
        process_id = request.args.get("id")

        # Wait counter... if not started after X then error.
        # This is required due to a latency when launching a new
        # process
        counter = request.args.get("counter")
        counter = int(counter) + 1
        layout = request.args.get("layout")

        # Read the list of input files
        files = []
        if osp.exists(co2wui_fpath("output", process_id, "files.dat")):
          started = True
          with open(co2wui_fpath("output", process_id, "files.dat"), "rb") as files_list:
              try:
                  files = pickle.load(files_list)
              except:
                  return None

        # Read the header containing run information
        header = {}
        if osp.exists(co2wui_fpath("output", process_id, "header.dat")):
          with open(co2wui_fpath("output", process_id, "header.dat"), "rb") as header_file:
              try:
                  header = pickle.load(header_file)
              except:
                  return None

        # Default page status
        page = "run_progress"

        # Simulation is "done" if there's a result file
        if osp.exists(co2wui_fpath("output", process_id, "result.dat")):
            done = True
            page = "run_complete"
            session['active_pid'] = None

        # Get the summary of the execution (if ready)
        summary = get_summary(process_id)
        result = "KO" if (summary is None or len(summary[0].keys()) <= 2) else "OK"

        # Result is KO if not started and counter > 1
        if (not started and counter > 1):
          result = "KO"
          page = "run_complete"
          session['active_pid'] = None

        # Check that the process is still running
        active_processes =  multiprocessing.active_children()
        alive = False
        for p in active_processes:
          if (str(p.pid) == process_id):
            alive = True

        if not done and not alive:
            result = "KO"
            page = "run_complete"
            session['active_pid'] = None

        # Get the log file
        log = ""
        loglines = []
        if osp.exists(co2wui_fpath("output", process_id, "logfile.txt")):
          with open(co2wui_fpath("output", process_id, "logfile.txt")) as f:
              loglines = f.readlines()
        else:
          loglines = ['Waiting for data...']

        # Collect log, exclude web server info and colorize
        for logline in loglines:
            if (logline.startswith('CO2MPAS output written into')):
                num_processed += 1
            if not re.search("- INFO -", logline):
                log += colorize(logline)

        # If simulation is stopped the log is not interesting
        if (stopped):
          loglines = ['Simulation stopped.']

        # Collect data related to execution phases
        phases = [logline.replace(': done', '').rstrip() for logline in loglines if ": done" in logline]

        # Collect result files
        results = []
        if not (summary is None or len(summary[0].keys()) <= 2):
            output_files = [f.name for f in listdir_outputs("output", process_id)]
            results.append({"name": process_id, "files": output_files})

        # Render page progress/complete
        return render_template(
            "layout.html" if layout == "layout" else "ajax.html",
            action=page,
            data={
                "breadcrumb": ["Co2mpas", _("Run simulation")],
                "props": {
                    "active": {"run": "active", "sync": "", "doc": "", "expert": ""}
                },
                "process_id": process_id,
                "log": log,
                "result": result,
                "stopped": stopped,
                "counter": counter,
                "texts": co2wui_texts,
                "progress":
                  (
                    (num_processed * (100 / int(round(len(files)))))
                    + int(round((progress_bar[phases[len(phases)-1]] / len(files))))
                  ) if (len(phases)) > 0 else 0,
                "summary": summary[0] if summary is not None else None,
                "results": results if results is not None else None,
                "header": header,
            },
        )

    @app.route("/run/stop-simulation/<process_id>", methods=["GET"])
    def stop_simulation(process_id):
        # Check that the process is still running
        active_processes =  multiprocessing.active_children()
        for p in active_processes:
          if (str(p.pid) == process_id):
            p.terminate()
            time.sleep(1)

        return redirect("/run/progress?layout=layout&stopped=1&counter=999&id=" + str(process_id), code=302)

    @app.route("/run/add-file", methods=["POST"])
    def add_file():
        f = request.files["file"]
        f.save(str(co2wui_fpath("input", secure_filename(f.filename))))
        files = {"file": f.read()}
        return redirect("/run/simulation-form", code=302)

    @app.route("/run/delete-file", methods=["GET"])
    def delete_file():
        fn = request.args.get("fn")
        inputs = listdir_inputs("input")
        inputs[int(fn) - 1].unlink()
        return redirect("/run/simulation-form", code=302)

    @app.route("/run/view-results")
    def view_results():

        dirpath = "output"
        entries = (co2wui_fpath(dirpath, fn) for fn in os.listdir(co2wui_fpath(dirpath)))
        entries = ((os.stat(path), path) for path in entries)
        entries = (
            (stat[ST_CTIME], path) for stat, path in entries if S_ISDIR(stat[ST_MODE])
        )

        results = []
        for cdate, path in sorted(entries):
            dirname = osp.basename(path)
            output_files = [f.name for f in listdir_outputs("output", dirname)]
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

        files = listdir_outputs("output", runid)
        rf = files[int(fnum) - 1]

        # Read from file
        data = None
        with open(rf, "rb") as result:
            data = result.read()

        # Output xls file
        iofile = io.BytesIO(data)
        iofile.seek(0)
        return send_file(
            iofile, attachment_filename=files[int(fnum) - 1].name, as_attachment=True
        )

    @app.route("/run/delete-results", methods=["POST"])
    def delete_results():

        for k in request.form.keys():
            if re.match(r"select-[0-9]+", k):
                runid = k.rpartition("-")[2]
                shutil.rmtree(co2wui_fpath("output", runid))

        return redirect("/run/view-results", code=302)

    @app.route("/run/download-log/<runid>")
    def download_log(runid):

        rf = co2wui_fpath("output", runid, "logfile.txt")

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
                "texts": co2wui_texts,
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
        inputs = [f.name for f in listdir_inputs("sync", "input")]
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
                "timestamp": time.time(),
                "inputs": inputs,
                "texts": co2wui_texts,
            },
        )

    @app.route("/sync/add-sync-file", methods=["POST"])
    def add_sync_file():
        for f in listdir_inputs("sync", "input"):
            f.unlink()

        f = request.files["file"]
        f.save(str(input_fpath("sync", "input") / secure_filename(f.filename)))
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

        # Input file
        inputs = listdir_inputs("sync", "input")
        input_file = str(inputs[0])

        # Output file
        output_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = co2wui_fpath("sync", "output", output_name + ".sync.xlsx")

        # Remove old output files
        previous = listdir_outputs("sync", "output")
        for f in previous:
          os.remove(str(f))

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
                dict(input_fpath=input_file, output_fpath=str(output_file), **kwargs)
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
        for f in listdir_inputs("sync", "input"):
            f.unlink()

        return redirect("/sync/synchronisation-form", code=302)

    @app.route("/sync/load-log", methods=["GET"])
    def load_sync_log():
        fpath = Path.cwd() / "sync" / "logfile.txt"
        with open(fpath) as f:
            loglines = f.readlines()

        log = ""
        for logline in loglines:
            log += logline

        return log

    @app.route("/sync/download-result/<timestr>")
    def sync_download_result(timestr):
        synced = str(listdir_outputs("sync", "output")[0])
        synced_name = os.path.basename(synced)
        return send_file(
            synced, attachment_filename=synced_name, as_attachment=True
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
        demofiles = [f for f in os.listdir(of) if osp.isfile(osp.join(of, f))]

        # Create zip archive on the fly
        zip_subdir = of
        iofile = io.BytesIO()
        zf = zipfile.ZipFile(iofile, mode="w", compression=zipfile.ZIP_DEFLATED)

        # Adds demo files to archive
        for f in demofiles:
            # Add file, at correct path
            zf.write(osp.abspath(osp.join(of, f)), f)

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
                "texts": co2wui_texts,
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
        files = [conf_fpath().name]
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
        fpath = conf_fpath()
        if fpath.exists():
            fpath.unlink()

        f = request.files["file"]
        f.save(str(fpath))
        return redirect("/conf/configuration-form", code=302)

    @app.route("/conf/delete-file", methods=["GET"])
    def delete_conf_file():
        fpath = conf_fpath()
        fpath.unlink()
        return redirect("/conf/configuration-form", code=302)

    @app.route("/keys/keys-form")
    def keys_form():

        enc_keys = [enc_keys_fpath().name]
        key_pass = [key_pass_fpath().name]
        key_sign = [key_sign_fpath().name]

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
        filepaths = {
            "enc_keys": enc_keys_fpath(),
            "key_pass": key_pass_fpath(),
            "key_sign": key_sign_fpath(),
        }

        fpath = filepaths.get(upload_type)
        if fpath.exists():
            fpath.unlink()

        f = request.files["file"]
        f.save(str(fpath))
        return redirect("/keys/keys-form", code=302)

    @app.route("/keys/delete-file", methods=["GET"])
    def delete_key_file():

        upload_type = request.args.get("upload_type")
        filepaths = {
            "enc_keys": enc_keys_fpath(),
            "key_pass": key_pass_fpath(),
            "key_sign": key_sign_fpath(),
        }
        fpath = filepaths.get(upload_type)
        fpath.unlink()
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
                "texts": co2wui_texts,
            },
        )

    @app.route("/conf/generate")
    def conf_generate():

        # Conf file name
        of = conf_fpath()

        # Input parameters
        inputs = {"output_file": of.name}

        # Dispatcher
        d = dsp.register()
        ret = d.dispatch(inputs, ["conf", "done"])

        return redirect("/conf/configuration-form", code=302)

    # Demo/download
    @app.route("/conf/download")
    def conf_download():
        of = conf_fpath()

        return send_file(of.open("rb"), attachment_filename=of.name, as_attachment=True)

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
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    create_app().run(debug=True)
