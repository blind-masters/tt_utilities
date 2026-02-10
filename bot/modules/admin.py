from TeamTalk5 import BanType, BannedUser, UserAccount, UserType, TextMsgType, TextMessage, ttstr
from bot.utils import BotUtils as utils, ShutdownSignal, RestartSignal
import TeamTalk5 as teamtalk
import time
from threading import Thread
import paramiko
import re
import os

class AdminCog:
    """
    A module for handling all administrator-level commands.
    """
    def __init__(self, bot):
        self.bot = bot
        self._ = bot._        
        self.duration_kicks = {}
        self.pending_kicks = {}
        self.banned_users = {}
        self.duration_bans = {}

    def register(self, command_handler):
        """Registers all the admin commands."""
        command_handler.register_command('reboot', self.handle_reboot_command, admin_only=True, help_text=self._("Reboots the server."))
        command_handler.register_command('exec', self.handle_exec_command, admin_only=True, help_text=self._("Executes a command on the server via SSH. Usage: /exec <command>"))
        command_handler.register_command('db', self.handle_duration_ban_ip, admin_only=True, help_text=self._("Bans a user by IP for a duration. Usage: /db <name> <duration> (e.g., 1h30m)"))
        command_handler.register_command('udb', self.handle_duration_ban_user, admin_only=True, help_text=self._("Bans a username for a duration. Usage: /udb <username> <duration>"))
        command_handler.register_command('dk', self.handle_duration_kick_nickname, admin_only=True, help_text=self._("Kicks a user by nickname for a duration. Usage: /dk <name> <duration>"))
        command_handler.register_command('udk', self.handle_duration_kick_by_username, admin_only=True, help_text=self._("Kicks a user by username for a duration. Usage: /udk <username> <duration>"))
        command_handler.register_command('bm', self.handle_admin_broadcast, admin_only=True, help_text=self._("Sends a broadcast message to all users on the server. Usage: /bm <message>"))
        command_handler.register_command('clear', self.handle_clear_command, admin_only=True, help_text=self._("Clears a temporary ban/kick. Usage: /clear <name/ip/username> or /clear without arguments to clear all temporary bans / kicks."))
        command_handler.register_command('cn', self.handle_change_name_command, admin_only=True, help_text=self._("Changes the bot's nickname. Usage: /cn <new_name>"))
        command_handler.register_command('save', self.save_bot_config, admin_only=True, help_text=self._("Saves the bot's current configuration to the config file."))
        command_handler.register_command('cs', self.handle_change_status, admin_only=True, help_text=self._("Changes the bot's status message. Usage: /cs <new_status>"))
        command_handler.register_command('cg', self.handle_change_gender, admin_only=True, help_text=self._("Changes the bot's gender. Usage: /cg <m|f|n>. send /cg without arguments for more details."))
        command_handler.register_command('new', self.handle_new_account_command, admin_only=True, help_text=self._("Creates a new user account. Usage: /new <user> <pass> [rights]. the rights is a list of user rights separated by spaces for each number."))
        command_handler.register_command('l', self.handle_lock_command, admin_only=True, help_text=self._("Locks or unlocks bot commands (admins only). Usage: /l"))
        command_handler.register_command('shutdown', self.handle_shutdown_command, admin_only=True, help_text=self._("Shuts down the bot."))
        command_handler.register_command('sd', self.handle_shutdown_command, admin_only=True, help_text=self._("Alias for /shutdown."))
        command_handler.register_command('restart', self.handle_restart_command, admin_only=True, help_text=self._("Restarts the bot."))
        command_handler.register_command('rs', self.handle_restart_command, admin_only=True, help_text=self._("Alias for /restart."))

    def handle_shutdown_command(self, textmessage, *args):
        """Handles the command to shut down the bot."""
        self.bot.privateMessage(textmessage.nFromUserID, self._("Shutting down..."))
        print("\nShutdown requested by admin command.")
        raise ShutdownSignal

    def handle_restart_command(self, textmessage, *args):
        """Handles the command to restart the bot."""
        self.bot.privateMessage(textmessage.nFromUserID, self._("Restarting..."))
        print("\nRestart requested by admin command.")
        raise RestartSignal

    def handle_lock_command(self, textmessage, *args):
        """Toggles command lock so only admins can run commands."""
        self.bot.commands_locked = not self.bot.commands_locked
        if self.bot.commands_locked:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Commands locked. Only admins can use commands."))
        else:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Commands unlocked. Commands available to everyone."))

    def handle_user_login_checks(self, user):
        """Handles all administrative checks when a user logs in."""
        nickname = ttstr(user.szNickname)
        username = ttstr(user.szUsername)
        ip_address = ttstr(user.szIPAddress)
        user_id = user.nUserID

        # 1. Check for auto-jailing
        if username in self.bot.bot_config["jail_users"] or nickname in self.bot.bot_config["jail_names"]:
            jail_channel_id = self.bot.getChannelIDFromPath(ttstr(self.bot.bot_config["jail_channel"]))
            if jail_channel_id:
                self.bot.doMoveUser(user_id, jail_channel_id)

        # 2. Check for pending duration kicks (by nickname and username)
        if nickname.lower() in self.pending_kicks:
            _, duration, end_time = self.pending_kicks[nickname.lower()]
            if time.time() < end_time:
                self.bot.kick_user(user_id)
                user_data = (nickname, ip_address, username)
                self.duration_kicks[user_data] = (duration, end_time)
            del self.pending_kicks[nickname.lower()]
            return True # User was kicked, stop processing

        if username.lower() in self.pending_kicks:
            _, duration, end_time = self.pending_kicks[username.lower()]
            if time.time() < end_time:
                self.bot.kick_user(user_id)
                user_data = (nickname, ip_address, username)
                self.duration_kicks[user_data] = (duration, end_time)
            del self.pending_kicks[username.lower()]
            return True # User was kicked, stop processing

        # 3. Check for active duration kicks
        for user_data, (duration, end_time) in list(self.duration_kicks.items()):
            if time.time() < end_time:
                if user_data[0] == nickname or user_data[1] == ip_address or (user_data[2] and user_data[2] == username):
                    self.bot.kick_user(user_id)
                    return True # User was kicked, stop processing
            else:
                del self.duration_kicks[user_data] # Clean up expired kick

        # 4. Check for active duration bans
        if ip_address in self.duration_bans:
            _, end_time = self.duration_bans[ip_address]
            if time.time() < end_time:
                self.bot.kick_user(user_id)
                return True
            else:
                del self.duration_bans[ip_address]
    
        if username in self.duration_bans:
            _, end_time = self.duration_bans[username]
            if time.time() < end_time:
                self.bot.kick_user(user_id)
                return True
            else:
                del self.duration_bans[username]
            
        # 5. Check against blacklist.txt (using the utility loader)
        blacklist = utils.load_blacklist("blacklist.txt")
        if any(word in blacklist for word in nickname.lower().split()):
            if self.bot.bot_config["blacklist_mode"] == 1:
                self.bot.kick_user(user_id)
            elif self.bot.bot_config["blacklist_mode"] == 2:
                self.bot.ban_user(user_id, BanType.BANTYPE_IPADDR)
                self.bot.kick_user(user_id)
            return True

        # 6. Check for "NoName"
        if self.bot.bot_config['prevent_noname']:
            if not nickname or re.match(r"^NoName\s*(?:-\s*#\d+)?$", nickname):
                self.bot.privateMessage(user_id, self.bot.bot_config['noname_note'])
                self.bot.kick_user(user_id)
                return True

        # 7. Check for character limit
        char_limit = self.bot.bot_config["char_limit"]
        if char_limit > 0 and len(nickname) > char_limit:
            if self.bot.bot_config["char_limit_mode"] == 1:
                self.bot.privateMessage(user_id, self._("You have been kicked due to username exceeding {chars} characters.").format(chars=char_limit))
                self.bot.kick_user(user_id)
            elif self.bot.bot_config["char_limit_mode"] == 2:
                self.bot.ban_user(user_id, BanType.BANTYPE_IPADDR)
                self.bot.kick_user(user_id)
            return True
        return False

    def check_message_for_blacklist(self, textmessage: TextMessage):
        """Checks a text message for blacklisted words and takes action."""
        if textmessage.nFromUserID == self.bot.getMyUserID():
            return False

        message_text = ttstr(textmessage.szMessage)
        blacklist = utils.load_blacklist("blacklist.txt")
        pattern = r"\b(" + "|".join(re.escape(word) for word in blacklist) + r")\b"

        if blacklist and re.search(pattern, message_text, re.IGNORECASE):
            streamer = teamtalk.VideoCodec()
            streamer.nCodec = 1
            self.bot.startStreamingMediaFileToChannel(ttstr(os.path.join("files", "blacklist.wav")), streamer)
            
            if self.bot.bot_config['blacklist_mode'] == 1:
                self.bot.kick_user(textmessage.nFromUserID)
            elif self.bot.bot_config['blacklist_mode'] == 2:
                self.bot.ban_user(textmessage.nFromUserID)
                self.bot.kick_user(textmessage.nFromUserID)
            return True
        return False

    def handle_reboot_command(self, textmessage, *args):
        self.bot.send_broadcast_message(self._("Attention, The server is rebooting..."))
        self._execute_ssh_command("reboot", textmessage.nFromUserID)

    def handle_exec_command(self, textmessage, *args):
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Usage: /exec <command>"))
            return
        command = " ".join(args)
        self._execute_ssh_command(command, textmessage.nFromUserID)

    def _execute_ssh_command(self, command, user_id):
        user_ip = ttstr(self.bot.getUser(user_id).szIPAddress)
        if user_ip not in self.bot.ssh_config.get('allowed_ips', []):
            self.bot.privateMessage(user_id, self._("Not authorized for this IP address."))
            return
        
        def ssh_task():
            try:
                with paramiko.SSHClient() as ssh_client:
                    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh_client.connect(
                        hostname=self.bot.ssh_config["hostname"],
                        port=self.bot.ssh_config["port"],
                        username=self.bot.ssh_config["username"],
                        password=self.bot.ssh_config["password"],
                        timeout=10
                    )
                    _, stdout, stderr = ssh_client.exec_command(command, timeout=30)
                    output = stdout.read().decode('utf-8', errors='ignore')
                    error = stderr.read().decode('utf-8', errors='ignore')

                    if error: self.bot.privateMessage(user_id, f"Error: {error}")
                    if output:
                        for chunk in self.bot.split_long_message(output):
                            self.bot.privateMessage(user_id, chunk)
            except Exception as e:
                self.bot.privateMessage(user_id, self._("SSH connection error: {e}").format(e=e))
        
        self.bot.quick_task_pool.submit(ssh_task)


    def handle_duration_ban_ip(self, textmessage, *args):
        self._handle_duration_ban(textmessage, BanType.BANTYPE_IPADDR, " ".join(args))

    def handle_duration_ban_user(self, textmessage, *args):
        self._handle_duration_ban(textmessage, BanType.BANTYPE_USERNAME, " ".join(args))

    def _handle_duration_ban(self, textmessage, ban_type, args_str):
        try:
            parts = args_str.rsplit(" ", 1)
            if len(parts) != 2:
                raise ValueError("Invalid format")
            nickname, duration_str = parts[0], parts[1]
            duration_seconds = self.parse_duration_string(duration_str)
            user = self.bot.getUserByName(nickname)
            if user:
                self.bot.ban_user(user.nUserID, ban_type)
                self.bot.send_message(self._("{nickname} has been banned for {duration}.").format(nickname=ttstr(user.szNickname), duration=duration_str))
                Thread(target=self.remove_ban_after_duration, args=(user, duration_seconds, ban_type)).start()
                self.bot.kick_user(user.nUserID)
            else:
                self.bot.privateMessage(textmessage.nFromUserID, self._("User '{nickname}' not found.").format(nickname=nickname))
        except (ValueError, IndexError):
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid format. Usage: /db <nickname> <duration> (e.g., 1h:30m:10s)"))

    def handle_duration_kick_nickname(self, textmessage, *args):
        try:
            args_str = " ".join(args)
            parts = args_str.rsplit(" ", 1)
            if len(parts) != 2:
                raise ValueError("Invalid format")
            nickname, duration_str = parts[0], parts[1]
            duration_seconds = self.parse_duration_string(duration_str)
            user = self.bot.getUserByName(nickname)
            if user:
                self.bot.kick_user(user.nUserID)
                self.bot.send_message(self._("{nickname} has been kicked for {duration}.").format(nickname=ttstr(user.szNickname), duration=duration_str))
                user_data = (ttstr(user.szNickname), ttstr(user.szIPAddress), ttstr(user.szUsername))
                self.duration_kicks[user_data] = (duration_seconds, time.time() + duration_seconds)
            else:
                self.pending_kicks[nickname.lower()] = ("nickname", duration_seconds, time.time() + duration_seconds)
                self.bot.send_message(self._("User '{nickname}' not found. They will be kicked when they log in for {duration}.").format(nickname=nickname, duration=duration_str))
        except (ValueError, IndexError):
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid format. Usage: /dk <nickname> <duration>"))

    def handle_duration_kick_by_username(self, textmessage, *args):
        try:
            args_str = " ".join(args)
            parts = args_str.rsplit(" ", 1)
            if len(parts) != 2:
                raise ValueError("Invalid format")
            username, duration_str = parts[0], parts[1]
            duration_seconds = self.parse_duration_string(duration_str)
            user = self.bot.getUserByUsername(ttstr(username))
            if user and user.nUserID != 0:
                self.bot.kick_user(user.nUserID)
                self.bot.send_message(self._("User with username '{username}' has been kicked for {duration}.").format(username=username, duration=duration_str))
                user_data = (ttstr(user.szNickname), ttstr(user.szIPAddress), ttstr(user.szUsername))
                self.duration_kicks[user_data] = (duration_seconds, time.time() + duration_seconds)
            else:
                self.pending_kicks[username.lower()] = ("username", duration_seconds, time.time() + duration_seconds)
                self.bot.send_message(self._("User with username '{username}' not found. They will be kicked when they log in for {duration}.").format(username=username, duration=duration_str))
        except (ValueError, IndexError):
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid format. Usage: /udk <username> <duration>"))

    def parse_duration_string(self, duration_str):
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

    def remove_ban_after_duration(self, user, duration_seconds, ban_type):
        time.sleep(duration_seconds)
        if ban_type == BanType.BANTYPE_IPADDR:
            self.bot.doUnBanUser(user.szIPAddress, 0)
            self.bot.send_message(self._("{nickname} (IP ban) has been unbanned.").format(nickname=ttstr(user.szNickname)))
        else:
            banned_user = BannedUser()
            banned_user.szUsername = user.szUsername
            banned_user.uBanTypes = BanType.BANTYPE_USERNAME
            self.bot.doUnbanUserEx(banned_user)
            self.bot.send_message(self._("{nickname} (Username ban) has been unbanned.").format(nickname=ttstr(user.szNickname)))


    def handle_change_name_command(self, textmessage, *args):
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Usage: /cn <new_name>"))
            return
        new_name = " ".join(args)
        self.bot.bot_config["nickname"] = new_name
        self.bot.doChangeNickname(ttstr(new_name))
        self.bot.privateMessage(textmessage.nFromUserID, self._("Bot name changed to '{new_name}'.").format(new_name=new_name))

    def handle_change_status(self, textmessage, *args):
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Usage: /cs <new_status>"))
            return
        status_message = " ".join(args)
        self.bot.bot_config["status_message"] = status_message
        self.bot.doChangeStatus(self.bot.bot_config['gender'], ttstr(status_message))
        self.bot.privateMessage(textmessage.nFromUserID, self._("Success"))

    def handle_change_gender(self, textmessage, *args):
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Usage: /cg <m|f|n>"))
            return
        gender_mode = args[0].lower()
        gender_map = {'m': 0, 'f': 256, 'n': 4096}
        if gender_mode in gender_map:
            self.bot.bot_config["gender"] = gender_map[gender_mode]
            self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(self.bot.bot_config['status_message']))
            self.bot.privateMessage(textmessage.nFromUserID, self._("Success"))
        else:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Available modes are: m for male, f for female, n for neutral."))
            
    def save_bot_config(self, textmessage, *args):
        self.bot.config_handler.save_bot_config(self.bot.bot_config)
        self.bot.privateMessage(textmessage.nFromUserID, self._("Bot configuration saved."))

    def handle_new_account_command(self, textmessage, *args):
        try:
            if len(args) < 2:
                raise ValueError("Not enough arguments")
            
            username = args[0]
            password = args[1]
            rights = [int(r) for r in args[2:]]
            
            account = UserAccount()
            account.szUsername = ttstr(username)
            account.szPassword = ttstr(password)
            account.uUserType = UserType.USERTYPE_DEFAULT
            account.uUserRights = self.bot.account_creator.calculate_user_rights(rights)

            self.bot.doNewUserAccount(account)
            self.bot.privateMessage(textmessage.nFromUserID, self._("Account '{username}' created successfully.").format(username=username))
        except ValueError:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command format. Usage: /new <username> <password> [rights separated by space]"))

    def handle_clear_command(self, textmessage, *args):
        target = " ".join(args)
        if target:
            self.clear_for_target(target)
        else:
            self.clear_all()

    def clear_for_target(self, target):
        found = False
        target_lower = target.lower()
        if target in self.banned_users:
            self.unban_user(self.banned_users[target])
            self.bot.send_message(self._("Cleared ban for {target}.").format(target=target))
            found = True
        
        for user_data, (duration, end_time) in list(self.duration_kicks.items()):
            nickname, ip_address, username = user_data
            if target in (nickname, ip_address, username):
                del self.duration_kicks[user_data]
                self.bot.send_message(self._("Cleared duration kick for {target}.").format(target=target))
                found = True
        
        if target_lower in self.pending_kicks:
            del self.pending_kicks[target_lower]
            self.bot.send_message(self._("Cleared pending kick for {target}.").format(target=target))
            found = True
            
        if not found:
            self.bot.send_message(self._("Target '{target}' not found in active bans or kicks.").format(target=target))

    def clear_all(self):
        if not self.banned_users and not self.duration_kicks and not self.pending_kicks:
            self.bot.send_message(self._("There are no active bans or kicks to clear."))
            return
        
        for ban_key in list(self.banned_users.keys()):
            self.unban_user(self.banned_users[ban_key])
        
        self.duration_kicks.clear()
        self.pending_kicks.clear()
        self.bot.send_message(self._("Cleared all bans and duration kicks."))

    def unban_user(self, banned_user_obj):
        try:
            if banned_user_obj.uBanTypes == BanType.BANTYPE_IPADDR:
                self.bot.doUnBanUser(banned_user_obj.szIPAddress, 0)
                if banned_user_obj.szIPAddress in self.banned_users:
                    del self.banned_users[banned_user_obj.szIPAddress]
            elif banned_user_obj.uBanTypes == BanType.BANTYPE_USERNAME:
                self.bot.doUnbanUserEx(banned_user_obj)
                if banned_user_obj.szUsername in self.banned_users:
                    del self.banned_users[banned_user_obj.szUsername]
        except Exception as e:
            print(f"Error during unban: {e}")

    def handle_admin_broadcast(self, textmessage, *args):
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Usage: /bm <message>"))
            return
        message = " ".join(args)
        self.bot.send_broadcast_message(self._("Message from administrators: {message}").format(message=message))

    def ban_user(self, user_id, ban_type=BanType.BANTYPE_USERNAME):
        """Bans a user by either IP or Username, updating internal state."""
        while True:
            user = self.bot.getUser(user_id)
            if user is not None:
                break
            else:
                continue

        banned_user = BannedUser()        
        effective_ban_type = ban_type
        identifier = None

        if ban_type == BanType.BANTYPE_IPADDR:
            while True:
                identifier = ttstr(user.szIPAddress)
                if identifier is None or identifier == "": continue
                else: break
        else:
            username = ttstr(user.szUsername)
            if username == 'guest' or username == self.bot.accounts_config.get('custom_username', ''):
                # Fallback to IP ban for guest-like accounts
                effective_ban_type = BanType.BANTYPE_IPADDR
                while True:
                    identifier = ttstr(user.szIPAddress)
                    if identifier is None or identifier == "": continue
                    else: break
            else:
                identifier = username

        if not identifier:
            print(f"Admin: Could not get a valid identifier to ban user {user.szNickname}")
            return
            
        if effective_ban_type == BanType.BANTYPE_IPADDR:
            banned_user.szIPAddress = ttstr(identifier)
        else:
            banned_user.szUsername = ttstr(identifier)
        
        banned_user.uBanTypes = effective_ban_type        
        self.banned_users[identifier] = banned_user
        self.bot.doBan(banned_user)
