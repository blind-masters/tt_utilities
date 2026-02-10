import mpv
import time
import asyncio
from py_yt import VideosSearch
import yt_dlp

class Player(mpv.MPV):
    def __init__(self, config_handler, cookiefile=None, *args, **kwargs):
        super().__init__(ytdl=False, vo='null', video=False, *args, **kwargs)
        self.config_handler = config_handler # <-- STORE THE INJECTED INSTANCE
        self.playback_config = self.config_handler.get_playback_config()
        self.is_playing=False
        self.volume=self.playback_config['default_volume']
        self.current_link=None
        self.search_results = {}
        self.current_search_index = 0
        self.recent_history = {}
        self.end_callback = None
        self.set_output_device()
        ydl_opts = {
            'format': 'bestaudio[ext=m4a]/bestaudio/best', 
            'noplaylist': True,
            'extract-audio': True,
            'audio-format': 'm4a',
        }

        if cookiefile:
            ydl_opts['cookiefile'] = cookiefile
        self.ydl = yt_dlp.YoutubeDL(ydl_opts)

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
            info = self.ydl.extract_info(link, download=False)
            direct_link = info['url']  
            self.media_title = info['title']
            self.is_playing = True
            self.play(direct_link)
            self.current_link = link
            self.observe_property('idle-active', self._on_idle_active) 
            self.add_to_recent_history(self.media_title, link)

        except Exception as e:
            print(f"Error playing stream: {e}")

    def pause_stream(self):
        self.pause=True

    def seek_forward(self, amount):
        self.seek(amount, reference="relative")

    def seek_back(self, amount):
        try:
            amount=-amount
            self.seek(amount)
        except:
            raise(ValueError)

    def _on_idle_active(self, name, value):
        """Callback function for 'idle-active' property change."""
        if value is True and self.is_playing:
            self.is_playing = False

            # Stop observing idle-active to prevent further triggers 
            self.unobserve_property('idle-active', self._on_idle_active)

            if self.end_callback: 
                self.end_callback()

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
