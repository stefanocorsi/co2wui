import warnings
import unittest
import os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException

class TestCo2mpasWui(unittest.TestCase):
    def setUp(self):
        print("setUp executed")
        opts = Options()
        opts.headless = True

        self.driver = webdriver.Firefox(
            options=opts, executable_path="C:/Apps/geckodriver/geckodriver.exe"
        )
        
    def test_datasync_form(self):
        
        driver = self.driver
        print("Starting datasync UI test")
        driver.get("http://localhost:5000/sync/template-form")

        elem = driver.find_element_by_tag_name("h1");
        self.assertEqual(elem.text, "Data synchronisation")
        
        elem = driver.find_element_by_tag_name("h2");
        self.assertEqual(elem.text, 'Download a Co2mpas datasync template')
        
        elem = driver.find_element_by_id("cycle");
        self.assertEqual(elem.text, "WLTP\nNEDC")

        elem = driver.find_element_by_id("wltpclass");
        self.assertEqual(elem.text, "Class 1\nClass 2\nClass 3a\nClass 3b")

        elem = driver.find_element_by_id("gearbox");
        self.assertEqual(elem.text, "Automatic\nManual")
        
    def tearDown(self):
        self.driver.close()
        print("tearDown executed")


if __name__ == "__main__":
    unittest.main()
