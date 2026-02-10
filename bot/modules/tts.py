from TeamTalk5 import ttstr
import TeamTalk5 as teamtalk
import os
import asyncio
import langdetect
import random
from gtts import gTTS
import edge_tts


class EdgeTTSWrapper:
    def __init__(self):
        self.voice = "en-US-JennyNeural"
        self.rate = "+0%"
        self.pitch = "+0Hz"
        self.volume = "+0%"

    async def get_voices_list(self):
        voices = await edge_tts.list_voices()
        normalized = []
        for voice in voices:
            normalized.append({
                "FriendlyName": voice.get("FriendlyName") or voice.get("Name") or voice.get("ShortName"),
                "ShortName": voice.get("ShortName") or voice.get("Name"),
                "Locale": voice.get("Locale"),
            })
        return normalized

    async def set_voice(self, voice_name):
        if voice_name:
            self.voice = voice_name

    async def set_rate(self, rate):
        self.rate = self._format_rate(rate)

    async def set_pitch(self, pitch):
        self.pitch = self._format_pitch(pitch)

    async def set_volume(self, volume):
        self.volume = self._format_volume(volume)

    async def synthesize(self, text, filepath):
        communicate = edge_tts.Communicate(
            text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
            volume=self.volume,
        )
        await communicate.save(filepath)
        return os.path.getsize(filepath) if os.path.exists(filepath) else 0

    @staticmethod
    def _format_rate(rate):
        try:
            rate_value = int(rate)
        except (TypeError, ValueError):
            rate_value = 0
        rate_value = max(-100, min(100, rate_value))
        return f"{rate_value:+d}%"

    @staticmethod
    def _format_pitch(pitch):
        try:
            pitch_value = int(pitch)
        except (TypeError, ValueError):
            pitch_value = 0
        pitch_value = max(-100, min(100, pitch_value))
        return f"{pitch_value:+d}Hz"

    @staticmethod
    def _format_volume(volume):
        try:
            volume_value = float(volume)
        except (TypeError, ValueError):
            volume_value = 1.0
        volume_value = max(0.0, min(1.0, volume_value))
        percent = int(round((volume_value - 1.0) * 100))
        return f"{percent:+d}%"

