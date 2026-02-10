import mpv
import time
import asyncio
import threading
from py_yt import VideosSearch
import yt_dlp

class Player(mpv.MPV):
    def __init__(self, config_handler, cookiefile=None, *args, **kwargs):
        super().__init__(ytdl=False, vo='null', video=False, *args, **kwargs)
        self.config_handler = config_handler # <-- STORE THE INJECTED INSTANCE
        self.playback_config = self.config_handler.get_playback_config()
        self.is_playing=False
        self.volume=self.playback_config['default_volume']
        self.volume_fading = float(self.playback_config.get('volume_fading', 0) or 0)
        self.current_link=None
        self.current_title=None
        self.current_stream_url=None
        self.search_results = {}
        self.current_search_index = 0
        self.recent_history = {}
        self.end_callback = None
        self.set_output_device()
        self._register_end_callback()
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best', 
            'noplaylist': True,
            'extract-audio': True,
            'audio-format': 'm4a',
        }

        if cookiefile:
            ydl_opts['cookiefile'] = cookiefile
        self.ydl_opts = ydl_opts
        self.ydl = yt_dlp.YoutubeDL(ydl_opts)
        self.prefetch_cache = {}
        self.prefetch_lock = threading.Lock()

    def search_youtube(self, query):
        """
        Searches YouTube and returns the results.
        This is a blocking network call and should be run in a thread.
        """
        try:
            return self._run_search(query)
        except Exception as e:
            print(f"Error during YouTube search: {e}")
            return []

    def _run_search(self, query):
        try:
            return asyncio.run(self._search_youtube_async(query))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._search_youtube_async(query))
            finally:
                loop.close()

    async def _search_youtube_async(self, query):
        search = VideosSearch(query, limit=50)
        results = []
        search_result_data = await search.next()
        for video in search_result_data.get('result', []):
            title = video.get('title') or "Unknown title"
            link = video.get('link')
            if not link:
                video_id = video.get('id')
                uri = video.get('uri')
                if video_id:
                    link = f"https://www.youtube.com/watch?v={video_id}"
                elif uri:
                    link = f"https://www.youtube.com{uri}"
            if link:
                results.append({
                    'title': title,
                    'link': link
                })
        return results

    def play_stream(self, link):
        """Plays the audio stream using yt_dlp."""
        try:
            cached = self.prefetch_cache.pop(link, None)
            if cached:
                direct_link = cached.get('url')
                self.current_title = cached.get('title')
            else:
                with self.prefetch_lock:
                    info = self.ydl.extract_info(link, download=False)
                direct_link = info['url']
                self.current_title = info['title']

            self.is_playing = True
            self.play(direct_link)
            self.current_link = link
            self.current_stream_url = direct_link
            self.add_to_recent_history(self.current_title, link)

        except Exception as e:
            print(f"Error playing stream: {e}")

    def fetch_playlist_entries(self, link):
        """Fetches playlist entries without resolving streams."""
        try:
            ydl_opts = dict(self.ydl_opts)
            ydl_opts.update({
                'extract_flat': True,
                'skip_download': True,
                'quiet': True,
                'noplaylist': False,
            })
            with self.prefetch_lock:
                ydl = yt_dlp.YoutubeDL(ydl_opts)
                info = ydl.extract_info(link, download=False)
            entries = info.get('entries') if info else None
            if not entries:
                return []
            results = []
            for entry in entries:
                if not entry:
                    continue
                title = entry.get('title') or "Unknown title"
                entry_link = entry.get('webpage_url') or entry.get('url') or entry.get('id')
                if entry_link and not entry_link.startswith("http"):
                    entry_link = f"https://www.youtube.com/watch?v={entry_link}"
                if entry_link:
                    results.append({'title': title, 'link': entry_link})
            return results
        except Exception as e:
            print(f"Error fetching playlist entries: {e}")
            return []

    def prefetch_stream_info(self, link):
        if not link or link in self.prefetch_cache:
            return
        try:
            with self.prefetch_lock:
                ydl = yt_dlp.YoutubeDL(self.ydl_opts)
                info = ydl.extract_info(link, download=False)
            self.prefetch_cache[link] = {
                'url': info.get('url'),
                'title': info.get('title')
            }
        except Exception:
            return

    def clear_prefetch_cache(self):
        self.prefetch_cache.clear()

    def pause_stream(self):
        self.pause=True

    def seek_forward(self, amount):
        self._perform_with_fade(lambda: self.seek(amount, reference="relative"))

    def seek_back(self, amount):
        try:
            amount=-amount
            self._perform_with_fade(lambda: self.seek(amount))
        except:
            raise(ValueError)

    def set_volume(self, volume):
        try:
            target = float(volume)
        except (TypeError, ValueError):
            target = volume
        if self.volume_fading > 0:
            self._fade_volume(float(self.volume), float(target), self.volume_fading)
        else:
            self.volume = target

    def _perform_with_fade(self, action):
        duration = self.volume_fading
        if duration <= 0:
            action()
            return
        try:
            current = float(self.volume)
        except (TypeError, ValueError):
            current = None
        if current is None:
            action()
            return
        fade_target = max(1.0, current * 0.5)
        half = duration / 2.0
        if half <= 0:
            action()
            return
        self._fade_volume(current, fade_target, half)
        action()
        self._fade_volume(fade_target, current, half)

    def _fade_volume(self, start, end, duration):
        if duration <= 0:
            self.volume = end
            return
        steps = max(1, int(duration * 10))
        step_time = duration / steps
        for i in range(1, steps + 1):
            value = start + (end - start) * (i / steps)
            self.volume = value
            time.sleep(step_time)
        self.volume = end

    def _register_end_callback(self):
        @self.event_callback("end-file")
        def _on_end_file(event):
            ev = event.get("event") or {}
            if ev.get("reason") not in (mpv.MpvEventEndFile.EOF, mpv.MpvEventEndFile.ERROR):
                return
            if self.is_playing:
                self.is_playing = False
                if self.end_callback:
                    self.end_callback()
        self._end_file_handler = _on_end_file

    def replay_current(self):
        if not self.current_link:
            return False
        try:
            self.stop()
            self.is_playing = True
            if self.current_stream_url:
                self.play(self.current_stream_url)
                self.add_to_recent_history(self.current_title, self.current_link)
            else:
                self.play_stream(self.current_link)
            return True
        except Exception as e:
            print(f"Error replaying stream: {e}")
            return False

    def stop(self, keep_playlist=False):
        super().stop(keep_playlist=keep_playlist)
        self.is_playing = False

    def set_output_device(self):
        """Sets the output device based on the config file index."""
        output_device_index = self.config_handler.get_playback_config().get("output_device")
        if output_device_index is not None:
            try:
                output_device_index = int(output_device_index)  # Convert from string to int
                output_devices = self.audio_device_list
                if 0 <= output_device_index < len(output_devices):
                    device_name = output_devices[output_device_index]['name']
                    self.audio_device = device_name
                    print(f"Output device set to: {device_name}")
                else:
                    print("Invalid output device index in config file.")
            except (ValueError, IndexError) as e:
                print(f"Error setting output device: {e}")

    def format_time(self, seconds):
        minutes = int(seconds // 60)
        hours = minutes // 60

        sec = round(seconds % 60, 2)

        if sec == 60:
            sec = 0
            minutes += 1

        if minutes == 60:
            minutes = 0
            hours += 1

        minutes %= 60  # Equivalent to minutes = minutes % 60
        return f"{hours:02d}:{minutes:02d}:{sec:05.2f}" 

    def add_to_recent_history(self, title, link):
        """Adds a played video to the recent history."""
        if len(self.recent_history) >= 32:
            self.recent_history.pop(next(iter(self.recent_history)))
        self.recent_history[title] = link

    def get_recent_history(self):
        """Returns the recent history as a formatted string."""
        if not self.recent_history:
            return "Recent history is empty."

        history_str = "Recent History:\n"
        for i, (title, link) in enumerate(self.recent_history.items()):
            history_str += f"{i+1}: {title}\n"
        return history_str

    def play_from_history(self, index):
        """Plays a video from the recent history based on its index."""
        if 1 <= index <= len(self.recent_history):
            title = list(self.recent_history.keys())[index - 1]
            link = self.recent_history[title]
            self.play_stream(link)
            return f"Playing: {title}"
        else:
            return "Invalid history index."
