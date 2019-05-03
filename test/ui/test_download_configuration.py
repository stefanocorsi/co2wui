import os
import warnings
import unittest
from selenium import webdriver
from selenium.webdriver.firefox.options import Options


class DownloadConfigurationScenario(unittest.TestCase):

    def setUp(self):

        print("setUp executed")
        opts = Options()
        opts.headless = True
        self.driver = webdriver.Firefox(options=opts, executable_path=
                                        "C:/Apps/geckodriver/geckodriver.exe")

    def test_download_configuration_link(self):
        warnings.filterwarnings(action="ignore", message="unclosed",
                                category=ResourceWarning)
        driver = self.driver
        print("Firefox Headless Browser Invoked")
        driver.get("http://127.0.0.1:5000/")
        elem = driver.find_element_by_link_text("Download configuration")
        self.assertEqual(elem.text, "Download configuration")

    def test_upload_configuration_link(self):
        warnings.filterwarnings(action="ignore", message="unclosed",
                                category=ResourceWarning)
        driver = self.driver
        print("Firefox Headless Browser Invoked")
        driver.get("http://127.0.0.1:5000/")
        elem = driver.find_element_by_link_text("Upload configuration")
        self.assertEqual(elem.text, "Upload configuration")

    def test_browse_button_to_upload_input_file(self):
        driver = self.driver
        print("Firefox Headless Browser Invoked")
        driver.get("http://127.0.0.1:5000/configuration/upload-form")
        upload_elem = driver.find_element_by_id("file-input")

        upload_elem.send_keys(os.getcwd()+"\\test\\ui\\test001.txt")
        driver.find_element_by_id("submit-button")

    def test_reset_button_to_cancel_upload_input_file(self):
        warnings.filterwarnings(action="ignore", message="unclosed",
                                category=ResourceWarning)
        driver = self.driver
        print("Firefox Headless Browser Invoked")
        driver.get("http://127.0.0.1:5000/configuration/upload-form")
        upload_elem = driver.find_element_by_id("file-input")
        upload_elem.send_keys(os.getcwd()+"\\test\\ui\\test001.txt")
        reset_elem = driver.find_element_by_id("reset-button")
        reset_elem.click()

    def tearDown(self):
        self.driver.close()
        print("tearDown executed")


if __name__ == "__main__":
    # https://stackoverflow.com/questions/48160728/resourcewarning-unclosed-socket-in-python-3-unit-test
    unittest.main()