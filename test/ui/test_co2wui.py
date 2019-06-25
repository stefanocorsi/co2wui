import warnings
import unittest
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

    def test_co2mpas_home_page(self):
        warnings.filterwarnings(
            action="ignore", message="unclosed", category=ResourceWarning
        )
        driver = self.driver
        print("Firefox Headless Browser Invoked")
        driver.get("http://localhost:5000/")

        # Print co2mpas webpage title
        title = driver.title
        print("Co2mpas website Title is: " + title)

        # Test for the Synchronize text functionality name on the left menu bar
        elem = driver.find_element_by_link_text("Synchronize data")
        self.assertEqual(elem.text, "Synchronize data")

        # Test for the Demo file text functionality name on the left menu bar
        elem = driver.find_element_by_link_text("Demo file")
        self.assertEqual(elem.text, "Demo file")

        # Test for the Load keys text functionality name on the left menu bar
        elem = driver.find_element_by_link_text("Load keys")
        self.assertEqual(elem.text, "Load keys")

        # Test for the Expert functionalities text name on the left menu bar
        elem = driver.find_element_by_link_text("Expert functionalities")
        self.assertEqual(elem.text, "Expert functionalities")

        # Test for the Support & docs text name on the left menu bar
        elem = driver.find_element_by_link_text("Support & docs")
        self.assertEqual(elem.text, "Support & docs")

        # Locate Run simulation button & synchronize data on co2mpas home page
        run_simulation_button = driver.find_element_by_id("run-button")

        # Click Run simulation button on co2mpas home page
        try:
            run_simulation_button.click()
        except WebDriverException:
            print("Synchronize data button is not clickable")

        file_browser = WebDriverWait(self.driver, 5).until(
            EC.element_to_be_clickable((By.ID, "file_browser"))
        )

        file_browser.click()

        driver.back()

        # Download co2mpas input file from the home page for the first time
        try:
            click_download_link = driver.find_element_by_partial_link_text(
                "Haven't done it yet?"
            )
            click_download_link.click()
            print("Co2mpas input file downloaded!")
        except WebDriverException:
            print("Unable to downloaded co2mpas input file")

        # Wait 10 seconds until home page is refreshed &
        # click synchronization button
        wait = WebDriverWait(self.driver, 10)
        synchronize_data_button = wait.until(
            EC.element_to_be_clickable((By.ID, "synchronize-button"))
        )
        synchronize_data_button.click()

        driver.back()

        # check if the synchronization functionality on left menu bar works
        sync_data_link_left_menu = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "synchronize-data-link"))
        )

        sync_data_link_left_menu.click()

        elem = driver.find_element_by_tag_name("h2")
        self.assertEqual(elem.text, "Feature not implemented", "")

        driver.back()

        # Test search box on the right of top bar
        search_box = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "search-box"))
        )

        search_box.click()
        search_box.send_keys("run simulation")

    def test_co2mpas_download_template_page(self):
        warnings.filterwarnings(
            action="ignore", message="unclosed", category=ResourceWarning
        )
        driver = self.driver
        print("Firefox Headless Browser Invoked")
        driver.get("http://localhost:5000/run/download-template-form")

        # Check Download input template functionality text on the left menu bar
        elem = driver.find_element_by_link_text("Download input template")
        self.assertEqual(elem.text, "Download input template")

        download_input_template = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "download-template-action"))
        )

        download_input_template.click()

    def test_co2mpas_run_simulation(self):
        warnings.filterwarnings(
            action="ignore", message="unclosed", category=ResourceWarning
        )
        driver = self.driver
        print("Firefox Headless Browser Invoked")
        driver.get("http://localhost:5000/run/simulation-form")

        # Locate Run simulation button & file delete on run simulation page
        file_browser = driver.find_element_by_id("file_browser")

        # Click file delete button on co2mpas run simulation
        try:
            file_browser.click()
        except WebDriverException:
            print("file browser button is not clickable")

        # click to see advanced options
        try:
            click_download_link = driver.find_element_by_partial_link_text(
                "Advanced options"
            )
            click_download_link.click()
        except WebDriverException:
            print("Advanced options is not clickable")

    def test_co2mpas_past_execution_page(self):
        warnings.filterwarnings(
            action="ignore", message="unclosed", category=ResourceWarning
        )
        driver = self.driver
        print("Firefox Headless Browser Invoked")
        driver.get("http://localhost:5000/run/view-results")

        # Check Download input template functionality text on the left menu bar
        elem = driver.find_element_by_link_text("View results")
        self.assertEqual(elem.text, "View results")

        delete_past_exec_files_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "delete-selected"))
        )

        delete_past_exec_files_btn.click()

    def tearDown(self):
        self.driver.close()
        print("tearDown executed")


if __name__ == "__main__":
    unittest.main()
