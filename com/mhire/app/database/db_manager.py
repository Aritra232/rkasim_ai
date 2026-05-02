import datetime
import logging
from typing import Dict, List, Tuple, Optional

from fastapi import HTTPException

from com.mhire.app.database.db_connection import DBConnection

logger = logging.getLogger(__name__)

class DBManager(DBConnection):
    def __init__(self):
        super().__init__()
        self.MAX_FACESET_CAPACITY = 1000

    async def save_face_token(self, face_token: str, faceset_id: str = None) -> bool:
        """Save a face token to an available faceset, create new if needed
        
        Args:
            face_token: The face token to save
            faceset_id: Optional faceset ID to use (must exist in Face++ API)
        """
        try:
            # If faceset_id is provided, use it (it should already exist in Face++ API)
            if not faceset_id:
                # Find a faceset with available capacity
                available_faceset = await self.find_available_faceset()
                
                if available_faceset:
                    faceset_id, current_count = available_faceset
                else:
                    # This should not happen as the faceset should be created in Face++ API first
                    # and then passed to this method
                    logger.error("No faceset ID provided and no available faceset found")
                    return False

            # Get existing faceset or create new one
            result = await self.collection.find_one_and_update(
                {'_id': faceset_id},
                {
                    '$setOnInsert': {
                        'created_at': datetime.datetime.now(),
                    },
                    '$push': {'face_tokens': face_token},
                    '$inc': {'count': 1}
                },
                upsert=True,
                return_document=True
            )

            return True
        except Exception as e:
            logger.error(f"Error saving face token: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save face token: {str(e)}")

    async def get_all_stored_faces(self) -> Dict[str, List[str]]:
        """Get all facesets and their tokens for verification"""
        try:
            result = {}
            cursor = self.collection.find({}, {'face_tokens': 1})
            async for doc in cursor:
                result[str(doc['_id'])] = doc.get('face_tokens', [])
            return result
        except Exception as e:
            logger.error(f"Error getting stored faces: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get stored faces: {str(e)}")

    async def get_faceset_metadata(self) -> Dict[str, Dict]:
        """Get metadata for all facesets"""
        try:
            result = {}
            cursor = self.collection.find({}, {'count': 1, 'created_at': 1})
            async for doc in cursor:
                result[str(doc['_id'])] = {
                    "count": doc.get("count", 0),
                    "created_at": doc.get("created_at")
                }
            return result
        except Exception as e:
            logger.error(f"Error getting faceset metadata: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to get faceset metadata: {str(e)}")

    async def find_available_faceset(self) -> Optional[Tuple[str, int]]:
        """Find a faceset with available capacity"""
        try:
            # Find a faceset with count less than max capacity
            doc = await self.collection.find_one(
                {'count': {'$lt': self.MAX_FACESET_CAPACITY}},
                sort=[('count', 1)]  # Sort by count ascending to get the least full faceset
            )
            if doc:
                return str(doc['_id']), doc.get('count', 0)
            return None
        except Exception as e:
            logger.error(f"Error finding available faceset: {str(e)}")
            return None

    async def update_faceset_count(self, faceset_id: str, count: int) -> bool:
        """Update the face count for a faceset"""
        try:
            result = await self.collection.update_one(
                {'_id': faceset_id},
                {'$set': {'count': count}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating faceset count: {str(e)}")
            return False

    # ===== NID VERIFICATION METHODS =====
    
    async def check_nid_exists(self, nid: str) -> bool:
        """Check if NID already exists in the database"""
        try:
            result = await self.collection.find_one(
                {'nid': nid}
            )
            return result is not None
        except Exception as e:
            logger.error(f"Error checking NID existence: {str(e)}")
            return False

    async def get_user_by_nid(self, nid: str) -> Optional[Dict]:
        """Get user record by NID"""
        try:
            user = await self.collection.find_one(
                {'nid': nid}
            )
            return user
        except Exception as e:
            logger.error(f"Error getting user by NID: {str(e)}")
            return None

    async def save_user_with_nid(self, nid: str, face_token: str, faceset_id: str, user_data: Dict = None) -> Optional[str]:
        """
        Save a new user with NID and face token
        
        Args:
            nid: National ID number
            face_token: Face token from Face++ API
            faceset_id: FaceSet ID where face is stored
            user_data: Additional user data (email, phone, name, etc.)
        
        Returns:
            User ID if successful, None otherwise
        """
        try:
            user_document = {
                'nid': nid,
                'face_token': face_token,
                'faceset_id': faceset_id,
                'created_at': datetime.datetime.now(),
                'is_verified': True,
                'status': 'active'
            }
            
            # Add optional user data
            if user_data:
                user_document.update(user_data)
            
            result = await self.collection.insert_one(user_document)
            logger.info(f"User created successfully with NID: {nid}, User ID: {result.inserted_id}")
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"Error saving user with NID: {str(e)}")
            return None

    async def get_user_by_face_token(self, face_token: str) -> Optional[Dict]:
        """Get user record by face token"""
        try:
            user = await self.collection.find_one(
                {'face_token': face_token}
            )
            return user
        except Exception as e:
            logger.error(f"Error getting user by face token: {str(e)}")
            return None

    async def create_unique_index_on_nid(self) -> bool:
        """Create unique index on NID field to prevent duplicates"""
        try:
            await self.collection.create_index('nid', unique=True)
            logger.info("Unique index created on NID field")
            return True
        except Exception as e:
            logger.warning(f"Could not create unique index on NID: {str(e)}")
            return False
    
    # ===== NID INFORMATION EXTRACTION METHODS =====
    
    async def check_nid_info_exists(self, id_number: str) -> bool:
        """Check if NID information already exists in the database by ID number"""
        try:
            result = await self.collection.find_one(
                {'nid_info.id_number': id_number}
            )
            return result is not None
        except Exception as e:
            logger.error(f"Error checking NID info existence: {str(e)}")
            return False
    
    async def get_nid_info_by_id_number(self, id_number: str) -> Optional[Dict]:
        """Get NID information by ID number"""
        try:
            user = await self.collection.find_one(
                {'nid_info.id_number': id_number}
            )
            return user
        except Exception as e:
            logger.error(f"Error getting NID info by ID number: {str(e)}")
            return None
    
    async def save_nid_information(self, nid_info: Dict, face_token: str = None, faceset_id: str = None) -> Optional[str]:
        """
        Save extracted NID information to database
        
        Args:
            nid_info: Dictionary containing extracted NID data (name, id_number, confidence, etc.)
            face_token: Optional face token if face verification was done
            faceset_id: Optional faceset ID
            
        Returns:
            User ID if successful, None otherwise
        """
        try:
            # Check if this ID number already exists
            if nid_info.get('id_number') and await self.check_nid_info_exists(nid_info['id_number']):
                logger.warning(f"NID information already exists for ID: {nid_info['id_number']}")
                return None
            
            user_document = {
                'nid_info': nid_info,
                'created_at': datetime.datetime.now(),
                'status': 'active',
                'source': 'nid_extraction'
            }
            
            # Add face information if provided
            if face_token:
                user_document['face_token'] = face_token
            if faceset_id:
                user_document['faceset_id'] = faceset_id
            
            result = await self.collection.insert_one(user_document)
            logger.info(f"NID information saved successfully for ID: {nid_info.get('id_number')}, User ID: {result.inserted_id}")
            return str(result.inserted_id)
            
        except Exception as e:
            logger.error(f"Error saving NID information: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save NID information: {str(e)}")
    
    async def update_nid_with_face_info(self, id_number: str, face_token: str, faceset_id: str) -> bool:
        """Update existing NID record with face verification information"""
        try:
            result = await self.collection.update_one(
                {'nid_info.id_number': id_number},
                {
                    '$set': {
                        'face_token': face_token,
                        'faceset_id': faceset_id,
                        'face_verified_at': datetime.datetime.now()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating NID with face info: {str(e)}")
            return False