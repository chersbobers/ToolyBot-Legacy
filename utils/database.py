import json
import os
import logging
from datetime import datetime, timezone
from copy import deepcopy
from typing import Dict, Any  # ADD THIS LINE
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
        self.filename = 'data/bot_data.json'  # ADD THIS LINE - was missing
        os.makedirs('data', exist_ok=True)
        self.load()
    
    def load(self):
        """Load data from JSON file"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.data = json.load(f)
                logger.info(f'✅ Loaded data from {self.filename}')
            except Exception as e:
                logger.error(f'❌ Failed to load {self.filename}: {e}')
                self.data = {
                    'levels': {},
                    'economy': {},
                    'warnings': {},
                    'lastVideoId': {},
                    'leaderboard_messages': {},
                    'shop_items': {},
                    'inventory': {}
                }
        else:
            logger.info(f'📝 Creating new {self.filename}')
            self.save()
    
    def save(self):
        """Save data to JSON file"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.debug(f'💾 Saved data to {self.filename}')
        except Exception as e:
            logger.error(f'❌ Failed to save {self.filename}: {e}')
    
    def get_user_level(self, guild_id: str, user_id: str) -> Dict[str, Any]:
        """Get user level data - RETURNS A COPY"""
        if 'levels' not in self.data:
            self.data['levels'] = {}
        if guild_id not in self.data['levels']:
            self.data['levels'][guild_id] = {}
        
        if user_id not in self.data['levels'][guild_id]:
            default_data = {
                'level': 1,
                'xp': 0,
                'lastMessage': 0
            }
            self.data['levels'][guild_id][user_id] = default_data
            logger.debug(f'Created new level entry for user {user_id} in guild {guild_id}')
        
        return deepcopy(self.data['levels'][guild_id][user_id])
    
    def set_user_level(self, guild_id: str, user_id: str, data: Dict[str, Any]):
        """Set user level data"""
        if 'levels' not in self.data:
            self.data['levels'] = {}
        if guild_id not in self.data['levels']:
            self.data['levels'][guild_id] = {}
        
        self.data['levels'][guild_id][user_id] = data
        logger.debug(f'Updated level for user {user_id} in guild {guild_id}')
    
    def get_user_economy(self, guild_id: str, user_id: str) -> Dict[str, Any]:
        """Get user economy data - RETURNS A COPY to avoid reference issues"""
        if 'economy' not in self.data:
            self.data['economy'] = {}
        if guild_id not in self.data['economy']:
            self.data['economy'][guild_id] = {}
        
        if user_id not in self.data['economy'][guild_id]:
            # Create new user with default values
            default_data = {
                'coins': 0,
                'bank': 0,
                'lastDaily': 0,
                'lastWork': 0
            }
            self.data['economy'][guild_id][user_id] = default_data
            logger.debug(f'Created new economy entry for user {user_id} in guild {guild_id}')
        
        # Return a COPY to prevent reference issues
        return deepcopy(self.data['economy'][guild_id][user_id])
    
    def set_user_economy(self, guild_id: str, user_id: str, data: Dict[str, Any]):
        """Set user economy data - properly updates without overwriting others"""
        if 'economy' not in self.data:
            self.data['economy'] = {}
        if guild_id not in self.data['economy']:
            self.data['economy'][guild_id] = {}
        
        # Update only this user's data, preserving others
        self.data['economy'][guild_id][user_id] = data
        logger.debug(f'Updated economy for user {user_id} in guild {guild_id}: {data}')
    
    def get_user_inventory(self, guild_id: str, user_id: str) -> Dict[str, Any]:
        """Get user inventory - RETURNS A COPY"""
        if 'inventory' not in self.data:
            self.data['inventory'] = {}
        if guild_id not in self.data['inventory']:
            self.data['inventory'][guild_id] = {}
        if user_id not in self.data['inventory'][guild_id]:
            self.data['inventory'][guild_id][user_id] = {}
        
        return deepcopy(self.data['inventory'][guild_id][user_id])
    
    def add_to_inventory(self, guild_id: str, user_id: str, item_id: str):
        """Add item to user inventory"""
        if 'inventory' not in self.data:
            self.data['inventory'] = {}
        if guild_id not in self.data['inventory']:
            self.data['inventory'][guild_id] = {}
        if user_id not in self.data['inventory'][guild_id]:
            self.data['inventory'][guild_id][user_id] = {}
        
        from datetime import datetime
        self.data['inventory'][guild_id][user_id][item_id] = {
            'purchased': datetime.utcnow().timestamp(),
            'quantity': self.data['inventory'][guild_id][user_id].get(item_id, {}).get('quantity', 0) + 1
        }
        logger.info(f'Added item {item_id} to user {user_id} in guild {guild_id}')
    
    def get_shop_items(self, guild_id: str) -> Dict[str, Any]:
        """Get shop items for a guild - RETURNS A COPY"""
        if 'shop_items' not in self.data:
            self.data['shop_items'] = {}
        if guild_id not in self.data['shop_items']:
            self.data['shop_items'][guild_id] = {}
        
        return deepcopy(self.data['shop_items'][guild_id])


