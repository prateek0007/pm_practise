// Network Connectivity Test for JobPro to BMAD Backend
// This test helps diagnose connection issues between JobPro and BMAD backend

import configManager from './config/configManager.js';

// Test 1: Check if BMAD backend is accessible from the browser
async function testBmadBackendAccessibility() {
  console.log('🧪 Testing BMAD Backend Accessibility from Browser...');
  
  const backendUrl = configManager.getBmadBackendUrl();
  console.log('Backend URL to test:', backendUrl);
  
  try {
    // Test basic connectivity
    const response = await fetch(backendUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (response.ok) {
      console.log('✅ BMAD backend is accessible from browser');
      return true;
    } else {
      console.log('⚠️  BMAD backend responded with status:', response.status);
      return false;
    }
  } catch (error) {
    console.log('❌ BMAD backend is not accessible from browser:', error.message);
    return false;
  }
}

// Test 2: Check if JobPro server is accessible
async function testJobProAccessibility() {
  console.log('\n🧪 Testing JobPro Server Accessibility...');
  
  const jobProUrl = `http://${NETWORK_CONFIG.VM_IP}:${NETWORK_CONFIG.JOBPRO_PORT}/jobpro/pipiline`;
  console.log('JobPro URL to test:', jobProUrl);
  
  try {
    const response = await fetch(jobProUrl, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (response.ok) {
      console.log('✅ JobPro server is accessible');
      return true;
    } else {
      console.log('⚠️  JobPro server responded with status:', response.status);
      return false;
    }
  } catch (error) {
    console.log('❌ JobPro server is not accessible:', error.message);
    return false;
  }
}

// Test 3: Test the specific endpoint that JobPro is trying to call
async function testSpecificEndpoint() {
  console.log('\n🧪 Testing Specific BMAD Backend Endpoint...');
  
      const endpointUrl = `${configManager.getBmadBackendUrl()}/tasks`;
  console.log('Testing endpoint:', endpointUrl);
  
  try {
    // Test with OPTIONS to check if endpoint exists
    const optionsResponse = await fetch(endpointUrl, {
      method: 'OPTIONS',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    console.log('✅ Endpoint exists (OPTIONS response):', optionsResponse.status);
    
    // Test with POST (what JobPro is trying to do)
    const postResponse = await fetch(endpointUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: 'test prompt',
        workflow_id: null,
        workflow_sequence: null,
        agent_specific_prompts: null
      })
    });
    
    if (postResponse.ok) {
      console.log('✅ POST request to /tasks endpoint successful');
      return true;
    } else {
      console.log('⚠️  POST request failed with status:', postResponse.status);
      const errorText = await postResponse.text();
      console.log('Error response:', errorText);
      return false;
    }
    
  } catch (error) {
    console.log('❌ Endpoint test failed:', error.message);
    return false;
  }
}

// Test 4: Network configuration check
function testNetworkConfiguration() {
  console.log('\n🧪 Testing Network Configuration...');
  
  console.log('Current Network Config:');
  console.log('- VM IP:', NETWORK_CONFIG.VM_IP);
  console.log('- JobPro Port:', NETWORK_CONFIG.JOBPRO_PORT);
  console.log('- BMAD Backend Port:', NETWORK_CONFIG.BMAD_BACKEND_PORT);
  console.log('- Frontend Port:', NETWORK_CONFIG.FRONTEND_PORT);
  
  console.log('\nConstructed URLs:');
  console.log('- JobPro API:', `http://${NETWORK_CONFIG.VM_IP}:${NETWORK_CONFIG.JOBPRO_PORT}/jobpro/pipiline`);
      console.log('- BMAD Backend:', configManager.getBmadBackendUrl());
    console.log('- BMAD Tasks Endpoint:', `${configManager.getBmadBackendUrl()}/tasks`);
  
  // Check if we're running on the same network
  const currentHostname = window.location.hostname;
  console.log('\nCurrent hostname:', currentHostname);
  
  if (currentHostname === NETWORK_CONFIG.VM_IP) {
    console.log('✅ Running on VM IP - same network as JobPro and BMAD backend');
  } else if (currentHostname === 'localhost' || currentHostname === '127.0.0.1') {
    console.log('⚠️  Running on localhost - different network from JobPro and BMAD backend');
  } else {
    console.log('⚠️  Running on different hostname - may have network issues');
  }
}

// Test 5: Simulate JobPro request
async function simulateJobProRequest() {
  console.log('\n🧪 Simulating JobPro Request...');
  
  const jobData = {
          url: `${configManager.getBmadBackendUrl()}/tasks`,
    method: 'POST',
    connection_name: 'jobprtal',
    createdBy: '2025',
    updatedBy: '2025',
    job_type: 'submit_task',
    ref: '1'
  };
  
  console.log('JobPro would send this data:');
  console.log(JSON.stringify(jobData, null, 2));
  
  // Test if we can reach the target URL
  try {
    const response = await fetch(jobData.url, {
      method: jobData.method,
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        prompt: 'test prompt from JobPro simulation',
        workflow_id: null,
        workflow_sequence: null,
        agent_specific_prompts: null
      })
    });
    
    if (response.ok) {
      console.log('✅ Simulated JobPro request would succeed');
      return true;
    } else {
      console.log('⚠️  Simulated JobPro request failed with status:', response.status);
      return false;
    }
  } catch (error) {
    console.log('❌ Simulated JobPro request failed:', error.message);
    return false;
  }
}

