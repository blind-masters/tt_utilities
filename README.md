# TeamTalk admin utilities

We're proud to introduce our first project: A powerful bot for TeamTalk administrators.

This bot is developed by the [BlindMasters team](https://blindmasters.org/).

The main goal of this project is to block spammers and unwanted people from entering your server by automating some actions.

## Features

While the main goal of the bot is to block spammers, there are a set of features that will help you. Please note that this is the first release, and you may encounter some bugs.

Features:
- VPN detection
- Bans users that are using VPN
- Automatically kicking no-name users
- Blacklist for bad words that are sent by users or even in nicknames
- Weather info, Including time, wind speed, condition, and other info
- Wikipedia search to get a summary about any topic in Wikipedia
- Supports uploading entire HTML page files about your Wikipedia query
- SSH control to execute quick commands on your server
- Text to speech, using Google TTS voices and language detection
- Sending random announcements or messages at intervals, completely customizable

## Setup

Follow the below instructions to setup your bot on Windows.

The bot currently supports Windows only, and we're working on supporting Ubuntu and Linux distributions in the future.

1. Install Git, necessary for installing some libraries. Download [git 64 bit for Windows](https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe) or [git 32 bit for Windows](https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-32-bit.exe).
2. You'll need to install Python. This project is tested on Python 3.11 and 3.12. Download [Python v3.12, 64 bit for Windows](https://www.python.org/ftp/python/3.12.2/python-3.12.2-amd64.exe).
3. Install Git and Python on your machine.
   Please note: when installing Python, make sure that the option "add Python to environment variables" checkbox is checked to avoid problems, and to make things much easier for you to execute scripts directly through the command prompt.
4. After completing the above steps, go to the directory where you downloaded the project and open the command prompt in the current directory.
   - Press F4, type "cmd" and press Enter
   - Press the right-click button or the application key on an empty space, and choose "Open PowerShell window here". In the new window, type `cmd` and press Enter.
5. Install the requirements file using this command:
pip install -r requirements.txt
This will install all libraries needed for the bot. Wait for it to finish, and then you can close this window.

## Configuring and running the bot

Before you start, you'll need to have these for the bot to work correctly:
- ipinfo access token: get one [here](https://ipinfo.io/)
- Weather API: sign up to get one from [here](https://www.weatherapi.com)

After you get these, it's time to run the bot.
If you are the first time running the bot, it will ask you some questions to configure the bot so you don't have to enter info each time. Please follow the instructions carefully.

Important notes:
- The bot doesn't support encrypted servers currently; we may add it later.
- If you have other bots on your server (e.g., music box), please add it to the exclusion IP list because these are detected as VPN users.
- You also need to add the stats IP address in the exclusions list. Read below.
- The blacklist words don't support Arabic for now because I need to implement it manually due to its Unicode differences.

The stats IP address is: `139.144.24.23`

The bot can run in 3 detection modes, see below:
- Guest accounts: means that it will only take actions on users who log in with the guest account.
- All accounts: will detect all accounts and take actions accordingly.
- Custom username: If you have a public account that is different from the guest account, choose this option and enter your public account when configuring the bot.

Once you do all the configurations, the bot will run, log in to your server, and join the root channel.

## Commands

All bot commands start with a slash, either in a private message or a channel message.

List of supported commands:
- `/weather`: This command will send you weather info about you, or another person if specified. If sent in a private message: you can't specify a name, while in a channel message, you could send `/weather` or `/weather somebody`, both will work.
- `/exec command`: Will execute a command on your SSH server specified in the config file. Please note: You need to add your username and all usernames that can execute commands in the config file or when you configure the bot for the first time.
- `/reboot`: Will reboot the server and send a broadcast notifying all users that the server is about to restart.
- `/search query`: Will search for the query on Wikipedia, send the summary of the page, and the link to the full page on Wikipedia.
- `/file query`: Will search for the specified query on Wikipedia and upload the entire HTML file for the page to the current channel.
- `/say` or `'` text: Will say the text you've entered. This is useful if you don't want to talk with your voice.

Please note: when using the `/say` command, it detects the language you entered. And for this to work correctly, you need at least 2 words or more. Words like "hello", "hi", and so on may be wrongly detected as other languages, so be careful.

Please note that the bot is still in beta, and you may encounter some bugs. Feel free to report any bugs you may encounter using any of the accounts below.

## Contact us

If you have any questions, suggestions, code contributing, or bug reports, feel free to contact us using one of the following ways:
- Telegram: [abdalrahmen maher](https://t.me/abdalrahmen_maher)
- Telegram: [ahmad sabbah](https://t.me/ahmadsabbah)
- Telegram: [ziyad mohamed](https;//t.me/icestar31)
- WhatsApp: [eyad ahmed](https://wa.me/201125810378)

Enjoy.
