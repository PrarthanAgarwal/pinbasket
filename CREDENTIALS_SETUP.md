# Setting Up Pinterest Credentials Securely

When using PinBasket, you may want to authenticate with your Pinterest account to access more content and avoid rate limiting. This guide explains how to set up your credentials securely without compromising your account information.

## Option 1: Using Environment Variables (Recommended)

### For Windows Users

1. Run the provided `setup_credentials.bat` script:
   ```
   setup_credentials.bat
   ```

2. Enter your Pinterest email and password when prompted.

3. The script will create environment variables on your system and generate a `set_pinterest_env.bat` file. These files are automatically ignored by git.

4. Now when you run `pinterest_search.bat`, it will automatically use your stored credentials.

### For macOS/Linux Users

1. Add the following lines to your `~/.bashrc`, `~/.zshrc`, or equivalent shell configuration file:
   ```bash
   export PINTEREST_EMAIL="your.email@example.com"
   export PINTEREST_PASSWORD="your_password"
   ```

2. Reload your shell configuration:
   ```bash
   source ~/.bashrc   # or source ~/.zshrc
   ```

3. Run the scraper, and it will automatically use your credentials.

## Option 2: Manual Entry Each Time

If you prefer not to store your credentials at all, you can simply run `pinterest_search.bat` without setting up environment variables. The script will prompt you to enter your credentials when needed.

## Option 3: Using a .env File (Advanced)

1. Create a file named `.env` in the project root with the following content:
   ```
   PINTEREST_EMAIL=your.email@example.com
   PINTEREST_PASSWORD=your_password
   ```

2. Install the python-dotenv package:
   ```
   pip install python-dotenv
   ```

3. The scraper will automatically load these credentials if you modify the Python code to use python-dotenv.

## Security Considerations

- **Never commit credential files to git** - all credential files are added to .gitignore
- **Avoid storing credentials in plaintext** if possible
- **Use a Pinterest account dedicated to scraping** rather than your main account
- **Regularly change your password** if using the scraper frequently

## Troubleshooting

If you're experiencing issues with authentication:

1. Make sure your credentials are correctly set up
2. Check if Pinterest has implemented new login security measures
3. Try running in visible mode to see if any captchas or verification steps appear 