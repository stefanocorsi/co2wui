import warnings
import unittest
import os
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
import re    

class TestCo2mpasWui(unittest.TestCase):
    def setUp(self):
        print("setUp executed")
        opts = Options()
        opts.headless = True

        self.driver = webdriver.Firefox(
            options=opts, executable_path="C:/Apps/geckodriver/geckodriver.exe"
        )
               
    def test_100_datasync_form(self):
        
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
        
    def test_200_generate_config_file(self):
    
        driver = self.driver
        
        print("Starting generate config file test")
        driver.get("http://localhost:5000/conf/configuration-form")
        
        elem = driver.find_element_by_tag_name("h1");
        self.assertEqual(elem.text, "Co2mpas configuration file")
        
        elem = driver.find_element_by_tag_name("h2");
        self.assertEqual(elem.text, 'Upload and download your Co2mpas configuration file')
        
        src = driver.page_source
        text_found = re.search(r'Do you want to generate a blank configuration file', src)
        self.assertNotEqual(text_found, None)

        elem = driver.find_element_by_id("generate-link");
        elem.click()
        
        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "conf-table")))
        
        src = driver.page_source
        text_found = re.search(r'Do you want to generate a blank configuration file', src)
        self.assertEqual(text_found, None)
        
        src = driver.page_source
        text_found = re.search(r'conf.yaml', src)
        self.assertNotEqual(text_found, None)
        
        text_found = re.search(r'Download', src)
        self.assertNotEqual(text_found, None)
        
        text_found = re.search(r'Delete', src)
        self.assertNotEqual(text_found, None)
        
    def test_210_delete_config_file(self):
        
        driver = self.driver
        
        print("Starting delete config file test")
        driver.get("http://localhost:5000/conf/configuration-form")
        
        elem = driver.find_element_by_id("delete-button");
        elem.click()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "generate-link")))
          
        src = driver.page_source
        text_found = re.search(r'Do you want to generate a blank configuration file', src)
        self.assertNotEqual(text_found, None)
        
    def test_220_upload_config_file(self):
                
        driver = self.driver
        
        print("Starting upload config file test")
        driver.get("http://localhost:5000/conf/configuration-form")
        
        elem = driver.find_element_by_id("file-input")
        elem.send_keys(os.path.join(os.getcwd(), "test", "sample.conf.yaml"))

        elem = driver.find_element_by_id("conf-file-form").submit()

        wait = WebDriverWait(driver, 10)
        cond = wait.until(EC.visibility_of_element_located((By.ID, "conf-table")))
        
        src = driver.page_source
        text_found = re.search(r'Do you want to generate a blank configuration file', src)
        self.assertEqual(text_found, None)
        
        src = driver.page_source
        text_found = re.search(r'conf.yaml', src)
        self.assertNotEqual(text_found, None)
        
        text_found = re.search(r'Download', src)
        self.assertNotEqual(text_found, None)
        
        text_found = re.search(r'Delete', src)
        self.assertNotEqual(text_found, None)
                      
    def tearDown(self):
        self.driver.quit()
        print("tearDown executed")


if __name__ == "__main__":
    if os.path.exists("conf.yaml"):
      os.remove("conf.yaml")                
      
    unittest.main()