// Comprehensive network test
async function runComprehensiveNetworkTest() {
  console.log('🚀 Running Comprehensive Network Connectivity Test...');
  console.log('This will help diagnose the connection refused error\n');
  
  // Test 1: Network configuration
  testNetworkConfiguration();
  
  // Test 2: JobPro accessibility
  const jobProAccessible = await testJobProAccessibility();
  
  // Test 3: BMAD backend accessibility
  const bmadAccessible = await testBmadBackendAccessibility();
  
  // Test 4: Specific endpoint
  const endpointAccessible = await testSpecificEndpoint();
  
  // Test 5: Simulate JobPro request
  const jobProSimulation = await simulateJobProRequest();
  
  // Summary
  console.log('\n📊 Network Test Summary:');
  console.log('- JobPro Server Accessible:', jobProAccessible ? '✅' : '❌');
  console.log('- BMAD Backend Accessible:', bmadAccessible ? '✅' : '❌');
  console.log('- Tasks Endpoint Accessible:', endpointAccessible ? '✅' : '❌');
  console.log('- JobPro Simulation Works:', jobProSimulation ? '✅' : '❌');
  
  // Recommendations
  console.log('\n💡 Recommendations:');
  
  if (!bmadAccessible) {
    console.log('❌ BMAD backend is not accessible. Check:');
    console.log('   - Is BMAD backend running on port 9191?');
    console.log('   - Is the VM IP correct?');
    console.log('   - Are there any firewall rules blocking the connection?');
  }
  
  if (!jobProAccessible) {
    console.log('❌ JobPro server is not accessible. Check:');
    console.log('   - Is JobPro running on port 31170?');
    console.log('   - Is the VM IP correct?');
  }
  
  if (bmadAccessible && !endpointAccessible) {
    console.log('⚠️  BMAD backend is accessible but /tasks endpoint is not. Check:');
    console.log('   - Is the API endpoint correct?');
    console.log('   - Are there any authentication requirements?');
  }
  
  if (jobProAccessible && bmadAccessible && !jobProSimulation) {
    console.log('⚠️  Both servers are accessible but JobPro simulation fails. Check:');
    console.log('   - Network routing between JobPro and BMAD backend');
    console.log('   - Firewall rules between services');
  }
  
  return {
    jobProAccessible,
    bmadAccessible,
    endpointAccessible,
    jobProSimulation
  };
}

// Export test functions
export { 
  testBmadBackendAccessibility, 
  testJobProAccessibility, 
  testSpecificEndpoint, 
  testNetworkConfiguration, 
  simulateJobProRequest, 
  runComprehensiveNetworkTest 
};

// Auto-run tests if in browser console
if (typeof window !== 'undefined') {
  console.log('🚀 Network Connectivity Test Suite Loaded');
  console.log('Run runComprehensiveNetworkTest() to diagnose connection issues');
  console.log('Run testBmadBackendAccessibility() to test BMAD backend access');
  console.log('Run testJobProAccessibility() to test JobPro server access');
  console.log('Run testSpecificEndpoint() to test the /tasks endpoint');
  console.log('Run testNetworkConfiguration() to check network settings');
  console.log('Run simulateJobProRequest() to simulate JobPro\'s request');
  
  // Make functions available globally for console testing
  window.runComprehensiveNetworkTest = runComprehensiveNetworkTest;
  window.testBmadBackendAccessibility = testBmadBackendAccessibility;
  window.testJobProAccessibility = testJobProAccessibility;
  window.testSpecificEndpoint = testSpecificEndpoint;
  window.testNetworkConfiguration = testNetworkConfiguration;
  window.simulateJobProRequest = simulateJobProRequest;
  
  // Auto-run the comprehensive test
  console.log('\n🔄 Auto-running comprehensive network test...');
  setTimeout(() => {
    runComprehensiveNetworkTest();
  }, 500);
}
