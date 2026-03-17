import logging
import os
from typing import Optional
import aiohttp
import asyncio
from pathlib import Path

logger = logging.getLogger(__name__)


class FurAffinityClient:
    """Client for posting to FurAffinity using Selenium browser automation."""

    LOGIN_URL = "https://www.furaffinity.net/login/"
    JOURNAL_URL = "https://www.furaffinity.net/controls/journal/"
    SUBMIT_URL = "https://www.furaffinity.net/submit/"

    def __init__(self, username: str, password: str, selenium_url: Optional[str] = None):
        self.username = username
        self.password = password
        self.selenium_url = selenium_url or os.getenv("SELENIUM_URL", "http://selenium:4444/wd/hub")
        self.driver = None

    # ------------------------------------------------------------------
    # Driver lifecycle
    # ------------------------------------------------------------------

    def _create_driver(self):
        """Create a Selenium WebDriver connected to the remote Chrome service."""
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        try:
            driver = webdriver.Remote(
                command_executor=self.selenium_url,
                options=options,
            )
            driver.implicitly_wait(10)
            logger.info("✅ Selenium remote driver created")
            return driver
        except Exception as e:
            logger.error(f"Failed to create remote Selenium driver: {e}")
            raise

    def _quit_driver(self):
        """Safely quit the WebDriver."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"Error quitting Selenium driver: {e}")
            finally:
                self.driver = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _login(self) -> bool:
        """Log into FurAffinity.  Returns True on success."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            logger.info("Navigating to FurAffinity login page…")
            self.driver.get(self.LOGIN_URL)

            wait = WebDriverWait(self.driver, 15)

            # Fill in username
            username_field = wait.until(
                EC.presence_of_element_located((By.NAME, "name"))
            )
            username_field.clear()
            username_field.send_keys(self.username)

            # Fill in password
            password_field = self.driver.find_element(By.NAME, "pass")
            password_field.clear()
            password_field.send_keys(self.password)

            # Submit the login form
            login_button = self.driver.find_element(By.NAME, "login")
            login_button.click()

            # Wait until we are no longer on the login page
            wait.until(EC.url_changes(self.LOGIN_URL))

            # Verify we are logged in by checking for a logout link
            if "login" in self.driver.current_url:
                logger.error("FurAffinity login failed – still on login page")
                return False

            logger.info("✅ Logged into FurAffinity")
            return True

        except Exception as e:
            logger.error(f"FurAffinity login error: {e}")
            return False

    # ------------------------------------------------------------------
    # Image download helper
    # ------------------------------------------------------------------

    async def download_image(self, image_url: str, max_size_mb: int = 10) -> Optional[str]:
        """Download an image from URL and save it locally.
        
        Args:
            image_url: URL of the image to download
            max_size_mb: Maximum file size in MB (FurAffinity limit is typically 10MB)
        
        Returns:
            Local file path if successful, None otherwise
        """
        try:
            # Create images directory if it doesn't exist
            img_dir = "/config/data/fa_images"
            os.makedirs(img_dir, exist_ok=True)
            
            # Generate unique filename from URL
            from urllib.parse import urlparse
            parsed = urlparse(image_url)
            filename = parsed.path.split('/')[-1]
            if not filename or len(filename) == 0:
                filename = f"image_{int(os.times()[4] * 1000)}.jpg"
            
            local_path = os.path.join(img_dir, filename)
            
            # Download image with aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url, timeout=30) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to download image: HTTP {resp.status}")
                        return None
                    
                    # Check size
                    content = await resp.read()
                    size_mb = len(content) / (1024 * 1024)
                    if size_mb > max_size_mb:
                        logger.warning(f"Image too large ({size_mb:.2f}MB > {max_size_mb}MB), skipping")
                        return None
                    
                    # Save file
                    with open(local_path, 'wb') as f:
                        f.write(content)
                    
                    logger.info(f"✅ Downloaded image: {local_path} ({size_mb:.2f}MB)")
                    return local_path
        
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None

    # ------------------------------------------------------------------
    # Journal posting
    # ------------------------------------------------------------------

    def post_journal(self, title: str, content: str) -> bool:
        """Post a journal entry to FurAffinity.

        Args:
            title:   Journal title (plain text).
            content: Body of the journal (BBCode or plain text).

        Returns:
            True if the journal was submitted successfully, False otherwise.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        try:
            self.driver = self._create_driver()

            if not self._login():
                return False

            logger.info("Navigating to journal submission page…")
            self.driver.get(self.JOURNAL_URL)

            wait = WebDriverWait(self.driver, 15)

            # Subject / title field
            subject_field = wait.until(
                EC.presence_of_element_located((By.NAME, "subject"))
            )
            subject_field.clear()
            subject_field.send_keys(title)

            # Body / content field
            message_field = self.driver.find_element(By.NAME, "message")
            message_field.clear()
            message_field.send_keys(content)

            # Submit button
            submit_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            submit_button.click()

            # Wait for the page to navigate away from the journal editor.
            # A successful submission lands on a journal view page (URL contains /journal/).
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.url_contains("/journal/")
                )
            except Exception:
                current_url = self.driver.current_url
                if "controls/journal" in current_url:
                    logger.warning(f"Journal submission may have failed – URL: {current_url}")
                    return False

            logger.info(f"✅ Journal posted to FurAffinity: {title[:50]}")
            return True

        except Exception as e:
            logger.error(f"FurAffinity journal post error: {e}")
            return False

        finally:
            self._quit_driver()

    # ------------------------------------------------------------------
    # Image submission
    # ------------------------------------------------------------------

    def post_image(
        self,
        image_path: str,
        title: str,
        description: str,
        category: str = "1",
        rating: str = "general",
    ) -> bool:
        """Post an image submission to FurAffinity.

        The submission follows FurAffinity's multi-step upload wizard:
          Step 1 – choose submission type (image)
          Step 2 – upload the file
          Step 3 – fill in metadata and submit

        Args:
            image_path:  Absolute path to the image file on disk.
            title:       Submission title.
            description: Submission description / artist's comments.
            category:    Numeric category ID string (default "1" = Artwork/Digital).
            rating:      "general", "mature", or "adult".

        Returns:
            True if the image was submitted successfully, False otherwise.
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.support.ui import Select

        if not os.path.isfile(image_path):
            logger.error(f"Image file not found: {image_path}")
            return False

        try:
            self.driver = self._create_driver()

            if not self._login():
                return False

            wait = WebDriverWait(self.driver, 15)

            # ── Step 1: choose type ─────────────────────────────────��────
            logger.info("Starting FurAffinity image submission (step 1)…")
            self.driver.get(self.SUBMIT_URL)

            # Select the "image" submission type radio button
            try:
                image_radio = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='submission_type'][value='submission']"))
                )
                image_radio.click()
            except Exception:
                pass  # May already be selected or labelled differently

            next_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"))
            )
            next_button.click()

            # ── Step 2: upload file ──────────────────────────────────────
            logger.info("Uploading image file (step 2)…")
            file_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            file_input.send_keys(image_path)

            next_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"))
            )
            next_button.click()

            # ── Step 3: metadata ─────────────────────────────────────────
            logger.info("Filling in submission metadata (step 3)…")

            # Title
            title_field = wait.until(
                EC.presence_of_element_located((By.NAME, "title"))
            )
            title_field.clear()
            title_field.send_keys(title)

            # Description
            try:
                desc_field = self.driver.find_element(By.NAME, "message")
                desc_field.clear()
                desc_field.send_keys(description)
            except Exception as e:
                logger.warning(f"Could not fill description field: {e}")

            # Category
            try:
                cat_select = Select(self.driver.find_element(By.NAME, "cat"))
                cat_select.select_by_value(category)
            except Exception as e:
                logger.warning(f"Could not set category: {e}")

            # Rating
            # FurAffinity's internal rating values: 0 = General, 1 = Adult (explicit), 2 = Mature (nudity/violence).
            rating_map = {"general": "0", "mature": "2", "adult": "1"}
            rating_value = rating_map.get(rating.lower(), "0")
            try:
                rating_radio = self.driver.find_element(
                    By.CSS_SELECTOR, f"input[name='rating'][value='{rating_value}']"
                )
                rating_radio.click()
            except Exception as e:
                logger.warning(f"Could not set rating: {e}")

            # Submit
            submit_button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], input[type='submit']"))
            )
            submit_button.click()

            # A successful image submission redirects to the view page (URL contains /view/).
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.url_contains("/view/")
                )
            except Exception:
                current_url = self.driver.current_url
                if "submit" in current_url:
                    logger.warning(f"Image submission may have failed – URL: {current_url}")
                    return False

            logger.info(f"✅ Image submitted to FurAffinity: {title[:50]}")
            return True

        except Exception as e:
            logger.error(f"FurAffinity image post error: {e}")
            return False

        finally:
            self._quit_driver()