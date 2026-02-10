# -*- coding: utf-8 -*
from TeamTalk5 import TeamTalk, User, UserType, UserAccount, UserRight, TextMessage, ttstr, TextMsgType, Subscription, TTMessage, VideoCodec, Channel, ChannelType, AudioCodec, OpusCodec, Codec, OPUS_APPLICATION_VOIP, BanType
import TeamTalk5
from bot.command_handler import CommandHandler
from bot.utils import BotUtils as utils, LoggingThreadPoolExecutor
from bot.modules.admin import AdminCog
from bot.modules.general import GeneralCog
from bot.modules.jail import JailCog
from bot.modules.tts import TTSCog
from bot.modules.player import PlayerCog
from bot.modules.translator import TranslatorCog
from bot.user_manager import UserManager
import gettext
import logging
import time
import traceback
from datetime import datetime
import os, sys, re, configparser, argparse
import random
import threading
from threading import Thread, Lock
from concurrent.futures import ThreadPoolExecutor
from bot.player import Player


class TTUtilities(TeamTalk):
    def __init__(self, config_handler, account_creator, cookiefile=None):
        self.config_handler = config_handler
        self.account_creator = account_creator

        # Load config from the config handler
        self.server_config = self.config_handler.get_server_config()
        self.bot_config = self.config_handler.get_bot_config()
        self.playback_config = self.config_handler.get_playback_config()
        self.telegram_config = self.config_handler.get_telegram_config()
        self.exclusion_config = self.config_handler.get_exclusion_config()
        self.accounts_config = self.config_handler.get_accounts_config()
        self.weather_config = self.config_handler.get_weather_config()
        self.ssh_config = self.config_handler.get_ssh_config()
        self.teamtalk_license_config = self.config_handler.get_teamtalk_license_config()
        self.cookiefile = cookiefile or self.playback_config.get("cookiefile_path")

        self.io_pool = None
        self.quick_task_pool = None
        self.player = Player(self.config_handler, cookiefile=self.cookiefile)
        self.command_handler = CommandHandler(self, prefix='/')
        self.commands_locked = False
        self.initialize_connection()
        self._register_cogs()

    def initialize_connection(self):
        """
        Initializes the TeamTalk C-instance, audio devices, and connects to the server.
        This method is safe to call multiple times (after a shutdown).
        """
        super().__init__()
        self.io_pool = LoggingThreadPoolExecutor(max_workers=10, thread_name_prefix='TTBot_IO')
        self.quick_task_pool = LoggingThreadPoolExecutor(max_workers=5, thread_name_prefix='TTBot_Quick')
        
        self.just_joined = True
        self.last_command_sender_id = None
        self.last_command_sender_username = None

        # Set language
        self.language = self.bot_config.get("language")
        gettext.bindtextdomain("messages", "locales")
        gettext.textdomain("messages")
        try:
            translation = gettext.translation("messages", "locales", [self.language])
            translation.install()
            self._ = translation.gettext
        except FileNotFoundError:
            print(f"Language '{self.language}' not found, defaulting to English.")
            translation = gettext.translation("messages", "locales", ["en"])
            translation.install()
            self._ = gettext.gettext

        if self.teamtalk_license_config.get('license_name') and self.teamtalk_license_config.get('license_key'):
            TeamTalk5.setLicense(ttstr(self.teamtalk_license_config['license_name']), ttstr(self.teamtalk_license_config['license_key']))

        utils.check_for_updates(self._)
        try:
            print(self._("Initializing audio devices..."))
            self.initSoundInputDevice(self.playback_config['input_device'])
            print(self._("Audio devices Initialized."))
        except Exception as e:
            print(self._("Error while initializing audio devices: {e}").format(e=e))

        try:
            print(self._("Connecting to {address}:{port}...").format(
                address=self.server_config["address"],
                port=self.server_config["port"]
            ))
            self.connect(ttstr(self.server_config["address"]), self.server_config["port"], self.server_config["port"], bEncrypted=self.server_config.get("encrypted", False))
        except Exception as e:
            logging.error(f"Connection failed during initialization: {e}")
            print(self._("Error: Connection failed. Check server details or network. See errors.log for details."))

    def shutdown(self):
        """Cleanly shuts down all resources used by the bot instance."""
        print("Shutdown sequence started.")
        try:
            print("Terminating media player...")
            self.player.terminate()
            print("Media player terminated.")

            print("Disconnecting from TeamTalk server...")
            self.disconnect()
            print("Disconnected from server.")

            print("Closing TeamTalk instance...")
            self.closeTeamTalk()
            print("TeamTalk instance closed.")

            if self.io_pool:
                print("Shutting down IO thread pool...")
                self.io_pool.shutdown(wait=False)
                print("IO thread pool shutdown initiated.")
            
            if self.quick_task_pool:
                print("Shutting down quick task thread pool...")
                self.quick_task_pool.shutdown(wait=False)
                print("Quick task thread pool shutdown initiated.")

            print("Shutdown complete.")
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")
            print(f"An error occurred during shutdown: {e}")
            traceback.print_exc()

    def _register_cogs(self):
        """Initializes and registers all command cogs."""
        self.general_cog = GeneralCog(self)
        self.user_manager = UserManager(self)
        self.tts_cog = TTSCog(self)
        self.player_cog = PlayerCog(self)
        self.translator_cog = TranslatorCog(self)
        self.admin_cog = AdminCog(self)
        self.jail_cog = JailCog(self)

        cogs_to_register = [
            self.general_cog,
            self.user_manager,
            self.tts_cog,
            self.player_cog,
            self.translator_cog,
            self.admin_cog,
            self.jail_cog
        ]
    
        for cog in cogs_to_register:
            cog.register(self.command_handler)    
        print(self._("All command modules have been registered."))

    def onConnectSuccess(self):
        print(self._("Connected successfully!"))
        self.doLogin(ttstr(self.bot_config["nickname"]), ttstr(self.server_config["username"]), ttstr(self.server_config["password"]), ttstr(self.bot_config["client_name"]))

    def onConnectFailed(self):
        print(self._("Could not connect to server {server_address} port={port}").format(server_address=self.server_config["address"], port=self.server_config["port"]))
        print(self._("Trying to reconnect."))
        self.reconnect()

    def onConnectionLost(self):
        print(self._("Connection lost. Trying to reconnect..."))
        self.reconnect()

    def reconnect(self):
        """Performs a full, in-process reconnect by shutting down and re-initializing."""
        print(self._("Connection lost. Attempting to reconnect in 5 seconds..."))
        self.shutdown()
        time.sleep(5)
        self.initialize_connection()
    
    def onCmdMyselfLoggedIn(self, userid, useraccount):
        print(self._("Logged in successfully"))
        channel_id = self.getChannelIDFromPath(ttstr(self.bot_config['default_channel']))

        if channel_id == 0 or channel_id is None:
            print(self._("Error: Could not get channel ID for default channel."))
        else:
            self.doJoinChannelByID(channel_id, ttstr(self.bot_config['channel_password']))
        self.subscribe_user_messages()
        self.subscribe_channel_messages()
        if self.bot_config["status_message"] is not None:
            self.doChangeStatus(ttstr(self.bot_config["gender"]), ttstr(self.bot_config["status_message"]))
        else:
            self.doChangeStatus(ttstr(self.bot_config["gender"]), ttstr(""))

    def onCmdMyselfKickedFromChannel(self, channelid, user):
        print(self._("I've been kicked from the channel. Reconnecting in 5 seconds..."))
        time.sleep(5)
        self.doLogin(ttstr(self.bot_config["nickname"]), ttstr(self.server_config["username"]), ttstr(self.server_config["password"]), ttstr(self.bot_config["client_name"]))
        time.sleep(0.1)
        self.doJoinChannelByID(self.getRootChannelID(), ttstr(""))
        time.sleep(0.1)
        self.subscribe_user_messages()
        self.subscribe_channel_messages()
        time.sleep(0.1)
        if self.bot_config["status_message"] is not None:
            self.doChangeStatus(ttstr(self.bot_config["gender"]), ttstr(self.bot_config["status_message"]))
        else:
            self.doChangeStatus(ttstr(self.bot_config["gender"]), ttstr(""))
        time.sleep(0.1)
        self.send_broadcast_message(self._("Hey! Why did you kick me?"))

        self.config_handler.read_config_file()

    def subscribe_user_messages(self):
        users = self.getServerUsers()

        for user in users:
            self.doSubscribe(user.nUserID, Subscription.SUBSCRIBE_USER_MSG)
            if self.bot_config['intercept_channel_messages'] is True:
                self.doSubscribe(user.nUserID, 131072)
                print(self._("intercepting channel messages for user {user}").format(user=ttstr(user.szNickname)))
        print(self._("subscribed to user messages"))

    def subscribe_channel_messages(self):
        channel_id = self.getMyChannelID()

        self.doSubscribe(channel_id, Subscription.SUBSCRIBE_CHANNEL_MSG)
        print(self._("Subscribed to channel messages"))

    def onCmdUserLoggedIn(self, user: User):
        if self.just_joined:
            self.just_joined = False
            return
            
        self.subscribe_user_messages()
        if self.accounts_config['detect_server_admins'] is True and user.uUserType == UserType.USERTYPE_ADMIN:
            username_lower = ttstr(user.szUsername).lower()
            if username_lower not in [u.lower() for u in self.accounts_config['authorized_users']]:
                self.accounts_config['authorized_users'].append(ttstr(user.szUsername))

        if ttstr(user.szUsername) in self.exclusion_config["usernames"] or \
           ttstr(user.szNickname) in self.exclusion_config["nicknames"] or \
           ttstr(user.szIPAddress) in self.exclusion_config["ips"]:
            print(self._("User {nickname} is excluded, skipping checks.").format(nickname=ttstr(user.szNickname)))
            return

        user_was_actioned = self.admin_cog.handle_user_login_checks(user)        
        # Only proceed with the welcome message if no action was taken.
        if not user_was_actioned:
            self.user_manager.on_user_logged_in(user)

    def onCmdUserJoinedChannel(self, user: User):
        self.jail_cog.handle_user_join_channel(user)

    def onCmdUserLeftChannel(self, channelid: int, user: User):
        self.user_manager.on_user_parted(user)
        self.translator_cog.on_user_parted(user)
        self.tts_cog.on_user_parted(user)

    def onCmdUserLoggedOut(self, user: User):
        self.user_manager.on_user_parted(user)
        self.translator_cog.on_user_parted(user)
        self.tts_cog.on_user_parted(user)

    def split_long_message(self, message, chunk_size=500):
        chunks = []
        while message:
            chunk = message[:chunk_size]
            message = message[chunk_size:]
            if message:
                last_space = chunk.rfind(" ")
                if last_space != -1:
                    chunk = chunk[:last_space]
                    message = chunk[last_space + 1:] + message
            chunks.append(chunk)
        return chunks

    def onCmdUserTextMessage(self, textmessage: TextMessage):
        message_text = ttstr(textmessage.szMessage)
        print(self._("Message received: {message} from {username}").format(message=message_text, username=ttstr(textmessage.szFromUsername)))
        
        if self.admin_cog.check_message_for_blacklist(textmessage):
            return

        if self.tts_cog.handle_prefixed_message(textmessage):
            return
        if self.player_cog.handle_prefixed_message(textmessage):
            return

        if message_text.startswith(self.command_handler.prefix):
            self.command_handler.handle_message(textmessage)
            return

        self.translator_cog.handle_whisper_translation(textmessage)            
        if self.translator_cog.handle_channel_translation(textmessage):
            return
        if self.translator_cog.handle_private_translation(textmessage):
            return        
        super().onCmdUserTextMessage(textmessage)

    def onCmdChannelNew(self, channel: Channel):
        blacklist = utils.load_blacklist("blacklist.txt")
        if not blacklist:
            return

        pattern = r"\b(" + "|".join(blacklist) + r")\b"
        if re.search(pattern, ttstr(channel.szName), re.IGNORECASE) or re.search(pattern, ttstr(channel.szTopic), re.IGNORECASE):
            self.doRemoveChannel(channel.nChannelID)
            return

    def onUserAccount(self, useraccount: UserAccount):
        username = ttstr(useraccount.szUsername)
        user_type = useraccount.uUserType

        if username == self.last_command_sender_username:
            user = self.getUserByUsername(ttstr(username))  # Get the User object
            if user:
                nickname = ttstr(user.szNickname)
                ip_address = ttstr(user.szIPAddress)
                status_message = ttstr(user.szStatusMsg)
                password = ttstr(useraccount.szPassword)

                info_message = self._("User Info:\n Nickname: {nickname}\n Username: {username}\n Password: {password}\n  IP Address: {ip_address}\n Status Message: {status_message}").format(nickname=nickname, username=username, password=password, status_message=status_message, ip_address=ip_address)
                self.privateMessage(self.last_command_sender_id, info_message)
                self.last_command_sender_id = None
                self.last_command_sender_username = None

    def getUserByName(self, nickname):
        nickname = ttstr(nickname)
        users = self.getServerUsers()
        for user in users:
            if user.szNickname.strip() == nickname:
                return user
        return None

    def privateMessage(self, user_id, message_text):
        message = TextMessage()
        message.nMsgType = 1
        message.nToUserID = user_id
        message.nFromUserID = self.getMyUserID()
        message.szMessage = ttstr(message_text)
        self.doTextMessage(message)

    def send_message(self, message_text, channel_id=None):
        if channel_id is None:
            channel_id=self.getMyChannelID()
        message = TextMessage()
        message.nMsgType = TextMsgType.MSGTYPE_CHANNEL
        message.nChannelID = channel_id
        message.szMessage = ttstr(message_text)
        self.doTextMessage(message)

    def send_broadcast_message(self, message_text):
        message = TextMessage()
        message.nMsgType = TextMsgType.MSGTYPE_BROADCAST
        message.szMessage = ttstr(message_text)
        self.doTextMessage(message)

    def kick_user(self, user_id):
        user_channel_id = self.getUser(user_id).nChannelID
        self.doKickUser(user_id, user_channel_id)
        self.doKickUser(user_id, 0)

    def ban_user(self, user_id, ban_type=BanType.BANTYPE_USERNAME):
        banned_user = BannedUser()
        while True:
            user = self.getUser(user_id)
            if user is not None:
                break
            else:
                continue
        if ban_type == BanType.BANTYPE_IPADDR:
            while True:
                ip_address=user.szIPAddress
                if ip_address is None or ip_address == "":
                    continue
                else:
                    banned_user.szIPAddress =ip_address
                    break
            self.banned_users[user.szIPAddress] = banned_user
            banned_user.uBanTypes =BanType.BANTYPE_IPADDR
        else:
            if user.szUsername=='guest' or user.szUsername==self.accounts_config['custom_username']:
                while True:
                    ip_address=user.szIPAddress
                    if ip_address is None or ip_address == "":
                        continue
                    else:
                        banned_user.szIPAddress =ip_address
                        break
                self.banned_users[user.szIPAddress] = banned_user
                banned_user.uBanTypes =BanType.BANTYPE_IPADDR
            else:
                banned_user.szUsername = user.szUsername
                self.banned_users[user.szUsername] = banned_user
                banned_user.uBanTypes =BanType.BANTYPE_USERNAME
        self.doBan(banned_user)

    def send_broadcast_messages_at_intervals(self, messages):
        random.seed()
        while True:
            if self.bot_config["random_message_interval"] > 0:
                message = random.choice(messages)
                nickname = self.get_random_nickname()

                message = message.format(name=ttstr(nickname))
                self.send_broadcast_message(message)
                time.sleep(self.bot_config["random_message_interval"] * 60)

    def get_random_nickname(self):
        online_users = [u for u in self.getServerUsers() if u.nUserID != self.getMyUserID()]
        if online_users:
            random_user = random.choice(online_users)
            return random_user.szNickname
        else:
            return "Someone"
