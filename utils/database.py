import os
import logging
from datetime import datetime
from copy import deepcopy
from typing import Dict, Any
from pymongo import MongoClient

logger = logging.getLogger('tooly_bot.database')

# MongoDB connection (synchronous - works with your existing code)
mongo_uri = os.getenv('MONGO_URI')
if not mongo_uri:
    raise ValueError("❌ MONGO_URI environment variable not set!")

client = MongoClient(mongo_uri)
db = client['tooly_bot']

class BotData:
    def __init__(self):
        """Initialize MongoDB collections"""
        self.levels_col = db['levels']
        self.economy_col = db['economy']
        self.warnings_col = db['warnings']
        self.videos_col = db['videos']
        self.leaderboards_col = db['leaderboards']
        self.shop_items_col = db['shop_items']
        self.inventory_col = db['inventory']
        self.profiles_col = db['profiles']
        self.bot_profiles_col = db['bot_profiles']
        
        logger.info('✅ MongoDB connection initialized')
        
        # Create indexes for better performance
        try:
            self.levels_col.create_index([('guild_id', 1), ('user_id', 1)], unique=True)
            self.economy_col.create_index([('guild_id', 1), ('user_id', 1)], unique=True)
            self.profiles_col.create_index([('guild_id', 1), ('user_id', 1)], unique=True)
            self.bot_profiles_col.create_index([('guild_id', 1)], unique=True)
        except:
            pass  # Indexes may already exist
    
    def load(self):
        """No-op for MongoDB (backwards compatibility)"""
        pass
    
    def save(self):
        """No-op for MongoDB (backwards compatibility)"""
        pass
    
    def get_user_level(self, guild_id: str, user_id: str) -> Dict[str, Any]:
        """Get user level data"""
        data = self.levels_col.find_one({
            'guild_id': guild_id,
            'user_id': user_id
        })
        
        if not data:
            return {
                'level': 1,
                'xp': 0,
                'lastMessage': 0
            }
        
        return {
            'level': data.get('level', 1),
            'xp': data.get('xp', 0),
            'lastMessage': data.get('lastMessage', 0)
        }
    
    def set_user_level(self, guild_id: str, user_id: str, data: Dict[str, Any]):
        """Set user level data"""
        self.levels_col.update_one(
            {'guild_id': guild_id, 'user_id': user_id},
            {'$set': {
                'level': data.get('level', 1),
                'xp': data.get('xp', 0),
                'lastMessage': data.get('lastMessage', 0),
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )
        logger.debug(f'Updated level for user {user_id} in guild {guild_id}')
    
    def get_user_economy(self, guild_id: str, user_id: str) -> Dict[str, Any]:
        """Get user economy data"""
        data = self.economy_col.find_one({
            'guild_id': guild_id,
            'user_id': user_id
        })
        
        if not data:
            return {
                'coins': 0,
                'bank': 0,
                'lastDaily': 0,
                'lastWork': 0
            }
        
        return {
            'coins': data.get('coins', 0),
            'bank': data.get('bank', 0),
            'lastDaily': data.get('lastDaily', 0),
            'lastWork': data.get('lastWork', 0)
        }
    
    def set_user_economy(self, guild_id: str, user_id: str, data: Dict[str, Any]):
        """Set user economy data"""
        self.economy_col.update_one(
            {'guild_id': guild_id, 'user_id': user_id},
            {'$set': {
                'coins': data.get('coins', 0),
                'bank': data.get('bank', 0),
                'lastDaily': data.get('lastDaily', 0),
                'lastWork': data.get('lastWork', 0),
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )
        logger.debug(f'Updated economy for user {user_id} in guild {guild_id}')
    
    def get_user_profile(self, guild_id: str, user_id: str) -> Dict[str, Any]:
        """Get user profile customizations"""
        data = self.profiles_col.find_one({
            'guild_id': guild_id,
            'user_id': user_id
        })
        
        if not data:
            return {}
        
        return {
            'customName': data.get('customName'),
            'customPfp': data.get('customPfp')
        }
    
    def set_user_profile(self, guild_id: str, user_id: str, profile_data: Dict[str, Any]):
        """Set user profile customizations"""
        update_data = {'updated_at': datetime.utcnow()}
        
        if 'customName' in profile_data:
            update_data['customName'] = profile_data['customName']
        if 'customPfp' in profile_data:
            update_data['customPfp'] = profile_data['customPfp']
        
        self.profiles_col.update_one(
            {'guild_id': guild_id, 'user_id': user_id},
            {'$set': update_data},
            upsert=True
        )
        logger.debug(f'Updated profile for user {user_id} in guild {guild_id}')
    
    def get_bot_profile(self, guild_id: str) -> Dict[str, Any]:
        """Get bot profile customizations for a specific guild"""
        data = self.bot_profiles_col.find_one({'guild_id': guild_id})
        
        if not data:
            return {}
        
        return {
            'customName': data.get('customName'),
            'customPfp': data.get('customPfp')
        }
    
    def set_bot_profile(self, guild_id: str, profile_data: Dict[str, Any]):
        """Set bot profile customizations for a specific guild"""
        update_data = {'updated_at': datetime.utcnow()}
        
        if 'customName' in profile_data:
            update_data['customName'] = profile_data['customName']
        if 'customPfp' in profile_data:
            update_data['customPfp'] = profile_data['customPfp']
        
        self.bot_profiles_col.update_one(
            {'guild_id': guild_id},
            {'$set': update_data},
            upsert=True
        )
        logger.info(f'Updated bot profile for guild {guild_id}')
    
    def get_user_inventory(self, guild_id: str, user_id: str) -> Dict[str, Any]:
        """Get user inventory"""
        data = self.inventory_col.find_one({
            'guild_id': guild_id,
            'user_id': user_id
        })
        
        if not data:
            return {}
        
        return data.get('items', {})
    
    def add_to_inventory(self, guild_id: str, user_id: str, item_id: str):
        """Add item to user inventory"""
        # Get current inventory
        inv_data = self.inventory_col.find_one({
            'guild_id': guild_id,
            'user_id': user_id
        })
        
        items = inv_data.get('items', {}) if inv_data else {}
        
        # Add or increment item
        if item_id in items:
            items[item_id]['quantity'] = items[item_id].get('quantity', 0) + 1
        else:
            items[item_id] = {
                'purchased': datetime.utcnow().timestamp(),
                'quantity': 1
            }
        
        # Update in database
        self.inventory_col.update_one(
            {'guild_id': guild_id, 'user_id': user_id},
            {'$set': {
                'items': items,
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )
        logger.info(f'Added item {item_id} to user {user_id} in guild {guild_id}')
    
    def get_shop_items(self, guild_id: str) -> Dict[str, Any]:
        """Get shop items for a guild"""
        data = self.shop_items_col.find_one({'guild_id': guild_id})
        
        if not data:
            return {}
        
        return data.get('items', {})
    
    def set_shop_items(self, guild_id: str, items: Dict[str, Any]):
        """Set shop items for a guild"""
        self.shop_items_col.update_one(
            {'guild_id': guild_id},
            {'$set': {
                'items': items,
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )
    
    def get_warnings(self, guild_id: str, user_id: str) -> list:
        """Get user warnings"""
        data = self.warnings_col.find_one({
            'guild_id': guild_id,
            'user_id': user_id
        })
        
        if not data:
            return []
        
        return data.get('warnings', [])
    
    def add_warning(self, guild_id: str, user_id: str, reason: str, moderator_id: str):
        """Add warning to user"""
        warning = {
            'reason': reason,
            'moderator_id': moderator_id,
            'timestamp': datetime.utcnow().timestamp()
        }
        
        self.warnings_col.update_one(
            {'guild_id': guild_id, 'user_id': user_id},
            {'$push': {'warnings': warning}},
            upsert=True
        )
    
    def clear_warnings(self, guild_id: str, user_id: str):
        """Clear all warnings for a user"""
        self.warnings_col.update_one(
            {'guild_id': guild_id, 'user_id': user_id},
            {'$set': {'warnings': []}},
            upsert=True
        )
    
    def get_last_video_id(self, guild_id: str) -> str:
        """Get last video ID for YouTube notifications"""
        data = self.videos_col.find_one({'guild_id': guild_id})
        
        if not data:
            return None
        
        return data.get('last_video_id')
    
    def set_last_video_id(self, guild_id: str, video_id: str):
        """Set last video ID for YouTube notifications"""
        self.videos_col.update_one(
            {'guild_id': guild_id},
            {'$set': {
                'last_video_id': video_id,
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )
    
    def get_leaderboard_message(self, guild_id: str) -> Dict[str, Any]:
        """Get leaderboard message info"""
        data = self.leaderboards_col.find_one({'guild_id': guild_id})
        
        if not data:
            return {}
        
        return {
            'channel_id': data.get('channel_id'),
            'message_id': data.get('message_id')
        }
    
    def set_leaderboard_message(self, guild_id: str, channel_id: str, message_id: str):
        """Set leaderboard message info"""
        self.leaderboards_col.update_one(
            {'guild_id': guild_id},
            {'$set': {
                'channel_id': channel_id,
                'message_id': message_id,
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )


class ReactionRoles:
    """Manages reaction role mappings"""
    def __init__(self):
        self.collection = db['reaction_roles']
        logger.info('✅ ReactionRoles MongoDB connection initialized')
    
    def load(self):
        """No-op for MongoDB (backwards compatibility)"""
        pass
    
    def save(self):
        """No-op for MongoDB (backwards compatibility)"""
        pass
    
    def add_reaction_role(self, guild_id: str, message_id: str, emoji: str, role_id: str):
        """Add a reaction role mapping"""
        self.collection.update_one(
            {'guild_id': guild_id, 'message_id': message_id},
            {'$set': {
                f'reactions.{emoji}': role_id,
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )
        logger.info(f'Added reaction role: {emoji} -> {role_id} in guild {guild_id}')
    
    def remove_reaction_role(self, guild_id: str, message_id: str, emoji: str = None):
        """Remove a reaction role mapping"""
        if emoji:
            self.collection.update_one(
                {'guild_id': guild_id, 'message_id': message_id},
                {'$unset': {f'reactions.{emoji}': ''}}
            )
        else:
            self.collection.delete_one({
                'guild_id': guild_id,
                'message_id': message_id
            })
        logger.info(f'Removed reaction role in guild {guild_id}')
    
    def get_role_for_reaction(self, guild_id: str, message_id: str, emoji: str) -> str:
        """Get role ID for a reaction"""
        data = self.collection.find_one({
            'guild_id': guild_id,
            'message_id': message_id
        })
        
        if not data:
            return None
        
        return data.get('reactions', {}).get(emoji)


class ServerSettings:
    """Manages per-server settings"""
    def __init__(self):
        self.collection = db['server_settings']
        logger.info('✅ ServerSettings MongoDB connection initialized')
    
    def load(self):
        """No-op for MongoDB (backwards compatibility)"""
        pass
    
    def save(self):
        """No-op for MongoDB (backwards compatibility)"""
        pass
    
    def get(self, guild_id: str, key: str, default=None):
        """Get a setting for a guild"""
        data = self.collection.find_one({'guild_id': guild_id})
        
        if not data:
            return default
        
        return data.get('settings', {}).get(key, default)
    
    def set(self, guild_id: str, key: str, value):
        """Set a setting for a guild"""
        self.collection.update_one(
            {'guild_id': guild_id},
            {'$set': {
                f'settings.{key}': value,
                'updated_at': datetime.utcnow()
            }},
            upsert=True
        )
        logger.info(f'Updated setting {key} for guild {guild_id}')
    
    def get_all(self, guild_id: str) -> Dict[str, Any]:
        """Get all settings for a guild"""
        data = self.collection.find_one({'guild_id': guild_id})
        
        if not data:
            return {}
        
        return data.get('settings', {})


# Global instances
bot_data = BotData()
reaction_roles = ReactionRoles()
server_settings = ServerSettings()