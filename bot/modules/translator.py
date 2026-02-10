import time
import langdetect
from langdetect.lang_detect_exception import LangDetectException
from concurrent.futures import ThreadPoolExecutor
from deep_translator import GoogleTranslator
from deep_translator.exceptions import LanguageNotSupportedException
from TeamTalk5 import TextMessage, TextMsgType, ttstr
from bot.utils import LoggingThreadPoolExecutor

class TranslatorCog:
    """
    A module for handling all translation related commands and logic.
    """
    def __init__(self, bot):
        self.bot = bot
        self._ = bot._
        self.translation_pool = LoggingThreadPoolExecutor(max_workers=30, thread_name_prefix='TTBot_Translation')
        self.auto_translate = False
        self.source_lang = 'auto'
        self.target_lang = 'en'
        self.last_translated_message = None
        self.user_translation_modes = {}
        self.whisper_translate_modes = {}
        self.user_translation_cooldowns = {}
        self.last_t_command_time = 0

    def register(self, command_handler):
        """Registers all the translator commands."""
        command_handler.register_command('t', self.handle_t_command, help_text=self._("Toggles auto-translation for channel messages. Usage: /t <source_language_code> <target_language_code>. If the mode is already active, send /t again without arguments to disable."))
        command_handler.register_command('pt', self.handle_pt_command, help_text=self._("Toggles private translation mode for you. Usage: /pt <source_language_code> <target_language_code>. If the mode is already active, send /pt again without arguments to disable."))
        command_handler.register_command('wt', self.handle_wt_command, help_text=self._("Toggles whisper translate mode, sending you private translations of channel messages. Usage: /wt <source_language_code> <target_language_code>"))

    def on_user_parted(self, user):
        """Cleans up translation state when a user leaves."""
        user_id = user.nUserID
        if user_id in self.user_translation_modes:
            del self.user_translation_modes[user_id]
        if user_id in self.user_translation_cooldowns:
            del self.user_translation_cooldowns[user_id]
        if user_id in self.whisper_translate_modes:
            del self.whisper_translate_modes[user_id]
            
    def handle_channel_translation(self, textmessage: TextMessage):
        """If auto-translation is on, submits the message for translation."""
        sender = self.bot.getUser(textmessage.nFromUserID)
        is_bot_message = ttstr(textmessage.szFromUsername) == self.bot.server_config["username"] and \
                         ttstr(sender.szNickname) == self.bot.bot_config["nickname"]

        if not is_bot_message and self.auto_translate and \
           (textmessage.nMsgType in [TextMsgType.MSGTYPE_CHANNEL, TextMsgType.MSGTYPE_BROADCAST]):
            self.translation_pool.submit(self._translate_and_send_channel, textmessage)
            return True
        return False

    def handle_private_translation(self, textmessage: TextMessage):
        """If a user is in private translate mode, submits the message for translation."""
        user_id = textmessage.nFromUserID
        if textmessage.nMsgType == TextMsgType.MSGTYPE_USER and user_id in self.user_translation_modes:
            if user_id in self.user_translation_cooldowns and time.time() - self.user_translation_cooldowns.get(user_id, 0) < 1.3:
                return True # Cooldown active, message handled (ignored)
            
            self.user_translation_cooldowns[user_id] = time.time()
            self.translation_pool.submit(self._translate_and_send_private, textmessage)
            return True
        return False

    def handle_whisper_translation(self, textmessage: TextMessage):
        """
        If any user has whisper translate enabled, this translates channel messages
        and sends them privately to that user.
        """
        if textmessage.nMsgType not in [TextMsgType.MSGTYPE_CHANNEL, TextMsgType.MSGTYPE_BROADCAST]:
            return False

        # Ignore messages sent by the bot itself to prevent translation loops
        if textmessage.nFromUserID == self.bot.getMyUserID():
            return False

        # If there are no users in whisper mode, do nothing
        if not self.whisper_translate_modes:
            return False

        for recipient_id, settings in self.whisper_translate_modes.items():
            # Don't translate a user's own messages back to them
            if textmessage.nFromUserID == recipient_id:
                continue

            self.translation_pool.submit(self._translate_and_send_whisper, textmessage, recipient_id, settings)        
        # We return False because this doesn't "consume" the message; 
        # other handlers might still need to process it (like public channel translation).
        return False
        
    def _translate_and_send_channel(self, textmessage: TextMessage):
        """Worker thread for channel translation."""
        message_text = ttstr(textmessage.szMessage)
        if message_text == self.last_translated_message:
            return

        try:
            detected_lang = langdetect.detect(message_text)
            if detected_lang == self.target_lang:
                return
        except LangDetectException:
            pass

        try:
            translated = GoogleTranslator(source=self.source_lang, target=self.target_lang).translate(message_text)
            if translated:
                self.bot.send_message(f"{translated}")
                self.last_translated_message = message_text
        except LanguageNotSupportedException:
            self.bot.send_message(self._("The language you have requested is not supported or Invalid Language Code. Disabling translation."))
        except Exception as e:
            self.bot.send_message(self._("Error during translation: {e}. Disabling auto-translate.").format(e=e))
            self.auto_translate = False

    def _translate_and_send_private(self, textmessage: TextMessage):
        """Worker thread for private translation."""
        user_id = textmessage.nFromUserID
        translation_mode = self.user_translation_modes.get(user_id)
        if not translation_mode:
            return

        user = self.bot.getUser(user_id)
        if not user or user.nChannelID != self.bot.getMyChannelID():
            del self.user_translation_modes[user_id]
            self.bot.privateMessage(user_id, self._("Private translate mode disabled as you are no longer in the same channel as the bot."))
            return

        try:
            message_text = ttstr(textmessage.szMessage)
            translated = GoogleTranslator(
                source=translation_mode["source"], target=translation_mode["target"]
            ).translate(message_text)
            if translated and translated.strip().lower() != message_text.strip().lower():
                self.bot.send_message(self._("{nickname} says: {translated}").format(nickname=ttstr(user.szNickname), translated=translated))
        except LanguageNotSupportedException:
            self.bot.privateMessage(user_id, self._("The language you have requested is not supported or Invalid Language Code. Disabling translation."))
            if user_id in self.user_translation_modes:
                del self.user_translation_modes[user_id]
        except Exception as e:
            self.bot.privateMessage(user_id, self._("Error: {e}. Disabling private translate mode.").format(e=e))
            if user_id in self.user_translation_modes:
                del self.user_translation_modes[user_id]

    def _translate_and_send_whisper(self, textmessage: TextMessage, recipient_id: int, settings: dict):
        """Worker thread for whisper translation to a specific user."""
        try:
            original_sender = self.bot.getUser(textmessage.nFromUserID)
            if not original_sender:
                return # Can't get sender info, abort

            message_text = ttstr(textmessage.szMessage)
            translated = GoogleTranslator(source=settings["source"], target=settings["target"]).translate(message_text)

            if translated and translated.strip().lower() != message_text.strip().lower():
                self.bot.privateMessage(recipient_id, f"{ttstr(original_sender.szNickname)} says: {translated}")
        except LanguageNotSupportedException:
            self.bot.send_message(self._("The language you have requested is not supported or Invalid Language Code. Disabling translation."))
        except Exception as e:
            self.bot.privateMessage(recipient_id, self._("A translation error occurred: {e}. Disabling translation.").format(e=str(e).split('\n')[0]))
            if recipient_id in self.whisper_translate_modes:
                del self.whisper_translate_modes[recipient_id]

    def handle_t_command(self, textmessage, *args):
        """Toggles auto-translation for channel messages."""
        if self.auto_translate:
            self.auto_translate = False
            self.bot.send_message(self._("Auto-translation disabled."))
        else:
            self.auto_translate = True
            if len(args) >= 2:
                self.source_lang, self.target_lang = args[0], args[1]
            self.bot.send_message(self._("Auto-translation enabled from {source} to {target}.").format(source=self.source_lang, target=self.target_lang))

    def handle_pt_command(self, textmessage, *args):
        """Toggles private translation mode for a user."""
        user_id = textmessage.nFromUserID
        if user_id in self.user_translation_modes:
            del self.user_translation_modes[user_id]
            self.bot.privateMessage(user_id, self._("Private translate mode disabled."))
        else:
            if len(args) < 2:
                self.bot.privateMessage(user_id, self._("Usage: /pt <source_lang> <target_lang>"))
                return
            self.user_translation_modes[user_id] = {"source": args[0], "target": args[1]}
            self.bot.privateMessage(user_id, self._("Private translate mode enabled from {source} to {target}.").format(source=args[0], target=args[1]))

    def handle_wt_command(self, textmessage, *args):
        """Toggles whisper translation mode for a user."""
        user_id = textmessage.nFromUserID
        if user_id in self.whisper_translate_modes:
            del self.whisper_translate_modes[user_id]
            self.bot.privateMessage(user_id, self._("Whisper translate mode disabled."))
        else:
            if len(args) < 2:
                self.bot.privateMessage(user_id, self._("Usage: /wt <source_lang> <target_lang>"))
                return
            self.whisper_translate_modes[user_id] = {"source": args[0], "target": args[1]}
            self.bot.privateMessage(user_id, self._("Whisper translate mode enabled from {source} to {target}.").format(source=args[0], target=args[1]))
