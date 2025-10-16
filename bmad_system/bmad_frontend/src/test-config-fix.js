// Test Configuration Fix
// This test verifies that the BMAD backend URL is correctly configured

import configManager from './config/configManager.js';
import jobProService from './services/jobProService.js';

// Test environment detection
function testEnvironmentDetection() {
  console.log('🧪 Testing Environment Detection...');
  
  try {
    const env = getCurrentEnvironment();
    console.log('✅ Environment detected:', env);
    
    const backendUrl = configManager.getBmadBackendUrl();
    console.log('✅ BMAD Backend URL:', backendUrl);
    
    // Verify the URL is absolute
    if (backendUrl.startsWith('http://') || backendUrl.startsWith('https://')) {
      console.log('✅ URL is absolute');
    } else {
      console.log('❌ URL is relative:', backendUrl);
    }
    
    return { env, backendUrl };
    
  } catch (error) {
    console.error('❌ Environment detection failed:', error);
    return null;
  }
}

// Test JobPro service configuration
function testJobProConfiguration() {
  console.log('\n🧪 Testing JobPro Service Configuration...');
  
  try {
    // Debug current configuration
    const config = jobProService.debugConfiguration();
    console.log('✅ Current configuration:', config);
    
    // Test URL validation
    const isValid = jobProService.validateBackendUrl();
    console.log('✅ URL validation:', isValid);
    
    // Test URL construction
    try {
      const testUrl = jobProService.getFullUrl('/tasks');
      console.log('✅ URL construction test:', testUrl);
    } catch (error) {
      console.log('❌ URL construction failed:', error.message);
    }
    
    return config;
    
  } catch (error) {
    console.error('❌ JobPro configuration test failed:', error);
    return null;
  }
}

// Test configuration refresh
function testConfigurationRefresh() {
  console.log('\n🧪 Testing Configuration Refresh...');
  
  try {
    // Force refresh configuration
    jobProService.forceRefreshConfiguration();
    
    // Wait a bit for the async refresh to complete
    setTimeout(() => {
      console.log('✅ Configuration refresh completed');
      const config = jobProService.debugConfiguration();
      console.log('✅ Refreshed configuration:', config);
    }, 1000);
    
  } catch (error) {
    console.error('❌ Configuration refresh failed:', error);
  }
}

// Test the complete flow
function testCompleteFlow() {
  console.log('\n🧪 Testing Complete Flow...');
  
  try {
    // 1. Check environment
    const envResult = testEnvironmentDetection();
    if (!envResult) {
      console.log('❌ Environment detection failed, stopping test');
      return;
    }
    
    // 2. Check JobPro configuration
    const jobProResult = testJobProConfiguration();
    if (!jobProResult) {
      console.log('❌ JobPro configuration failed, stopping test');
      return;
    }
    
    // 3. Test URL construction
    try {
      const testUrl = jobProService.getFullUrl('/tasks');
      console.log('✅ Complete flow test successful');
      console.log('Final URL for JobPro:', testUrl);
      
      // Verify it matches expected format
      if (testUrl === 'http://157.66.191.31:9191/api/tasks') {
        console.log('🎉 Perfect! URL format is correct for JobPro');
      } else {
        console.log('⚠️  URL format is different than expected');
        console.log('Expected: http://157.66.191.31:9191/api/tasks');
        console.log('Got:     ', testUrl);
      }
      
    } catch (error) {
      console.log('❌ Complete flow test failed:', error.message);
    }
    
  } catch (error) {
    console.error('❌ Complete flow test failed:', error);
  }
}

// Export test functions
export { testEnvironmentDetection, testJobProConfiguration, testConfigurationRefresh, testCompleteFlow };

// Auto-run tests if in browser console
if (typeof window !== 'undefined') {
  console.log('🚀 Configuration Fix Test Suite Loaded');
  console.log('Run testCompleteFlow() to test the complete configuration');
  console.log('Run testEnvironmentDetection() to test environment detection');
  console.log('Run testJobProConfiguration() to test JobPro configuration');
  console.log('Run testConfigurationRefresh() to test configuration refresh');
  
  // Make functions available globally for console testing
  window.testCompleteFlow = testCompleteFlow;
  window.testEnvironmentDetection = testEnvironmentDetection;
  window.testJobProConfiguration = testJobProConfiguration;
  window.testConfigurationRefresh = testConfigurationRefresh;
  
  // Auto-run the complete test
  console.log('\n🔄 Auto-running complete flow test...');
  setTimeout(() => {
    testCompleteFlow();
  }, 500);
}
