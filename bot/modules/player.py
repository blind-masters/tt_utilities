from TeamTalk5 import ttstr
import os
import yt_dlp
import threading
import time
import random

class PlayerCog:
    """
    A module for handling all music and media player related commands.
    """
    def __init__(self, bot):
        self.bot = bot
        self.player = bot.player
        self._ = bot._        
        self.download_in_progress = False
        self.upload_timers = {}
        self.loading_new_track = False        
        self.player.end_callback = self.on_playback_end
        self.playback_mode = "tl"
        self.random_pool = []
        self.mode_labels = {
            "st": self._("single track"),
            "rt": self._("repeat single track"),
            "tl": self._("track list"),
            "rtl": self._("repeat track list"),
            "rnd": self._("random"),
        }

    def register(self, command_handler):
        """Registers all the player commands with the command handler."""
        command_handler.register_command('u', self.handle_play_url_command, help_text=self._("Plays a stream from a URL. Usage: /u <link>"))
        command_handler.register_command('p', self.handle_play_search_or_pause_command, help_text=self._("Searches on Youtube and plays the search result. Without arguments, pauses or resumes the currently playing stream or video. Usage: /p <query (Optional)>"))
        command_handler.register_command('n', self.handle_next_track_command, help_text=self._("Plays the next track in the search results."))
        command_handler.register_command('b', self.handle_previous_track_command, help_text=self._("Plays the previous track in the search results."))
        command_handler.register_command('v', self.handle_change_volume_command, help_text=self._("Changes playback volume. Without arguments, shows the current volume. Usage: /v <volume (Optional)>"))
        command_handler.register_command('sp', self.handle_speed_command, help_text=self._("Changes playback speed. Usage: /sp + or /sp - or /sp <value>. Without arguments, shows the current speed."))
        command_handler.register_command('m', self.handle_mode_command, help_text=self._("Shows or changes playback mode. Usage: /m or /m <mode>"))
        command_handler.register_command('gl', self.handle_get_link_command, help_text=self._("Gets the link of the currently playing track."))
        command_handler.register_command('d', self.handle_get_duration_command, help_text=self._("Shows the duration of the current track."))
        command_handler.register_command('r', self.handle_history_command, help_text=self._("Shows recent tracks or plays from history. Usage: /r [index]. When used without arguments, shows a history of the recent tracks."))
        command_handler.register_command('dl', self.handle_download_command, help_text=self._("Downloads the current track as an audio file. Usage: /dl <link (Optional)>. When sent without arguments, downloads the currently playing track."))
        command_handler.register_command('s', self.handle_stop_command, help_text=self._("Stops playback."))

    def handle_prefixed_message(self, textmessage):
        """
        Handles special-prefix messages like '+' for seek that don't use the standard command prefix.
        Returns True if the message was handled, False otherwise.
        """
        message_text = ttstr(textmessage.szMessage)
        if message_text.startswith("+"):
            self.handle_seek_forward(textmessage, message_text[1:].strip())
            return True
        elif message_text.startswith("-"):
            self.handle_seek_back(textmessage, message_text[1:].strip())
            return True
        return False

    def _is_in_same_channel(self, user_id):
        """Helper to check if a user is in the bot's channel."""
        user = self.bot.getUser(user_id)
        if user.nChannelID != self.bot.getMyChannelID():
            self.bot.privateMessage(user_id, self._("You are not in the same channel"))
            return False
        return True

    def _announce(self, channel_message, user_id=None, private_message=None):
        if self.bot.playback_config.get("send_channel_messages", True):
            self.bot.send_message(channel_message)
            return
        if self.bot.playback_config.get("channel_messages_mode", "private") != "private":
            return
        if user_id is None or not private_message:
            return
        self.bot.privateMessage(user_id, private_message)

    def _announce_autoplay(self, title):
        if self.bot.playback_config.get("send_channel_messages", True):
            self.bot.send_message(self._("Auto playing: {title}").format(title=title))

    def _reset_random_pool(self):
        self.random_pool = []

    def _init_random_pool(self):
        count = len(self.player.search_results) if self.player.search_results else 0
        if count <= 0:
            self.random_pool = []
            return
        self.random_pool = list(range(count))
        current_index = self.player.current_search_index
        if 0 <= current_index < count and current_index in self.random_pool and count > 1:
            self.random_pool.remove(current_index)

    def _next_random_index(self):
        count = len(self.player.search_results) if self.player.search_results else 0
        if count <= 0:
            return None
        if not self.random_pool:
            self._init_random_pool()
        if not self.random_pool:
            return None
        index = random.choice(self.random_pool)
        self.random_pool.remove(index)
        return index

    def _prefetch_next_in_list(self):
        if not self.player.search_results:
            return
        if self.playback_mode not in ("tl", "rtl"):
            return
        count = len(self.player.search_results)
        next_index = self.player.current_search_index + 1
        if next_index >= count:
            if self.playback_mode == "rtl":
                next_index = 0
            else:
                return
        next_link = self.player.search_results[next_index].get('link')
        if next_link:
            self.bot.io_pool.submit(self.player.prefetch_stream_info, next_link)

    def _play_index(self, index, announce_autoplay=False, user_id=None):
        if not self.player.search_results:
            return
        if index < 0 or index >= len(self.player.search_results):
            return
        self.loading_new_track = True
        self.player.stop()
        self.player.current_search_index = index
        if index in self.random_pool:
            self.random_pool.remove(index)
        next_video = self.player.search_results[index]
        self.player.current_link = next_video['link']
        self.bot.enableVoiceTransmission(True)
        self.player.play_stream(next_video['link'])
        if announce_autoplay:
            self._announce_autoplay(next_video.get('title') or self.player.current_title)
        elif user_id is not None:
            self.bot.privateMessage(user_id, self._("Playing: {title}").format(title=next_video.get('title') or self.player.current_title))
        self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(self._("Playing: {title}").format(title=self.player.current_title)))
        self.loading_new_track = False
        self._prefetch_next_in_list()

    def handle_play_url_command(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return
            
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command. Usage: /u <link>"))
            return

        link = " ".join(args)
        if self._looks_like_playlist(link):
            self.bot.io_pool.submit(self._play_playlist_url_task, link, textmessage.nFromUserID)
            return

        self.player.search_results = []
        self.player.current_search_index = 0
        self._reset_random_pool()
        self.player.clear_prefetch_cache()

        self.player.current_link = link
        self.bot.enableVoiceTransmission(True)
        self.player.play_stream(link)
        user_nickname = ttstr(self.bot.getUser(textmessage.nFromUserID).szNickname)
        self._announce(
            self._("{nickname} requested playing from a URL").format(nickname=user_nickname),
            textmessage.nFromUserID,
            self._("Playing: {title}").format(title=self.player.current_title),
        )
        self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(self._("Playing: {title}").format(title=self.player.current_title)))

    def _looks_like_playlist(self, link):
        lowered = link.lower()
        return "list=" in lowered or "/playlist" in lowered

    def _play_playlist_url_task(self, link, user_id):
        results = self.player.fetch_playlist_entries(link)
        if not results:
            self.bot.privateMessage(user_id, self._("No playlist items found."))
            return

        self.player.clear_prefetch_cache()
        self.player.search_results = results
        self.player.current_search_index = 0
        self._init_random_pool()
        first_video = results[0]
        self.player.current_link = first_video['link']
        self.bot.enableVoiceTransmission(True)
        self.player.play_stream(first_video['link'])
        user_nickname = ttstr(self.bot.getUser(user_id).szNickname)
        self._announce(
            self._("{nickname} requested playing from a playlist").format(nickname=user_nickname),
            user_id,
            self._("Playing: {title}").format(title=first_video['title']),
        )
        self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(self._("Playing: {title}").format(title=self.player.current_title)))
        self._prefetch_next_in_list()

    def handle_play_search_or_pause_command(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return

        if args: # This is a search request
            if self.player.is_playing:
                self.bot.privateMessage(textmessage.nFromUserID, self._("The bot is already playing something. Please stop the playback before attempting to play something else"))
                return
            query = " ".join(args)
            self.bot.privateMessage(textmessage.nFromUserID, self._("Searching..."))
            self.bot.io_pool.submit(self._search_and_play_task, query, textmessage.nFromUserID)
        else: # This is a pause/resume request
            self.handle_pause_command(textmessage)

    def _search_and_play_task(self, query, user_id):
        """Task to be run in the thread pool for searching and playing."""
        results = self.player.search_youtube(query)
        if results:
            self.player.clear_prefetch_cache()
            self.player.search_results = results
            self.player.current_search_index = 0
            self._init_random_pool()
            first_video = results[0]
            self.player.current_link = first_video['link']
            self.bot.enableVoiceTransmission(True)
            self.player.play_stream(first_video['link'])
            user_nickname = ttstr(self.bot.getUser(user_id).szNickname)
            self._announce(
                self._("{nickname} requested to play: {title}").format(nickname=user_nickname, title=first_video['title']),
                user_id,
                self._("Playing: {title}").format(title=first_video['title']),
            )
            self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(self._("Playing: {title}").format(title=self.player.current_title)))
            self._prefetch_next_in_list()
        else:
            self.bot.privateMessage(user_id, self._("No results found for '{query}'.").format(query=query))

    def handle_pause_command(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return
            
        title = self.player.current_title
        if self.player.is_playing and not self.player.pause:
            self.player.pause_stream()
            self.bot.enableVoiceTransmission(False)
            user_nickname = ttstr(self.bot.getUser(textmessage.nFromUserID).szNickname)
            self._announce(
                self._("{nickname} paused the playback").format(nickname=user_nickname),
                textmessage.nFromUserID,
                self._("Paused: {title}").format(title=title),
            )
            self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(self._("Paused: {title}").format(title=title)))
        elif self.player.pause:
            self.player.pause = False
            self.bot.enableVoiceTransmission(True)
            self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(self._("Playing: {title}").format(title=title)))
        else:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Nothing is currently playing to pause or resume."))

    def handle_seek_forward(self, textmessage, arg_str):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return
        if not self.player.is_playing:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Nothing is currently playing"))
            return
        
        try:
            amount = int(arg_str) if arg_str else self.bot.playback_config['seek_step']
            self.player.seek_forward(amount)
        except ValueError:
            self.player.seek_forward(self.bot.playback_config['seek_step'])
            
    def handle_seek_back(self, textmessage, arg_str):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return
        if not self.player.is_playing:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Nothing is currently playing"))
            return
        
        try:
            amount = int(arg_str) if arg_str else self.bot.playback_config['seek_step']
            self.player.seek_back(amount)
        except ValueError:
            self.player.seek_back(self.bot.playback_config['seek_step'])

    def handle_next_track_command(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return

        def play_next_track():
            if not self.player.search_results:
                self.bot.privateMessage(textmessage.nFromUserID, self._("No search results to play from."))
                return

            if self.player.current_search_index < len(self.player.search_results) - 1:
                next_index = self.player.current_search_index + 1
                self._play_index(next_index, user_id=textmessage.nFromUserID)
            else:
                self.bot.privateMessage(textmessage.nFromUserID, self._("You've reached the end of the search results."))
        
        self.bot.io_pool.submit(play_next_track)

    def handle_previous_track_command(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return

        def play_previous_track():
            if not self.player.search_results:
                self.bot.privateMessage(textmessage.nFromUserID, self._("No search results to play from."))
                return

            if self.player.current_search_index > 0:
                prev_index = self.player.current_search_index - 1
                self._play_index(prev_index, user_id=textmessage.nFromUserID)
            else:
                self.bot.privateMessage(textmessage.nFromUserID, self._("You are at the beginning of the search results."))

        self.bot.io_pool.submit(play_previous_track)
        
    def handle_stop_command(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return

        if self.player.is_playing:
            self.player.stop()
            self.player.current_link = None
            self.player.search_results = {}
            self.player.current_search_index = 0
            self._reset_random_pool()
            self.player.clear_prefetch_cache()
            self.bot.enableVoiceTransmission(False)
            user_nickname = ttstr(self.bot.getUser(textmessage.nFromUserID).szNickname)
            self._announce(
                self._("{nickname} stopped the playback").format(nickname=user_nickname),
                textmessage.nFromUserID,
                self._("Playback stopped."),
            )
            status_msg = self.bot.bot_config.get('status_message', "")
            self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(status_msg))
        else:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Nothing is currently playing"))
            
    def handle_change_volume_command(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return
        
        try:
            if not args:
                self.bot.privateMessage(textmessage.nFromUserID, self._("The current volume is {volume}").format(volume=int(self.player.volume)))
                return
            
            volume = int(args[0])
            max_volume = self.bot.playback_config['max_volume']
            if volume > max_volume:
                self.bot.privateMessage(textmessage.nFromUserID, self._("Maximum allowed volume is {max_volume}").format(max_volume=max_volume))
            else:
                self.player.set_volume(volume)
                user_nickname = ttstr(self.bot.getUser(textmessage.nFromUserID).szNickname)
                self._announce(
                    self._("{name} has changed the volume to {volume}").format(name=user_nickname, volume=volume),
                    textmessage.nFromUserID,
                    self._("Volume set to {volume}").format(volume=volume),
                )
        except (ValueError, IndexError):
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command. Usage: /v [volume_level]"))

    def handle_speed_command(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return

        try:
            current_speed = float(getattr(self.player, "speed", 1.0))
        except (TypeError, ValueError):
            current_speed = 1.0

        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Current speed: {speed}").format(speed=round(current_speed, 2)))
            return

        arg = args[0].strip().lower()
        if arg in ("+", "plus"):
            new_speed = current_speed + 0.1
        elif arg in ("-", "minus"):
            new_speed = max(0.1, current_speed - 0.1)
        else:
            try:
                new_speed = float(arg)
            except ValueError:
                self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command. Usage: /sp + or /sp - or /sp <value>"))
                return

        if new_speed <= 0:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Speed must be greater than 0."))
            return

        self.player.speed = new_speed
        user_nickname = ttstr(self.bot.getUser(textmessage.nFromUserID).szNickname)
        self._announce(
            self._("{name} set speed to {speed}").format(name=user_nickname, speed=round(new_speed, 2)),
            textmessage.nFromUserID,
            self._("Speed set to {speed}").format(speed=round(new_speed, 2)),
        )

    def handle_mode_command(self, textmessage, *args):
        user_id = textmessage.nFromUserID
        if not args:
            current_label = self.mode_labels.get(self.playback_mode, self.playback_mode)
            lines = [
                self._("Current mode is {label} ({mode})").format(label=current_label, mode=self.playback_mode),
                self._("Available modes:"),
                self._("single track (st)"),
                self._("repeat single track (rt)"),
                self._("track list (tl)"),
                self._("repeat track list (rtl)"),
                self._("random (rnd)"),
            ]
            self.bot.privateMessage(user_id, "\n".join(lines))
            return

        mode = args[0].strip().lower()
        if mode not in self.mode_labels:
            self.bot.privateMessage(user_id, self._("Invalid mode. Use /m to see available modes."))
            return

        self.playback_mode = mode
        if mode == "rnd":
            self._init_random_pool()
        label = self.mode_labels.get(mode, mode)
        self.bot.privateMessage(user_id, self._("Playback mode changed to {label}.").format(label=label))

    def on_playback_end(self):
        """Callback function to be called when playback ends."""
        if self.loading_new_track:
            return

        def handle_end():
            mode = self.playback_mode
            if mode == "rt":
                if self.player.current_link:
                    self.loading_new_track = True
                    self.bot.enableVoiceTransmission(True)
                    if self.player.replay_current():
                        self.bot.doChangeStatus(
                            ttstr(self.bot.bot_config['gender']),
                            ttstr(self._("Playing: {title}").format(title=self.player.current_title)),
                        )
                    else:
                        self._finish_playback()
                    self.loading_new_track = False
                    return

            if mode in ("tl", "rtl", "rnd"):
                if not self.player.search_results:
                    self._finish_playback()
                    return
                next_index = None
                if mode == "rnd":
                    next_index = self._next_random_index()
                else:
                    if self.player.current_search_index < len(self.player.search_results) - 1:
                        next_index = self.player.current_search_index + 1
                    elif mode == "rtl":
                        next_index = 0
                if next_index is None:
                    self._finish_playback()
                    return
                self._play_index(next_index, announce_autoplay=True)
                return

            self._finish_playback()

        self.bot.io_pool.submit(handle_end)

    def _finish_playback(self):
        self.bot.enableVoiceTransmission(False)
        status_msg = self.bot.bot_config.get('status_message', "")
        self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(status_msg))

    def handle_get_link_command(self, textmessage, *args):
        if self.player.current_link and self.player.current_link.startswith("http"):
            self.bot.privateMessage(textmessage.nFromUserID, self.player.current_link)
        else:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Nothing is currently playing"))

    def handle_get_duration_command(self, textmessage, *args):
        if not self.player.is_playing:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Nothing is currently playing"))
            return

        elapsed_time = self.player.playback_time or 0
        total_duration = self.player.duration or 0
        remaining_time = total_duration - elapsed_time
        
        self.bot.privateMessage(textmessage.nFromUserID, 
            self._("Total duration: {total_duration}. Elapsed time: {elapsed_time}. Remaining time: {remaining_time}").format(
                total_duration=self.player.format_time(total_duration), 
                elapsed_time=self.player.format_time(elapsed_time), 
                remaining_time=self.player.format_time(remaining_time)))

    def handle_history_command(self, textmessage, *args):
        if args:
            self.handle_play_from_history(textmessage, *args)
        else:
            self.handle_recent_history(textmessage)

    def handle_recent_history(self, textmessage):
        history_str = self.player.get_recent_history()
        history_lines = history_str.splitlines()
        for i in range(0, len(history_lines), 4):
            chunk = "\n".join(history_lines[i:i + 4])
            self.bot.privateMessage(textmessage.nFromUserID, chunk)

    def handle_play_from_history(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return

        try:
            index = int(args[0])
            self.player.search_results = {}
            self.player.current_search_index = 0
            self._reset_random_pool()
            self.player.clear_prefetch_cache()
            self.bot.enableVoiceTransmission(True)
            result_message = self.player.play_from_history(index)
            if "Playing" in result_message:
                user_nickname = ttstr(self.bot.getUser(textmessage.nFromUserID).szNickname)
                self._announce(
                    self._("{nickname} requested to play {title} from history").format(nickname=user_nickname, title=self.player.current_title),
                    textmessage.nFromUserID,
                    self._("Playing: {title}").format(title=self.player.current_title),
                )
                self.bot.doChangeStatus(ttstr(self.bot.bot_config['gender']), ttstr(self._("Playing: {title}").format(title=self.player.current_title)))
            else:
                self.bot.privateMessage(textmessage.nFromUserID, result_message)
        except (ValueError, IndexError):
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command. Usage: /r <index>"))

    def handle_download_command(self, textmessage, *args):
        if not self._is_in_same_channel(textmessage.nFromUserID):
            return
        
        if self.download_in_progress:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Download already in progress. Please wait."))
            return

        link = " ".join(args) if args else self.player.current_link
        
        if not link:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Invalid command. Usage: /dl <youtube_link> or play a track first."))
            return

        self.bot.io_pool.submit(self._download_and_upload_task, textmessage.nFromUserID, link)

    def _download_and_upload_task(self, user_id, link):
        """Task for downloading and uploading audio, run in the thread pool."""
        self.download_in_progress = True
        self.bot.privateMessage(user_id, self._("Downloading audio. Please wait..."))
        try:
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': os.path.join("files", "%(title)s.%(ext)s"),
                'cookiefile': self.bot.cookiefile
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(link, download=True)
                filename = ydl.prepare_filename(info_dict)

            channel_id = self.bot.getUser(user_id).nChannelID
            self.bot.doSendFile(channel_id, ttstr(filename))
            filename_only = os.path.basename(filename)
            self.bot.privateMessage(user_id, self._("File {filename} downloaded. Uploading...").format(filename=filename_only))
            
            if self.bot.bot_config['video_deletion_timer'] > 0:
                self.upload_timers[filename] = threading.Timer(
                    self.bot.bot_config['video_deletion_timer'] * 60, 
                    self.delete_uploaded_file, 
                    args=(filename, channel_id)
                )
                self.upload_timers[filename].start()

        except Exception as e:
            self.bot.privateMessage(user_id, self._("Error downloading or uploading: {e}").format(e=str(e)))
        finally:
            self.download_in_progress = False

    def delete_uploaded_file(self, filename, channel_id):
        """Deletes the uploaded audio file after the timer expires."""
        try:
            file_id = self.get_file_id_by_name(channel_id, os.path.basename(filename)) 
            if file_id:
                self.bot.doDeleteFile(channel_id, file_id)
            if os.path.exists(filename):
                os.remove(filename)
            del self.upload_timers[filename]
        except Exception as e:
            print(self._("Error deleting file: {e}").format(e=str(e)))

    def get_file_id_by_name(self, channel_id, filename):
        """Gets the file ID from the TeamTalk server based on filename."""
        files = self.bot.getChannelFiles(channel_id)
        for file in files:
            if ttstr(file.szFileName) == filename:
                return file.nFileID
        return None
