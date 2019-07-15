import socket

import pytest
from pytest_flask.fixtures import LiveServer, _rewrite_server_name
from selenium import webdriver
from selenium.webdriver.firefox.options import Options

import co2wui.app


# from https://pytest-flask.readthedocs.io/en/latest/tutorial.html#step-2-configure
@pytest.fixture(scope="session")
def app():
    return co2wui.app.create_app()


## Avoid restarting server by launching it ONCE for every test-session.
#
# Code below is just a copy of original *pytest-flask* fixture
# with changes from https://github.com/pytest-dev/pytest-flask/pull/63/files
@pytest.fixture(scope="session")
def live_server(request, app, pytestconfig):
    """Run application in a separate process.
    When the ``live_server`` fixture is applied, the ``url_for`` function
    works as expected::
        def test_server_is_up_and_running(live_server):
            index_url = url_for('index', _external=True)
            assert index_url == 'http://localhost:5000/'
            res = urllib2.urlopen(index_url)
            assert res.code == 200
    """
    port = pytestconfig.getvalue("live_server_port")

    if port == 0:
        # Bind to an open port
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("", 0))
        port = s.getsockname()[1]
        s.close()

    host = pytestconfig.getvalue("live_server_host")

    # Explicitly set application ``SERVER_NAME`` for test suite
    # and restore original value on test teardown.
    server_name = app.config["SERVER_NAME"] or "localhost"
    app.config["SERVER_NAME"] = _rewrite_server_name(server_name, str(port))

    clean_stop = request.config.getvalue("live_server_clean_stop")
    server = LiveServer(app, host, port, clean_stop)
    if request.config.getvalue("start_live_server"):
        server.start()

    request.addfinalizer(server.stop)
    return server


## See https://github.com/pytest-dev/pytest-selenium/issues/59
@pytest.fixture(scope="session")
def driver(app, live_server):
    opts = Options()
    opts.headless = True

    driver = webdriver.Firefox(options=opts)
    driver.implicitly_wait(10)
    driver.get("http://localhost:5000")
    elem = driver.find_element_by_id("do-not-show")
    elem.click()

    elem = driver.find_element_by_id("close-hints")
    elem.click()

    try:
        yield driver
    finally:
        driver.quit()
