import gettext
import configparser
import os
import ast
import sys
import TeamTalk5 as teamtalk
import mpv
import getpass

class ConfigHandler:
    """
    Manages reading and writing the bot's configuration file (config.ini).
    If the file doesn't exist, it guides the user through an interactive
    setup process via the terminal or a graphical interface on Windows.
    """

    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.language = "en"
        self._ = gettext.gettext  # Initialize _ for default language
        self.CONFIG_STRUCTURE = self._get_config_structure()        
        self.read_config_file()

    def _get_config_structure(self):
        """
        Defines the entire structure of the config.ini file.
        This centralized structure makes validation and extension easy.
        The `_` calls are placeholders and will be replaced by the selected language.
        """
        return [
            # Each dict represents a single configuration key.
            # 'section' and 'key' are mandatory.
            # 'prompt' and 'help_text' are for user interaction.
            # 'type' determines the kind of input (text, int, float, bool, choice, device, password).
            # 'default' provides a fallback value.
            # 'required' ensures a value must be present.

            {'type': 'header', 'text': self._("Language Selection")},
            {'section': 'bot', 'key': 'language', 'type': 'language', 'prompt': self._("Setup Language"), 'help_text': self._("Choose the language for the bot and setup process."), 'default': 'en'},

            {'type': 'header', 'text': self._("TeamTalk Server Connection")},
            {'section': 'server', 'key': 'address', 'type': 'text', 'prompt': self._("Server Address"), 'help_text': self._("The IP address or hostname of the TeamTalk server (e.g., myserver.com)."), 'required': True},
            {'section': 'server', 'key': 'port', 'type': 'int', 'prompt': self._("Server Port"), 'help_text': self._("The TCP/UDP port of the server."), 'default': 10333},
            {'section': 'server', 'key': 'encrypted', 'type': 'bool', 'prompt': self._("Is the server encrypted?"), 'help_text': self._("Set to 'yes' if the server requires an encrypted connection."), 'default': False},
            {'section': 'server', 'key': 'username', 'type': 'text', 'prompt': self._("Bot's Username"), 'help_text': self._("The username for the bot's account on the server."), 'required': True},
            {'section': 'server', 'key': 'password', 'type': 'password', 'prompt': self._("Bot's Password"), 'help_text': self._("The password for the bot's account.")},

            {'type': 'header', 'text': self._("Bot Identity and Behavior")},
            {'section': 'bot', 'key': 'nickname', 'type': 'text', 'prompt': self._("Bot's Nickname"), 'help_text': self._("The name the bot will display in the channel."), 'required': True},
            {'section': 'bot', 'key': 'client_name', 'type': 'text', 'prompt': self._("Bot's Client Name"), 'help_text': self._("The client name shown in the user info (e.g., 'TTUtilities Bot v2.3')."), 'default': "TTUtilities Bot"},
            {'section': 'bot', 'key': 'gender', 'type': 'choice', 'prompt': self._("Bot's Gender"), 'help_text': self._("This affects the bot's default icon."), 'options': {'Male': '0', 'Female': '256', 'Neutral': '4096'}, 'default': 'Male'},
            {'section': 'bot', 'key': 'default_channel', 'type': 'text', 'prompt': self._("Default Channel"), 'help_text': self._("The full path of the channel the bot should join after login (e.g., '/chatting'). The default is the root channel (/)."), 'default': "/"},
            {'section': 'bot', 'key': 'channel_password', 'type': 'text', 'prompt': self._("Channel Password"), 'help_text': self._("The password for the default channel, if required.")},
            {'section': 'bot', 'key': 'status_message', 'type': 'text', 'prompt': self._("Status Message"), 'help_text': self._("An optional status message for the bot.")},
            {'section': 'bot', 'key': 'welcome_broadcast', 'type': 'bool', 'prompt': self._("Send Welcome Broadcast?"), 'help_text': self._("Send a public welcome message when a user logs in."), 'default': True},
            {'section': 'bot', 'key': 'random_message_interval', 'type': 'int', 'prompt': self._("Random Message Interval (minutes)"), 'help_text': self._("Interval in minutes for sending random broadcast messages from messages.txt. Set to 0 to disable."), 'default': 0},

            {'type': 'header', 'text': self._("Audio and Playback Settings")},
            {'section': 'playback', 'key': 'input_device', 'type': 'device', 'device_type': 'input', 'prompt': self._("Input Device"), 'help_text': self._("The audio device for voice transmission.")},
            {'section': 'playback', 'key': 'output_device', 'type': 'device', 'device_type': 'output', 'prompt': self._("Output Device"), 'help_text': self._("The audio device for media playback.")},
            {'section': 'playback', 'key': 'seek_step', 'type': 'int', 'prompt': self._("Seek Step (seconds)"), 'help_text': self._("Default number of seconds to seek forward/backward in media playback."), 'default': 5},
            {'section': 'playback', 'key': 'default_volume', 'type': 'int', 'prompt': self._("Default Playback Volume"), 'help_text': self._("The initial volume for media playback (0-100)."), 'default': 80},
            {'section': 'playback', 'key': 'max_volume', 'type': 'int', 'prompt': self._("Maximum Playback Volume"), 'help_text': self._("The highest volume users can set (e.g., 100)."), 'default': 100},
            {'section': 'playback', 'key': 'send_channel_messages', 'type': 'bool', 'prompt': self._("Send Playback Messages to Channel?"), 'help_text': self._("Announce playback actions (play/pause/stop/volume) in the channel."), 'default': True},
            {'section': 'playback', 'key': 'channel_messages_mode', 'type': 'choice', 'prompt': self._("If Disabled, Send Playback Messages By"), 'help_text': self._("Choose whether to send playback messages privately or stay silent when channel announcements are disabled."), 'options': {'Private messages': 'private', 'Silent': 'silent'}, 'default': 'Private messages'},
            {'section': 'playback', 'key': 'volume_fading', 'type': 'float', 'prompt': self._("Volume Fading (seconds)"), 'help_text': self._("Fade audio when seeking or changing volume. Set to 0 to disable."), 'default': 0.0},
            {'section': 'playback', 'key': 'cookiefile_path', 'type': 'text', 'prompt': self._("Cookies File Path"), 'help_text': self._("Optional path to a cookies file (e.g., cookies.txt) for yt-dlp to access private or restricted videos.")},

            {'type': 'header', 'text': self._("Moderation and Security")},
            {'section': 'bot', 'key': 'vpn_detection', 'type': 'bool', 'prompt': self._("Enable VPN/Proxy Detection?"), 'help_text': self._("Check if users are connecting via a known VPN or proxy service."), 'default': True},
            {'section': 'bot', 'key': 'prevent_noname', 'type': 'bool', 'prompt': self._("Kick 'NoName' users?"), 'help_text': self._("Automatically kick users who log in with the default 'NoName' nickname."), 'default': True},
            {'section': 'bot', 'key': 'noname_note', 'type': 'text', 'prompt': self._("Message for 'NoName' users"), 'help_text': self._("The private message sent to a user before they are kicked for having no name."), 'default': "Hello. Please set your nickname first by pressing F4 (On windows) or Options, > settings, > General, > Nickname  (On Android), then reconnect. Thank you."},
            {'section': 'bot', 'key': 'intercept_channel_messages', 'type': 'bool', 'prompt': self._("Intercept All Channel Messages?"), 'help_text': self._("Allows the bot to 'see' messages in all channels for features like word blacklisting and general bot commands, such as weather and other commands, even if it's not in that channel. Highly recommended."), 'default': True},
            {'section': 'bot', 'key': 'char_limit', 'type': 'int', 'prompt': self._("Nickname Character Limit"), 'help_text': self._("Maximum allowed characters in a user's nickname. Set to 0 to disable."), 'default': 0},
            {'section': 'bot', 'key': 'char_limit_mode', 'type': 'choice', 'prompt': self._("Action for Long Nicknames"), 'help_text': self._("What to do when a user's nickname exceeds the character limit."), 'options': {'Kick the user': '1', 'Ban the user': '2'}, 'default': 'Kick the user'},
            {'section': 'bot', 'key': 'blacklist_mode', 'type': 'choice', 'prompt': self._("Action for Blacklisted Words"), 'help_text': self._("What to do when a user uses a word from blacklist.txt in their name or messages."), 'options': {'Kick the user': '1', 'Ban the user': '2'}, 'default': 'Kick the user'},
            {'section': 'bot', 'key': 'banned_countries', 'type': 'text', 'prompt': self._("Banned Countries"), 'help_text': self._("A comma-separated list of country names to ban from the server (e.g., North Korea,Israel).")},
            {'section': 'bot', 'key': 'video_deletion_timer', 'type': 'int', 'prompt': self._("Uploaded Video Deletion Timer (minutes)"), 'help_text': self._("Time in minutes before a downloaded/uploaded video is automatically deleted from the server channel. Set to 0 to disable."), 'default': 15},

            {'type': 'header', 'text': self._("Jail System")},
            {'section': 'bot', 'key': 'jail_users', 'type': 'text', 'prompt': self._("Jailed Usernames"), 'help_text': self._("A comma-separated list of usernames to automatically confine to the jail channel upon login.")},
            {'section': 'bot', 'key': 'jail_names', 'type': 'text', 'prompt': self._("Jailed Nicknames"), 'help_text': self._("A comma-separated list of nicknames to confine to the jail channel.")},
            {'section': 'bot', 'key': 'jail_channel', 'type': 'text', 'prompt': self._("Jail Channel Path"), 'help_text': self._("The full path to the channel where jailed users will be moved."), 'default': "/jail"},
            {'section': 'bot', 'key': 'jail_timer_seconds', 'type': 'int', 'prompt': self._("Jail Flood Timer (seconds)"), 'help_text': self._("The time window in seconds to monitor a jailed user for spamming join attempts."), 'default': 10},
            {'section': 'bot', 'key': 'jail_flood_count', 'type': 'int', 'prompt': self._("Jail Flood Count"), 'help_text': self._("Number of join attempts within the timer window that will trigger a ban."), 'default': 5},

            {'type': 'header', 'text': self._("Exclusions (Immunity)")},
            {'section': 'exclusion', 'key': 'ips', 'type': 'text', 'prompt': self._("Excluded IP Addresses"), 'help_text': self._("Comma-separated list of IP addresses immune to moderation rules. The stats IP is excluded by default."), 'default': '139.144.24.23'},
            {'section': 'exclusion', 'key': 'usernames', 'type': 'text', 'prompt': self._("Excluded Usernames"), 'help_text': self._("Comma-separated list of usernames immune to moderation rules.")},
            {'section': 'exclusion', 'key': 'nicknames', 'type': 'text', 'prompt': self._("Excluded Nicknames"), 'help_text': self._("Comma-separated list of nicknames immune to moderation rules.")},

            {'type': 'header', 'text': self._("Administrator and Account Settings")},
            {'section': 'accounts', 'key': 'authorized_users', 'type': 'text', 'prompt': self._("Authorized Users"), 'help_text': self._("Comma-separated list of usernames who can use the bot's admin commands.")},
            {'section': 'accounts', 'key': 'detect_server_admins', 'type': 'bool', 'prompt': self._("Auto-authorize Server Admins?"), 'help_text': self._("Should users with the 'Administrator' user type on the server automatically get bot admin privileges?"), 'default': True},
            {'section': 'accounts', 'key': 'detection_mode', 'type': 'choice', 'prompt': self._("Account Detection Mode"), 'help_text': self._("Which type of accounts should trigger the bot's actions, such as VPN detection, welcome messages, and other actions?"), 'options': {'Guest accounts only': '1', 'All new accounts': '2', 'Accounts with a specific username': '3'}, 'default': 'Guest accounts only'},
            {'section': 'accounts', 'key': 'custom_username', 'type': 'text', 'prompt': self._("Custom Username for Detection"), 'help_text': self._("If you chose option 3 above, enter the specific username to watch for here.")},
            
            {'type': 'header', 'text': self._("Optional Integrations")},
            {'section': 'telegram', 'key': 'telegram_bot_token', 'type': 'text', 'prompt': self._("Telegram Bot Token"), 'help_text': self._("Token for your Telegram bot to enable notifications. Leave blank to disable.")},
            {'section': 'weather', 'key': 'api_key', 'type': 'text', 'prompt': self._("weatherapi.com API Key"), 'help_text': self._("API key for the weather command. See the README for instructions on how to get one.")},
            {'section': 'ssh', 'key': 'hostname', 'type': 'text', 'prompt': self._("SSH Hostname"), 'help_text': self._("Hostname or IP for the SSH server for the /exec and /reboot commands. Leave blank to disable.")},
            {'section': 'ssh', 'key': 'port', 'type': 'int', 'prompt': self._("SSH Port"), 'default': 22},
            {'section': 'ssh', 'key': 'username', 'type': 'text', 'prompt': self._("SSH Username")},
            {'section': 'ssh', 'key': 'password', 'type': 'password', 'prompt': self._("SSH Password")},
            {'section': 'ssh', 'key': 'allowed_ips', 'type': 'text', 'prompt': self._("SSH Allowed IPs"), 'help_text': self._("Comma-separated list of user IP addresses allowed to use SSH commands via the bot.")},

            {'type': 'header', 'text': self._("TeamTalk License (Optional)")},
            {'section': 'teamtalk_license', 'key': 'license_name', 'type': 'text', 'prompt': self._("License Name"), 'help_text': self._("Your TeamTalk SDK license name, if you have one.")},
            {'section': 'teamtalk_license', 'key': 'license_key', 'type': 'text', 'prompt': self._("License Key"), 'help_text': self._("Your TeamTalk SDK license key.")},
        ]
                
    def _select_language_and_translate_structure(self, ask_in_terminal=True):
        """
        Sets the language and translates the prompts in CONFIG_STRUCTURE.
        The `ask_in_terminal` flag prevents the terminal prompt on Windows.
        """
        if ask_in_terminal:
            self.select_language()
        
        gettext.bindtextdomain("messages", "locales")
        gettext.textdomain("messages")
        try:
            translation = gettext.translation("messages", "locales", [self.language])
            self._ = translation.gettext
        except FileNotFoundError:
            self._ = gettext.gettext

        self.CONFIG_STRUCTURE = self._get_config_structure()
    
    def select_language(self):
        """Allows the user to select a language for the setup process."""
        locales_dir = "locales"
        try:
            available_langs = [d for d in os.listdir(locales_dir) if os.path.isdir(os.path.join(locales_dir, d))]
        except FileNotFoundError:
            print("Warning: 'locales' directory not found. Defaulting to English.")
            available_langs = []

        if available_langs:
            print("\nPlease choose the language for the setup process.")
            for i, lang in enumerate(available_langs):
                print(f"{i + 1}. {lang}")

            while True:
                try:
                    choice = int(input("Select language number: ")) - 1
                    if 0 <= choice < len(available_langs):
                        self.language = available_langs[choice]
                        break
                    else:
                        print("Invalid choice.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
        
        # Install the selected language for gettext
        gettext.bindtextdomain("messages", locales_dir)
        gettext.textdomain("messages")
        try:
            translation = gettext.translation("messages", locales_dir, [self.language])
            translation.install()
            self._ = translation.gettext
        except FileNotFoundError:
            print(f"Language '{self.language}' not found, defaulting to English.")
            self._ = gettext.gettext

    def read_config_file(self):
        """
        Reads the configuration file. If it doesn't exist, launches the
        appropriate setup wizard (GUI for Windows, Terminal for others).
        """
        if not os.path.isfile(self.config_file):
            if sys.platform == "win32":
                self._run_gui_wizard()
            else:
                self.select_language()
                self.create_config_file_terminal(self.CONFIG_STRUCTURE)
                
        self.config.read(self.config_file)

        missing_items = self._validate_config()
        
        if missing_items:
            print(self._("Warning: Your config.ini is missing some settings."))
            if self.config.has_option('bot', 'language'):
                self.language = self.config.get('bot', 'language')
            if sys.platform == "win32":
                self._select_language_and_translate_structure(ask_in_terminal=False)
                self._prompt_for_missing(missing_items)
            else:
                self._select_language_and_translate_structure(ask_in_terminal=True)
                self._prompt_for_missing(missing_items)
            self.config.read(self.config_file)

    def _validate_config(self):
        """
        Checks the loaded config against the defined structure.
        Returns a list of missing item definitions.
        """
        missing = []
        for item in self.CONFIG_STRUCTURE:
            if 'section' not in item or 'key' not in item:
                continue
            if not self.config.has_section(item['section']) or not self.config.has_option(item['section'], item['key']):
                missing.append(item)
        return missing

    def _prompt_for_missing(self, missing_items):
        """Launches the appropriate UI to ask the user for missing values."""
        if sys.platform == "win32":
            self._run_gui_missing_dialog(missing_items)
        else:
            print(self._("I'll ask you for the required values now."))
            self.create_config_file_terminal(missing_items)

    def _run_gui_wizard(self):
        """Runs the full GUI setup wizard."""
        import wx
        import wx.lib.scrolledpanel as scrolled
        from bot.gui import ConfigWizard
        app = wx.App(False)
        wizard = ConfigWizard(None, self._("TTUtilities Bot Configuration"), self.CONFIG_STRUCTURE, self._)
        app.MainLoop()
        if not os.path.isfile(self.config_file):
            print(self._("Configuration was not saved. Exiting."))
            sys.exit(1)

    def _run_gui_missing_dialog(self, missing_items):
        """Runs the GUI dialog to fix a broken config."""
        import wx
        import wx.lib.scrolledpanel as scrolled
        from bot.gui import MissingConfigDialog
        app = wx.App(False)
        dialog = MissingConfigDialog(None, self._("Missing Configuration"), missing_items, self.config_file)
        app.MainLoop()


    def _print_header(self, text):
        """Prints a formatted section header."""
        print(f"--- {text} ---")

    def _ask_text(self, prompt, help_text, required=False, default=None):
        """Asks for a simple text input."""
        while True:
            print(f"\n? {self._(prompt)}")
            if help_text:
                print(f"  > {self._(help_text)}")
            
            default_str = f" [Default: {default}]" if default is not None else ""
            user_input = input(f"Enter value{default_str}: ").strip()

            if user_input:
                return user_input
            if default is not None:
                return default
            if not required:
                return ""
            
            print(self._("This field is required. Please enter a value."))
    
    def _ask_password(self, prompt, help_text):
        """Asks for a password input securely."""
        print(f"\n? {self._(prompt)}")
        if help_text:
            print(f"  > {self._(help_text)}")
        return getpass.getpass("Enter value: ")

    def _ask_int(self, prompt, help_text, default=None):
        """Asks for an integer input."""
        while True:
            val_str = self._ask_text(prompt, help_text, default=str(default) if default is not None else None)
            try:
                return int(val_str)
            except ValueError:
                print(self._("Invalid input. Please enter a whole number."))

    def _ask_float(self, prompt, help_text, default=None):
        """Asks for a float input."""
        while True:
            val_str = self._ask_text(prompt, help_text, default=str(default) if default is not None else None)
            try:
                return float(val_str)
            except ValueError:
                print(self._("Invalid input. Please enter a number."))

    def _ask_bool(self, prompt, help_text, default=True):
        """Asks a yes/no question."""
        while True:
            print(f"\n? {self._(prompt)}")
            if help_text:
                print(f"  > {self._(help_text)}")

            default_str = "(Y/n)" if default else "(y/N)"
            user_input = input(f"Enter choice {default_str}: ").strip().lower()

            if user_input == 'y':
                return True
            if user_input == 'n':
                return False
            if user_input == '':
                return default
            
            print(self._("Invalid choice. Please enter 'y' or 'n'."))

    def _ask_choice(self, prompt, help_text, options, default=None):
        """Asks the user to choose from a list of options."""
        print(f"\n? {self._(prompt)}")
        if help_text:
            print(f"  > {self._(help_text)}")
        
        option_keys = list(options.keys())
        for i, key in enumerate(option_keys):
            print(f"  {i + 1}. {self._(key)}")
        
        while True:
            default_str = f" [Default: {default}]" if default is not None else ""
            choice_str = input(f"Enter choice number{default_str}: ").strip()
            
            if choice_str == '' and default is not None:
                # Find the key corresponding to the default value for display
                default_key_index = option_keys.index(default) + 1
                print(f"Selected default: {default_key_index}")
                return options[default]

            try:
                choice_idx = int(choice_str) - 1
                if 0 <= choice_idx < len(option_keys):
                    selected_key = option_keys[choice_idx]
                    return options[selected_key]
                else:
                    print(self._("Invalid choice number."))
            except ValueError:
                print(self._("Invalid input. Please enter a number."))

    def _get_devices(self, type):
        """Helper to get audio devices from TeamTalk or MPV."""
        if type == 'input':
            try:
                tt = teamtalk.TeamTalk()
                devices = tt.getSoundDevices()
                tt.closeTeamTalk()
                return [d for d in devices if d.nMaxInputChannels > 0]
            except Exception:
                return []
        elif type == 'output':
            try:
                player = mpv.MPV(vo='null', video=False)
                devices = player.audio_device_list
                player.terminate()
                return devices
            except Exception:
                return []

    def create_config_file_terminal(self, items_to_ask):
        """
        Guides the user through creating a config.ini file via a data-driven
        terminal interface. This replaces the old, hardcoded method.
        """
        if len(items_to_ask) == len(self.CONFIG_STRUCTURE):
            print(self._("Welcome to the TTUtilities Bot setup wizard!"))
            print(self._("I'll ask a few questions to create your configuration file."))
        
        collected_values = {}
        for item in items_to_ask:
            # The header is only useful in the full setup wizard
            if item.get('type') in ['header', 'language']:
                if item.get('type') == 'header' and len(items_to_ask) == len(self.CONFIG_STRUCTURE):
                    self._print_header(item['text'])
                continue

            section, key = item['section'], item['key']
            prompt, help_text = item['prompt'], item.get('help_text', '')
            default = item.get('default')
            item_type = item['type']

            value = None
            if item_type == 'text':
                value = self._ask_text(prompt, help_text, item.get('required', False), default)
            elif item_type == 'password':
                value = self._ask_password(prompt, help_text)
            elif item_type == 'int':
                value = self._ask_int(prompt, help_text, default)
            elif item_type == 'float':
                value = self._ask_float(prompt, help_text, default)
            elif item_type == 'bool':
                value = self._ask_bool(prompt, help_text, default)
            elif item_type == 'choice':
                value = self._ask_choice(prompt, help_text, item['options'], default)
            elif item_type == 'device':
                devices = self._get_devices(item['device_type'])
                if not devices:
                    print(self._("Could not find any {type} devices. You may need to set this manually in config.ini.").format(type=item['device_type']))
                    value = -1 # Default to an invalid ID
                else:
                    if item['device_type'] == 'input':
                        options = {teamtalk.ttstr(d.szDeviceName): d.nDeviceID for d in devices}
                    else: # output
                        options = {d['description']: i for i, d in enumerate(devices)}
                    
                    value = self._ask_choice(self._("Select {type} Device").format(type=item['device_type'].title()), "", options)

            # Store the collected value
            if (section, key) not in collected_values:
                collected_values[(section, key)] = value

        self._write_config(collected_values)

    def _write_config(self, values):
        """Writes the collected values to the config.ini file."""
        new_config = configparser.ConfigParser()
        for (section, key), value in values.items():
            if not new_config.has_section(section):
                new_config.add_section(section)
            new_config.set(section, key, str(value))
        
        with open(self.config_file, "w", encoding="utf-8") as configfile:
            new_config.write(configfile)
            print(self._("\nConfiguration saved to config.ini! You can now start the bot normally."))
        
        self.config = new_config

    # These methods safely retrieve values from the loaded config file.

    def get_server_config(self):
        try:
            server_section = self.config["server"]
            return {
                "address": server_section.get("address"),
                "port": server_section.getint("port"),
                "encrypted": server_section.getboolean("encrypted"),
                "username": server_section.get("username"),
                "password": server_section.get("password"),
            }
        except (configparser.Error, KeyError, ValueError) as e:
            print(self._("Config file error in [server] section: {e}. Please delete config.ini and run again.").format(e=e))
            sys.exit(1)

    def get_bot_config(self):
        try:
            bot_section = self.config["bot"]
            return {
                "nickname": bot_section.get("nickname"),
                "client_name": bot_section.get("client_name"),
                "gender": bot_section.getint("gender"),
                "language": bot_section.get("language", "en"),
                "default_channel": bot_section.get("default_channel", "/"),
                "channel_password": bot_section.get("channel_password", ""),
                "status_message": bot_section.get("status_message", ""),
                "welcome_broadcast": bot_section.getboolean("welcome_broadcast", True),
                "vpn_detection": bot_section.getboolean("vpn_detection", True),
                "prevent_noname": bot_section.getboolean("prevent_noname", True),
                "noname_note": bot_section.get("noname_note", ""),
                "intercept_channel_messages": bot_section.getboolean("intercept_channel_messages", True),
                "jail_users": [u.strip() for u in bot_section.get("jail_users", "").split(",") if u.strip()],
                "jail_names": [n.strip() for n in bot_section.get("jail_names", "").split(",") if n.strip()],
                "jail_channel": bot_section.get("jail_channel", "/jail"),
                "jail_timer_seconds": bot_section.getint("jail_timer_seconds", 10),
                "jail_flood_count": bot_section.getint("jail_flood_count", 5),
                "random_message_interval": bot_section.getint("random_message_interval", 0),
                "char_limit": bot_section.getint("char_limit", 0),
                "char_limit_mode": bot_section.getint("char_limit_mode", 1),
                "blacklist_mode": bot_section.getint("blacklist_mode", 1),
                "video_deletion_timer": bot_section.getint("video_deletion_timer", 15),
                "banned_countries": [c.strip() for c in bot_section.get("banned_countries", "").split(",") if c.strip()],
            }
        except (configparser.Error, KeyError, ValueError) as e:
            print(self._("Config file error in [bot] section: {e}. Please delete config.ini and run again.").format(e=e))
            sys.exit(1)

    def get_playback_config(self):
        try:
            playback_section = self.config["playback"]
            return {
                "input_device": playback_section.getint("input_device"),
                "output_device": playback_section.getint("output_device"),
                "seek_step": playback_section.getint("seek_step", 5),
                "default_volume": playback_section.getint("default_volume", 80),
                "max_volume": playback_section.getint("max_volume", 100),
                "send_channel_messages": playback_section.getboolean("send_channel_messages", True),
                "channel_messages_mode": playback_section.get("channel_messages_mode", "private"),
                "volume_fading": playback_section.getfloat("volume_fading", fallback=0.0),
                "cookiefile_path": playback_section.get("cookiefile_path", fallback=None),
            }
        except (configparser.Error, KeyError, ValueError) as e:
            print(self._("Config file error in [playback] section: {e}. Please delete config.ini and run again.").format(e=e))
            sys.exit(1)

    def save_playback_config(self, playback_config):
        """Saves the playback configuration section to the config file."""
        try:
            self.config["playback"] = {
                "input_device": playback_config.get("input_device"),
                "output_device": playback_config.get("output_device"),
                "seek_step": playback_config.get("seek_step", 5),
                "default_volume": playback_config.get("default_volume", 80),
                "max_volume": playback_config.get("max_volume", 100),
                "send_channel_messages": str(playback_config.get("send_channel_messages", True)),
                "channel_messages_mode": playback_config.get("channel_messages_mode", "private"),
                "volume_fading": playback_config.get("volume_fading", 0.0),
                "cookiefile_path": playback_config.get("cookiefile_path") or "",
            }
            with open(self.config_file, "w", encoding="utf-8") as configfile:
                self.config.write(configfile)
        except (configparser.Error, KeyError) as e:
            print(self._(f"Error saving playback config: {e}"))

    def get_telegram_config(self):
        try:
            return {"telegram_bot_token": self.config.get("telegram", "telegram_bot_token", fallback=None)}
        except (configparser.Error, KeyError) as e:
            print(self._("Config file error in [telegram] section: {e}.").format(e=e))
            return {"telegram_bot_token": None}

    def get_exclusion_config(self):
        try:
            exclusion_section = self.config["exclusion"]
            return {
                "ips": [ip.strip() for ip in exclusion_section.get("ips", "").split(",") if ip.strip()],
                "usernames": [u.strip() for u in exclusion_section.get("usernames", "").split(",") if u.strip()],
                "nicknames": [n.strip() for n in exclusion_section.get("nicknames", "").split(",") if n.strip()],
            }
        except (configparser.Error, KeyError, ValueError) as e:
            print(self._("Config file error in [exclusion] section: {e}. Please delete config.ini and run again.").format(e=e))
            sys.exit(1)

    def get_accounts_config(self):
        try:
            accounts_section = self.config["accounts"]
            return {
                "detection_mode": accounts_section.getint("detection_mode", 1),
                "custom_username": accounts_section.get("custom_username", ""),
                "authorized_users": [u.strip() for u in accounts_section.get("authorized_users", "").split(",") if u.strip()],
                "detect_server_admins": accounts_section.getboolean("detect_server_admins", True),
            }
        except (configparser.Error, KeyError, ValueError) as e:
            print(self._("Config file error in [accounts] section: {e}. Please delete config.ini and run again.").format(e=e))
            sys.exit(1)

    def get_weather_config(self):
        try:
            return self.config.get("weather", "api_key", fallback=None)
        except (configparser.Error, KeyError) as e:
            print(self._("Config file error in [weather] section: {e}.").format(e=e))
            return None

    def get_ssh_config(self):
        try:
            ssh_section = self.config["ssh"]
            return {
                "hostname": ssh_section.get("hostname", None),
                "port": ssh_section.getint("port", 22),
                "username": ssh_section.get("username", None),
                "password": ssh_section.get("password", None),
                "allowed_ips": [ip.strip() for ip in ssh_section.get("allowed_ips", "").split(",") if ip.strip()]
            }
        except (configparser.Error, KeyError, ValueError) as e:
            print(self._("Config file error in [ssh] section: {e}. Please delete config.ini and run again.").format(e=e))
            sys.exit(1)

    def get_teamtalk_license_config(self):
        try:
            return {
                "license_name": self.config.get("teamtalk_license", "license_name", fallback=None),
                "license_key": self.config.get("teamtalk_license", "license_key", fallback=None),
            }
        except (configparser.Error, KeyError) as e:
            print(self._("Config file error in [teamtalk_license] section: {e}.").format(e=e))
            return {"license_name": None, "license_key": None}

    def save_bot_config(self, bot_config):
        """Saves the bot configuration section to the config file."""
        try:
            self.config["bot"] = {
                "nickname": str(bot_config["nickname"]),
                "client_name": str(bot_config["client_name"]),
                "gender": str(bot_config["gender"]),
                "language": str(bot_config["language"]),
                "default_channel": str(bot_config['default_channel']),
                "channel_password": str(bot_config['channel_password']),
                "status_message": str(bot_config["status_message"]),
                "welcome_broadcast": str(bot_config.get('welcome_broadcast', True)),
                "vpn_detection": str(bot_config['vpn_detection']),
                "prevent_noname": str(bot_config['prevent_noname']),
                "noname_note": str(bot_config['noname_note']),
                "intercept_channel_messages": str(bot_config['intercept_channel_messages']),
                "jail_users": ",".join(bot_config["jail_users"]),
                "jail_names": ",".join(bot_config["jail_names"]),
                "jail_channel": str(bot_config["jail_channel"]),
                "jail_timer_seconds": str(bot_config["jail_timer_seconds"]),
                "jail_flood_count": str(bot_config["jail_flood_count"]),
                "random_message_interval": str(bot_config["random_message_interval"]),
                "char_limit": str(bot_config["char_limit"]),
                "char_limit_mode": str(bot_config["char_limit_mode"]),
                "blacklist_mode": str(bot_config["blacklist_mode"]),
                "video_deletion_timer": str(bot_config["video_deletion_timer"]),
                "banned_countries": ",".join(bot_config["banned_countries"]),
            }
            with open(self.config_file, "w", encoding="utf-8") as configfile:
                self.config.write(configfile)
        except (configparser.Error, KeyError) as e:
            print(self._("Error saving bot config: {e}").format(e=e))
