// Test Network Configuration for Production Setup
// Run this in the browser console to test the production configuration

import configManager from './config/configManager.js';

// Test production network configuration
async function testNetworkConfig() {
  console.log('🧪 Testing Production Network Configuration...');
  
  try {
    // Test 1: Check current configuration
    console.log('\n1. Current Production Configuration:');
    configManager.logCurrentConfig();
    
    // Test 2: Check JobPro API URL
    console.log('\n2. JobPro API URL:');
    const jobProUrl = configManager.getJobProApiUrl();
    console.log('✅ JobPro API URL:', jobProUrl);
    
    // Test 3: Check BMAD Backend URL
    console.log('\n3. BMAD Backend URL:');
    const bmadUrl = configManager.getBmadBackendUrl();
    console.log('✅ BMAD Backend URL:', bmadUrl);
    
    // Test 4: Test JobPro connectivity
    console.log('\n4. Testing JobPro connectivity...');
    try {
      const response = await fetch(jobProUrl, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      console.log('✅ JobPro connectivity test:', response.status, response.statusText);
    } catch (error) {
      console.log('⚠️ JobPro connectivity test failed:', error.message);
    }
    
    // Test 5: Test BMAD backend connectivity
    console.log('\n5. Testing BMAD backend connectivity...');
    try {
      const response = await fetch(bmadUrl, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      console.log('✅ BMAD backend connectivity test:', response.status, response.statusText);
    } catch (error) {
      console.log('⚠️ BMAD backend connectivity test failed:', error.message);
    }
    
    // Test 6: Test configuration manager
    console.log('\n6. Testing Configuration Manager:');
    const productionConfig = configManager.getProductionConfig();
    console.log('✅ Production Config:', productionConfig);
    
    const jobProConfig = configManager.getJobProConfig();
    console.log('✅ JobPro Config:', jobProConfig);
    
    const bmadConfig = configManager.getBmadConfig();
    console.log('✅ BMAD Config:', bmadConfig);
    
    // Test 7: Test URL construction for JobPro jobs
    console.log('\n7. Testing URL construction for JobPro jobs:');
    const chatPromptUrl = `${bmadUrl}/tasks`;
    console.log('✅ Chat prompt URL for JobPro:', chatPromptUrl);
    
    const resumeWorkflowUrl = `${bmadUrl}/tasks/test-task-123/resume-workflow`;
    console.log('✅ Resume workflow URL for JobPro:', resumeWorkflowUrl);
    
    const rerunWorkflowUrl = `${bmadUrl}/tasks/test-task-123/reexecute`;
    console.log('✅ Rerun workflow URL for JobPro:', rerunWorkflowUrl);
    
    console.log('\n🎉 Production network configuration test completed successfully!');
    console.log('\n📋 Summary:');
    console.log(`JobPro Server: ${jobProUrl}`);
    console.log(`BMAD Backend: ${bmadUrl}`);
    console.log(`Chat Prompt URL: ${chatPromptUrl}`);
    console.log(`Deployment Environment: ${productionConfig.deployment}`);
    
  } catch (error) {
    console.error('❌ Production network configuration test failed:', error);
  }
}

// Export test function
export { testNetworkConfig };

// Auto-run tests if in browser console
if (typeof window !== 'undefined') {
  console.log('🚀 Production Network Configuration Test Suite Loaded');
  console.log('Run testNetworkConfig() to test the complete production setup');
  
  // Make function available globally for console testing
  window.testNetworkConfig = testNetworkConfig;
}
