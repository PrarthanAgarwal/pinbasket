#!/usr/bin/env python3
"""
Pinterest Board Scraper

A tool to scrape high-quality images from Pinterest boards using Playwright.
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

class PinterestBoardScraper:
    def __init__(self, board_url, output_dir="pinterest_board_images", headless=True, 
                 min_width=800, min_height=800, limit=50, scroll_count=5):
        """
        Initialize the Pinterest board scraper.
        
        Args:
            board_url (str): The URL of the Pinterest board to scrape
            output_dir (str): Directory to save the images
            headless (bool): Whether to run the browser in headless mode
            min_width (int): Minimum width for scraped images
            min_height (int): Minimum height for scraped images
            limit (int): Maximum number of images to download
            scroll_count (int): Number of times to scroll down to load more content
        """
        self.board_url = board_url
        self.output_dir = output_dir
        self.headless = headless
        self.min_width = min_width
        self.min_height = min_height
        self.limit = limit
        self.scroll_count = scroll_count
        self.image_urls = set()
        self.downloaded_count = 0
        
        # Extract board name for file naming
        try:
            self.board_name = board_url.rstrip('/').split('/')[-1]
        except:
            self.board_name = "pinterest_board"

        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def start_scraping(self):
        """Main method to start the scraping process"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
            )
            
            page = await context.new_page()
            
            # Set up request interception for image responses
            await self._setup_interception(page)
            
            try:
                print(f"Navigating to Pinterest board: {self.board_url}...")
                await page.goto(self.board_url, wait_until="domcontentloaded")
                
                # Wait for pins to load
                await page.wait_for_selector('div[data-test-id="pinGrid"]', timeout=10000)
                
                # Scroll to load more images
                print("Scrolling to load more pins...")
                await self._scroll_page(page)
                
                # Click on pins to get high-resolution images
                await self._extract_images_from_pins(page)
                
                # Process images
                print(f"Found {len(self.image_urls)} image URLs. Starting download...")
                await self._download_images()
                
            except Exception as e:
                print(f"An error occurred: {e}")
            finally:
                await browser.close()
                
        print(f"\nSuccessfully downloaded {self.downloaded_count} high-quality images to '{self.output_dir}'")
        return self.downloaded_count
    
    async def _setup_interception(self, page):
        """Set up interception to capture high-quality image URLs"""
        
        # Listen for network responses
        page.on("response", lambda response: asyncio.create_task(self._handle_response(response)))
    
    async def _handle_response(self, response):
        """Process responses to extract high-quality image URLs"""
        if self.limit and len(self.image_urls) >= self.limit:
            return
            
        if response.request.resource_type == "image" and response.status == 200:
            url = response.url
            
            # Focus on original images, not thumbnails
            if url.endswith(('.jpg', '.jpeg', '.png')) and '/originals/' in url:
                self.image_urls.add(url)
                
        # Also check for JSON responses which often contain image metadata
        if response.request.resource_type == "xhr" or response.request.resource_type == "fetch":
            try:
                text = await response.text()
                if '"original_width":' in text and '"original_height":' in text:
                    # Extract image data from JSON
                    matches = re.finditer(r'"original":\s*"([^"]+)".*?"original_width":\s*(\d+).*?"original_height":\s*(\d+)', text)
                    for match in matches:
                        url, width, height = match.groups()
                        width, height = int(width), int(height)
                        
                        # Only keep high-quality images
                        if width >= self.min_width and height >= self.min_height:
                            self.image_urls.add(url.replace("\\", ""))
            except Exception:
                pass
    
    async def _scroll_page(self, page):
        """Scroll down the page to load more images"""
        for i in range(self.scroll_count):
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(2000)  # Wait for new images to load
            
            # Check if we've found enough images
            if self.limit and len(self.image_urls) >= self.limit:
                break
    
    async def _extract_images_from_pins(self, page):
        """Click on pins to load and extract high-resolution images"""
        try:
            # Get all pin elements
            pin_elements = await page.query_selector_all('div[data-test-id="pinWrapper"]')
            
            # Limit the number of pins to process
            pins_to_process = pin_elements[:min(len(pin_elements), self.limit * 2)]
            
            print(f"Found {len(pins_to_process)} pins to process...")
            
            # Process each pin
            for i, pin in enumerate(pins_to_process):
                try:
                    # Click on the pin to open it
                    await pin.click()
                    
                    # Wait for the pin modal to load
                    await page.wait_for_selector('div[data-test-id="closeupImage"]', timeout=5000)
                    
                    # Wait a moment for high-res image to load
                    await page.wait_for_timeout(1000)
                    
                    # Close the pin modal
                    close_button = await page.query_selector('button[aria-label="Close"]')
                    if close_button:
                        await close_button.click()
                    else:
                        await page.keyboard.press("Escape")
                        
                    # Wait for modal to close
                    await page.wait_for_timeout(500)
                    
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
    
    async def _download_images(self):
        """Download the scraped images"""
        # Limit to the specified number of images
        urls_to_download = list(self.image_urls)[:self.limit] if self.limit else list(self.image_urls)
        
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
            # Create a temporary browser context just for this download
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()
                
                # Get the image data
                response = await page.goto(url)
                if not response or response.status != 200:
                    return False
                
                image_data = await response.body()
                
                # Generate a simplified filename
                filename = f"{self.board_name}_{index+1}.jpg"
                filepath = os.path.join(self.output_dir, filename)
                
                # Save the image
                async with aiofiles.open(filepath, 'wb') as f:
                    await f.write(image_data)
                
                # Verify image quality
                try:
                    with Image.open(filepath) as img:
                        width, height = img.size
                        if width < self.min_width or height < self.min_height:
                            os.remove(filepath)
                            return False
                except Exception:
                    return False
                    
                await browser.close()
                return True
                
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False

async def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Scrape high-quality images from Pinterest boards")
    parser.add_argument("board_url", help="URL of the Pinterest board to scrape")
    parser.add_argument("--output", "-o", default="pinterest_board_images", help="Output directory for images")
    parser.add_argument("--limit", "-l", type=int, default=50, help="Maximum number of images to download")
    parser.add_argument("--min-width", type=int, default=800, help="Minimum width for images")
    parser.add_argument("--min-height", type=int, default=800, help="Minimum height for images")
    parser.add_argument("--scroll", type=int, default=5, help="Number of scrolls to perform")
    parser.add_argument("--visible", action="store_false", dest="headless", 
                        help="Run in visible mode (not headless)")
    
    args = parser.parse_args()
    
    scraper = PinterestBoardScraper(
        board_url=args.board_url,
        output_dir=args.output,
        headless=args.headless,
        min_width=args.min_width,
        min_height=args.min_height,
        limit=args.limit,
        scroll_count=args.scroll
    )
    
    await scraper.start_scraping()

if __name__ == "__main__":
    asyncio.run(main()) 