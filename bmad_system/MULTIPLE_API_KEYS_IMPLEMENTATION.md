# Multiple Gemini API Keys Implementation

## Overview

The BMAD system now supports multiple Gemini API keys with automatic rotation when quota is exhausted. This ensures workflow continuity without manual intervention when one API key reaches its quota limit.

## Key Features

### 🔑 **Multiple API Key Support**
- **Primary Key**: Main API key (required)
- **Other Keys**: Up to 2 additional keys for rotation
- **Automatic Rotation**: Seamlessly switches to next available key
- **Session Restart**: Automatically restarts Gemini CLI session with new key

### 🔄 **Automatic Key Rotation**
- **Quota Exhaustion Detection**: Automatically detects when a key is exhausted
- **Smart Rotation**: Only rotates on quota exhaustion, not rate limits
- **Session Management**: Restarts Gemini CLI session to pick up new key
- **Workflow Continuity**: Tasks continue without interruption

### 🛡️ **Error Handling**
- **Quota vs Rate Limit**: Distinguishes between quota exhaustion and rate limiting
- **Retry Logic**: Implements retry attempts before marking key as exhausted
- **Fallback Strategy**: Gracefully handles when all keys are exhausted

## Architecture

### Backend Components

#### 1. **GeminiAPIKeyManager** (`bmad_backend/src/llm_clients/gemini_api_key_manager.py`)
- **Core Management**: Handles all API key operations
- **Persistent Storage**: Stores keys in `instance/gemini_api_keys.json`
- **Rotation Logic**: Manages automatic key switching
- **Status Tracking**: Monitors key health and exhaustion

#### 2. **Enhanced GeminiCLIClient** (`bmad_backend/src/llm_clients/gemini_cli_client.py`)
- **Integration**: Uses API key manager for all operations
- **Session Management**: Automatically restarts sessions with new keys
- **Error Handling**: Integrates with key manager for automatic rotation
- **Backward Compatibility**: Maintains existing API

#### 3. **New API Endpoints** (`bmad_backend/src/routes/bmad_api.py`)
- `GET /api/config/gemini/keys` - Get key status
- `POST /api/config/gemini/keys` - Add new key
- `DELETE /api/config/gemini/keys/<key>` - Remove key
- `POST /api/config/gemini/keys/reset` - Reset exhausted keys
- `POST /api/config/gemini/keys/rotate` - Manual rotation

### Frontend Components

#### 1. **Enhanced Settings UI** (`bmad_frontend/src/App.jsx`)
- **Multiple Key Inputs**: Primary + 2 additional keys
- **Real-time Status**: Shows current key status and rotation
- **Management Controls**: Reset exhausted keys, manual rotation
- **Security**: Never displays full API keys in UI

#### 2. **Key Status Display**
- **Visual Indicators**: Shows active/exhausted key status
- **Rotation Controls**: Buttons for manual operations
- **Statistics**: Total keys, available keys, current key

## Configuration

### Environment Variables

```bash
# Primary API key (required)
GEMINI_API_KEY=your_primary_api_key_here

# Additional API keys (optional)
GEMINI_OTHER_KEY_1=your_second_api_key_here
GEMINI_OTHER_KEY_2=your_third_api_key_here
```

### Storage Location

API keys are stored in:
```
bmad_backend/instance/gemini_api_keys.json
```

**Security Note**: This file contains sensitive information and should be protected.

## How It Works

### 1. **Initialization**
```python
# System starts with primary key from environment
manager = GeminiAPIKeyManager()
# Loads existing keys from storage or environment
```

### 2. **Normal Operation**
```python
# Use current active key
current_key = manager.get_current_key()
# Set as environment variable for Gemini CLI
os.environ['GEMINI_API_KEY'] = current_key
```

### 3. **Quota Exhaustion Detection**
```python
# When API call fails with quota error
if manager.is_quota_exhausted_error(error_message):
    # Mark current key as exhausted
    manager.mark_key_exhausted(current_key, "quota_exhausted")
    # Automatically rotate to next available key
    # Restart Gemini CLI session
```

### 4. **Key Rotation Process**
```python
def _rotate_to_next_key(self):
    # Find next non-exhausted key
    while attempts < len(self.api_keys):
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        current_key = self.api_keys[self.current_key_index]
        
        if current_key not in self.exhausted_keys:
            return True  # Rotation successful
    
    return False  # All keys exhausted
```

### 5. **Session Restart**
```python
def restart_session_with_new_key(self):
    # Reconfigure with new key
    self._configure_api_key()
    # Clear conversation history
    self.conversation_history.clear()
    # Start new chat session
    self.start_chat_session()
```

## Error Handling Strategy

