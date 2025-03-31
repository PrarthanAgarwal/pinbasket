# 🖼️ PinBasket: Your Pinterest Image Scraping Sidekick!

> *"Because manually saving Pinterest images is so 2010..."*

## 🚀 What is PinBasket?

PinBasket is a powerful, high-performance Pinterest image scraper that helps you collect high-quality images from Pinterest searches and boards. Whether you're building a mood board, gathering design inspiration, or collecting reference images for an AI training dataset, PinBasket has got you covered!

### ✨ Features

- 🔍 **Search Mode**: Scrape images from Pinterest search results
- 📌 **Board Mode**: Extract all images from specific Pinterest boards
- 🖼️ **Quality Control**: Filter images by minimum dimensions
- 🚄 **Lightning Fast**: Asynchronous downloading for maximum speed
- 🧠 **Smart Scrolling**: Automatically scrolls to find more content
- 🔐 **Login Support**: Authenticate with your Pinterest account
- 👀 **Visible or Headless**: Run with or without browser UI
- 🌐 **Proxy Support**: Use proxies for anonymity and to avoid rate limits

## 📋 Prerequisites

- Python 3.8+
- Windows, macOS, or Linux

## 🔧 Installation

### Windows (Easy Setup)

1. **Clone this repository or download the files**

2. **Run the setup script**
   ```
   Double-click on setup_venv.bat
   ```
   This script will:
   - Create a virtual environment
   - Install all required dependencies
   - Set up Playwright browsers
   
3. **Set up credentials (optional)**
   ```
   Double-click on setup_credentials.bat
   ```

### Manual Setup

1. **Clone this repository or download the files**

2. **Set up a virtual environment (recommended)**
   ```batch
   python -m venv venv
   venv\Scripts\activate  # Windows
   # OR
   source venv/bin/activate  # macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

5. **Set up credentials (optional but recommended)**
   ```bash
   # On Windows
   setup_credentials.bat
   
   # On macOS/Linux
   # See CREDENTIALS_SETUP.md for instructions
   ```
   For more details on secure credential handling, see [CREDENTIALS_SETUP.md](CREDENTIALS_SETUP.md)

## 🎮 Usage

### 🖥️ Using the Interactive Batch File (Windows)

The easiest way to run PinBasket is to use the included batch file:

1. Double-click on `pinterest_search.bat`
2. Enter your search query when prompted
3. Specify the number of images to download (default: 10)
4. Set the scroll count for loading more images (default: 5)
5. Sit back and watch PinBasket do its magic!

> **Note:** The batch file will automatically activate the virtual environment, so you don't need to worry about activating it manually.

### ⌨️ Command Line Usage

If you prefer to use the command line directly (make sure your virtual environment is activated):

#### Scraping from a Search Query

```bash
python pinterest_img_scraper.py --query "aesthetic wallpapers" --limit 20 --scroll 5
```

#### Scraping from a Pinterest Board

```bash
python pinterest_img_scraper.py --board "https://www.pinterest.com/username/boardname/" --limit 50
```

#### Running with Your Pinterest Account

```bash
python pinterest_img_scraper.py --query "minimalist logos" --email "your@email.com" --password "yourpassword"
```

### 🔐 Secure Credential Handling

For security reasons, it's recommended to use environment variables for credentials instead of passing them directly:

1. Set environment variables:
   ```
   # Windows
   set PINTEREST_EMAIL=your@email.com
   set PINTEREST_PASSWORD=yourpassword
   
   # macOS/Linux
   export PINTEREST_EMAIL=your@email.com
   export PINTEREST_PASSWORD=yourpassword
   ```

2. Run the script without email/password arguments:
   ```bash
   python pinterest_img_scraper.py --query "minimalist logos"
   ```

The script will automatically use the environment variables. See [CREDENTIALS_SETUP.md](CREDENTIALS_SETUP.md) for more details.

### 🎛️ Advanced Options

PinBasket offers many customization options:

```
--limit NUMBER       Maximum number of images to download (default: 50)
--scroll NUMBER      Number of page scrolls to perform (default: 5)
--min-width NUMBER   Minimum image width to download (default: 800)
--min-height NUMBER  Minimum image height to download (default: 800)
--output DIRECTORY   Custom output directory for downloaded images
--visible            Run in visible mode (show browser UI)
--proxy URL          Use a proxy server (format: http://user:pass@host:port)
--timeout NUMBER     Timeout in ms for page operations (default: 30000)
```

## 📚 How It Works

PinBasket uses Playwright, a modern browser automation library, to:

1. 🖥️ Launch a browser (either visible or headless)
2. 🔍 Navigate to Pinterest search results or a board
3. 📜 Scroll the page to load more images
4. 🕵️ Intercept network requests to find high-resolution image URLs
5. 👮 Filter images by quality (dimensions)
6. ⬇️ Download images asynchronously with progress bars
7. 🖼️ Save the images to your specified output directory

## 🎭 The Three Musketeers

This project includes three Python scripts for different use cases:

- **pinterest_img_scraper.py**: The full-featured main scraper (recommended)
- **pinterest_scraper.py**: A simpler version for scraping from search results 
- **pinterest_board_scraper.py**: A specialized version for scraping only from boards


## 🤔 Troubleshooting

- **No images downloaded?** Try increasing the scroll count or check your search terms
- **Script crashes?** Make sure you have the latest version of Playwright and dependencies
- **Pinterest blocking requests?** Try using your account (email/password) or a proxy
- **Images too small?** Adjust the min-width and min-height parameters

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgements

- [Playwright](https://playwright.dev/) for browser automation
- [asyncio](https://docs.python.org/3/library/asyncio.html) for asynchronous operations
- [PIL/Pillow](https://pillow.readthedocs.io/) for image handling
- [tqdm](https://tqdm.github.io/) for those cool progress bars

---

## 📸 Happy Collecting! 📸

Made with ❤️ by a Pinterest enthusiast 