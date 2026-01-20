# Setup and install.
1. fork the repo and publish as public repo
2. go to discord dev site https://discord.com/developers
3. make an app then name it
4. get the bot token 
5. ost on render.com
6. set the envs the needed ones are AUTOMOD_ENABLED=true PORT=3000 PYTHON_VERSION=3.11.0 AUTOMOD_LOG_CHANNEL=thechannelforautomodsid and the bot token from step 4
7. go to uptimerobot make a account a setup a moniter then set it to check the onrender site url every 5 mins to keep it up
8. build command pip install -r requirements.txt
run command python bot.py

# Optional features and the envs

DM_LOG_CHANNEL_ID=forgettingrepliestodmsfromthebot
NOTIFICATION_CHANNEL_ID=forcheckingnewytposts needs the YOUTUBE_CHANNEL_ID
PEXELS_API_KEY=yourpexelsapiforimages
YOUTUBE_CHANNEL_ID=yourytchannelid

