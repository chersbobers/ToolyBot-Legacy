import os
import json
import logging
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from utils.config import Config

logger = logging.getLogger('tooly_bot.database')
load_dotenv()

USE_MONGO = True  # Set to False if you want to use JSON

# --- MongoDB Setup ---
if USE_MONGO:
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        logger.error("❌ MONGO_URI environment variable not set!")
        raise EnvironmentError("MONGO_URI not defined in environment variables")
    client = MongoClient(mongo_uri)
    db = client['toolybot']

# --- Placeholder dicts for imports ---
reaction_roles = {}      # For your reactions cog
server_settings = {}     # For YouTube cog / other server-specific settings

class BotData:
    def __init__(self):
        self.data = {}  # Always define to prevent AttributeErrors

        if USE_MONGO:
            self.db = db
        else:
            self.data = {
                'levels': {},
                'economy': {},
                'warnings': {},
                'lastVideoId': {},
                'leaderboard_messages': {},
                'shop_items': {},
                'inventory': {}
            }
            os.makedirs('data', exist_ok=True)
            self.load()

        if USE_MONGO:
            self.migrate_json_to_mongo()

    # --- JSON Load/Save ---
    def load(self):
        try:
            if os.path.exists(Config.DATA_FILE):
                with open(Config.DATA_FILE, 'r') as f:
                    self.data.update(json.load(f))
                logger.info('✅ Data loaded successfully')
            else:
                logger.info('ℹ️ No existing data file, starting fresh')
                self.save()
        except Exception as e:
            logger.error(f'❌ Error loading data: {e}')

    def save(self):
        if USE_MONGO:
            return  # MongoDB updates are immediate
        try:
            with open(Config.DATA_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.debug('💾 Data saved successfully')
        except Exception as e:
            logger.error(f'❌ Error saving data: {e}')

    # --- Economy Methods ---
    def get_user_economy(self, guild_id, user_id):
        if USE_MONGO:
            doc = self.db['economy'].find_one({"guild_id": guild_id, "user_id": user_id})
            if doc:
                doc.pop('_id', None)
                return doc
            return {
                'coins': 0, 'bank': 0, 'lastDaily': 0, 'lastWork': 0,
                'lastFish': 0, 'lastGamble': 0, 'fishCaught': 0,
                'totalGambled': 0, 'gamblingWins': 0, 'gamblingLosses': 0,
                'biggestWin': 0, 'biggestLoss': 0, 'winStreak': 0,
                'currentStreak': 0, 'fishInventory': {}
            }
        else:
            return self.data.get('economy', {}).get(guild_id, {}).get(user_id, {
                'coins': 0, 'bank': 0, 'lastDaily': 0, 'lastWork': 0,
                'lastFish': 0, 'lastGamble': 0, 'fishCaught': 0,
                'totalGambled': 0, 'gamblingWins': 0, 'gamblingLosses': 0,
                'biggestWin': 0, 'biggestLoss': 0, 'winStreak': 0,
                'currentStreak': 0, 'fishInventory': {}
            })

    def set_user_economy(self, guild_id, user_id, data):
        if USE_MONGO:
            self.db['economy'].update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": data},
                upsert=True
            )
        else:
            if 'economy' not in self.data:
                self.data['economy'] = {}
            if guild_id not in self.data['economy']:
                self.data['economy'][guild_id] = {}
            self.data['economy'][guild_id][user_id] = data
            self.save()

    # --- Levels Methods ---
    def get_user_level(self, guild_id, user_id):
        if USE_MONGO:
            doc = self.db['levels'].find_one({"guild_id": guild_id, "user_id": user_id})
            if doc:
                doc.pop('_id', None)
                return doc
            return {'xp': 0, 'level': 1, 'lastMessage': 0}
        else:
            return self.data.get('levels', {}).get(guild_id, {}).get(user_id, {'xp': 0, 'level': 1, 'lastMessage': 0})

    def set_user_level(self, guild_id, user_id, data):
        if USE_MONGO:
            self.db['levels'].update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": data},
                upsert=True
            )
        else:
            if 'levels' not in self.data:
                self.data['levels'] = {}
            if guild_id not in self.data['levels']:
                self.data['levels'][guild_id] = {}
            self.data['levels'][guild_id][user_id] = data
            self.save()

    # --- Migration ---
    def migrate_json_to_mongo(self):
        if not os.path.exists(Config.DATA_FILE):
            return
        try:
            with open(Config.DATA_FILE, 'r') as f:
                old_data = json.load(f)

            # Migrate economy
            for guild_id, users in old_data.get('economy', {}).items():
                for user_id, econ in users.items():
                    self.set_user_economy(guild_id, user_id, econ)

            # Migrate levels
            for guild_id, users in old_data.get('levels', {}).items():
                for user_id, lvl in users.items():
                    self.set_user_level(guild_id, user_id, lvl)

            logger.info("✅ Migration to MongoDB completed")
        except Exception as e:
            logger.error(f'❌ Migration failed: {e}')


bot_data = BotData()