### **Quota Exhaustion** → **Automatic Rotation**
- **Triggers**: "quota exceeded", "insufficient quota", "billing not enabled"
- **Action**: Mark key as exhausted, rotate to next key, restart session
- **Result**: Workflow continues seamlessly

### **Rate Limiting** → **No Rotation**
- **Triggers**: "rate limit exceeded", "too many requests", "429"
- **Action**: Wait for rate limit to reset, keep current key
- **Result**: Temporary delay, no key rotation needed

### **Other Errors** → **Incremental Retry**
- **Triggers**: Network errors, timeouts, other API errors
- **Action**: Increment retry counter, rotate if max retries reached
- **Result**: Graceful degradation with retry limits

## API Usage Examples

### **Add Multiple API Keys**
```bash
# Add primary key
curl -X POST http://localhost:5006/api/config/gemini/keys \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your_primary_key"}'

# Add additional keys
curl -X POST http://localhost:5006/api/config/gemini/keys \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your_second_key"}'

curl -X POST http://localhost:5006/api/config/gemini/keys \
  -H "Content-Type: application/json" \
  -d '{"api_key": "your_third_key"}'
```

### **Check Key Status**
```bash
curl http://localhost:5006/api/config/gemini/keys
```

### **Manual Key Rotation**
```bash
curl -X POST http://localhost:5006/api/config/gemini/keys/rotate
```

### **Reset Exhausted Keys**
```bash
curl -X POST http://localhost:5006/api/config/gemini/keys/reset
```

## Frontend Usage

### **Adding Keys**
1. Navigate to **Settings** → **API Configuration**
2. Enter **Primary Gemini API Key**
3. Optionally enter **Other API Key 1** and **Other API Key 2**
4. Click **Update Configuration**

### **Monitoring Status**
- **Total Keys**: Number of configured keys
- **Available Keys**: Number of non-exhausted keys
- **Current Key**: Which key is currently active
- **Key Details**: Individual key status with visual indicators

### **Manual Operations**
- **Reset Exhausted**: Clear exhaustion status for all keys
- **Rotate Key**: Manually switch to next available key

## Benefits

### **🔄 Workflow Continuity**
- No manual intervention required when quota is exhausted
- Tasks continue automatically with new API key
- Seamless user experience

### **💰 Cost Management**
- Distribute usage across multiple API keys
- Extend daily/monthly quotas
- Better resource utilization

### **🛡️ Reliability**
- Automatic fallback when keys fail
- Intelligent error handling
- Robust retry mechanisms

### **🔒 Security**
- Keys stored securely in backend
- Never exposed in frontend
- Encrypted storage support (future enhancement)

## Security Considerations

### **Key Storage**
- Keys stored in `instance/` directory (not in version control)
- JSON format with proper permissions
- Consider encryption for production environments

### **Access Control**
- API endpoints require proper authentication
- Keys never returned in full (only last 4 characters)
- Secure transmission over HTTPS

### **Monitoring**
- Log all key rotation events
- Track usage per key
- Alert on suspicious activity

## Future Enhancements

### **🔐 Encryption**
- Encrypt stored API keys
- Hardware security module (HSM) integration
- Key rotation policies

### **📊 Analytics**
- Usage tracking per key
- Cost analysis and optimization
- Predictive quota management

### **🤖 Advanced Rotation**
- Time-based rotation
- Load balancing across keys
- Custom rotation policies

### **🔗 Integration**
- Google Cloud IAM integration
- Service account key management
- Automated key provisioning

## Troubleshooting

### **Common Issues**

#### **No Keys Available**
```bash
# Check if keys are loaded
curl http://localhost:5006/api/config/gemini/keys

# Add keys through frontend or API
```

#### **Keys Not Rotating**
```bash
# Check key status
curl http://localhost:5006/api/config/gemini/keys

# Reset exhausted keys if needed
curl -X POST http://localhost:5006/api/config/gemini/keys/reset
```

#### **Session Not Restarting**
```bash
# Check backend logs for rotation events
# Verify Gemini CLI is working with new key
# Check environment variable updates
```

### **Debug Commands**
```bash
# Test API key manager
python3 test_api_key_manager.py

# Check key storage file
cat bmad_backend/instance/gemini_api_keys.json

# Monitor backend logs
tail -f bmad_backend/logs/bmad.log
```

## Conclusion

The multiple API key system provides robust, automatic key management that ensures workflow continuity while maintaining security and ease of use. Users can now configure multiple keys and let the system handle rotation automatically, eliminating the need for manual intervention when quota limits are reached.

This implementation follows best practices for API key management and provides a solid foundation for future enhancements in security, monitoring, and automation.
