from TeamTalk5 import ttstr, UserType
import wikipedia
import langdetect
import requests

class GeneralCog:
    """
    A module for handling general utility commands available to all users.
    """
    def __init__(self, bot):
        self.bot = bot
        self._ = bot._

    def register(self, command_handler):
        """Registers all the general commands."""
        command_handler.register_command('weather', self.handle_weather_command, help_text=self._("Gets the current weather info for your location or a specified user. Usage: /weather <nickname (Optional)>"))
        command_handler.register_command('search', self.handle_search_command, help_text=self._("Searches Wikipedia for a summary. Usage: /search <query>"))
        command_handler.register_command('h', self.handle_help_command, help_text=self._("Shows this help message."))
        command_handler.register_command('help', self.handle_help_command, help_text=self._("Shows this help message."))
        command_handler.register_command('myinfo', self.handle_myinfo_command, help_text=self._("Shows your user account information."))

    def handle_weather_command(self, textmessage, *args):
        sender_user_id = textmessage.nFromUserID
        
        # Determine the user to look up
        if args:
            target_nickname = " ".join(args)
            target_user = self.bot.getUserByName(target_nickname)
            if not target_user:
                self.bot.privateMessage(sender_user_id, self._("User '{user}' not found.").format(user=target_nickname))
                return
            lookup_user_id = target_user.nUserID
        else:
            lookup_user_id = sender_user_id
        
        self.bot.io_pool.submit(self._weather_task, lookup_user_id, textmessage.nMsgType)

    def _weather_task(self, lookup_user_id, msg_type):
        """Task to get user location and weather info."""
        country, city = self.bot.user_manager.get_user_location(lookup_user_id)

        if country and city:
            weather_info = self.get_weather_from_api(country, city)
            sender_channel_id = self.bot.getUser(lookup_user_id).nChannelID
            if msg_type == 1: # Private message
                self.bot.privateMessage(lookup_user_id, weather_info)
            else:
                self.bot.send_message(weather_info, sender_channel_id or 0)
        else:
            self.bot.privateMessage(lookup_user_id, self._("Could not retrieve location information."))

    def get_weather_from_api(self, country_name, city):
        """Fetches and formats weather data from the API."""
        base_url = "http://api.weatherapi.com/v1/forecast.json"
        params = { "key": self.bot.weather_config, "q": f"{city}, {country_name}", "days": 1 }
        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json()
            current = data["current"]
            forecast = data["forecast"]["forecastday"][0]["day"]
            current_time_str = data["location"]["localtime"]
            current_hour = int(current_time_str.split(" ")[1].split(":")[0])
            forecast_hour = data["forecast"]["forecastday"][0]["hour"][current_hour]
            
            return self._("The current weather in {city}, {country_name} is {temperature}°C, {condition}. "
                          "The perceived temperature is {feels_like} degrees C, the wind speed is at {wind_speed} kph, "
                          "The wind gusts are at {gust_kph} kph, The windchill is {windchill_c}°C.\n"
                          "The Precipitation is {precip_mm} MM, The cloudiness is of {cloudiness}%, "
                          "With a {chance_of_rain}% chance of rain.\n"
                          "The visibility is up to {visibility} km. The humidity is {humidity}%, "
                          "The current time is {time}.").format(
                city=city, country_name=country_name, temperature=current["temp_c"], condition=current["condition"]["text"],
                feels_like=current["feelslike_c"], wind_speed=current["wind_kph"], gust_kph=current["gust_kph"],
                windchill_c=forecast_hour["windchill_c"], precip_mm=current["precip_mm"], cloudiness=current["cloud"],
                chance_of_rain=forecast["daily_chance_of_rain"], visibility=current["vis_km"], humidity=current["humidity"],
                time=data["location"]["localtime"])

        except (requests.exceptions.RequestException, KeyError) as e:
            print(f"Error fetching weather data: {e}")
            return self._("Error fetching weather data.")

    def handle_search_command(self, textmessage, *args):
        if not args:
            self.bot.privateMessage(textmessage.nFromUserID, self._("Usage: /search <query>"))
            return
        query = " ".join(args)
        self.bot.io_pool.submit(self._wikipedia_summary_task, query, textmessage.nFromUserID)

    def _wikipedia_summary_task(self, query, user_id):
        try:
            lang = langdetect.detect(query)
            wikipedia.set_lang(lang)
            summary = wikipedia.summary(query, sentences=10)
            
            for chunk in self.bot.split_long_message(summary):
                self.bot.privateMessage(user_id, chunk)
            
            page_url = wikipedia.page(query).url
            self.bot.privateMessage(user_id, self._("Wikipedia link: {page_url}").format(page_url=page_url))
        except wikipedia.exceptions.PageError:
            self.bot.privateMessage(user_id, self._("Page not found on Wikipedia."))
        except wikipedia.exceptions.DisambiguationError:
            self.bot.privateMessage(user_id, self._("Multiple pages found for '{query}'. Please be more specific.").format(query=query))
        except Exception as e:
            self.bot.privateMessage(user_id, self._("An error occurred: {e}").format(e=e))

    def handle_help_command(self, textmessage, *args):
        """Dynamically generates and sends the help message."""
        user_id = textmessage.nFromUserID
        sender_user = self.bot.getUser(user_id)
        is_admin = False
        
        if sender_user:
            sender_username = ttstr(sender_user.szUsername).lower()
            authorized_users = [u.strip().lower() for u in self.bot.accounts_config.get("authorized_users", [])]
            if sender_username in authorized_users or (self.bot.accounts_config.get('detect_server_admins') and sender_user.uUserType == UserType.USERTYPE_ADMIN):
                is_admin = True
        
        self.bot.privateMessage(user_id, self._("--- Available Commands ---"))
        # Sort commands alphabetically for readability
        commands = sorted(self.bot.command_handler.commands.items())
        for name, command in commands:
            # If the command is admin-only and the user is not an admin, skip it
            if command.admin_only and not is_admin:
                continue
            
            prefix = self.bot.command_handler.prefix
            help_text = command.help_text or self._("No description available.")
            message = f"{prefix}{name}: {help_text}"
            self.bot.privateMessage(user_id, message)
        
        self.bot.privateMessage(user_id, self._("--- Special Commands ---"))
        self.bot.privateMessage(user_id, self._("'<text>: Make the bot speaks some text, Same as /say command, but for quick usability."))
        self.bot.privateMessage(user_id, self._("+ <seconds (Optional)>, Plus sign: Seek forward in the current media file. Without arguments, seek forward using the default value. With arguments, seek forward by how many seconds are specified. For example, + 10 will seek forward by 10 seconds."))
        self.bot.privateMessage(user_id, self._("- <seconds (Optional)>, Dash sign: Seek backward in the current media file. With arguments, seek backward using the default value. With arguments, seek backward by how many seconds are specified. For example, -10 will seek backward by 10 seconds."))

    def handle_myinfo_command(self, textmessage, *args):
        self.bot.last_command_sender_id = textmessage.nFromUserID
        self.bot.last_command_sender_username = ttstr(textmessage.szFromUsername)
        self.bot.doListUserAccounts(0, 100)