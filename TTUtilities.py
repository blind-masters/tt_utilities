from TeamTalk5 import TeamTalk, User, TextMessage, BanType, ttstr, BannedUser, TextMsgType, Subscription, TTMessage, VideoCodec
import TeamTalk5
import time
import ipinfo
import re
import configparser
import os
import requests
import zipfile
import sys
from tqdm import tqdm
from swagger_client import *
from ctypes import c_int  # Import c_int from ctypes
import ctypes
import random
import threading
import paramiko
import wikipedia
import langdetect
from gtts import gTTS
import ast

def load_messages(filename):
    with open(filename, "r") as f:
        messages = [line.strip() for line in f]
    return messages

def load_blacklist(filename):
    with open(filename, "r") as f:
        blacklist = [line.strip().lower() for line in f]
    return blacklist

if not os.path.exists("files"):
    os.makedirs("files")

class VPNDetectorBot(TeamTalk):

    access_token=""
    handler=ipinfo.getHandler(access_token)

    def __init__(self):
        super().__init__()
        self.just_joined = True
        self.detection_mode = None
        self.excluded_ips = []
        self.doSubscribe(0, Subscription.SUBSCRIBE_USER_MSG)
        self.encrypted=False

        if not os.path.isfile("config.ini"):
            self.create_config_file()
        else:
            self.read_config_file()

    def check_for_updates(self):
        current_version = "1.1"
        update_url = "https://blindmasters.org/TTUtilities/version.txt"
        download_url = "https://blindmasters.org/TTUtilities/TTUtilities.zip"

        try:
            response = requests.get(update_url)
            response.raise_for_status()  # Raise an exception for error status codes

            server_version = response.text.strip()

            if server_version > current_version:
                print(f"A new version has been detected: {server_version}")
                response = requests.get(download_url, stream=True)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                block_size = 4096
                with open("spamKiller.zip", "wb") as f:
                    for data in tqdm(response.iter_content(block_size), total=total_size / block_size, unit='KiB'):
                        f.write(data)

                with zipfile.ZipFile("spamKiller.zip", "r") as zip_ref:
                    zip_ref.extractall(".")

                print("Update downloaded and extracted successfully!")
                input("Press Enter to close the application and apply the update.")
                sys.exit(0)
            else:
                print("No updates found.")

        except requests.exceptions.RequestException as e:
            print(f"Failed to check for updates: {e}")

    def create_config_file(self):
        print("Welcome to TeamTalk utilities bot, a powerful bot, not just for spammers")
        print("\nDeveloped by: Blind masters team")
        print("\nSince it's the first time you open the bot: it will ask you some questions to create the config file, Please follow the instructions carefully and be sure to enter all info correctly.")
        print("\nServer info: ")
        while True:
            server_address = input("Enter server address: ")
            if server_address:
                break
            else:
                print("Error: Server address cannot be blank. Please try again.")
        while True:
            server_port_str = input("Enter server port: ").strip()
            if server_port_str:
                try:
                    server_port = int(server_port_str)
                    break
                except ValueError:
                    print("Error: Invalid server port. Please enter a number.")
            else:
                print("Error: Server port cannot be blank. Please try again.")

        while True:
            print("\nChoose your server type: ")
            print("1: unencrypted server ")
            print("2: encrypted server ")
            try:
                encryption=int(input("Enter your choice: "))
                if encryption==1:
                    self.encrypted=False
                    break
                elif encryption ==2:
                    self.encrypted=True
                    break
            except ValueError:
                print("Invalid choice ")

        while True:
            server_username = input("Enter bot username: ")
            if server_username:
                break
            else:
                print("Error: username cannot be blank, Please try again ")

        while True:
            server_password = input("Enter bot password: ")
            if server_password:
                break
            else:
                print("Error: Please type the password ")

        print("\nDone, now: Please enter the exclution IP addresses you want to exclude, seperate with a comma between each IP ")
        exclusion_ips = input("Enter exclusion IPs (comma-separated): ")
        ipinfo_access_token = input("Enter ipinfo access token, Please read the readme file to know how to get one: ")

        print("\nBot details ")
        while True:
            bot_nickname = input("Enter bot nickname: ")
            if bot_nickname:
                break
            else:
                print("Error: nickname cannot be blank ")

        while True:
            bot_client_name = input("Enter bot client name: ")
            if bot_client_name:
                break
            else:
                print("Client name can't be blank ")

        print("Please note that the following 2 features are optional, the character limit is to prevent long nicknames, if you want to disable it: enter  0 when asked.")
        random_message_interval =int(input("Specify the interval between sending messages, Leave blank to disable: "))

        while True:
            char_limit_str=input("Specify how long the name to kick if the name is longer than this limit, Enter 0 to disable: ")
            if char_limit_str:
                try:
                    char_limit=int(char_limit_str)
                    break
                except ValueError:
                    print("Error: Only numbers are allowed here")

        weather_api_key=input("Enter your weather API key, Please read the readme file for more info on how to get one: ")

        print("\nSSH info, Note: this section is made because in case you want to interact with your SSH server from your bot, and you may skip it if you don't have a server, read the readme file for more info ")
        print("We do not collect such info or share it, because the bot is completely controled by you and no one else, the bot is not connected to any servers to track users or bans them from accessing the bot, Just a reminder in case you're worried about your server info ")
        ssh_hostname = input("Enter SSH hostname: ")
        ssh_port_str = input("Enter SSH port: ")
        if ssh_port_str:
            try:
                ssh_port=int(ssh_port_str)
            except ValueError:
                pass  # defaulting to port 22
        else:
            ssh_port=22

        ssh_username = input("Enter SSH username: ")
        ssh_password = input("Enter SSH password: ")

        print("\nAuthorized usernames or admins: those who can control your SSH server from your bot, you may skip it if you don't have an SSH server")
        authorized_users = input("Enter authorized usernames (comma-separated): ")

        while True:
            print("\nChoose detection mode for accounts: ")
            print("1: guest accounts")
            print("2: All accounts")
            print("3: Custom userName account")
            mode = input("Enter your choice: ")
            if mode in ("1", "2", "3"):
                detection_mode = int(mode)
                break
            else:
                print("Invalid choice. Please enter 1, 2, or 3.")

        custom_username = ""
        if detection_mode == 3:
            custom_username = input("Enter the custom username to detect: ")

        config = configparser.ConfigParser()
        config["server"] = {
            "address": server_address,
            "port": server_port,
            "encrypted": self.encrypted,
            "username": server_username,
            "password": server_password,
        }
        config["bot"] = {
            "nickname": bot_nickname,
            "client_name": bot_client_name,
            "random_message_interval": random_message_interval,
            "char_limit": char_limit,
        }
        config["exclusion"] = {"ips": exclusion_ips}
        config["ipinfo"] = {"access_token": ipinfo_access_token}
        config["accounts"] = {"detection_mode": detection_mode, "custom_username": custom_username, "authorized_users": authorized_users}
        config["weather"] = {"api_key": weather_api_key}
        config["ssh"] = {
            "hostname": ssh_hostname,
            "port": ssh_port,
            "username": ssh_username,
            "password": ssh_password
        }
        with open("config.ini", "w") as configfile:
            config.write(configfile)
            print("\nCreated the config file")

        self.read_config_file()

    def read_config_file(self):
        config = configparser.ConfigParser()
        config.read("config.ini")

        server_section = config["server"]
        self.server_address = server_section.get("address")
        self.server_port = server_section.getint("port")
        self.encrypted = ast.literal_eval(server_section.get("encrypted"))
        self.server_username = server_section.get("username")
        self.server_password = server_section.get("password")

        bot_section = config["bot"]
        self.bot_nickname = bot_section.get("nickname")
        self.bot_client_name = bot_section.get("client_name")
        random_message_interval_str = bot_section.get("random_message_interval")
        if random_message_interval_str:
            self.random_message_interval = int(random_message_interval_str)
        else:
            self.random_message_interval = None
        self.char_limit = bot_section.getint("char_limit")

        exclusion_section = config["exclusion"]
        self.excluded_ips = exclusion_section.get("ips").split(",")

        ipinfo_section = config["ipinfo"]
        self.access_token = ipinfo_section.get("access_token")
        self.handler = ipinfo.getHandler(self.access_token)

        weather_section = config["weather"]
        self.weather_api_key = weather_section.get("api_key")

        accounts_section = config["accounts"]
        self.detection_mode = accounts_section.getint("detection_mode")
        self.custom_username = accounts_section.get("custom_username")
        self.authorized_users = accounts_section.get("authorized_users").split(",")
        ssh_section = config["ssh"]
        self.ssh_hostname = ssh_section.get("hostname")
        self.ssh_port = ssh_section.getint("port")
        self.ssh_username = ssh_section.get("username")
        self.ssh_password = ssh_section.get("password")


    def subscribe_user_messages(self):
        users = self.getServerUsers()

        for user in users:
            result = self.doSubscribe(user.nUserID, Subscription.SUBSCRIBE_USER_MSG)
            print("subscribed to user messages")

    def subscribe_channel_messages(self):
        channel_id = self.getMyChannelID()

        result = self.doSubscribe(channel_id, Subscription.SUBSCRIBE_CHANNEL_MSG)
        print("Subscribed to channel messages")

    def onCmdUserLoggedIn(self, user: User):
        if self.just_joined:
            self.just_joined = False
            return

        blacklist = load_blacklist("blacklist.txt")

        if self.detection_mode == 1:
            if not user.szUsername.startswith("guest"):
                return
        elif self.detection_mode == 3:
            if user.szUsername != custom_username:
                return

        user_id = user.nUserID

        if user.szNickname.lower() in blacklist:
            self.kick_user(user.nUserID)
            return

        if user.szNickname == "" or re.match(r"^NoName\s*(?:-\s*#\d+)?$", user.szNickname):
            self.send_broadcast_message(f"Hay, stranger,(NoName) interduce yourself first and then come back.")
            self.privateMessage(user_id, f"Hay, stranger,(NoName) interduce yourself first and then come back.")
            self.kick_user(user.nUserID)

        ip_address = user.szIPAddress

        if ip_address in self.excluded_ips:
                return

        if self.is_vpn(ip_address):
            self.ban_user(user.nUserID, BanType.BANTYPE_IPADDR)
            self.send_broadcast_message(f"{user.szNickname} has been banned for using a VPN.")
            self.kick_user(user.nUserID)

        if self.char_limit==0:
            return
        elif len(user.szNickname) > self.char_limit:
            self.send_broadcast_message(f"{user.szNickname} has been kicked due to username exceeding 30 characters.")
            self.privateMessage(user_id, f"{user.szNickname} has been kicked due to username exceeding 30 characters.")
            self.kick_user(user.nUserID)

        details = self.handler.getDetails(user.szIPAddress)
        country_name = details.country_name

        self.send_broadcast_message(f"{user.szNickname} from {country_name} has joined the server")

    def onCmdUserTextMessage(self, textmessage: TextMessage):
        print(f"Message received: {textmessage.szMessage} from {textmessage.szFromUsername}")
        blacklist = load_blacklist("blacklist.txt")
        pattern = r"\b(" + "|".join(blacklist) + r")\b"

        if re.search(pattern, textmessage.szMessage, re.IGNORECASE):
            streamer=TeamTalk5.VideoCodec()
            streamer.nCodec=1
            self.startStreamingMediaFileToChannel(os.path.join("files", "blacklist.wav"), streamer)
            self.kick_user(textmessage.nFromUserID)
            return

        if textmessage.szMessage.startswith("/weather"):
            command, *rest = textmessage.szMessage.split(maxsplit=1)

            if textmessage.nMsgType == 1:
                sender_id = textmessage.nFromUserID
                user = self.getUser(sender_id)
                user_ip = user.szIPAddress
                details = self.handler.getDetails(user_ip)
                country_name = details.country_name
                city = details.city

                weather_info = self.get_weather(country_name, city)
                self.privateMessage(sender_id, weather_info)
            else:
                if len(rest) == 0:
                    sender_id = textmessage.nFromUserID
                    user = self.getUser(sender_id)
                    user_ip = user.szIPAddress
                    details = self.handler.getDetails(user_ip)
                    country_name = details.country_name
                    city = details.city
                    self.send_message(self.get_weather(country_name, city))
                else:
                    nickname = rest[0]

                    users = self.getServerUsers()

                    user = None
                    for u in users:
                        if u.szNickname == nickname:
                            user = u
                            break

                    if user is None:
                        self.send_message(f"User '{nickname}' not found.")
                        return

                    user_ip = user.szIPAddress
                    details = self.handler.getDetails(user_ip)
                    country_name = details.country_name
                    city = details.city

                    self.send_message(self.get_weather(country_name, city))
        elif textmessage.szMessage == "/reboot":
            username = textmessage.szFromUsername
            if username.lower() in map(str.strip, map(str.lower, self.authorized_users)):  # Case-insensitive comparison
                self.send_broadcast_message("Attention, The server is rebooting...")
                self.execute_ssh_command(textmessage, self.ssh_hostname, self.ssh_port, self.ssh_username, self.ssh_password, "reboot")
            elif username not in self.authorized_users:
                self.privateMessage(textmessage.nFromUserID, "You don't have permission to reboot the server.")
        elif textmessage.szMessage.startswith("/exec"):
            username = textmessage.szFromUsername
            if username.lower() in map(str.strip, map(str.lower, self.authorized_users)):
                command = textmessage.szMessage.split("/exec ", 1)[1]

                self.execute_ssh_command(textmessage, self.ssh_hostname, self.ssh_port, self.ssh_username, self.ssh_password, command)
            else:
                self.privateMessage(textmessage.nFromUserID, "You don't have permission to execute commands.")
        elif textmessage.szMessage.startswith("/search"):
            query = textmessage.szMessage.split("/search ", 1)[1]
            lang = langdetect.detect(query)
            wikipedia.set_lang(lang)

            try:
                summary = wikipedia.summary(query, sentences=10)

                if isinstance(summary, list):
                    summary = summary[0]  # Get the first result

                if len(summary) > 500:
                    chunks = []
                    while summary:
                        chunk = summary[:500]
                        summary = summary[500:]
                        if summary:
                            last_space = chunk.rfind(" ")
                            if last_space != -1:
                                chunk = chunk[:last_space]
                                summary = chunk[last_space + 1:] + summary
                        chunks.append(chunk)
                    for chunk in chunks:
                        self.privateMessage(textmessage.nFromUserID, chunk)
                else:
                    self.privateMessage(textmessage.nFromUserID, summary)

                page_url = wikipedia.page(query).url
                self.privateMessage(textmessage.nFromUserID, f"Wikipedia link: {page_url}")

            except wikipedia.exceptions.PageError:
                self.privateMessage(textmessage.nFromUserID, "Page not found on Wikipedia.")
            except wikipedia.exceptions.DisambiguationError as e:
                self.privateMessage(textmessage.nFromUserID, f"Multiple pages found for '{query}'. Please be more specific.")
        elif textmessage.szMessage.startswith("/file"):
            query = textmessage.szMessage.split("/file ", 1)[1]
            lang = langdetect.detect(query)
            wikipedia.set_lang(lang)

            try:
                filename = os.path.join("files", f"{query}.html")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(wikipedia.page(query).html())

                self.doSendFile(self.getMyChannelID(), filename)

                self.send_message(f"Wikipedia page for '{query}' uploaded as {filename}")

            except wikipedia.exceptions.PageError:
                self.send_message("Page not found on Wikipedia.")
            except wikipedia.exceptions.DisambiguationError as e:
                self.send_message(f"Multiple pages found for '{query}'. Please be more specific.")
        elif textmessage.szMessage.startswith("/say"):
            text_to_speak = textmessage.szMessage.split("/say ", 1)[1]
            language = langdetect.detect(text_to_speak)

            try:
                if language=="en":
                    tts = gTTS(text=text_to_speak, lang="en-us", tld="us")
                else:
                    tts = gTTS(text=text_to_speak, lang=language)
                tts.save(os.path.join("files", "speech.mp3"))

                streamer=TeamTalk5.VideoCodec()
                streamer.nCodec=1
                self.startStreamingMediaFileToChannel(os.path.join("files", "speech.mp3"), streamer)
            except ValueError:
                self.privateMessage(textmessage.nFromUserID, "Error: language is not supported.")
        elif textmessage.szMessage.startswith("'"):
            try:
                text_to_speak = textmessage.szMessage.split("' ", 1)[1]
            except IndexError:
                pass  

            try:
                if text_to_speak:
                    language = langdetect.detect(text_to_speak)

                    if language=="en":
                        tts = gTTS(text=text_to_speak, lang="en-us", tld="us")
                    else:
                        tts = gTTS(text=text_to_speak, lang=language)
                    tts.save(os.path.join("files", "speech.mp3"))

                    streamer=TeamTalk5.VideoCodec()
                    streamer.nCodec=1
                    self.startStreamingMediaFileToChannel(os.path.join("files", "speech.mp3"), streamer)
            except Exception as e:
                self.privateMessage(textmessage.nFromUserID, "Invalid command: Missing text.")
        else:
            super().onCmdUserTextMessage(textmessage)

    def execute_ssh_command(self, textmessage: TextMessage, hostname, port, username, password, command):
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh_client.connect(self.ssh_hostname, self.ssh_port, username=self.ssh_username, password=self.ssh_password)
            stdin, stdout, stderr = ssh_client.exec_command(command)
            output = stdout.read().decode()
            error = stderr.read().decode()
            if error:
                print(f"Error: {error}")
            else:
                print(f"Output: {output}")
                sender_id = textmessage.nFromUserID
                user = self.getUser(sender_id)
                self.privateMessage(textmessage.nFromUserID, output)
        except Exception as e:
            print(f"SSH connection error: {e}")
        finally:
            ssh_client.close()

    def get_weather(self, country_name, city):
        base_url = "http://api.weatherapi.com/v1/current.json"
        params = {
            "key": self.weather_api_key,
            "q": f"{city}, {country_name}"
        }

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()

            data = response.json()

            temperature = data["current"]["temp_c"]
            condition = data["current"]["condition"]["text"]
            feels_like = data["current"]["feelslike_c"]
            wind_speed = data["current"]["wind_kph"]
            cloudiness = data["current"]["cloud"]
            humidity = data["current"]["humidity"]
            time=data["location"]["localtime"]
            visibility=data["current"]["vis_km"]

            return f"The current weather in {city}, {country_name} is {temperature}°C,  {condition},  \nThe perceived temperature is {feels_like} degrees C, the wind speed is at {wind_speed} kilometers per hour, \nThe cloudiness is of {cloudiness}%, And the visibility is up to {visibility} kilometers, The humidity is {humidity}%, \nThe current time is {time}."
        except requests.exceptions.RequestException as e:
            return f"Error fetching weather data: {e}"

    def privateMessage(self, user_id, message_text):
        message = TextMessage()
        message.nMsgType = 1
        message.nToUserID = user_id
        message.nFromUserID = self.getMyUserID()
        message.szMessage = ttstr(message_text)
        self.doTextMessage(message)

    def send_message(self, message_text):
        message = TextMessage()
        message.nMsgType = TextMsgType.MSGTYPE_CHANNEL
        message.nChannelID = self.getMyChannelID()
        message.szMessage = ttstr(message_text)
        self.doTextMessage(message)

    def is_vpn(self, ip_address):
        handler=ipinfo.getHandler(self.access_token)
        details=handler.getDetails(ip_address)

        if details.all["isEU"]==False:
            return False
        else:
            return True

    def ban_user(self, user_id, ban_type):
        banned_user = BannedUser()
        banned_user.szIPAddress = self.getUser(user_id).szIPAddress
        banned_user.uBanTypes = ban_type

        self.doBan(banned_user)

    def send_broadcast_message(self, message_text):
        message = TextMessage()
        message.nMsgType = TextMsgType.MSGTYPE_BROADCAST
        message.szMessage = ttstr(message_text)
        self.doTextMessage(message)

    def kick_user(self, user_id):
        user_channel_id = self.getUser(user_id).nChannelID
        self.doKickUser(user_id, user_channel_id)
        self.doKickUser(user_id, 0)

    def send_broadcast_messages_at_intervals(self, messages, interval_minutes):
        random.seed()
        while True:
            if self.random_message_interval is not None:
                message = random.choice(messages)
                nickname = self.get_nicknames()

                message = message.format(name=nickname)

                # Send the broadcast message
                self.send_broadcast_message(message)

                time.sleep(self.random_message_interval * 60)

    def get_nicknames(self):
        online_users = self.getServerUsers()
        if online_users:
            random_user = random.choice(online_users)
            return random_user.szNickname
        else:
            return None


if __name__ == "__main__":
    bot = VPNDetectorBot()

    bot.check_for_updates()

    bot.connect(ttstr(bot.server_address), bot.server_port, bot.server_port, bEncrypted=bot.encrypted)
    print("connected successfully")
    print("attempting to login")
    time.sleep(2.5)
    bot.doLogin(ttstr(bot.bot_nickname), ttstr(bot.server_username), ttstr(bot.server_password), ttstr(bot.bot_client_name))
    time.sleep(2.5)
    bot.doJoinChannelByID(ttstr(bot.getRootChannelID()), "")
    print("Logged in successfully")
    bot.subscribe_user_messages()
    bot.subscribe_channel_messages()

    messages = load_messages("messages.txt")
    message_thread = threading.Thread(target=bot.send_broadcast_messages_at_intervals, args=(messages, bot.random_message_interval))
    message_thread.start()

    while True:
        bot.runEventLoop()