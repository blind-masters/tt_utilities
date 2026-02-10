import time
from threading import Thread
from TeamTalk5 import BanType, ttstr

class JailCog:
    """
    A module for handling the user jailing system, including flood protection.
    """
    def __init__(self, bot):
        self.bot = bot
        self._ = bot._
        self.user_join_timers = {}

    def register(self, command_handler):
        """Registers all jail-related commands."""
        command_handler.register_command('jail', self.handle_jail_command, admin_only=True, help_text=self._("Jails a user by username. Usage: /jail <nickname>"))
        command_handler.register_command('unjail', self.handle_unjail_command, admin_only=True, help_text=self._("Unjails a user. Usage: /unjail <nickname>"))
        command_handler.register_command('jails', self.handle_jails_command, admin_only=True, help_text=self._("Lists all jailed users."))

    def handle_user_join_channel(self, user):
        """Event handler called when any user joins any channel."""
        username = ttstr(user.szUsername)
        nickname = ttstr(user.szNickname)

        if username in self.bot.bot_config.get("jail_users", []) or nickname in self.bot.bot_config.get("jail_names", []):
            jail_channel_id = self.bot.getChannelIDFromPath(ttstr(self.bot.bot_config["jail_channel"]))
            if user.nChannelID != jail_channel_id:
                self.bot.doMoveUser(user.nUserID, jail_channel_id)
                self.track_user_joins(user)

    def track_user_joins(self, user):
        """Starts tracking a jailed user's attempts to leave the jail channel."""
        user_id = user.nUserID
        if user_id not in self.user_join_timers:
            self.user_join_timers[user_id] = {
                "start_time": time.time(),
                "join_count": 1
            }
            self.bot.io_pool.submit(self.monitor_user_joins, user_id)
        else:
            self.user_join_timers[user_id]["join_count"] += 1

    def monitor_user_joins(self, user_id):
        """Monitors a jailed user's join attempts and bans them if they exceed the flood count."""
        timer_data = self.user_join_timers.get(user_id)
        if not timer_data:
            return

        warning_sent = False
        jail_timer_seconds = self.bot.bot_config.get("jail_timer_seconds", 10)
        jail_flood_count = self.bot.bot_config.get("jail_flood_count", 5)

        while time.time() - timer_data["start_time"] < jail_timer_seconds:
            current_join_count = self.user_join_timers.get(user_id, {}).get("join_count", 0)
            if current_join_count >= 3 and not warning_sent:
                self.bot.privateMessage(user_id, self._("Warning: You are trying to get out of jail. If you continue to spam, you will be banned."))
                warning_sent = True
            
            if current_join_count >= jail_flood_count:
                user = self.bot.getUser(user_id)
                if user:
                    ban_type = BanType.BANTYPE_IPADDR if ttstr(user.szUsername) == "guest" else BanType.BANTYPE_USERNAME
                    self.bot.admin_cog.ban_user(user_id, ban_type)
                    self.bot.kick_user(user_id)
                    self.bot.send_broadcast_message(self._("{nickname} has been banned due to jail flood protection.").format(nickname=ttstr(user.szNickname)))
                break
            
            time.sleep(1)        
        if user_id in self.user_join_timers:
            del self.user_join_timers[user_id]


    def handle_jail_command(self, textmessage, *args):
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Usage: /jail <nickname>"))
            return
        nickname = " ".join(args)
        user = self.bot.getUserByName(nickname)
        if user and user.nUserID != 0:
            username = ttstr(user.szUsername)
            if "jail_users" not in self.bot.bot_config: self.bot.bot_config["jail_users"] = []
            
            if username not in self.bot.bot_config["jail_users"]:
                self.bot.bot_config["jail_users"].append(username)
                self.bot.config_handler.save_bot_config(self.bot.bot_config)
            
            jail_channel_id = self.bot.getChannelIDFromPath(ttstr(self.bot.bot_config["jail_channel"]))
            if jail_channel_id:
                self.bot.doMoveUser(user.nUserID, jail_channel_id)
                self.bot.send_message(self._("{nickname} has been jailed.").format(nickname=nickname))
        else:
            self.bot.privateMessage(textmessage.nFromUserID, self._("User '{nickname}' not found.").format(nickname=nickname))

    def handle_unjail_command(self, textmessage, *args):
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Usage: /unjail <nickname>"))
            return
        nickname = " ".join(args)
        user = self.bot.getUserByName(nickname)
        if user and user.nUserID != 0:
            username = ttstr(user.szUsername)
            if username in self.bot.bot_config.get("jail_users", []):
                self.bot.bot_config["jail_users"].remove(username)
                self.bot.config_handler.save_bot_config(self.bot.bot_config)
            
            root_channel_id = self.bot.getRootChannelID()
            self.bot.doMoveUser(user.nUserID, root_channel_id)
            self.bot.send_message(self._("{nickname} has been unjailed.").format(nickname=nickname))
        else:
            self.bot.privateMessage(textmessage.nFromUserID, self._("User '{nickname}' not found.").format(nickname=nickname))
            
    def handle_jails_command(self, textmessage, *args):
        jailed_users = self.bot.bot_config.get("jail_users", [])
        if jailed_users:
            jailed_users_str = ", ".join(jailed_users)
            self.bot.privateMessage(textmessage.nFromUserID, self._("Jailed users: {jailed_users}").format(jailed_users=jailed_users_str))
        else:
            self.bot.privateMessage(textmessage.nFromUserID, self._("No users are currently jailed."))