class ReactionRoles:
    """Manages reaction role mappings"""
    def __init__(self):
        self.data = {}
        self.filename = 'data/reaction_roles.json'
        os.makedirs('data', exist_ok=True)
        self.load()
    
    def load(self):
        """Load reaction roles from JSON"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.data = json.load(f)
                logger.info(f'✅ Loaded reaction roles from {self.filename}')
            except Exception as e:
                logger.error(f'❌ Failed to load {self.filename}: {e}')
                self.data = {}
        else:
            logger.info(f'📝 Creating new {self.filename}')
            self.save()
    
    def save(self):
        """Save reaction roles to JSON"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.debug(f'💾 Saved reaction roles to {self.filename}')
        except Exception as e:
            logger.error(f'❌ Failed to save {self.filename}: {e}')
    
    def add_reaction_role(self, guild_id: str, message_id: str, emoji: str, role_id: str):
        """Add a reaction role mapping"""
        if guild_id not in self.data:
            self.data[guild_id] = {}
        if message_id not in self.data[guild_id]:
            self.data[guild_id][message_id] = {}
        
        self.data[guild_id][message_id][emoji] = role_id
        self.save()
    
    def remove_reaction_role(self, guild_id: str, message_id: str, emoji: str = None):
        """Remove a reaction role mapping"""
        if guild_id not in self.data or message_id not in self.data[guild_id]:
            return
        
        if emoji:
            if emoji in self.data[guild_id][message_id]:
                del self.data[guild_id][message_id][emoji]
        else:
            del self.data[guild_id][message_id]
        
        self.save()
    
    def get_role_for_reaction(self, guild_id: str, message_id: str, emoji: str) -> str:
        """Get role ID for a reaction"""
        return self.data.get(guild_id, {}).get(message_id, {}).get(emoji)


class ServerSettings:
    """Manages per-server settings"""
    def __init__(self):
        self.data = {}
        self.filename = 'data/server_settings.json'
        os.makedirs('data', exist_ok=True)
        self.load()
    
    def load(self):
        """Load server settings from JSON"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r') as f:
                    self.data = json.load(f)
                logger.info(f'✅ Loaded server settings from {self.filename}')
            except Exception as e:
                logger.error(f'❌ Failed to load {self.filename}: {e}')
                self.data = {}
        else:
            logger.info(f'📝 Creating new {self.filename}')
            self.save()
    
    def save(self):
        """Save server settings to JSON"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.debug(f'💾 Saved server settings to {self.filename}')
        except Exception as e:
            logger.error(f'❌ Failed to save {self.filename}: {e}')
    
    def get(self, guild_id: str, key: str, default=None):
        """Get a setting for a guild"""
        return self.data.get(guild_id, {}).get(key, default)
    
    def set(self, guild_id: str, key: str, value):
        """Set a setting for a guild"""
        if guild_id not in self.data:
            self.data[guild_id] = {}
        
        self.data[guild_id][key] = value
        self.save()


# Global instances
bot_data = BotData()
reaction_roles = ReactionRoles()
server_settings = ServerSettings()