import shlex
from TeamTalk5 import TextMessage, UserType, ttstr

class Command:
    def __init__(self, name, handler, admin_only=False, help_text=""):
        self.name = name
        self.handler = handler
        self.admin_only = admin_only
        self.help_text = help_text

class CommandHandler:
    def __init__(self, bot, prefix='/'):
        self.bot = bot
        self.prefix = prefix
        self.commands = {}

    def register_command(self, name, handler, admin_only=False, help_text=""):
        self.commands[name] = Command(name, handler, admin_only, help_text)

    def handle_message(self, textmessage: TextMessage):
        message_text = ttstr(textmessage.szMessage)
        if not message_text.startswith(self.prefix):
            return

        try:
            # shlex helps with quoted arguments
            parts = shlex.split(message_text)
            command_name = parts[0][len(self.prefix):].lower()
            args = parts[1:]
        except ValueError:
            # Fallback for simple splitting if shlex fails
            parts = message_text.split()
            command_name = parts[0][len(self.prefix):].lower()
            args = parts[1:]

        if command_name in self.commands:
            command = self.commands[command_name]
            
            # Check for admin_only commands
            if command.admin_only:
                sender_username = ttstr(textmessage.szFromUsername)
                authorized_users = [u.strip() for u in self.bot.accounts_config.get("authorized_users", [])]
                if sender_username not in authorized_users:
                    # Also check if the user is a server admin if that setting is enabled
                    if self.bot.accounts_config.get('detect_server_admins', False):
                        sender_user = self.bot.getUser(textmessage.nFromUserID)
                        if sender_user and sender_user.uUserType != UserType.USERTYPE_ADMIN:
                            self.bot.privateMessage(textmessage.nFromUserID, self.bot._("This command is for authorized users only."))
                            return
                    else:
                        self.bot.privateMessage(textmessage.nFromUserID, self.bot._("This command is for authorized users only."))
                        return

            command.handler(textmessage, *args)
