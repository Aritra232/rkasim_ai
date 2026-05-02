# Rkasim AI Platform

A FastAPI-based backend with multi-service architecture including:

1. **Chatbot Service**: Intent-based routing with RAG (Retrieval-Augmented Generation)
2. **User Signup & NID Verification**: Dual verification (NID + Face recognition) to prevent duplicate registrations
3. **Face Verification**: Face detection and duplicate prevention using Face++ API
4. **Resume Processing**: Resume analysis and information extraction
5. **Biometric Verification**: Face-to-NID card comparison for identity verification

## Key Features

### User Signup with NID Verification
- **NID Duplicate Prevention**: Checks if NID already registered before signup
- **Face Verification**: Validates face photos and detects duplicates
- **Dual Validation**: Both NID and face must be unique to prevent fraud
- **MongoDB Storage**: All user data including NID and face tokens stored persistently

### Biometric Verification
- Face-to-NID card comparison
- Multi-face handling in NID cards
- Automatic image resizing and optimization
- Quality analysis for faces
- Per-user conversation memory with ConversationBufferMemory

### Additional Features
- OpenAI GPT-4o-mini for LLM and embeddings
- FAISS vector store for document retrieval
- Face++ API integration for face recognition
- Error handling and graceful fallbacks

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables in `.env`:**
   ```
   OPENAI_API_KEY=your_openai_api_key
   API_KEY=your_faceplus_api_key
   API_SECRET=your_faceplus_api_secret
   MONGODB_URI=your_mongodb_connection_string
   MONGODB_DB=database_name
   MONGODB_COLLECTION=collection_name
   ```

3. **Initialize MongoDB:**
   - The system creates necessary indexes automatically
   - Ensure MongoDB is running and accessible

4. **Prepare knowledge base (optional):**
   - Place PDF documents in `data/knowledge_base/` directory
   - Run `python ingest.py` to create FAISS index

## Running the Application

### Development
```bash
python -m com.mhire.app.main
```

### Production
```bash
uvicorn com.mhire.app.main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### User Signup with NID Verification
**POST** `/api/v1/signup`

Multipart form data:
- `nid` (string, required): National ID number
- `face_photo` (file, required): Face image file (JPEG/PNG, max 10MB)
- `email` (string, optional): User email
- `phone` (string, optional): User phone
- `name` (string, optional): User full name

Response:
```json
{
  "status": "success|error|duplicate_nid|duplicate_face",
  "message": "Description of result",
  "success": true,
  "user_id": "generated_user_id",
  "face_token": "face_token_from_api",
  "nid": "registered_nid",
  "error": null
}
```

**Status Codes:**
- `success`: User registered successfully with unique NID and face
- `duplicate_nid`: NID already registered
- `duplicate_face`: Face already registered by another user
- `error`: Validation or processing error

### Check NID Availability
**POST** `/api/v1/check-nid`

Form data:
- `nid` (string, required): NID to check

Response:
```json
{
  "status": "available|duplicate|invalid|error",
  "available": true/false,
  "message": "Status message"
}
```

### Get User by NID
**GET** `/api/v1/user/{nid}`

Response:
```json
{
  "status": "found|not_found|error",
  "user": {
    "user_id": "id",
    "nid": "nid",
    "name": "name",
    "email": "email",
    "phone": "phone",
    "created_at": "timestamp",
    "status": "active"
  }
}
```

### Face Verification
**POST** `/api/v1/verify`

Multipart form data:
- `file` (file, required): Face image file

### Biometric Verification (Face vs NID)
**POST** `/api/v1/nid_verification`

Multipart form data:
- `nid_card` (file, required): NID card image
- `face_photo` (file, required): Face photo
- `confidence_threshold` (integer, optional): Confidence threshold 50-95

### Chat Endpoint
**POST** `/api/chat`

Request body:
```json
{
  "query": "Your question or message",
  "user_id": "optional_user_identifier"
}
```

## Database Schema

### Users Collection
```json
{
  "_id": ObjectId,
  "nid": "string (unique)",
  "face_token": "string (from Face++ API)",
  "faceset_id": "string",
  "email": "string (optional)",
  "phone": "string (optional)",
  "name": "string (optional)",
  "created_at": "datetime",
  "is_verified": true,
  "status": "active"
}
```

## Workflow: User Signup with NID Verification

```
User Request (NID + Face Photo)
    ↓
1. Validate NID format
    ↓
2. Check if NID exists in database
    ├─ YES → Return "duplicate_nid" error
    └─ NO → Continue
    ↓
3. Validate face photo (format, size)
    ├─ INVALID → Return error
    └─ VALID → Continue
    ↓
4. Process face with Face++ API
    ├─ No face detected → Return error
    └─ Face detected → Continue
    ↓
5. Search for duplicate faces
    ├─ Duplicate found → Return "duplicate_face" error
    └─ No duplicates → Continue
    ↓
6. Save face to FaceSet
    ↓
7. Save user to database (NID + face_token + metadata)
    ↓
Return success with user_id and face_token
```

## Project Structure

```
com/mhire/app/
├── main.py                              # FastAPI app setup
├── config/
│   └── config.py                        # Configuration loader
├── database/
│   ├── db_connection.py                 # MongoDB connection
│   └── db_manager.py                    # Database operations (NID, face tokens)
├── services/
│   ├── chatbot/                         # Chatbot service
│   ├── verification/                    # NID-Face biometric verification
│   ├── resume/                          # Resume processing
│   └── verification_system/
│       ├── signup_router.py             # Signup endpoint with NID verification
│       ├── face_verification/           # Face verification logic
│       │   ├── face_verification.py     # Core face verification
│       │   ├── face_verification_router.py
│       │   └── face_verification_schema.py
│       └── api_manager/
│           └── faceplusplus_manager.py  # Face++ API integration
data/
├── knowledge_base/                      # PDF documents for RAG
faiss_index/
├── index.faiss                          # FAISS vector store
```

## Environment Variables Required

```
# OpenAI
OPENAI_API_KEY=sk-...

# Face++ API
API_KEY=your_faceplus_key
API_SECRET=your_faceplus_secret
FPP_CREATE=true
FPP_DETECT=true
FPP_SEARCH=true
FPP_ADD=true
FPP_GET_DETAIL=true

# MongoDB
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=rkasim_db
MONGODB_COLLECTION=users

# LLM Configuration
MODEL=gpt-4o-mini
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
SEARCH_K=3
KNOWLEDGE_BASE_PATH=data/knowledge_base/
FAISS_INDEX_PATH=faiss_index/
```

## Error Handling

The application includes comprehensive error handling:
- NID format validation
- Duplicate NID prevention at database level (unique constraint)
- Face detection and quality validation
- Automatic image resizing for large files
- Graceful error responses with descriptive messages
- Detailed logging for debugging

## Security Notes

1. **NID Storage**: NIDs are stored in plain text in MongoDB (add encryption if needed for production)
2. **Face Data**: Face tokens are stored but actual face images are not persisted
3. **Authentication**: Add authentication middleware for user endpoints in production
4. **Rate Limiting**: Implement rate limiting for signup endpoint to prevent abuse
5. **Input Validation**: All inputs are validated and sanitized