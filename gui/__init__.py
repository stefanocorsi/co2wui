from flask import Flask, render_template, current_app, url_for
from flask import Response
import requests
import json

__version__ = '2.4'

def create_app(configfile=None):
    app = Flask(__name__)
    CO2MPAS_VERSION = '3'
    JQUERY_VERSION = '2.0.2'
    HTML5SHIV_VERSION = '3.7.0'
    RESPONDJS_VERSION = '1.3.0'
    
    app.config.setdefault('CO2MPAS_USE_MINIFIED', True)
    app.config.setdefault('CO2MPAS_CDN_FORCE_SSL', False)
    
    app.config.setdefault('CO2MPAS_QUERYSTRING_REVVING', True)
    app.config.setdefault('CO2MPAS_SERVE_LOCAL', False)
    
    app.jinja_env.globals['co2mpas_find_resource'] =\
        co2mpas_find_resource

    if not hasattr(app, 'extensions'):
            app.extensions = {}

    local = StaticCDN('co2mpas.static', rev=True)
    static = StaticCDN()

    def lwrap(cdn, primary=static):
        return ConditionalCDN('CO2MPAS_SERVE_LOCAL', primary, cdn)

    bootstrap = lwrap(
        WebCDN('//cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/%s/'
               % CO2MPAS_VERSION),
        local)

    jquery = lwrap(
        WebCDN('//cdnjs.cloudflare.com/ajax/libs/jquery/%s/'
               % JQUERY_VERSION),
        local)

    html5shiv = lwrap(
        WebCDN('//cdnjs.cloudflare.com/ajax/libs/html5shiv/%s/'
               % HTML5SHIV_VERSION))

    respondjs = lwrap(
        WebCDN('//cdnjs.cloudflare.com/ajax/libs/respond.js/%s/'
               % RESPONDJS_VERSION))

        
    app.extensions['co2mpas'] = {
            'cdns': {
                'local': local,
                'static': static,
                'bootstrap': bootstrap,
                'jquery': jquery,
                'html5shiv': html5shiv,
                'respond.js': respondjs,
            },
        }

    @app.route('/')
    def index():
        return render_template('layout.html', action='dashboard')
        
    @app.route('/configuration/download-form')
    def configuration_download_form():
        return render_template('layout.html', action='configuration')
		
    @app.route('/configuration/download', methods=['POST'])
    def configuration_download():
        url = "http://localhost:8080/"
        kw = {
            'inputs': dict(output_file='conf.yaml', api_mode=True),
            'outputs': ['conf', 'done'],
            'select_output_kw': {'keys': ['conf']}
        }
        response = requests.post(url, json={'kwargs': kw})
        obj = json.loads(response.text)



        return Response(('').join(obj["return"]["conf"]), mimetype='text/yaml')

    return app

class CDN(object):
    """Base class for CDN objects."""
    def get_resource_url(self, filename):
        """Return resource url for filename."""
        raise NotImplementedError


class StaticCDN(object):
    """A CDN that serves content from the local application.

    :param static_endpoint: Endpoint to use.
    :param rev: If ``True``, honor ``ADMINLTE_QUERYSTRING_REVVING``.
    """
    def __init__(self, static_endpoint='static', rev=False):
        self.static_endpoint = static_endpoint
        self.rev = rev

    def get_resource_url(self, filename):
        extra_args = {}

        if self.rev and current_app.config['CO2MPAS_QUERYSTRING_REVVING']:
            extra_args['co2mpas'] = __version__

        return url_for(self.static_endpoint, filename=filename, **extra_args)


class WebCDN(object):
    """Serves files from the Web.

    :param baseurl: The baseurl. Filenames are simply appended to this URL.
    """
    def __init__(self, baseurl):
        self.baseurl = baseurl

    def get_resource_url(self, filename):
        return self.baseurl + filename


class ConditionalCDN(object):
    """Serves files from one CDN or another, depending on whether a
    configuration value is set.

    :param confvar: Configuration variable to use.
    :param primary: CDN to use if the configuration variable is ``True``.
    :param fallback: CDN to use otherwise.
    """
    def __init__(self, confvar, primary, fallback):
        self.confvar = confvar
        self.primary = primary
        self.fallback = fallback

    def get_resource_url(self, filename):
        if current_app.config[self.confvar]:
            return self.primary.get_resource_url(filename)
        return self.fallback.get_resource_url(filename)

def co2mpas_find_resource(filename, cdn, use_minified=None, local=True):
    """Resource finding function, also available in templates.

    Tries to find a resource, will force SSL depending on
    ``ADMINLTE_CDN_FORCE_SSL`` settings.

    :param filename: File to find a URL for.
    :param cdn: Name of the CDN to use.
    :param use_minified': If set to ``True``/``False``, use/don't use
                          minified. If ``None``, honors
                          ``ADMINLTE_USE_MINIFIED``.
    :param local: If ``True``, uses the ``local``-CDN when
                  ``ADMINLTE_SERVE_LOCAL`` is enabled. If ``False``, uses
                  the ``static``-CDN instead.
    :return: A URL.
    """
    config = current_app.config

    if None == use_minified:
        use_minified = config['CO2MPAS_USE_MINIFIED']

    if use_minified:
        filename = '%s.min.%s' % tuple(filename.rsplit('.', 1))

    cdns = current_app.extensions['co2mpas']['cdns']
    resource_url = cdns[cdn].get_resource_url(filename)

    if resource_url.startswith('//') and config['CO2MPAS_CDN_FORCE_SSL']:
        resource_url = 'https:%s' % resource_url

    return resource_url

    
if __name__ == '__main__':
    create_app().run(debug=True)
