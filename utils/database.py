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

class ReactionRoles:
    """Handler for reaction roles"""
    def __init__(self):
        self.data = {}
    
    def get_role_for_reaction(self, guild_id, message_id, emoji):
        """Get role ID for a reaction"""
        return self.data.get(guild_id, {}).get(message_id, {}).get(emoji)
    
    def add_reaction_role(self, guild_id, message_id, emoji, role_id):
        """Add a reaction role mapping"""
        if guild_id not in self.data:
            self.data[guild_id] = {}
        if message_id not in self.data[guild_id]:
            self.data[guild_id][message_id] = {}
        self.data[guild_id][message_id][emoji] = role_id
    
    def remove_reaction_role(self, guild_id, message_id, emoji=None):
        """Remove a reaction role mapping"""
        if emoji:
            if guild_id in self.data and message_id in self.data[guild_id]:
                self.data[guild_id][message_id].pop(emoji, None)
        else:
            if guild_id in self.data:
                self.data[guild_id].pop(message_id, None)

class ServerSettings:
    """Handler for server settings"""
    def __init__(self):
        self.data = {}
    
    def get(self, guild_id, key, default=None):
        """Get a server setting"""
        return self.data.get(guild_id, {}).get(key, default)
    
    def set(self, guild_id, key, value):
        """Set a server setting"""
        if guild_id not in self.data:
            self.data[guild_id] = {}
        self.data[guild_id][key] = value

# Initialize global instances
reaction_roles = ReactionRoles()
server_settings = ServerSettings()

class BotData:
    def __init__(self):
        # Always initialize data dict with default keys to prevent KeyError
        self.data = {
            'levels': {},
            'economy': {},
            'warnings': {},
            'lastVideoId': None,  # Initialize as None instead of {}
            'leaderboard_messages': {},
            'shop_items': {},
            'inventory': {}
        }

        if USE_MONGO:
            self.db = db
            logger.info('✅ Connected to MongoDB')
        else:
            os.makedirs('data', exist_ok=True)
            self.load()

        if USE_MONGO:
            self.migrate_json_to_mongo()

    # --- JSON Load/Save ---
    def load(self):
        try:
            if os.path.exists(Config.DATA_FILE):
                with open(Config.DATA_FILE, 'r') as f:
                    loaded_data = json.load(f)
                    self.data.update(loaded_data)
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

    # --- Shop Methods ---
    def get_shop_items(self, guild_id):
        """Get all shop items for a guild"""
        if USE_MONGO:
            # For MongoDB, you might want to store shop items differently
            # For now, using the data dict
            return self.data.get('shop_items', {}).get(guild_id, {})
        else:
            return self.data.get('shop_items', {}).get(guild_id, {})

    # --- Inventory Methods ---
    def get_user_inventory(self, guild_id, user_id):
        """Get user's inventory"""
        if USE_MONGO:
            return self.data.get('inventory', {}).get(guild_id, {}).get(user_id, {})
        else:
            return self.data.get('inventory', {}).get(guild_id, {}).get(user_id, {})

    def add_to_inventory(self, guild_id, user_id, item_id):
        """Add an item to user's inventory"""
        if 'inventory' not in self.data:
            self.data['inventory'] = {}
        if guild_id not in self.data['inventory']:
            self.data['inventory'][guild_id] = {}
        if user_id not in self.data['inventory'][guild_id]:
            self.data['inventory'][guild_id][user_id] = {}
        
        self.data['inventory'][guild_id][user_id][item_id] = {
            'purchased': datetime.utcnow().timestamp()
        }
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