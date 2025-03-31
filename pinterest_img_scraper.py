#!/usr/bin/env python3
"""
Pinterest Image Scraper

A tool to scrape high-quality images from Pinterest using Playwright.
Can scrape from search results or specific Pinterest boards.
"""

import asyncio
import os
import re
import json
import argparse
import aiofiles
import urllib.parse
from datetime import datetime
from tqdm import tqdm
from PIL import Image
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

class PinterestImageScraper:
    def __init__(self, target, is_board=False, output_dir=None, headless=True, 
                 min_width=800, min_height=800, limit=50, scroll_count=5,
                 proxy=None, timeout=30000, email=None, password=None):
        """
        Initialize the Pinterest image scraper.
        
        Args:
            target (str): Either a search query or a board URL
            is_board (bool): Whether the target is a board URL
            output_dir (str): Directory to save the images
            headless (bool): Whether to run the browser in headless mode
            min_width (int): Minimum width for scraped images
            min_height (int): Minimum height for scraped images
            limit (int): Maximum number of images to download
            scroll_count (int): Number of times to scroll down to load more content
            proxy (str): Optional proxy server to use (format: http://user:pass@host:port)
            timeout (int): Timeout in milliseconds for page operations
            email (str): Pinterest account email for login
            password (str): Pinterest account password for login
        """
        self.target = target
        self.is_board = is_board
        self.headless = headless
        self.min_width = min_width
        self.min_height = min_height
        self.limit = limit
        self.scroll_count = scroll_count
        self.image_urls = set()
        self.downloaded_count = 0
        self.proxy = proxy
        self.timeout = timeout
        self.email = email
        self.password = password
        self.debug_mode = not headless
        
        if is_board:
            # Extract board name for file naming
            try:
                self.name = target.rstrip('/').split('/')[-1]
            except:
                self.name = "pinterest_board"
            
            if not output_dir:
                self.output_dir = f"pinterest_board_{self.name}"
            else:
                self.output_dir = output_dir
        else:
            self.name = target.replace(' ', '_')
            if not output_dir:
                self.output_dir = f"pinterest_search_{self.name}"
            else:
                self.output_dir = output_dir

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def start_scraping(self):
        """Main method to start the scraping process"""
        async with async_playwright() as p:
            browser_options = {
                "headless": self.headless
            }
            
            # Add proxy if provided
            if self.proxy:
                browser_options["proxy"] = {
                    "server": self.proxy
                }
            
            browser = await p.chromium.launch(**browser_options)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            )
            
            page = await context.new_page()
            
            # Create a flag to control when to start collecting images
            self.start_collecting = False
            self.inside_search_results = False  # Track if we're in search results
            self.relevant_image_ids = set()  # Track image IDs that are relevant to search
            
            # For ad-related searches, we'll be more permissive
            self.is_ad_search = 'ad' in self.target.lower() or 'ads' in self.target.lower() or 'advert' in self.target.lower()
            
            # Set up request interception for image responses
            await self._setup_interception(page)
            
            try:
                # Log in to Pinterest if credentials are provided
                login_success = False
                if self.email and self.password:
                    print(f"Logging in to Pinterest as {self.email}...")
                    login_success = await self._login(page)
                
                # Even if login fails, continue with the scraping
                if self.is_board:
                    url = self.target
                    print(f"Navigating to Pinterest board: {url}...")
                else:
                    encoded_query = urllib.parse.quote(self.target)
                    url = f"https://www.pinterest.com/search/pins/?q={encoded_query}"
                    print(f"Navigating to Pinterest search results for '{self.target}'...")
                
                # Clear any images collected during login
                print("Clearing any images collected during login phase...")
                self.image_urls.clear()
                
                # Now we start collecting images
                self.start_collecting = True
                print("Starting image collection...")
                
                # Navigate to the search URL
                await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                
                # Handle cookie consent if it appears
                await self._handle_cookie_consent(page)
                
                # Wait for content to load - focus on search-specific selectors first
                print("Waiting for content to load...")
                search_selectors = [
                    'div[data-test-id="search-pins-feed"]',
                    'div[data-test-id="griditems"]',
                    'div[data-test-id="masonry-grid"]',
                    'div.gridCentered',
                    'div[data-test-id="results"]',
                    'div[role="list"]',  # More generic selector for Pinterest lists
                ]
                
                content_loaded = False
                for selector in search_selectors:
                    try:
                        await page.wait_for_selector(selector, timeout=8000)
                        print(f"Found search content with selector: {selector}")
                        content_loaded = True
                        self.inside_search_results = True
                        break
                    except PlaywrightTimeoutError:
                        continue
                
                # If we couldn't find search-specific selectors, try general content selectors
                if not content_loaded:
                    general_selectors = [
                        'div[data-test-id="pinGrid"]',
                        'div[data-grid-item]',
                        'div.Collection-Item',
                        'div[role="list"]',
                        'div[data-test-id="pin"]',
                        'div.GrowthPin',
                        'div.Pin',
                        'img[srcset]',  # Look for any image with srcset
                    ]
                    
                    for selector in general_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            print(f"Found general content with selector: {selector}")
                            content_loaded = True
                            break
                        except PlaywrightTimeoutError:
                            continue
                
                if not content_loaded:
                    print("Could not find content with known selectors. Continuing anyway...")
                    # Take a screenshot to debug
                    screenshot_path = os.path.join(self.output_dir, "debug_screenshot.png")
                    await page.screenshot(path=screenshot_path)
                    print(f"Debug screenshot saved to {screenshot_path}")
                
                # Sometimes Pinterest shows a signup modal - try to close it
                await self._dismiss_signup_modal(page)
                
                # First capture the search result pin IDs - we'll use these to filter relevant images
                if self.inside_search_results and not self.is_board:
                    await self._capture_search_result_ids(page)
                
                # Scroll to load more images
                print("Scrolling to load more content...")
                await self._scroll_page(page)
                
                # If we don't have enough images yet, try clicking on pins
                if len(self.image_urls) < self.limit * 2:  # Try to get more than needed for better selection
                    if self.is_board:
                        await self._extract_images_from_pins(page)
                    else:
                        # For search results, we also need to click on pins to get high-res images
                        await self._extract_images_from_search_results(page)
                
                # Process images
                print(f"Found {len(self.image_urls)} potential image URLs. Starting download...")
                await self._download_images()
                
            except Exception as e:
                print(f"An error occurred: {e}")
                # Take a screenshot for debugging
                try:
                    error_screenshot_path = os.path.join(self.output_dir, "error_screenshot.png")
                    await page.screenshot(path=error_screenshot_path)
                    print(f"Error screenshot saved to {error_screenshot_path}")
                except:
                    pass
            finally:
                await browser.close()
                
        print(f"\nSuccessfully downloaded {self.downloaded_count} high-quality images to '{self.output_dir}'")
        return self.downloaded_count
    
    async def _login(self, page):
        """Log in to Pinterest with provided credentials"""
        try:
            # Go to the login page
            await page.goto('https://pinterest.com/login/', timeout=self.timeout)
            
            # Check if we're already on the login form
            try:
                # Wait for the email input field
                email_selector = await page.wait_for_selector('input[id="email"]', timeout=5000)
                if not email_selector:
                    # Try alternative selectors
                    for selector in ['input[name="id"]', 'input[type="email"]', 'input[placeholder*="email"]']:
                        email_selector = await page.wait_for_selector(selector, timeout=2000)
                        if email_selector:
                            break
                
                if not email_selector:
                    print("Could not find email input field. Continuing without login.")
                    return False
                    
                # Find password field
                password_selector = await page.wait_for_selector('input[id="password"]', timeout=2000)
                if not password_selector:
                    # Try alternative selectors
                    for selector in ['input[name="password"]', 'input[type="password"]', 'input[placeholder*="password"]']:
                        password_selector = await page.wait_for_selector(selector, timeout=2000)
                        if password_selector:
                            break
                
                if not password_selector:
                    print("Could not find password input field. Continuing without login.")
                    return False
                
                # Enter email and password
                await email_selector.fill(self.email)
                await password_selector.fill(self.password)
                
                # Click login button - try different selectors
                login_selectors = [
                    'button[type="submit"]',
                    'button:has-text("Log in")',
                    'button[aria-label*="Log in"]',
                    'button.SignupButton'
                ]
                
                for selector in login_selectors:
                    try:
                        login_button = await page.wait_for_selector(selector, timeout=2000)
                        if login_button:
                            await login_button.click()
                            # Wait for navigation to complete
                            await page.wait_for_load_state("networkidle", timeout=10000)
                            break
                    except PlaywrightTimeoutError:
                        continue
                
                # Check if login was successful - look for profile button
                try:
                    profile_selectors = [
                        'div[data-test-id="header-profile-button"]',
                        'div[aria-label*="Account"]',
                        'div.HeaderProfileButton'
                    ]
                    
                    for selector in profile_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=3000)
                            print("Login successful!")
                            return True
                        except PlaywrightTimeoutError:
                            continue
                    
                    print("Login might have failed or encountered an issue. Continuing anyway.")
                    
                    # Take screenshot for debugging
                    login_screenshot_path = os.path.join(self.output_dir, "login_debug.png")
                    await page.screenshot(path=login_screenshot_path)
                    print(f"Login debug screenshot saved to {login_screenshot_path}")
                    
                except PlaywrightTimeoutError:
                    print("Couldn't verify login. Continuing anyway.")
            
            except PlaywrightTimeoutError:
                print("Login form elements not found. Pinterest may have updated their login page. Continuing without login.")
                login_screenshot_path = os.path.join(self.output_dir, "login_page_debug.png")
                await page.screenshot(path=login_screenshot_path)
                print(f"Login page screenshot saved to {login_screenshot_path}")
        
        except Exception as e:
            print(f"Error during login: {e}. Continuing without login.")
        
        # Even if login fails, continue with the scraping
        return False
    
    async def _handle_cookie_consent(self, page):
        """Handle cookie consent dialog if it appears"""
        try:
            # Try different selectors for cookie consent buttons
            consent_button_selectors = [
                'button[data-test-id="cookie-banner-accept-button"]',
                'button[aria-label="Accept cookies"]',
                'button.acceptCookies',
                'button:has-text("Accept")',
                'button:has-text("Accept all cookies")',
            ]
            
            for selector in consent_button_selectors:
                try:
                    cookie_button = await page.wait_for_selector(selector, timeout=3000)
                    if cookie_button:
                        await cookie_button.click()
                        print("Accepted cookies")
                        await page.wait_for_timeout(1000)  # Wait for dialog to disappear
                        return
                except PlaywrightTimeoutError:
                    continue
        
        except Exception as e:
            print(f"No cookie consent dialog found or error handling it: {e}")
    
    async def _dismiss_signup_modal(self, page):
        """Dismiss signup modal if it appears"""
        try:
            # Try different selectors for close buttons
            close_button_selectors = [
                'button[aria-label="Close"]',
                'button[data-test-id="fullPageSignupClose"]',
                'button[class*="closeup-close-button"]',
                'button.closeBtn',
                'svg[class*="Jea"]',  # Pinterest often uses this class for close buttons
            ]
            
            for selector in close_button_selectors:
                try:
                    close_button = await page.wait_for_selector(selector, timeout=3000)
                    if close_button:
                        await close_button.click()
                        print("Closed signup modal")
                        await page.wait_for_timeout(1000)  # Wait for modal to disappear
                        return
                except PlaywrightTimeoutError:
                    continue
            
            # If no close button found, try pressing escape
            await page.keyboard.press("Escape")
            
        except Exception as e:
            print(f"No signup modal found or error dismissing it: {e}")
    
    async def _setup_interception(self, page):
        """Set up interception to capture high-quality image URLs"""
        
        # Listen for network responses
        page.on("response", lambda response: asyncio.create_task(self._handle_response(response)))
    
    async def _handle_response(self, response):
        """Process responses to extract high-quality image URLs"""
        # Only collect images if start_collecting flag is True
        if not hasattr(self, 'start_collecting') or not self.start_collecting:
            return
        
        if self.limit and len(self.image_urls) >= self.limit * 3:  # Collect more than needed, then filter
            return
            
        # Check if this is a search result page response
        try:
            if response.request.resource_type == "document" or response.request.resource_type == "xhr":
                url = response.url
                # For ad searches, be more permissive with matching
                search_terms = [self.target.lower()]
                if hasattr(self, 'is_ad_search') and self.is_ad_search:
                    search_terms.extend(['ad', 'ads', 'advert', 'advertisement', 'marketing'])
                
                # Check if any search term is in the URL
                for term in search_terms:
                    if "search/pins" in url and term in url.lower():
                        # This is likely the main search results response
                        self.inside_search_results = True
                        
                        # Try to extract pin IDs from search response
                        if response.request.resource_type == "xhr":
                            try:
                                text = await response.text()
                                # Look for our search terms in the response
                                term_found = False
                                for term in search_terms:
                                    if term in text.lower():
                                        term_found = True
                                        break
                                        
                                if term_found and ('pin_join' in text or 'grid_item' in text or 'closeup' in text):
                                    id_matches = re.finditer(r'"id":\s*"(\d+)"', text)
                                    for match in id_matches:
                                        self.relevant_image_ids.add(match.group(1))
                            except:
                                pass
                        break
        except:
            pass
            
        if response.request.resource_type == "image" and response.status == 200:
            url = response.url
            
            # Check if image is likely part of our search results
            is_relevant = False
            
            # For ad searches, be more permissive with determining relevance
            if hasattr(self, 'is_ad_search') and self.is_ad_search:
                is_relevant = True  # Consider all images relevant for ad searches to start
            
            # Check if the URL contains any of our captured pin IDs
            if hasattr(self, 'relevant_image_ids') and self.relevant_image_ids:
                for pin_id in self.relevant_image_ids:
                    if pin_id in url:
                        is_relevant = True
                        break
            
            # If we're not inside search results or it's a board, be more permissive
            if not self.inside_search_results or self.is_board:
                is_relevant = True
                
            # For non-ad searches, if we have relevant IDs, only accept images matching those IDs
            if self.inside_search_results and not self.is_board and not (hasattr(self, 'is_ad_search') and self.is_ad_search):
                if hasattr(self, 'relevant_image_ids') and self.relevant_image_ids and not is_relevant:
                    return
                
            # Skip tiny thumbnails immediately
            if '/60x60/' in url or '/75x75/' in url:
                if self.min_width > 100 or self.min_height > 100:
                    return
            
            # Look for various image URL patterns
            if any(ext in url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']) and \
               any(pattern in url for pattern in ['/originals/', '/236x/', '/474x/', '/736x/', '/1200x/', 'i.pinimg.com']):
                # Convert thumbnail URLs to higher resolution
                high_res_url = self._convert_to_high_res(url)
                
                # Skip if conversion returned None (too small)
                if high_res_url is None:
                    return
                
                # Skip Pinterest UI elements and icons - but be more permissive for ad searches
                skip_patterns = [
                    '/icons/', '/logo/', '/favicon/', '/avatar/', '/profile/', '/spinner/', 
                    '/loading/', '/error/', 'default_', 'placeholder', '/following/',
                    'profile-image', 'avatar.', 'user-image', 'default-user', 'icon_'
                ]
                
                # For ad searches, some UI elements might actually be relevant
                if hasattr(self, 'is_ad_search') and self.is_ad_search:
                    skip_patterns = ['/spinner/', '/loading/', '/error/', 'default_user', 'icon_']
                
                if any(pattern in url.lower() for pattern in skip_patterns):
                    return
                    
                if self.debug_mode:
                    relevance_info = " (RELEVANT)" if is_relevant else ""
                    print(f"Found image URL{relevance_info}: {url}")
                    if high_res_url != url:
                        print(f"Converted to high-res: {high_res_url}")
                
                # Store relevance info with the URL
                self.image_urls.add((high_res_url, is_relevant))

    def _convert_to_high_res(self, url):
        """Convert Pinterest thumbnail URLs to high-resolution versions"""
        # Pinterest uses patterns like /236x/, /474x/, /736x/ for different resolutions
        # We want to convert these to /originals/ or the highest resolution available
        
        # First, check if it's already a high-res URL
        if '/originals/' in url:
            return url
            
        # Don't try to convert very small thumbnails (avatars, icons)
        if '/60x60/' in url or '/75x75/' in url:
            # Skip tiny images that won't meet our size requirements
            if self.min_width > 100 or self.min_height > 100:
                return None
            else:
                return url
                
        # Pattern 1: Replace thumbnail size with 'originals'
        resolution_patterns = ['/236x/', '/474x/', '/736x/', '/1200x/']
        for pattern in resolution_patterns:
            if pattern in url:
                return url.replace(pattern, '/originals/')
                
        # Pattern 2: Handle pinimg.com URLs with size in path
        # Example: https://i.pinimg.com/236x/ab/cd/ef/abcdef123456.jpg
        match = re.search(r'(https://i\.pinimg\.com/)(\d+x/)(.+\.(?:jpg|jpeg|png|webp))', url)
        if match:
            return f"{match.group(1)}originals/{match.group(3)}"
        
        # If no patterns match, return the original URL
        return url
    
    async def _scroll_page(self, page):
        """Scroll down the page to load more images"""
        for i in range(self.scroll_count):
            # Scroll and wait for content to load
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)  # Wait for new images to load
            
            # Occasionally jiggle the scroll to trigger more image loading
            if i % 2 == 1:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.9)")
                await page.wait_for_timeout(500)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(500)
            
            # Check if we've found enough images
            if self.limit and len(self.image_urls) >= self.limit:
                break
                
            # Print current count periodically
            print(f"Current image count after scroll {i+1}: {len(self.image_urls)}")
    
    async def _extract_images_from_pins(self, page):
        """Click on pins to load and extract high-resolution images"""
        try:
            # Get all pin elements - try multiple selectors
            pin_selectors = [
                'div[data-test-id="pinWrapper"]',
                'div[data-grid-item]',
                'div.Pin',
                'div[data-test-id="pin"]',
                'div.GrowthPin',
            ]
            
            pin_elements = []
            for selector in pin_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        pin_elements = elements
                        print(f"Found {len(elements)} pins with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not pin_elements:
                print("No pins found to process.")
                return
            
            # Limit the number of pins to process
            pins_to_process = pin_elements[:min(len(pin_elements), self.limit * 2)]
            
            print(f"Processing {len(pins_to_process)} pins...")
            
            # Process each pin
            for i, pin in enumerate(pins_to_process):
                try:
                    # Click on the pin to open it
                    await pin.scroll_into_view_if_needed()
                    await pin.click()
                    
                    # Wait for the pin modal to load - try multiple selectors
                    pin_modal_selectors = [
                        'div[data-test-id="closeupImage"]',
                        'div[data-test-id="pin-closeup"]',
                        'div[data-test-id="PinCloseupContent"]',
                        'div.closeupContainer',
                    ]
                    
                    modal_found = False
                    for selector in pin_modal_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            modal_found = True
                            break
                        except PlaywrightTimeoutError:
                            continue
                    
                    if not modal_found:
                        print(f"Pin modal not found for pin {i}")
                        # Try to close whatever might be open
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(500)
                        continue
                    
                    # Wait a moment for high-res image to load
                    await page.wait_for_timeout(1500)
                    
                    # Close the pin modal
                    close_button = await page.query_selector('button[aria-label="Close"]')
                    if close_button:
                        await close_button.click()
                    else:
                        await page.keyboard.press("Escape")
                        
                    # Wait for modal to close
                    await page.wait_for_timeout(800)
                    
                    # Check if we've found enough images
                    if self.limit and len(self.image_urls) >= self.limit:
                        break
                        
                except Exception as e:
                    print(f"Error processing pin {i}: {e}")
                    # Try to close modal if it's still open
                    try:
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(500)
                    except:
                        pass
                    
        except Exception as e:
            print(f"Error extracting images from pins: {e}")
    
    async def _extract_images_from_search_results(self, page):
        """Extract images from search results by clicking on pins"""
        try:
            # First, try to find pins that are clearly part of search results
            search_grid_selectors = [
                'div[data-test-id="search-pins-feed"] div[data-grid-item]',
                'div[data-test-id="griditems"] div[data-grid-item]',
                'div[data-test-id="masonry-grid"] div[data-grid-item]',
                'div.gridCentered div[data-grid-item]',
                'div[data-test-id="results"] div[data-grid-item]',
                'div[role="list"] div[data-test-id="pin"]',
                'div[role="list"] div', # More generic selector
                'img[srcset]', # Direct image selector
            ]
            
            pin_elements = []
            for selector in search_grid_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    if elements and len(elements) > 0:
                        pin_elements = elements
                        print(f"Found {len(elements)} pins in search results with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not pin_elements:
                # Fall back to any pin elements if we couldn't find search-specific ones
                await self._extract_images_from_pins(page)
                return
                
            # Limit the number of pins to process - focus on the most relevant ones first
            pins_to_process = pin_elements[:min(len(pin_elements), self.limit * 3)]  # Process more pins than we need
            
            print(f"Processing {len(pins_to_process)} pins from search results...")
            
            # Process each pin
            for i, pin in enumerate(pins_to_process):
                try:
                    if self.limit and len(self.image_urls) >= self.limit * 2:  # Collect more than needed, then filter
                        break
                        
                    # For ad searches, don't skip product pins
                    is_product = False
                    if not (hasattr(self, 'is_ad_search') and self.is_ad_search):
                        try:
                            product_indicator = await pin.query_selector('span:has-text("Product")')
                            if product_indicator:
                                is_product = True
                                # Skip product pins for non-ad searches
                                continue
                        except:
                            pass
                    
                    # Scroll pin into view and click it
                    await pin.scroll_into_view_if_needed()
                    await page.wait_for_timeout(500)  # Increased delay for stability
                    await pin.click()
                    
                    # Wait for the pin modal to load - try multiple selectors
                    pin_modal_selectors = [
                        'div[data-test-id="closeupImage"]',
                        'div[data-test-id="pin-closeup"]',
                        'div[data-test-id="PinCloseupContent"]',
                        'div.closeupContainer',
                        'div[role="dialog"]'
                    ]
                    
                    modal_found = False
                    for selector in pin_modal_selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                            modal_found = True
                            break
                        except PlaywrightTimeoutError:
                            continue
                    
                    if not modal_found:
                        print(f"Pin modal not found for pin {i}")
                        # Try to close whatever might be open
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(800)
                        continue
                    
                    # Wait longer for high-res image to load (especially important for ad images)
                    await page.wait_for_timeout(3000)
                    
                    # Try to capture the pin ID from the URL to mark images as relevant
                    try:
                        current_url = page.url
                        pin_id_match = re.search(r'/pin/(\d+)', current_url)
                        if pin_id_match:
                            pin_id = pin_id_match.group(1)
                            self.relevant_image_ids.add(pin_id)
                    except:
                        pass
                    
                    # Close the pin modal
                    close_button = await page.query_selector('button[aria-label="Close"]')
                    if close_button:
                        await close_button.click()
                    else:
                        # Try closing with keyboard
                        await page.keyboard.press("Escape")
                        
                    # Wait for modal to close
                    await page.wait_for_timeout(1000)
                        
                except Exception as e:
                    print(f"Error processing pin {i}: {e}")
                    # Try to close modal if it's still open
                    try:
                        await page.keyboard.press("Escape")
                        await page.wait_for_timeout(800)
                    except:
                        pass
                    
        except Exception as e:
            print(f"Error extracting images from search results: {e}")
            # Fall back to regular pin extraction if this method fails
            await self._extract_images_from_pins(page)
    
    async def _download_images(self):
        """Download the scraped images"""
        # Extract URLs and relevance info
        all_urls = list(self.image_urls)
        
        # Split into relevant and non-relevant images
        relevant_urls = [url for url, is_relevant in all_urls if is_relevant]
        other_urls = [url for url, is_relevant in all_urls if not is_relevant]
        
        # Print stats
        print(f"Found {len(relevant_urls)} relevant image URLs and {len(other_urls)} other image URLs")
        
        # For ad searches, consider all images as potentially relevant
        unique_urls = []
        if hasattr(self, 'is_ad_search') and self.is_ad_search:
            unique_urls = list(set(relevant_urls + other_urls))
            print(f"Ad search: Using all {len(unique_urls)} images")
        else:
            # Prioritize relevant images, only use others if needed
            if len(relevant_urls) >= self.limit:
                unique_urls = relevant_urls
                print(f"Using only relevant images for download")
            else:
                # If we don't have enough relevant images, include some non-relevant ones
                needed_count = self.limit - len(relevant_urls)
                print(f"Using {len(relevant_urls)} relevant images plus {needed_count} additional images")
                unique_urls = relevant_urls + other_urls[:needed_count]
        
        if not unique_urls:
            print("No images found to download.")
            return
            
        # Sort URLs by resolution indicators (prioritize originals and larger sizes)
        def get_url_priority(url):
            # Higher number = higher priority
            if '/originals/' in url:
                return 5
            elif '/1200x/' in url:
                return 4
            elif '/736x/' in url:
                return 3
            elif '/474x/' in url:
                return 2
            elif '/236x/' in url:
                return 1
            else:
                return 0
                
        sorted_urls = sorted(unique_urls, key=get_url_priority, reverse=True)
        
        # Limit to the specified number of images
        urls_to_download = sorted_urls[:self.limit] if self.limit else sorted_urls
        
        # Create download tasks
        tasks = []
        for i, url in enumerate(urls_to_download):
            tasks.append(self._download_image(url, i))
        
        # Use tqdm to display a progress bar
        for task in tqdm(asyncio.as_completed(tasks), total=len(tasks), desc="Downloading images"):
            result = await task
            if result:
                self.downloaded_count += 1
    
    async def _download_image(self, url, index):
        """Download a single image"""
        try:
            # Generate a filename first
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{self.name}_{timestamp}_{index:03d}.jpg"
            filepath = os.path.join(self.output_dir, filename)
            
            # Try to download using a simpler direct request first
            try:
                # Create a temporary browser context just for this download
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await browser.new_context()
                    page = await context.new_page()
                    
                    # Get the image data
                    response = await page.goto(url, timeout=30000)
                    if not response or response.status != 200:
                        if self.debug_mode:
                            print(f"Failed to download image {url}, status: {response.status if response else 'No response'}")
                        return False
                    
                    # Check if content type is image
                    content_type = response.headers.get('content-type', '')
                    if not content_type.startswith('image/'):
                        if self.debug_mode:
                            print(f"URL doesn't point to an image. Content-Type: {content_type}")
                        return False
                    
                    image_data = await response.body()
                    
                    # First verify image dimensions from memory before saving to disk
                    try:
                        from io import BytesIO
                        with Image.open(BytesIO(image_data)) as img:
                            width, height = img.size
                            
                            # Print image dimensions in debug mode
                            if self.debug_mode:
                                print(f"Image dimensions: {width}x{height} (min required: {self.min_width}x{self.min_height})")
                                
                            # More lenient quality check - either width OR height needs to be sufficient
                            if width < self.min_width and height < self.min_height:
                                if self.debug_mode:
                                    print(f"Skipping image (too small): {width}x{height}, minimum required: {self.min_width}x{self.min_height}")
                                return False
                    except Exception as e:
                        if self.debug_mode:
                            print(f"Error checking image dimensions from memory: {e}")
                        # Continue anyway and try to save the file
                    
                    # Only save the file if it passes the size check
                    async with aiofiles.open(filepath, 'wb') as f:
                        await f.write(image_data)
                    
                    # Final verification that file exists and is valid
                    try:
                        # Ensure file is properly closed before verification
                        await page.wait_for_timeout(100)  # Short delay to ensure file is written
                        
                        with Image.open(filepath) as img:
                            width, height = img.size
                            
                            # Print image dimensions in debug mode
                            if self.debug_mode:
                                print(f"Downloaded image {filename}: {width}x{height}")
                                
                            # More lenient quality check - either width OR height needs to be sufficient
                            if width < self.min_width and height < self.min_height:
                                if self.debug_mode:
                                    print(f"Image {filename} is too small: {width}x{height}, minimum required: {self.min_width}x{self.min_height}")
                                try:
                                    # Close the image before trying to delete
                                    del img
                                    import gc
                                    gc.collect()  # Force garbage collection
                                    os.remove(filepath)
                                    if self.debug_mode:
                                        print(f"Deleted small image: {filename}")
                                except Exception as del_err:
                                    if self.debug_mode:
                                        print(f"Warning: Couldn't delete small image {filename}: {del_err}")
                                return False
                            
                            # If we succeeded, return True
                            return True
                            
                    except Exception as e:
                        if self.debug_mode:
                            print(f"Error verifying image {filename}: {e}")
                        # Don't try to delete if verification fails, it might be in use
                    
                await browser.close()
            
            except Exception as e:
                if self.debug_mode:
                    print(f"Error with Playwright download for {url}: {e}")
                # If Playwright method fails, fall back to direct download
                
            # Return True if we succeeded
            return True
                
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False

    async def _capture_search_result_ids(self, page):
        """Capture the IDs of pins that are in the search results to filter relevant images"""
        try:
            # Look for pin IDs in the main search grid
            print("Identifying search result pins...")
            
            # Get data-ids from pins in search results
            search_pin_selectors = [
                'div[data-test-id="search-pins-feed"] div[data-test-id="pin"]',
                'div[data-test-id="search-pins-feed"] div[data-grid-item]',
                'div[data-test-id="griditems"] div[data-grid-item]',
                'div.gridCentered div[data-grid-item]',
                'div[role="list"] div[data-test-id="pin"]'
            ]
            
            for selector in search_pin_selectors:
                pin_elements = await page.query_selector_all(selector)
                if pin_elements and len(pin_elements) > 0:
                    print(f"Found {len(pin_elements)} pins in search results with {selector}")
                    
                    for pin in pin_elements:
                        # Try to get pin ID from various attributes
                        pin_id = None
                        for attr in ['data-test-pin-id', 'data-id', 'id']:
                            try:
                                pin_id = await pin.get_attribute(attr)
                                if pin_id and pin_id.strip():
                                    break
                            except:
                                continue
                                
                        if pin_id:
                            self.relevant_image_ids.add(pin_id)
                            
                    if self.relevant_image_ids:
                        print(f"Identified {len(self.relevant_image_ids)} pins from search results")
                        return
                        
            # If we couldn't find pin IDs through attributes, try to extract from URLs
            links = await page.query_selector_all('a[href*="/pin/"]')
            for link in links:
                href = await link.get_attribute('href')
                if href and '/pin/' in href:
                    # Extract pin ID from URL like /pin/123456789/
                    match = re.search(r'/pin/(\d+)', href)
                    if match:
                        pin_id = match.group(1)
                        self.relevant_image_ids.add(pin_id)
            
            if self.relevant_image_ids:
                print(f"Identified {len(self.relevant_image_ids)} pins from search result links")
                
        except Exception as e:
            print(f"Error capturing search result IDs: {e}")

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Scrape high-quality images from Pinterest")
    
    # Define source group (either search query or board URL)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--query", "-q", help="Search query for Pinterest")
    source_group.add_argument("--board", "-b", help="URL of the Pinterest board to scrape")
    
    parser.add_argument("--output", "-o", help="Output directory for images")
    parser.add_argument("--limit", "-l", type=int, default=50, help="Maximum number of images to download")
    parser.add_argument("--min-width", type=int, default=800, help="Minimum width for images")
    parser.add_argument("--min-height", type=int, default=800, help="Minimum height for images")
    parser.add_argument("--scroll", type=int, default=5, help="Number of scrolls to perform")
    parser.add_argument("--visible", action="store_false", dest="headless", 
                        help="Run in visible mode (not headless)")
    parser.add_argument("--timeout", type=int, default=30000, 
                        help="Timeout in milliseconds for page operations")
    parser.add_argument("--proxy", help="Proxy server to use (format: http://user:pass@host:port)")
    parser.add_argument("--email", help="Pinterest account email for login")
    parser.add_argument("--password", help="Pinterest account password for login")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with more verbose output")
    
    args = parser.parse_args()
    
    # Determine if we're using a search query or board URL
    if args.query:
        target = args.query
        is_board = False
    else:
        target = args.board
        is_board = True
    
    # If debug mode is enabled, force visible browser
    if args.debug:
        args.headless = False
    
    scraper = PinterestImageScraper(
        target=target,
        is_board=is_board,
        output_dir=args.output,
        headless=args.headless,
        min_width=args.min_width,
        min_height=args.min_height,
        limit=args.limit,
        scroll_count=args.scroll,
        proxy=args.proxy,
        timeout=args.timeout,
        email=args.email,
        password=args.password
    )
    
    await scraper.start_scraping()

if __name__ == "__main__":
    asyncio.run(main()) 