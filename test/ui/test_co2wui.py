import os
import re
import unittest
import warnings

import flask
import pytest
from selenium.common.exceptions import NoSuchElementException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


# from https://pytest-flask.readthedocs.io/en/latest/features.html#start-live-server-start-live-server-automatically-default
@pytest.mark.usefixtures("app")
class TestLiveServer:
    def test_100_datasync_form(self, driver, live_server):

        print("Starting datasync download template UI test")
        driver.get("http://localhost:5000/sync/template-form")

        elem = driver.find_element_by_tag_name("h1")
        assert elem.text == "Data synchronisation"

        elem = driver.find_element_by_tag_name("h3")
        assert elem.text == "Choose a datasync template type"

        elem = driver.find_element_by_id("cycle")
        assert elem.text == "WLTP\nNEDC"

        elem = driver.find_element_by_id("wltpclass")
        assert elem.text == "Class 1\nClass 2\nClass 3a\nClass 3b"

        # Change to wltp, gearbox should be present
        elem = driver.find_element_by_id("cycle")
        select_element = Select(elem)
        select_element.select_by_value("nedc")
        elem = driver.find_element_by_id("gearbox")
        assert elem.text == "Automatic\nManual"

    def test_120_datasync(self, driver, live_server):

        print("Starting datasync UI test")
        driver.get("http://localhost:5000/sync/synchronisation-form")

        elem = driver.find_element_by_id("synchronise-button")
        assert elem.text == "Synchronise data"

        elem.click()
        WebDriverWait(driver, 5).until(
            EC.text_to_be_present_in_element(
                (By.ID, "sync-feedback"), "1 file has been processed"
            )
        )

    def test_130_new_sync(self, driver, live_server):

        print("Starting new synchronisation UI test")
        driver.get("http://localhost:5000/sync/synchronisation-form")

        elem = driver.find_element_by_id("synchronise-button")
        assert elem.text == "Synchronise data"

        elem.click()
        WebDriverWait(driver, 5).until(
            EC.text_to_be_present_in_element(
                (By.ID, "sync-feedback"), "1 file has been processed"
            )
        )

        elem = driver.find_element_by_id("synchronise-button")
        assert elem.is_displayed() is not True

        elem = driver.find_element_by_link_text("Synchronise another file")
        elem.click()

        elem = driver.find_element_by_id("synchronise-button")
        assert elem.is_displayed() is True

    def test_140_delete_file_and_upload(self, driver, live_server):

        print("Starting datasync delete file UI test")
        driver.get("http://localhost:5000/sync/synchronisation-form")

        src = driver.page_source
        text_found = re.search(r"datasync.xlsx", src)
        assert text_found is None

        elem = driver.find_element_by_id("delete-button")
        elem.click()

        src = driver.page_source
        text_found = re.search(r"datasync.xlsx", src)
        assert text_found is None

        elem = driver.find_element_by_id("file")
        elem.send_keys(os.path.join(os.getcwd(), "test", "datasync.xlsx"))

        elem = driver.find_element_by_id("add-sync-file-form").submit()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "delete-button")))

        src = driver.page_source
        text_found = re.search(r"datasync.xlsx", src)
        assert text_found is None

    def test_150_datasync_file_other_name(self, driver, live_server):

        print("Starting datasync other name UI test")
        driver.get("http://localhost:5000/sync/synchronisation-form")

        elem = driver.find_element_by_id("delete-button")
        elem.click()

        elem = driver.find_element_by_id("file")
        elem.send_keys(os.path.join(os.getcwd(), "test", "datasync-other-name.xlsx"))

        elem = driver.find_element_by_id("add-sync-file-form").submit()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "delete-button")))

        src = driver.page_source
        text_found = re.search(r"datasync-other-name.xlsx", src)
        assert text_found is None

        src = driver.page_source
        text_found = re.search(r"datasync.xlsx", src)
        assert text_found is None

        elem = driver.find_element_by_id("delete-button")
        elem.click()

        elem = driver.find_element_by_id("file")
        elem.send_keys(os.path.join(os.getcwd(), "test", "datasync.xlsx"))

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "delete-button")))

        src = driver.page_source
        text_found = re.search(r"datasync.xlsx", src)
        assert text_found is None

    def test_160_datasync_with_empty_file(self, driver, live_server):

        print("Starting datasync with empty file UI test")
        driver.get("http://localhost:5000/sync/synchronisation-form")

        elem = driver.find_element_by_id("delete-button")
        elem.click()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(
            EC.visibility_of_element_located((By.ID, "add-sync-file-form"))
        )

        elem = driver.find_element_by_id("file")
        elem.send_keys(os.path.join(os.getcwd(), "test", "datasync-empty.xlsx"))

        driver.implicitly_wait(2)
        elem = driver.find_element_by_id("add-sync-file-form").submit()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "delete-button")))

        elem = driver.find_element_by_id("synchronise-button")
        assert elem.text == "Synchronise data"

        elem.click()
        WebDriverWait(driver, 5).until(
            EC.text_to_be_present_in_element(
                (By.ID, "logarea"), "Synchronisation failed:"
            )
        )

        elem = driver.find_element_by_id("delete-button")
        elem.click()

        elem = driver.find_element_by_id("file")
        elem.send_keys(os.path.join(os.getcwd(), "test", "datasync.xlsx"))

        elem = driver.find_element_by_id("add-sync-file-form").submit()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "delete-button")))

    def test_200_generate_config_file(self, driver, live_server):

        print("Starting generate config file test")
        driver.get("http://localhost:5000/conf/configuration-form")

        elem = driver.find_element_by_tag_name("h1")
        assert elem.text == "Configuration file"

        src = driver.page_source
        text_found = re.search(
            r"A precompiled file to overwrite the input variables of the physical model can be generated and downloaded.",
            src,
        )
        assert text_found is None

        elem = driver.find_element_by_id("generate-link")
        elem.click()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "conf-table")))

        src = driver.page_source
        text_found = re.search(
            r"Do you want to generate a blank configuration file", src
        )
        assert text_found is None

        src = driver.page_source
        text_found = re.search(r"conf.yaml", src)
        assert text_found is None

        text_found = re.search(r"Download", src)
        assert text_found is None

        text_found = re.search(r"Delete", src)
        assert text_found is None

    def test_210_delete_config_file(self, driver, live_server):

        print("Starting delete config file test")
        driver.get("http://localhost:5000/conf/configuration-form")

        elem = driver.find_element_by_id("delete-button")
        elem.click()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "generate-link")))

        src = driver.page_source
        text_found = re.search(
            r"Do you want to generate a blank configuration file", src
        )
        assert text_found is None

    def test_220_upload_config_file(self, driver, live_server):

        print("Starting upload config file test")
        driver.get("http://localhost:5000/conf/configuration-form")

        elem = driver.find_element_by_id("file")
        elem.send_keys(os.path.join(os.getcwd(), "test", "sample.conf.yaml"))

        elem = driver.find_element_by_id("conf-file-form").submit()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "conf-table")))

        src = driver.page_source
        text_found = re.search(
            r"Do you want to generate a blank configuration file", src
        )
        assert text_found is None

        src = driver.page_source
        text_found = re.search(r"conf.yaml", src)
        assert text_found is None

        text_found = re.search(r"Download", src)
        assert text_found is None

        text_found = re.search(r"Delete", src)
        assert text_found is None

    def test_300_simulation_delete_and_upload(self, driver, live_server):

        print("Starting delete and upload simulation test")
        driver.get("http://localhost:5000/run/simulation-form")

        src = driver.page_source
        text_found = re.search(r"co2mpas_demo-0.xlsx", src)
        assert text_found is None

        elem = driver.find_element_by_id("delete-button")
        elem.click()

        src = driver.page_source
        text_found = re.search(r"No input files have been uploaded", src)
        assert text_found is None

        try:
            elem = driver.find_element_by_id("delete-button")
            assert False
        except NoSuchElementException:
            pass

        elem = driver.find_element_by_id("file")
        elem.send_keys(os.path.join(os.getcwd(), "test", "co2mpas_demo-0.xlsx"))

        elem = driver.find_element_by_id("add-file-form").submit()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "delete-button")))

    def test_310_run_simulation(self, driver, live_server):

        print("Starting run simulation test")
        driver.get("http://localhost:5000/run/simulation-form")

        elem = driver.find_element_by_id("run-simulation")
        elem.click()

        WebDriverWait(driver, 100).until(
            EC.text_to_be_present_in_element(
                (By.ID, "sim-result"), "Simulation results"
            )
        )
