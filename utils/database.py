import os
import json
import logging
from datetime import datetime, timezone
from utils.config import Config
from pymongo import MongoClient
from dotenv import load_dotenv

logger = logging.getLogger('tooly_bot.database')
load_dotenv()

USE_MONGO = True  # Toggle to False to use JSON

if USE_MONGO:
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client['toolybot']

class BotData:
    def __init__(self):
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

        # Run migration automatically if switching to Mongo
        if USE_MONGO:
            self.migrate_json_to_mongo()

    # --- JSON load/save ---
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
            return  # Mongo updates are immediate
        try:
            with open(Config.DATA_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.debug('💾 Data saved successfully')
        except Exception as e:
            logger.error(f'❌ Error saving data: {e}')

    # --- Economy ---
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
            guild_data = self.data['economy'].get(guild_id, {})
            return guild_data.get(user_id, {
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
            if guild_id not in self.data['economy']:
                self.data['economy'][guild_id] = {}
            self.data['economy'][guild_id][user_id] = data
            self.save()

    # --- Shop ---
    def get_shop_items(self, guild_id):
        if USE_MONGO:
            doc = self.db['shop_items'].find_one({"guild_id": guild_id})
            return doc.get('items', {}) if doc else {}
        else:
            return self.data.get('shop_items', {}).get(guild_id, {})

    def set_shop_items(self, guild_id, items):
        if USE_MONGO:
            self.db['shop_items'].update_one(
                {"guild_id": guild_id},
                {"$set": {"items": items}},
                upsert=True
            )
        else:
            if 'shop_items' not in self.data:
                self.data['shop_items'] = {}
            self.data['shop_items'][guild_id] = items
            self.save()

    # --- Inventory ---
    def get_user_inventory(self, guild_id, user_id):
        if USE_MONGO:
            doc = self.db['inventory'].find_one({"guild_id": guild_id, "user_id": user_id})
            return doc.get('inventory', {}) if doc else {}
        else:
            guild_data = self.data.get('inventory', {}).get(guild_id, {})
            return guild_data.get(user_id, {})

    def add_to_inventory(self, guild_id, user_id, item_id):
        if USE_MONGO:
            inv = self.get_user_inventory(guild_id, user_id)
            inv[item_id] = {'purchased': datetime.utcnow().timestamp()}
            self.db['inventory'].update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": {"inventory": inv}},
                upsert=True
            )
        else:
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

    # --- Levels ---
    def get_user_level(self, guild_id, user_id):
        if USE_MONGO:
            doc = self.db['levels'].find_one({"guild_id": guild_id, "user_id": user_id})
            if doc:
                doc.pop('_id', None)
                return doc
            return {'xp': 0, 'level': 1, 'lastMessage': 0}
        else:
            guild_data = self.data['levels'].get(guild_id, {})
            return guild_data.get(user_id, {'xp': 0, 'level': 1, 'lastMessage': 0})

    def set_user_level(self, guild_id, user_id, data):
        if USE_MONGO:
            self.db['levels'].update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": data},
                upsert=True
            )
        else:
            if guild_id not in self.data['levels']:
                self.data['levels'][guild_id] = {}
            self.data['levels'][guild_id][user_id] = data
            self.save()

    # --- Warnings ---
    def get_warnings(self, guild_id, user_id):
        if USE_MONGO:
            doc = self.db['warnings'].find_one({"guild_id": guild_id, "user_id": user_id})
            return doc.get('warnings', []) if doc else []
        else:
            guild_data = self.data['warnings'].get(guild_id, {})
            return guild_data.get(user_id, [])

    def add_warning(self, guild_id, user_id, warning):
        if USE_MONGO:
            warnings = self.get_warnings(guild_id, user_id)
            warnings.append(warning)
            self.db['warnings'].update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": {"warnings": warnings}},
                upsert=True
            )
        else:
            if guild_id not in self.data['warnings']:
                self.data['warnings'][guild_id] = {}
            if user_id not in self.data['warnings'][guild_id]:
                self.data['warnings'][guild_id][user_id] = []
            self.data['warnings'][guild_id][user_id].append(warning)
            self.save()

    # --- Migration ---
    def migrate_json_to_mongo(self):
        if not os.path.exists(Config.DATA_FILE):
            return
        try:
            with open(Config.DATA_FILE, 'r') as f:
                old_data = json.load(f)

            # Economy
            for guild_id, users in old_data.get('economy', {}).items():
                for user_id, econ in users.items():
                    self.set_user_economy(guild_id, user_id, econ)

            # Shop
            for guild_id, items in old_data.get('shop_items', {}).items():
                self.set_shop_items(guild_id, items)

            # Inventory
            for guild_id, users in old_data.get('inventory', {}).items():
                for user_id, inv in users.items():
                    for item_id in inv:
                        self.add_to_inventory(guild_id, user_id, item_id)

            # Levels
            for guild_id, users in old_data.get('levels', {}).items():
                for user_id, lvl in users.items():
                    self.set_user_level(guild_id, user_id, lvl)

            # Warnings
            for guild_id, users in old_data.get('warnings', {}).items():
                for user_id, warns in users.items():
                    for warn in warns:
                        self.add_warning(guild_id, user_id, warn)

            logger.info("✅ Migration to MongoDB completed")
        except Exception as e:
            logger.error(f'❌ Migration failed: {e}')


bot_data = BotData()
