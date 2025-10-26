import json
import os
import logging
from datetime import datetime, timezone
from utils.config import Config

logger = logging.getLogger('tooly_bot.database')

class BotData:
    def __init__(self):
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
    
    def load(self):
        try:
            if os.path.exists(Config.DATA_FILE):
                with open(Config.DATA_FILE, 'r') as f:
                    loaded = json.load(f)
                    self.data.update(loaded)
                logger.info('✅ Data loaded successfully')
            else:
                logger.info('ℹ️ No existing data file found, starting fresh')
                self.save()
        except Exception as e:
            logger.error(f'❌ Error loading data: {e}')
    
    def save(self):
        try:
            with open(Config.DATA_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.debug('💾 Data saved successfully')
        except Exception as e:
            logger.error(f'❌ Error saving data: {e}')
    
    def get_user_level(self, guild_id: str, user_id: str):
        guild_data = self.data['levels'].get(guild_id, {})
        return guild_data.get(user_id, {'xp': 0, 'level': 1, 'lastMessage': 0})
    
    def set_user_level(self, guild_id: str, user_id: str, data: dict):
        if guild_id not in self.data['levels']:
            self.data['levels'][guild_id] = {}
        self.data['levels'][guild_id][user_id] = data
        self.save()
    
    def get_user_economy(self, guild_id: str, user_id: str):
        guild_data = self.data['economy'].get(guild_id, {})
        return guild_data.get(user_id, {
            'coins': 0, 'bank': 0, 'lastDaily': 0, 'lastWork': 0,
            'lastFish': 0, 'lastGamble': 0, 'fishCaught': 0,
            'totalGambled': 0, 'gamblingWins': 0, 'gamblingLosses': 0,
            'biggestWin': 0, 'biggestLoss': 0, 'winStreak': 0,
            'currentStreak': 0, 'fishInventory': {}
        })
    
    def set_user_economy(self, guild_id: str, user_id: str, data: dict):
        if guild_id not in self.data['economy']:
            self.data['economy'][guild_id] = {}
        self.data['economy'][guild_id][user_id] = data
        self.save()
    
    def get_warnings(self, guild_id: str, user_id: str):
        guild_data = self.data['warnings'].get(guild_id, {})
        return guild_data.get(user_id, [])
    
    def add_warning(self, guild_id: str, user_id: str, warning: dict):
        if guild_id not in self.data['warnings']:
            self.data['warnings'][guild_id] = {}
        if user_id not in self.data['warnings'][guild_id]:
            self.data['warnings'][guild_id][user_id] = []
        self.data['warnings'][guild_id][user_id].append(warning)
        self.save()
    
    def get_shop_items(self, guild_id: str):
        return self.data.get('shop_items', {}).get(guild_id, {})
    
    def get_user_inventory(self, guild_id: str, user_id: str):
        guild_data = self.data.get('inventory', {}).get(guild_id, {})
        return guild_data.get(user_id, {})
    
    def add_to_inventory(self, guild_id: str, user_id: str, item_id: str):
        if 'inventory' not in self.data:
            self.data['inventory'] = {}
        if guild_id not in self.data['inventory']:
            self.data['inventory'][guild_id] = {}
        if user_id not in self.data['inventory'][guild_id]:
            self.data['inventory'][guild_id][user_id] = {}
        
        self.data['inventory'][guild_id][user_id][item_id] = {
            'purchased': datetime.now(timezone.utc).timestamp()
        }
        self.save()

class ServerSettings:
    def __init__(self):
        self.settings = {}
        self.load()
    
    def load(self):
        try:
            if os.path.exists(Config.SETTINGS_FILE):
                with open(Config.SETTINGS_FILE, 'r') as f:
                    self.settings = json.load(f)
                logger.info('✅ Settings loaded successfully')
            else:
                logger.info('ℹ️ No existing settings file found, starting fresh')
                self.save()
        except Exception as e:
            logger.error(f'❌ Error loading settings: {e}')
    
    def save(self):
        try:
            with open(Config.SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=2)
            logger.debug('💾 Settings saved successfully')
        except Exception as e:
            logger.error(f'❌ Error saving settings: {e}')
    
    def get(self, guild_id: str, key: str, default=None):
        return self.settings.get(guild_id, {}).get(key, default)
    
    def set(self, guild_id: str, key: str, value):
        if guild_id not in self.settings:
            self.settings[guild_id] = {}
        self.settings[guild_id][key] = value
        self.save()

class ReactionRoles:
    def __init__(self):
        self.data = {}
        self.load()
    
    def load(self):
        try:
            if os.path.exists(Config.REACTIONS_FILE):
                with open(Config.REACTIONS_FILE, 'r') as f:
                    self.data = json.load(f)
                logger.info('✅ Reaction roles loaded successfully')
            else:
                logger.info('ℹ️ No existing reaction roles file found, starting fresh')
                self.save()
        except Exception as e:
            logger.error(f'❌ Error loading reaction roles: {e}')
    
    def save(self):
        try:
            with open(Config.REACTIONS_FILE, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.debug('💾 Reaction roles saved successfully')
        except Exception as e:
            logger.error(f'❌ Error saving reaction roles: {e}')
    
    def add_reaction_role(self, guild_id: str, message_id: str, emoji: str, role_id: str):
        if guild_id not in self.data:
            self.data[guild_id] = {}
        if message_id not in self.data[guild_id]:
            self.data[guild_id][message_id] = {}
        self.data[guild_id][message_id][emoji] = role_id
        self.save()
    
    def remove_reaction_role(self, guild_id: str, message_id: str, emoji: str = None):
        if guild_id in self.data and message_id in self.data[guild_id]:
            if emoji:
                self.data[guild_id][message_id].pop(emoji, None)
                if not self.data[guild_id][message_id]:
                    del self.data[guild_id][message_id]
            else:
                del self.data[guild_id][message_id]
            self.save()
    
    def get_role_for_reaction(self, guild_id: str, message_id: str, emoji: str):
        return self.data.get(guild_id, {}).get(message_id, {}).get(emoji)
    
    def get_all_for_message(self, guild_id: str, message_id: str):
        return self.data.get(guild_id, {}).get(message_id, {})

bot_data = BotData()
server_settings = ServerSettings()
reaction_roles = ReactionRoles()