# Real-Time Key Rotation Features

## Overview

The BMAD system now provides comprehensive real-time visibility into API key rotation events, ensuring users are always aware of when and why keys are being rotated automatically.

## 🎯 **Key Features Implemented**

### 1. **Real-Time Event Detection**
- **Automatic Monitoring**: System continuously monitors API key status changes
- **Event Logging**: All key rotation and exhaustion events are logged with timestamps
- **Smart Detection**: Distinguishes between rotation, exhaustion, and rate limiting events

### 2. **Frontend Notifications**
- **Toast Notifications**: Real-time popup notifications for key events
- **Status Banners**: Persistent banners showing current rotation status
- **Event History**: Detailed log of recent key events in settings

### 3. **Task Monitor Integration**
- **Live Status**: Shows key rotation events during task execution
- **Context Awareness**: Displays rotation status in real-time as tasks run
- **User Guidance**: Clear explanations of what's happening and what to expect

## 🔍 **How It Works**

### **Event Detection System**
```javascript
// Monitor API key status changes
useEffect(() => {
  if (config.gemini_api_keys_status && lastKeyStatus) {
    const currentStatus = config.gemini_api_keys_status;
    
    // Check if key rotation occurred
    if (currentStatus.current_key_index !== lastKeyStatus.current_key_index) {
      // Create rotation event
      const rotationEvent = {
        type: 'key_rotation',
        message: `🔄 API key rotated from Key ${oldKeyIndex + 1} to Key ${newKeyIndex + 1}`,
        details: { from, to, reason, oldKeyStatus, newKeyStatus }
      };
      
      // Add to events and show notification
      setKeyRotationEvents(prev => [rotationEvent, ...prev.slice(0, 9)]);
      showKeyRotationNotification(rotationEvent);
    }
  }
}, [config.gemini_api_keys_status]);
```

### **Periodic Status Refresh**
```javascript
// Refresh config every 10 seconds to detect changes
useEffect(() => {
  const interval = setInterval(() => {
    if (activeSection === 'settings' || tasks.some(task => task.status === 'in_progress')) {
      fetchConfig();
    }
  }, 10000);
  
  return () => clearInterval(interval);
}, [activeSection, tasks]);
```

## 📱 **Frontend Components**

### 1. **Settings Page - API Key Status**
- **Real-Time Display**: Shows current key status and rotation events
- **Event History**: Lists last 10 key events with timestamps
- **Management Controls**: Reset exhausted keys, manual rotation
- **Visual Indicators**: Color-coded status for different event types

### 2. **Global Notification System**
- **Toast Notifications**: Appear in top-right corner for key events
- **Status Banners**: Fixed banner at top-center during rotation
- **Smart Duration**: Longer display for important events (8-10 seconds)

### 3. **Task Monitor Integration**
- **Live Status**: Real-time key rotation status during task execution
- **Context Awareness**: Shows rotation events as they happen
- **User Guidance**: Explains what the system is doing automatically

## 🎨 **Visual Design**

### **Color Coding**
- **🟢 Green**: Successful key rotation events
- **🟡 Yellow**: Key exhaustion warnings
- **🔴 Red**: API errors (existing system)

### **Status Indicators**
- **Animated Pulse**: Green dot during active rotation
- **Icons**: 🔄 for rotation, ⚠️ for warnings
- **Borders**: Color-coded borders for different event types

### **Layout**
- **Fixed Positioning**: Notifications don't interfere with content
- **Responsive Design**: Adapts to different screen sizes
- **Accessibility**: Clear contrast and readable text

## 📊 **Event Types Tracked**

### 1. **Key Rotation Events**
```javascript
{
  type: 'key_rotation',
  message: '🔄 API key rotated from Key 1 to Key 2',
  details: {
    from: 'Key 1',
    to: 'Key 2',
    reason: 'Quota exhausted',
    oldKeyStatus: 'Exhausted',
    newKeyStatus: 'Active'
  }
}
```

### 2. **Key Exhaustion Events**
```javascript
{
  type: 'key_exhausted',
  message: '⚠️ API Key 1 marked as exhausted',
  details: {
    keyIndex: 1,
    reason: 'quota_exhausted',
    timestamp: '2024-01-01T12:00:00Z'
  }
}
```

## 🔄 **Real-Time Updates**

### **Settings Page**
- **Live Status**: Updates every 10 seconds when active
- **Event Log**: Shows real-time rotation events
- **Key Health**: Displays current key status and availability

### **Task Monitor**
- **Live Detection**: Scans logs for rotation events in real-time
- **Status Banners**: Shows rotation status during task execution
- **Context Awareness**: Integrates with existing error handling

