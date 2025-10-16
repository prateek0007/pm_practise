// Test URL Construction for JobPro
// This test ensures JobPro receives absolute URLs instead of relative URLs

import jobProService from './services/jobProService.js';
import configManager from './config/configManager.js';

// Test URL construction
function testUrlConstruction() {
  console.log('🧪 Testing URL Construction for JobPro...');
  
  try {
    // Test 1: Check current backend URL
    console.log('\n1. Current BMAD Backend URL:');
    const currentBackendUrl = jobProService.getCurrentBackendUrl();
    console.log('✅ Backend URL:', currentBackendUrl);
    
    // Test 2: Check if URL is absolute
    console.log('\n2. URL Validation:');
    const isValid = jobProService.validateBackendUrl();
    console.log('✅ URL is valid:', isValid);
    
    // Test 3: Test URL construction for different endpoints
    console.log('\n3. URL Construction Tests:');
    
    const endpoints = [
      '/tasks',
      '/tasks/123/resume-workflow',
      '/tasks/123/reexecute',
      '/tasks/123/upload',
      'tasks'  // Test without leading slash
    ];
    
    endpoints.forEach(endpoint => {
      try {
        const fullUrl = jobProService.getFullUrl(endpoint);
        console.log(`✅ ${endpoint} → ${fullUrl}`);
        
        // Verify it's absolute
        if (fullUrl.startsWith('http://') || fullUrl.startsWith('https://')) {
          console.log(`   ✅ Absolute URL confirmed`);
        } else {
          console.log(`   ❌ Relative URL detected: ${fullUrl}`);
        }
      } catch (error) {
        console.log(`❌ ${endpoint} → Error: ${error.message}`);
      }
    });
    
    // Test 4: Test JobPro job data construction
    console.log('\n4. JobPro Job Data Construction:');
    
    const testJobData = {
      url: jobProService.getFullUrl('/tasks'),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: 'submit_task',
      ref: '1'
    };
    
    console.log('✅ Job Data for JobPro:');
    console.log(JSON.stringify(testJobData, null, 2));
    
    // Test 5: Verify the URL being sent to JobPro
    console.log('\n5. Final URL Verification:');
    const finalUrl = testJobData.url;
    console.log('Final URL:', finalUrl);
    
    if (finalUrl === 'http://157.66.191.31:9191/api/tasks') {
      console.log('✅ Correct URL format for JobPro!');
    } else {
      console.log('❌ Incorrect URL format. Expected: http://157.66.191.31:9191/api/tasks');
      console.log('   Got:', finalUrl);
    }
    
    console.log('\n🎉 URL construction test completed!');
    
  } catch (error) {
    console.error('❌ URL construction test failed:', error);
  }
}

// Test URL refresh
function testUrlRefresh() {
  console.log('🧪 Testing URL Refresh...');
  
  try {
    // Get current URL
    const currentUrl = jobProService.getCurrentBackendUrl();
    console.log('Current URL:', currentUrl);
    
    // Refresh from config
    const refreshedUrl = jobProService.refreshBackendUrl();
    console.log('Refreshed URL:', refreshedUrl);
    
    // Verify they match
    if (currentUrl === refreshedUrl) {
      console.log('✅ URL refresh successful');
    } else {
      console.log('❌ URL refresh failed - URLs do not match');
    }
    
  } catch (error) {
    console.error('❌ URL refresh test failed:', error);
  }
}

// Test error handling
function testErrorHandling() {
  console.log('🧪 Testing Error Handling...');
  
  try {
    // Test with invalid backend URL
    jobProService.setBmadBackendUrl('/api');  // This should be invalid
    
    const isValid = jobProService.validateBackendUrl();
    console.log('URL validation result:', isValid);
    
    // Try to construct a URL (should fail)
    try {
      const fullUrl = jobProService.getFullUrl('/tasks');
      console.log('❌ Should have failed, but got:', fullUrl);
    } catch (error) {
      console.log('✅ Correctly caught error:', error.message);
    }
    
    // Reset to valid URL
    jobProService.refreshBackendUrl();
    console.log('✅ Reset to valid URL');
    
  } catch (error) {
    console.error('❌ Error handling test failed:', error);
  }
}

// Export test functions
export { testUrlConstruction, testUrlRefresh, testErrorHandling };

// Auto-run tests if in browser console
if (typeof window !== 'undefined') {
  console.log('🚀 URL Construction Test Suite Loaded');
  console.log('Run testUrlConstruction() to test URL construction');
  console.log('Run testUrlRefresh() to test URL refresh');
  console.log('Run testErrorHandling() to test error handling');
  
  // Make functions available globally for console testing
  window.testUrlConstruction = testUrlConstruction;
  window.testUrlRefresh = testUrlRefresh;
  window.testErrorHandling = testErrorHandling;
}
