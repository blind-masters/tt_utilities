import random
import string
from threading import Lock
from TeamTalk5 import Channel, ChannelType, Codec, OPUS_APPLICATION_VOIP, UserType, ttstr
from .utils import BotUtils as utils

class UserManager:
    """
    Manages user-specific state, interactions, and event-driven logic.
    """
    def __init__(self, bot):
        self.bot = bot
        self._ = bot._        
        self.private_channels = {}
        self.private_channel_lock = Lock()
        self.notifications = {}
        self.username_notifications = {}
        self.user_messages = {}
        self.user_ip_info = {}

    def register(self, command_handler):
        """Registers all commands related to user management."""
        command_handler.register_command('private', self.handle_private_channel, help_text=self._("Creates a private, hidden channel with another user. Usage: /private <nickname>"))
        command_handler.register_command('who', self.handle_who_command, help_text=self._("Shows how many users are online from your country."))
        command_handler.register_command('whoall', self.handle_whoall_command, help_text=self._("Shows a summary of all users by country."))
        command_handler.register_command('notify', self.handle_notify_command, help_text=self._("Get a Telegram notification when a user logs in. Usage: /notify <nickname> <telegram_chat_id>"))
        command_handler.register_command('unotify', self.handle_unotify_command, help_text=self._("Get a Telegram notification when a username logs in. Usage: /unotify <username> <telegram_chat_id>"))
        command_handler.register_command('pm', self.handle_tell_command, help_text=self._("Leaves a message for an offline user. Usage: /pm <username> <message>"))
        command_handler.register_command('messages', self.handle_messages_command, help_text=self._("Checks for any pending messages you have sent."))
        command_handler.register_command('users', self.handle_users_command, help_text=self._("Lists detailed information about all online users."))


    def on_user_logged_in(self, user):
        """
        Handles all general logic for when a user logs in.
        """
        nickname = ttstr(user.szNickname)
        username = ttstr(user.szUsername)

        # 1. Handle Notifications
        if nickname in self.notifications:
            chat_id = self.notifications[nickname]["telegram_chat_id"]
            utils.send_telegram_notification(self.bot.telegram_config['telegram_bot_token'], chat_id, self._("Hello. Important: The user {name} has logged in.").format(name=nickname))
            del self.notifications[nickname]
        if username in self.username_notifications:
            chat_id = self.username_notifications[username]["telegram_chat_id"]
            utils.send_telegram_notification(self.bot.telegram_config['telegram_bot_token'], chat_id, self._("Hello. Important: The user {username} has logged in.").format(username=username))
            del self.username_notifications[username]

        # 2. Deliver Pending Messages
        if username in self.user_messages:
            for msg_data in self.user_messages[username]:
                self.bot.privateMessage(user.nUserID, self._("You have a message from {sender_nickname} ({sender_username}): {message}").format(**msg_data))
            del self.user_messages[username]
        
        # 3. Handle Welcome Message and Location-based Actions
        if self.bot.bot_config.get("welcome_broadcast", True):
            country, city = self.get_user_location(user.nUserID)
            if country and city:
                welcome_messages = [
                    self._("Welcome, {nickname} from {country}!").format(nickname=ttstr(user.szNickname), country=country),
                    self._("Ahoy there, {nickname} from {country}! Welcome aboard!").format(nickname=ttstr(user.szNickname), country=country),
                    self._("Greetings, {nickname} of {country}! We're glad to have you here.").format(nickname=ttstr(user.szNickname), country=country),
                    self._("Howdy, {nickname}! Welcome from {country}.").format(nickname=ttstr(user.szNickname), country=country),
                    self._("Whoa! {nickname} just arrived from {country}! Let's party!").format(nickname=ttstr(user.szNickname), country=country),
                    self._("Look who's here! {nickname} from {country} just logged in!").format(nickname=ttstr(user.szNickname), country=country),
                    self._("Good vibes only for {nickname} from {country}! Welcome, my friend!").format(nickname=ttstr(user.szNickname), country=country),
                    self._("Surprise, surprise! It's {nickname} from {country}! Glad to have you!").format(nickname=ttstr(user.szNickname), country=country),
                    self._("Let the fun begin! Welcome, {nickname} from the land of {country}!").format(nickname=ttstr(user.szNickname), country=country)
                ]

                self.bot.send_broadcast_message(random.choice(welcome_messages))
            else:
                self.bot.send_broadcast_message(self._("{nickname} has joined the server").format(nickname=nickname))

    def on_user_parted(self, user):
        """Cleans up all data associated with a user when they leave or log out."""
        user_id = user.nUserID
        if user_id in self.user_ip_info:
            del self.user_ip_info[user_id]
        self.cleanup_private_channel(user)

    def handle_private_channel(self, textmessage, *args):
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command. Usage: /private <second_name>"))
            return
        
        second_name = " ".join(args)
        sender = self.bot.getUser(textmessage.nFromUserID)
        sender_name = ttstr(sender.szNickname)
        self.create_private_channel(sender_name, second_name)

    def handle_who_command(self, textmessage, *args):
        user_id = textmessage.nFromUserID
        self.get_user_location(user_id) # Ensure user's own location is cached
        
        if user_id in self.user_ip_info and self.user_ip_info[user_id].get("country"):
            user_country = self.user_ip_info[user_id]["country"]
            count = sum(1 for info in self.user_ip_info.values() if info.get("country") == user_country)
            
            if count == 1:
                self.bot.privateMessage(user_id, self._("You are the only one from {country}.").format(country=user_country))
            else:
                self.bot.privateMessage(user_id, self._("There are {count} users from {country}.").format(count=count, country=user_country))
        else:
            self.bot.privateMessage(user_id, self._("Sorry, your country information is not available."))

    def handle_whoall_command(self, textmessage, *args):
        user_id = textmessage.nFromUserID
        for user in self.bot.getServerUsers():
            self.get_user_location(user.nUserID)

        country_counts = {}
        for info in self.user_ip_info.values():
            country = info.get("country")
            if country:
                country_counts[country] = country_counts.get(country, 0) + 1

        if country_counts:
            message_parts = [self._("There are {count} users from {country}").format(count=count, country=country) for country, count in country_counts.items()]
            full_message = self._("Currently: ") + ", ".join(message_parts) + "."
            self.bot.privateMessage(user_id, full_message)
        else:
            self.bot.privateMessage(user_id, self._("No country information available for users."))

    def handle_notify_command(self, textmessage, *args):
        try:
            full_args = " ".join(args)
            last_space_index = full_args.rfind(" ")
            if last_space_index == -1: raise ValueError
            
            nickname = full_args[:last_space_index]
            telegram_chat_id = full_args[last_space_index + 1:]

            self.notifications[nickname] = {
                "user_id": textmessage.nFromUserID,
                "telegram_chat_id": telegram_chat_id
            }
            self.bot.privateMessage(textmessage.nFromUserID, self._("Alright. You will be notified when {name} logs in.").format(name=nickname))
        except (ValueError, IndexError):
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command. Usage: /notify <nickname> <telegram_chat_id>"))

    def handle_unotify_command(self, textmessage, *args):
        try:
            full_args = " ".join(args)
            last_space_index = full_args.rfind(" ")
            if last_space_index == -1: raise ValueError

            username = full_args[:last_space_index]
            telegram_chat_id = full_args[last_space_index + 1:]

            self.username_notifications[username] = {
                "user_id": textmessage.nFromUserID,
                "telegram_chat_id": telegram_chat_id
            }
            self.bot.privateMessage(textmessage.nFromUserID, self._("Alright. You will be notified when {username} logs in.").format(username=username))
        except (ValueError, IndexError):
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command. Usage: /unotify <username> <telegram_chat_id>"))

    def handle_tell_command(self, textmessage, *args):
        try:
            target_username = args[0]
            message = " ".join(args[1:])
            if not target_username or not message: raise ValueError()

            sender = self.bot.getUser(textmessage.nFromUserID)
            sender_username = ttstr(sender.szUsername)
            sender_nickname = ttstr(sender.szNickname)
            
            if target_username not in self.user_messages:
                self.user_messages[target_username] = []
                
            self.user_messages[target_username].append({
                "sender_username": sender_username,
                "sender_nickname": sender_nickname,
                "message": message
            })
            self.bot.privateMessage(textmessage.nFromUserID, self._("Your message for {target_username} has been saved.").format(target_username=target_username))
        except (ValueError, IndexError):
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command. Usage: /pm <username> <message>"))
            
    def handle_messages_command(self, textmessage, *args):
        sender = self.bot.getUser(textmessage.nFromUserID)
        sender_username = ttstr(sender.szUsername)
        messages_found = False
        
        for target, messages in self.user_messages.items():
            for msg_data in messages:
                if msg_data["sender_username"] == sender_username:
                    self.bot.privateMessage(textmessage.nFromUserID, self._("Pending message to {target}: {message}").format(target=target, message=msg_data['message']))
                    messages_found = True
        
        if not messages_found:
            self.bot.privateMessage(textmessage.nFromUserID, self._("You have no pending messages."))

    def handle_users_command(self, textmessage, *args):
        recipient_id = textmessage.nFromUserID
        for user in self.bot.getServerUsers():
            if user.nUserID == self.bot.getMyUserID(): continue
            
            country, _ = self.get_user_location(user.nUserID)
            user_type_str = 'Administrator' if user.uUserType == UserType.USERTYPE_ADMIN else "User"
            
            user_info = self._("Nickname: {nickname}\nUsername: {username}\nType: {type}\nFrom: {country}\nStatus message: {status}").format(
                nickname=ttstr(user.szNickname), 
                username=ttstr(user.szUsername),
                type=user_type_str, 
                country=country or "Unknown", 
                status=ttstr(user.szStatusMsg)
            )
            self.bot.privateMessage(recipient_id, user_info)

    
    def get_user_location(self, user_id):
        if user_id in self.user_ip_info:
            return self.user_ip_info[user_id].get("country"), self.user_ip_info[user_id].get("city")
        
        user = self.bot.getUser(user_id)
        if not user or user.nUserID == 0:
            return None, None

        ip_address = ttstr(user.szIPAddress)
        country, city = utils.get_user_location(ip_address)
        if country:
            self.user_ip_info[user_id] = {"country": country, "city": city}
        return country, city

    def create_private_channel(self, sender_name_str, second_name_str):
        sender_name = ttstr(sender_name_str)
        second_name = ttstr(second_name_str)
        
        with self.private_channel_lock:
            for users in self.private_channels.keys():
                if sender_name in users or second_name in users:
                    sender_user = self.bot.getUserByName(sender_name)
                    if sender_user:
                        self.bot.privateMessage(sender_user.nUserID, self._("Either you or {second_name} is already in a private channel.").format(second_name=second_name))
                    return

            sender_user = self.bot.getUserByName(sender_name)
            second_user = self.bot.getUserByName(second_name)

            if not sender_user or not second_user:
                if sender_user:
                    self.bot.privateMessage(sender_user.nUserID, self._("User {second_name} not found.").format(second_name=second_name))
                return

            password = utils.generate_password()
            channel = Channel()
            channel.nParentID = self.bot.getRootChannelID()
            channel.szName = ttstr(f"Private: {sender_name} & {second_name}")
            channel.szPassword = ttstr(password)
            channel.bPassword = True
            channel.uChannelType = ChannelType.CHANNEL_HIDDEN
            channel.nMaxUsers = 2
            channel.audiocodec.nCodec = Codec.OPUS_CODEC
            channel.audiocodec.opus.nBitRate = 96000
            channel.audiocodec.u.opus.nSampleRate = 48000
            channel.audiocodec.u.opus.nChannels = 2
            channel.audiocodec.opus.nFrameSizeMSec = 20
            channel.audiocodec.u.opus.nTxIntervalMSec = 20
            channel.audiocodec.u.opus.nApplication = OPUS_APPLICATION_VOIP
            
            self.bot.doMakeChannel(channel)
            channel_key = tuple(sorted((sender_name, second_name)))
            self.private_channels[channel_key] = channel

            self.bot.privateMessage(sender_user.nUserID, self._("Joining private channel. Password: {password}").format(password=password))
            self.bot.privateMessage(second_user.nUserID, self._("Joining private channel. Password: {password}").format(password=password))
            
            def move_users_to_channel():
                channel_path = f"/{ttstr(channel.szName)}"
                channel_id = 0
                for _ in range(20):
                    channel_id = self.bot.getChannelIDFromPath(ttstr(channel_path))
                    if channel_id != 0: break
                    time.sleep(0.1)
                
                if channel_id != 0:
                    self.bot.doMoveUser(sender_user.nUserID, channel_id)
                    self.bot.doMoveUser(second_user.nUserID, channel_id)
                    self.bot.doChannelOp(sender_user.nUserID, channel_id, bMakeOperator=True)
                    self.bot.doChannelOp(second_user.nUserID, channel_id, bMakeOperator=True)
            
            Thread(target=move_users_to_channel).start()

    def cleanup_private_channel(self, user):
        user_nickname = ttstr(user.szNickname)
        with self.private_channel_lock:
            channel_key_to_delete = None
            for key in self.private_channels:
                if user_nickname in key:
                    channel_key_to_delete = key
                    break
            
            if channel_key_to_delete:
                channel_obj = self.private_channels[channel_key_to_delete]
                channel_path = f"/{ttstr(channel_obj.szName)}"
                channel_id = self.bot.getChannelIDFromPath(ttstr(channel_path))
                if channel_id != 0:
                    self.bot.doRemoveChannel(channel_id)
                del self.private_channels[channel_key_to_delete]