class TTSCog:
    """
    A module for handling all Text-to-Speech (TTS) related commands.
    """
    def __init__(self, bot):
        self.bot = bot
        self._ = bot._
        self.speech_engine = EdgeTTSWrapper()
        self.user_speech_settings = {}
        self.speech_thread = None
        self.voice_thread = None
        self.speech_synthesis_in_progress = False

    def register(self, command_handler):
        """Registers all the TTS commands with the command handler."""
        command_handler.register_command('say', self.handle_say_command, help_text=self._("Makes the bot speak text. Usage: /say <text> or ' <text>"))
        command_handler.register_command('rate', self.handle_rate_command, help_text=self._("Sets the TTS voice rate, [-100 to 100]. Usage: /rate <value>"))
        command_handler.register_command('pitch', self.handle_pitch_command, help_text=self._("Sets the TTS voice pitch, [-100 to 100]. Usage: /pitch <value>"))
        command_handler.register_command('volume', self.handle_volume_command, help_text=self._("Sets the TTS voice volume, [0.1 to 1.0]. Usage: /volume <value>"))
        command_handler.register_command('voice', self.handle_voice_command, help_text=self._("Sets the TTS voice. Usage: /voice <voice_name>"))
        command_handler.register_command('s', self.handle_stop_speech_command, admin_only=True, help_text=self._("Stops the bot's current speech file stream."))
        command_handler.register_command('ld', self.handle_ld_command, help_text=self._("Toggles automatic language detection for text to speech."))
        command_handler.register_command('voices', self.list_voices_thread, help_text=self._("Lists available TTS voices. Without arguments, lists all available voices for all languages. Usage: /get_voices <lang_code (Optional)>"))

    def on_user_parted(self, user):
        """Cleans up TTS state when a user leaves."""
        user_id = user.nUserID
        if user_id in self.user_speech_settings:
            del self.user_speech_settings[user_id]

    def handle_prefixed_message(self, textmessage):
        """
        Handles special-prefix messages like "'" for tts.
        Returns True if the message was handled, False otherwise.
        """
        message_text = ttstr(textmessage.szMessage)
        if message_text.startswith("'"):
            # We call the main 'say' handler but pass the text without the prefix
            text_to_speak = message_text[1:].strip()
            self.handle_say_command(textmessage, *text_to_speak.split())
            return True
        return False

    def handle_say_command(self, textmessage, *args):
        user = self.bot.getUser(textmessage.nFromUserID)
        if user.nChannelID != self.bot.getMyChannelID():
            self.bot.privateMessage(textmessage.nFromUserID, self._("Sorry, You are not in the same channel"))
            return

        if self.speech_synthesis_in_progress:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Another speech synthesis is already in progress. Please wait."))
            return

        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Please provide some text to speak."))
            return
            
        text_to_speak = " ".join(args)
        self.bot.quick_task_pool.submit(self._run_async_speak, text_to_speak, textmessage.nFromUserID)

    def _run_async_speak(self, text_to_speak, user_id):
        """Wrapper to run the async _speak method using asyncio."""
        self.speech_synthesis_in_progress = True
        try:
            asyncio.run(self._speak(text_to_speak, user_id))
        finally:
            self.speech_synthesis_in_progress = False

    async def _speak(self, text_to_speak, user_id, filename="speech.mp3"):
        """Asynchronous speech synthesis logic."""
        filepath = os.path.join("files", filename)
        try:
            user_settings = self.user_speech_settings.get(user_id, {})
            voice_name = user_settings.get("voice")
            rate = user_settings.get("rate", 0)
            pitch = user_settings.get("pitch", 0)
            volume = user_settings.get("volume", 1.0)
            lang_detection = user_settings.get("lang_detection", False)

            if lang_detection:
                try:
                    detected_lang = langdetect.detect(text_to_speak)
                    voices = await self.speech_engine.get_voices_list()
                    matching_voices = [v for v in voices if (v.get("Locale") or "").lower().startswith(detected_lang)]
                    if matching_voices:
                        voice_name = random.choice(matching_voices)["ShortName"]
                        self.bot.privateMessage(user_id, self._("Using voice {voice_name} for {detected_lang}").format(voice_name=voice_name, detected_lang=detected_lang))
                    else:
                        # Fallback to gTTS if no matching voice
                        self.bot.privateMessage(user_id, self._("The detected language ({detected_lang}) is not available in Microsoft Speech, using Google voices.").format(detected_lang=detected_lang))
                        tts = gTTS(text=text_to_speak, lang=detected_lang)
                        tts.save(filepath)
                        self._stream_file(user_id, filepath)
                        return # Exit after streaming
                except langdetect.lang_detect_exception.LangDetectException:
                    self.bot.privateMessage(user_id, self._("Language detection failed. Using default voice."))

            await self.speech_engine.set_voice(voice_name or "en-US-JennyNeural")
            await self.speech_engine.set_rate(rate)
            await self.speech_engine.set_pitch(pitch)
            await self.speech_engine.set_volume(volume)
            
            bytes_written = await self.speech_engine.synthesize(text_to_speak, filepath)
            if bytes_written > 0:
                self._stream_file(user_id, filepath)

        except Exception as e:
            self.bot.privateMessage(user_id, self._("Error during speech synthesis: {e}").format(e=e))

    def _stream_file(self, user_id, filepath):
        """Helper to stream the generated audio file."""
        streamer = teamtalk.VideoCodec()
        streamer.nCodec = 1
        user = self.bot.getUser(user_id)
        if user and user.nChannelID == self.bot.getMyChannelID():
            self.bot.startStreamingMediaFileToChannel(ttstr(filepath), streamer)

    def handle_rate_command(self, textmessage, *args):
        user_id = textmessage.nFromUserID
        if not args:
            self.bot.privateMessage(user_id, self._("Invalid command. Usage: /rate <rate_value>."))
            return
        try:
            rate_value = int(args[0])
            if -100 <= rate_value <= 100:
                self.user_speech_settings.setdefault(user_id, {})["rate"] = rate_value
                self.bot.privateMessage(user_id, self._("Rate set to {rate}.").format(rate=rate_value))
            else:
                self.bot.privateMessage(user_id, self._("Invalid rate value. Rate should be between -100 and 100."))
        except ValueError:
            self.bot.privateMessage(user_id, self._("Invalid command. Usage: /rate <rate_value>."))

    def handle_pitch_command(self, textmessage, *args):
        user_id = textmessage.nFromUserID
        if not args:
            self.bot.privateMessage(user_id, self._("Invalid command. Usage: /pitch <pitch_value>"))
            return
        try:
            pitch_value = int(args[0])
            if -100 <= pitch_value <= 100:
                self.user_speech_settings.setdefault(user_id, {})["pitch"] = pitch_value
                self.bot.privateMessage(user_id, self._("Pitch set to {pitch}.").format(pitch=pitch_value))
            else:
                self.bot.privateMessage(user_id, self._("Invalid pitch value. Pitch should be between -100 and 100."))
        except ValueError:
            self.bot.privateMessage(user_id, self._("Invalid command. Usage: /pitch <pitch_value>"))

    def handle_volume_command(self, textmessage, *args):
        user_id = textmessage.nFromUserID
        if not args:
            self.bot.privateMessage(user_id, self._("Invalid command. Usage: /volume <volume_value>"))
            return
        try:
            volume_value = float(args[0])
            if 0.1 <= volume_value <= 1.0:
                self.user_speech_settings.setdefault(user_id, {})["volume"] = volume_value
                self.bot.privateMessage(user_id, self._("Volume set to {volume}.").format(volume=volume_value))
            else:
                self.bot.privateMessage(user_id, self._("Invalid volume value. Volume should be between 0.1 and 1.0."))
        except ValueError:
            self.bot.privateMessage(user_id, self._("Invalid command. Usage: /volume <volume_value>"))

    def handle_voice_command(self, textmessage, *args):
        user_id = textmessage.nFromUserID
        if not args:
            self.bot.privateMessage(user_id, self._("Invalid command. Usage: /voice <voice_name>."))
            return
        voice_name = " ".join(args)
        self.user_speech_settings.setdefault(user_id, {})["voice"] = voice_name
        self.bot.privateMessage(user_id, self._("Voice set to {voice_name}.").format(voice_name=voice_name))

    def handle_stop_speech_command(self, textmessage, *args):
        user = self.bot.getUser(textmessage.nFromUserID)
        if user.nChannelID != self.bot.getMyChannelID():
            self.bot.privateMessage(textmessage.nFromUserID, self._("Sorry, You are not in the same channel"))
            return
        self.bot.stopStreamingMediaFileToChannel()

    def handle_ld_command(self, textmessage, *args):
        user_id = textmessage.nFromUserID
        current_setting = self.user_speech_settings.get(user_id, {}).get("lang_detection", False)
        self.user_speech_settings.setdefault(user_id, {})["lang_detection"] = not current_setting
        
        if not current_setting:
            self.bot.privateMessage(user_id, self._("Language detection is now ON."))
        else:
            self.bot.privateMessage(user_id, self._("Language detection is now OFF."))

    def list_voices_thread(self, textmessage, *args):
        """Runs the async voice listing in the bot's thread pool."""
        self.bot.quick_task_pool.submit(self._run_async_list_voices, textmessage, *args)

    def _run_async_list_voices(self, textmessage, *args):
        """Wrapper to run the async _list_voices method."""
        asyncio.run(self._list_voices(textmessage, *args))

    async def _list_voices(self, textmessage, *args):
        """Asynchronous logic for listing voices."""
        user_id = textmessage.nFromUserID
        try:
            voices = await self.speech_engine.get_voices_list()
            lang_code = args[0].lower() if args else None
            
            found_voices = []
            for voice in voices:
                locale = (voice.get("Locale") or "").lower()
                if not lang_code or locale.startswith(lang_code):
                    found_voices.append(self._("Name: {voice_name}, ShortName: {short_name}, Locale: {locale}").format(
                        voice_name=voice.get('FriendlyName'), short_name=voice.get('ShortName'), locale=voice.get('Locale')))
            
            if not found_voices:
                self.bot.privateMessage(user_id, self._("No voices found for the specified language code."))
                return

            # Send the list in chunks to avoid message length limits
            for i in range(0, len(found_voices), 4):
                chunk = "\n".join(found_voices[i:i+4])
                self.bot.privateMessage(user_id, chunk)

        except Exception as e:
            self.bot.privateMessage(user_id, self._("Error listing voices: {e}").format(e=e))
