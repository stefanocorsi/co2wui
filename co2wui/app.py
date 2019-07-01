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
import syncing
import zipfile
import shutil

def listdir_inputs(path):
    """Only allow for excel files as input 
    """
    return map(lambda x: os.path.basename(x), glob.glob(os.path.join(path, "*.xls*")))


def listdir_outputs(path):
    """Only allow for excel files as output 
    """
    return map(lambda x: os.path.basename(x), glob.glob(os.path.join(path, "*.xls*")))
    
def listdir_conf(path):
    """Only allow for conf.yaml files 
    """
    return map(lambda x: os.path.basename(x), glob.glob(os.path.join(path, "conf.yaml")))    

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
                "props": {"active": {"run": "", "sync": "", "doc": "", "expert": ""}},
            },
        )

    @app.route("/run/download-template-form")
    def download_template_form():
        return render_template(
            "layout.html",
            action="template_download_form",
            data={
                "breadcrumb": ["Co2mpas", "Download template"],
                "props": {"active": {"run": "active", "sync": "", "doc": "", "expert": ""}},
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
                "props": {"active": {"run": "active", "sync": "", "doc": "", "expert": ""}},
                "inputs": inputs,
            },
        )

    def run_process(args):

        thread = threading.current_thread()
        files = [
            os.path.join("input", f) for f in listdir_inputs("input") if isfile(os.path.join("input", f))
        ]

        # Create output directory for this execution
        output_folder = os.path.join("output", str(thread.ident))
        os.makedirs(output_folder or ".", exist_ok=True)

        # Dedicated logging for this run
        fileh = logging.FileHandler(
            os.path.join(
              "output",
              str(thread.ident),
              "logfile.txt"
            ), "a"
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
        f = open(os.path.join("output", str(thread.ident), "result.dat"), "w+")
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
        with open(os.path.join("output", thread_id, "logfile.txt")) as f:
            loglines = f.readlines()

        for logline in reversed(loglines):
            if not re.search("- INFO -", logline):
                log += logline

        return render_template(
            "layout.html" if layout == "layout" else "ajax.html",
            action=page,
            data={
                "breadcrumb": ["Co2mpas", title],
                "props": {"active": {"run": "active", "sync": "", "doc": "", "expert": ""}},
                "thread_id": thread_id,
                "log": log,
            },
        )

    @app.route("/run/add-file", methods=["POST"])
    def add_file():
        f = request.files["file"]
        f.save(os.path.join("input", secure_filename(f.filename)))
        files = {"file": f.read()}
        return redirect("/run/simulation-form", code=302)

    @app.route("/run/delete-file", methods=["GET"])
    def delete_file():
        fn = request.args.get("fn")
        inputs = [f for f in listdir_inputs("input") if isfile(join("input", f))]
        os.remove(os.path.join("input", inputs[int(fn) - 1]))
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
                for f in listdir_outputs(os.path.join("output", dirname))
                if isfile(os.path.join("output", dirname, f))
            ]
            results.append(
                {"datetime": time.ctime(cdate), "name": dirname, "files": output_files}
            )

        return render_template(
            "layout.html",
            action="view_results",
            data={
                "breadcrumb": ["Co2mpas", "View results"],
                "props": {"active": {"run": "active", "sync": "", "doc": "", "expert": ""}},
                "results": reversed(results),
            },
        )

    @app.route("/run/download-result/<runid>/<fnum>")
    def download_result(runid, fnum):

        files = list(listdir_outputs(os.path.join("output", runid)))
        rf = os.path.join("output", runid, files[int(fnum) - 1])

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

        rf = os.path.join("output", runid, "logfile.txt")

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
                "breadcrumb": ["Co2mpas", "Data synchronisation"],
                "props": {"active": {"run": "", "sync": "active", "doc": "", "expert": ""}},
                "title": "Data synchronisation"
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
        theoretical = sh.selector(['times', 'velocities'], dsp(inputs=dict(
            cycle_type=cycle_type.upper(), gear_box_type=gear_box_type,
            wltp_class=wltp_class, downscale_factor=0
        ), outputs=['times', 'velocities'], shrink=True))
        base = dict.fromkeys((
            'times', 'velocities', 'target gears', 'engine_speeds_out',
            'engine_coolant_temperatures', 'co2_normalization_references',
            'alternator_currents', 'battery_currents', 'target fuel_consumptions',
            'target co2_emissions', 'target engine_powers_out'
        ), [])
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
            iofile, attachment_filename='datasync.xlsx', as_attachment=True
        )
        
    @app.route("/sync/synchronisation-form")
    def synchronisation_form():
        inputs = [f for f in listdir_inputs("sync/input") if isfile(join("sync/input", f))]
        return render_template(
            "layout.html",
            action="synchronisation_form",
            data={
                "breadcrumb": ["Co2mpas", "Run synchronisation"],
                "props": {"active": {"run": "", "sync": "active", "doc": "", "expert": ""}},
                "interpolation_methods": [
                  "linear","nearest","zero","slinear","quadratic","cubic","pchip","akima","integral",
                  "polynomial0","polynomial1","polynomial2","polynomial3",
                  "polynomial4","spline5","spline7","spline9"
                ],
                "inputs": inputs,
            },
        )
        
    @app.route("/sync/add-sync-file", methods=["POST"])
    def add_sync_file():
        inputs = [f for f in listdir_inputs("sync") if isfile(join("sync", f))]
       
        for file in inputs:
          os.remove(os.path.join("sync/input", file))
        
        f = request.files["file"]
        f.save(os.path.join("sync/input", secure_filename(f.filename)))
        files = {"file": f.read()}
        return redirect("/sync/synchronisation-form", code=302)
        
    @app.route("/sync/run-synchronisation", methods=["POST"])
    def run_synchronisation():
    
        # Dedicated logging for this run
        fileh = logging.FileHandler(
            "sync/logfile.txt", "w"
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
    
        # Input and output files
        input_file = "sync/input/datasync.xlsx"
        output_file = "sync/output/datasync.sync.xlsx"
    
        # Arguments
        kwargs = {
            "x_label": request.form.get("x_label") if request.form.get("x_label") else 'times',
            "y_label": request.form.get("y_label") if request.form.get("y_label") else 'velocities',
            "interpolation_method": request.form.get("interpolation_method"),
            "header": request.form.get("header"),
            "reference_name": request.form.get("reference_name") if request.form.get("reference_name") else 'theoretical',
        }
        kwargs = {k: v for k, v in kwargs.items() if v}
        
        try:
        
          # Dispatcher
          _process = sh.SubDispatch(syncing.dsp, ['written'], output_type='value')
          ret = _process(dict(input_fpath=input_file, output_fpath=output_file, **kwargs))   
          return 'OK'
          
        except Exception as e:   
          return 'KO'
          
    @app.route("/sync/delete-file", methods=["GET"])
    def delete_sync_file():       
        os.remove("sync/input/datasync.xlsx")
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
    @app.route('/demo/download')
    def demo_download():
    
      # Temporary output folder  
      of = next(tempfile._get_candidate_names())
      
      # Input parameters
      inputs = {'output_folder': of}

      # Dispatcher
      d = dsp.register()
      ret = d.dispatch(inputs, ['demo', 'done'])
      
      # List of demo files created
      demofiles = [f for f in listdir(of) if isfile(join(of, f))]

      # Create zip archive on the fly
      zip_subdir = of
      iofile = io.BytesIO()
      zf = zipfile.ZipFile(iofile, mode='w', compression=zipfile.ZIP_DEFLATED)
      
      # Adds demo files to archive
      for f in demofiles:
        # Add file, at correct path
        zf.write(os.path.abspath(os.path.join(of, f)), f)
      
      # Close archive
      zf.close()
      
      # Remove temporary files
      shutil.rmtree(of)
      
      # Output zip file
      iofile.seek(0)
      return send_file(iofile, attachment_filename='co2mpas-demo.zip', as_attachment=True)
        
    @app.route("/plot/launched")
    def plot_launched():
      return render_template(
          "content.html",
          action="launch_plot",
          data={
              "breadcrumb": ["Co2mpas", "Plot launched"],
              "props": {"active": {"run": "", "sync": "", "doc": "", "expert": "active"}},
              "title": "Plot launched"
          },
      )
        
    @app.route("/plot/model-graph")
    def plot_model_graph():
      dsp(dict(plot_model=True, cache_folder='cache', host='127.0.0.1', port=4999), ['plot', 'done'])
      return ''
      
    @app.route("/conf/configuration-form")
    def configuration_form():
      files = [f for f in listdir_conf(".") if isfile(join(".", f))]
      return render_template(
            "layout.html",
            action="configuration_form",
            data={
                "breadcrumb": ["Co2mpas", "Co2mpas configuration file"],
                "props": {"active": {"run": "", "sync": "active", "doc": "", "expert": "active"}},
                "title": "Configuration form",
                "inputs": files,
            },
        )
        
    @app.route("/conf/add-conf-file", methods=["POST"])
    def add_conf_file():
        if os.path.exists("conf.yaml"):
          os.remove("conf.yaml")
        
        f = request.files["file"]
        f.save('conf.yaml')
        return redirect("/conf/configuration-form", code=302)
        
    @app.route("/conf/delete-file", methods=["GET"])
    def delete_conf_file():       
        os.remove("conf.yaml")
        return redirect("/conf/configuration-form", code=302)
        
      
    @app.route("/not-implemented")
    def not_implemented():
        return render_template(
            "layout.html",
            action="generic_message",
            data={
                "breadcrumb": ["Co2mpas", "Feature not implemented"],
                "props": {"active": {"run": "", "sync": "", "doc": "", "expert": ""}},
                "title": "Feature not implemented",
                "message": "Please refer to future versions of the application or contact xxxxxxx@xxxxxx.europa.eu for information.",
            },
        )
        
    # Demo/download
    @app.route('/conf/download')
    def conf_download():
    
      # Conf file name
      of = 'conf.yaml'
           
      # Input parameters
      inputs = {'output_file': of}
   
      # Dispatcher
      d = dsp.register()
      ret = d.dispatch(inputs, ['conf', 'done'])
      
      # Read from file
      data = None
      with open(of, "rb") as conf_yaml:
          data = conf_yaml.read()     

      # Output xls file
      iofile = io.BytesIO(data)
      iofile.seek(0)
      return send_file(
          iofile,
          attachment_filename="conf.yaml",
          as_attachment=True,
      )

    @app.route("/contact-us")
    def contact_us():
      return render_template(
            "layout.html",
            action="contact_us",
            data={
                "breadcrumb": ["Co2mpas", "Contact us"],
                "props": {"active": {"run": "", "sync": "", "doc": "active", "expert": ""}},
                "title": "Contact us",                
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
