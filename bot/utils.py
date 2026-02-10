import sys
import os
import requests
import zipfile
from tqdm import tqdm
import random
import string
import logging
import traceback
from concurrent.futures import ThreadPoolExecutor


class ShutdownSignal(Exception):
    """Custom exception to signal a clean shutdown from a command."""
    pass

class RestartSignal(Exception):
    """Custom exception to signal a clean restart from a command."""
    pass


class BotUtils:
    """
    A class for standalone utility functions used by the bot.
    """
    VERSION = "2.3.3"

    @staticmethod
    def load_messages(filename="messages.txt"):
        """Loads messages from a file, stripping whitespace."""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                messages = [line.strip() for line in f]
            return messages
        except FileNotFoundError:
            return ["Welcome, {name}!"]

    @staticmethod
    def load_blacklist(filename="blacklist.txt"):
        """Loads a blacklist from a file, converting to lowercase."""
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return [line.strip().lower() for line in f]
        except FileNotFoundError:
            return []

    @staticmethod
    def check_for_updates(gettext_func):
        """
        Checks for updates, downloads, and extracts them if a new version is found.
        
        Args:
            gettext_func (function): The gettext function (e.g., `bot._`) for translations.
        """
        _ = gettext_func
        update_url = "https://blindmasters.org/tt_utilities/version.txt"
        download_url = "https://blindmasters.org/tt_utilities/tt_utilities.zip"

        try:
            print(_("Checking for updates..."))
            response = requests.get(update_url)
            response.raise_for_status()
            server_version = response.text.strip()

            if server_version > BotUtils.VERSION:
                print(_("A new version has been detected: {server_version}").format(server_version=server_version))
                download_response = requests.get(download_url, stream=True)
                download_response.raise_for_status()
                total_size = int(download_response.headers.get('content-length', 0))
                zip_filename = "tt_utilities_update.zip"
                with open(zip_filename, "wb") as f, tqdm(
                    desc=zip_filename, total=total_size, unit='iB', unit_scale=True, unit_divisor=1024,
                ) as bar:
                    for data in download_response.iter_content(4096):
                        size = f.write(data)
                        bar.update(size)

                with zipfile.ZipFile(zip_filename, "r") as zip_ref:
                    zip_ref.extractall(".")

                print(_("Update downloaded and extracted successfully!"))
                os.remove(zip_filename)
                input(_("Press Enter to quit and run the new version."))
                sys.exit(0)
            else:
                print(_("No updates found. You are running the latest version: {version}").format(version=BotUtils.VERSION))
        except requests.exceptions.RequestException as e:
            print(_("Failed to check for updates: {error}").format(error=e))


    @staticmethod
    def generate_password(length=None):
        """Generates a random password of specified length."""
        if length is None:
            length = random.randint(15, 32)
        characters = string.ascii_letters + string.digits
        return ''.join(random.choice(characters) for _ in range(length))

    @staticmethod
    def parse_duration_string(duration_str):
        """Parses a duration string like '1h:30m:10s' into seconds."""
        if not duration_str:
            raise ValueError("Duration string cannot be empty")
        duration_seconds = 0
        for part in duration_str.replace(" ", "").split(':'):
            if not part: continue
            unit = part[-1].lower()
            try:
                value = int(part[:-1])
                if unit == 's': duration_seconds += value
                elif unit == 'm': duration_seconds += value * 60
                elif unit == 'h': duration_seconds += value * 3600
                elif unit == 'd': duration_seconds += value * 86400
                elif unit == 'w': duration_seconds += value * 604800
                else: raise ValueError(f"Invalid duration unit: {unit}")
            except (ValueError, IndexError):
                raise ValueError(f"Invalid duration part: {part}")
        return duration_seconds

    @staticmethod
    def get_user_location(ip_address):
        """Fetches country and city for a given IP address."""
        if not ip_address or ip_address == "127.0.0.1":
            return "Local", "Host"
        
        base_url = f"http://ip-api.com/json/{ip_address}"
        params = {"fields": "status,message,country,city"}
        try:
            response = requests.get(base_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "success":
                return data.get("country"), data.get("city")
            else:
                print(f"Error getting location for {ip_address}: {data.get('message')}")
                return None, None
        except requests.exceptions.RequestException as e:
            print(f"Error fetching location for {ip_address}: {e}")
            return None, None

    @staticmethod
    def is_vpn(ip_address):
        """Checks if an IP address is likely a VPN/proxy."""
        if not ip_address or ip_address == "127.0.0.1":
            return False
        
        base_url = f"http://ip-api.com/json/{ip_address}"
        params = {"fields": "status,message,proxy"}
        try:
            response = requests.get(base_url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "success":
                return data.get("proxy", False)
            return False
        except requests.exceptions.RequestException:
            return False

    @staticmethod
    def send_telegram_notification(token, chat_id, message):
        """Sends a notification to a specified Telegram chat ID."""
        if not token or not chat_id:
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        try:
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error sending Telegram notification: {e}")


class LoggingThreadPoolExecutor(ThreadPoolExecutor):
    """
    A ThreadPoolExecutor that automatically logs exceptions from submitted tasks.
    """
    def submit(self, fn, *args, **kwargs):
        """
        Wraps the submitted function to catch and log any exceptions.
        """
        def wrapped_fn(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as e:
                exc_info = traceback.format_exc()
                logging.error(f"Exception in thread pool for function '{fn.__name__}':\n{exc_info}")
        
        # Submit the wrapped function to the parent class's submit method
        return super().submit(wrapped_fn, *args, **kwargs)