### **Global Notifications**
- **Immediate Display**: Shows events as they happen
- **Persistent Banners**: Stays visible during active rotation
- **Smart Timing**: Longer display for important events

## 🎯 **User Experience**

### **Before Implementation**
- ❌ No visibility into key rotation
- ❌ Users unaware when keys are exhausted
- ❌ Manual intervention required
- ❌ No understanding of system behavior

### **After Implementation**
- ✅ **Real-time visibility** into all key events
- ✅ **Clear notifications** when rotation happens
- ✅ **Automatic operation** with user awareness
- ✅ **Comprehensive logging** of all events
- ✅ **Context-aware display** in relevant areas

## 🚀 **Benefits**

### **For Users**
- **Transparency**: Always know what's happening with API keys
- **Confidence**: Trust that the system is handling issues automatically
- **Understanding**: Clear view of system behavior and status
- **Control**: Manual options when needed

### **For System Administrators**
- **Monitoring**: Real-time visibility into key health
- **Debugging**: Detailed event logs for troubleshooting
- **Optimization**: Insights into key usage patterns
- **Maintenance**: Clear indicators when manual intervention is needed

## 🔧 **Technical Implementation**

### **State Management**
```javascript
const [keyRotationEvents, setKeyRotationEvents] = useState([]);
const [lastKeyStatus, setLastKeyStatus] = useState(null);
```

### **Event Detection**
```javascript
// Detect changes in key status
const currentStatus = config.gemini_api_keys_status;
const lastStatus = lastKeyStatus;

if (currentStatus.current_key_index !== lastStatus.current_key_index) {
  // Key rotation detected
  createRotationEvent(currentStatus, lastStatus);
}
```

### **Notification System**
```javascript
const showKeyRotationNotification = (event) => {
  const message = event.type === 'key_rotation' 
    ? `🔄 API key rotated: ${event.details.from} → ${event.details.to}`
    : `⚠️ API key exhausted: ${event.details.keyIndex}`;
  
  showNotification(message, event.type === 'rotation' ? 'info' : 'warning');
};
```

## 📱 **User Interface Elements**

### **Settings Page**
1. **API Key Status Section**
   - Total keys, available keys, current key
   - Real-time rotation indicator
   - Management buttons

2. **Event History Section**
   - Recent key events (last 10)
   - Detailed event information
   - Clear events button

3. **Key Rotation Banner**
   - Shows active rotation status
   - Animated indicators
   - Clear status information

### **Task Monitor**
1. **Key Rotation Status Banner**
   - Real-time rotation status
   - Context-aware messaging
   - Timestamp information

2. **Integration with Existing UI**
   - Non-intrusive placement
   - Consistent styling
   - Clear user guidance

### **Global Notifications**
1. **Toast Notifications**
   - Top-right corner placement
   - Color-coded by event type
   - Smart duration timing

2. **Status Banners**
   - Top-center placement
   - Persistent during active events
   - Clear event information

## 🔮 **Future Enhancements**

### **Advanced Monitoring**
- **Usage Analytics**: Track key usage patterns
- **Predictive Alerts**: Warn before keys are exhausted
- **Performance Metrics**: Monitor rotation efficiency

### **Enhanced Notifications**
- **Email Alerts**: Send notifications for critical events
- **Webhook Integration**: Integrate with external monitoring systems
- **Custom Alerts**: User-configurable notification preferences

### **Dashboard Integration**
- **Key Health Dashboard**: Comprehensive key status view
- **Usage Trends**: Historical key usage analysis
- **Cost Optimization**: Insights for better key management

## 📋 **Configuration Options**

### **Refresh Intervals**
- **Settings Page**: 10 seconds when active
- **Task Monitor**: 2 seconds during task execution
- **Global Monitoring**: Continuous with smart throttling

### **Event Retention**
- **Event History**: Last 10 events
- **Log Scanning**: Real-time during task execution
- **Status Persistence**: Maintained across page refreshes

### **Notification Settings**
- **Toast Duration**: 5-10 seconds based on event importance
- **Banner Display**: Persistent during active events
- **Event Logging**: Comprehensive with timestamps

## 🎉 **Conclusion**

The real-time key rotation features provide unprecedented visibility into the BMAD system's API key management. Users now have:

- **Complete transparency** into key rotation events
- **Real-time awareness** of system status
- **Clear understanding** of automatic operations
- **Comprehensive logging** of all events
- **Professional user experience** with modern UI patterns

This implementation transforms the system from a "black box" that users hope works, to a transparent, trustworthy system that clearly communicates its operations and status. Users can now confidently use the system knowing they'll be informed of any key-related events in real-time.
