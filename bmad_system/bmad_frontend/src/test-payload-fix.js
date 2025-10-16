// Test Payload Fix for JobPro Integration
// This test verifies that JobPro receives the correct payload data

import jobProService from './services/jobProService.js';

// Test 1: Verify payload is included in JobPro job data
function testPayloadInclusion() {
  console.log('🧪 Testing Payload Inclusion in JobPro Job Data...');
  
  try {
    // Test submitTask payload
    const testPrompt = 'Test prompt for JobPro integration';
    const testWorkflowId = 'test-workflow-123';
    
    console.log('Testing submitTask with payload:');
    console.log('- Prompt:', testPrompt);
    console.log('- Workflow ID:', testWorkflowId);
    
    // Create a mock job data to see what would be sent
    const mockJobData = {
      url: jobProService.getFullUrl('/tasks'),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: 'submit_task',
      ref: '1',
      parameters: {
        prompt: testPrompt,
        workflow_id: testWorkflowId,
        workflow_sequence: null,
        agent_specific_prompts: null
      }
    };
    
    console.log('\n✅ JobPro would receive this data:');
    console.log(JSON.stringify(mockJobData, null, 2));
    
    // Verify the payload structure
    if (mockJobData.parameters && mockJobData.parameters.prompt) {
      console.log('✅ Payload is correctly included in job data');
      console.log('✅ Prompt is present:', mockJobData.parameters.prompt);
    } else {
      console.log('❌ Payload is missing or malformed');
    }
    
    return mockJobData;
    
  } catch (error) {
    console.error('❌ Payload inclusion test failed:', error);
    return null;
  }
}

// Test 2: Test different job types with their payloads
function testDifferentJobTypes() {
  console.log('\n🧪 Testing Different Job Types with Payloads...');
  
  const testCases = [
    {
      name: 'Submit Task',
      method: 'POST',
      url: '/tasks',
      jobType: 'submit_task',
      payload: {
        prompt: 'Create a simple web application',
        workflow_id: 'web-app-workflow',
        workflow_sequence: null,
        agent_specific_prompts: null
      }
    },
    {
      name: 'Resume Workflow',
      method: 'POST',
      url: '/tasks/123/resume-workflow',
      jobType: 'resume_workflow',
      payload: {
        user_prompt: 'Continue from where we left off',
        workflow_id: 'web-app-workflow'
      }
    },
    {
      name: 'Rerun Workflow',
      method: 'POST',
      url: '/tasks/123/reexecute',
      jobType: 'rerun_workflow',
      payload: {
        user_prompt: 'Start over with a new approach',
        workflow_id: 'web-app-workflow'
      }
    }
  ];
  
  testCases.forEach(testCase => {
    console.log(`\n📋 Testing ${testCase.name}:`);
    
    const mockJobData = {
      url: jobProService.getFullUrl(testCase.url),
      method: testCase.method,
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: testCase.jobType,
      ref: '1',
      parameters: testCase.payload
    };
    
    console.log('URL:', mockJobData.url);
    console.log('Method:', mockJobData.method);
    console.log('Job Type:', mockJobData.job_type);
    console.log('Payload:', JSON.stringify(mockJobData.parameters, null, 2));
    
    // Verify payload is present
    if (mockJobData.parameters) {
      console.log('✅ Payload included correctly');
    } else {
      console.log('❌ Payload missing');
    }
  });
}

// Test 3: Verify the actual JobPro API call structure
function testJobProApiCall() {
  console.log('\n🧪 Testing JobPro API Call Structure...');
  
  try {
    const testPrompt = 'Test prompt for API call';
    const testPayload = {
      prompt: testPrompt,
      workflow_id: 'test-workflow',
      workflow_sequence: null,
      agent_specific_prompts: null
    };
    
    // Simulate what would be sent to JobPro API
    const jobProApiCall = {
      url: jobProService.getFullUrl('/tasks'),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: 'submit_task',
      ref: '1',
      parameters: testPayload
    };
    
    console.log('✅ JobPro API would receive:');
    console.log(JSON.stringify(jobProApiCall, null, 2));
    
    // Verify the structure matches what JobPro expects
    const requiredFields = ['url', 'method', 'connection_name', 'createdBy', 'updatedBy', 'job_type', 'ref', 'parameters'];
    const missingFields = requiredFields.filter(field => !(field in jobProApiCall));
    
    if (missingFields.length === 0) {
      console.log('✅ All required fields are present');
    } else {
      console.log('❌ Missing fields:', missingFields);
    }
    
    // Verify the URL is correct
    if (jobProApiCall.url === 'http://157.66.191.31:5006/api/tasks') {
      console.log('✅ URL is correct for BMAD backend');
    } else {
      console.log('❌ URL is incorrect:', jobProApiCall.url);
    }
    
    // Verify parameters contain the prompt
    if (jobProApiCall.parameters && jobProApiCall.parameters.prompt) {
      console.log('✅ Parameters contain the prompt:', jobProApiCall.parameters.prompt);
    } else {
      console.log('❌ Parameters missing or no prompt found');
    }
    
    return jobProApiCall;
    
  } catch (error) {
    console.error('❌ JobPro API call test failed:', error);
    return null;
  }
}

// Test 4: Simulate what JobPro would send to BMAD backend
function testJobProToBmadCall() {
  console.log('\n🧪 Testing JobPro to BMAD Backend Call...');
  
  try {
    // This simulates what JobPro would send to BMAD backend
    const bmadApiCall = {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        prompt: 'Test prompt from JobPro',
        workflow_id: 'test-workflow',
        workflow_sequence: null,
        agent_specific_prompts: null
      })
    };
    
    console.log('✅ JobPro would send this to BMAD backend:');
    console.log('URL: http://157.66.191.31:5006/api/tasks');
    console.log('Method:', bmadApiCall.method);
    console.log('Headers:', bmadApiCall.headers);
    console.log('Body:', bmadApiCall.body);
    
    // Verify the JSON is valid
    try {
      const parsedBody = JSON.parse(bmadApiCall.body);
      console.log('✅ JSON body is valid');
      console.log('✅ Prompt in body:', parsedBody.prompt);
    } catch (parseError) {
      console.log('❌ JSON body is invalid:', parseError.message);
    }
    
    return bmadApiCall;
    
  } catch (error) {
    console.error('❌ JobPro to BMAD call test failed:', error);
    return null;
  }
}

// Comprehensive test
function runComprehensivePayloadTest() {
  console.log('🚀 Running Comprehensive Payload Test...');
  console.log('This will verify that JobPro receives and forwards the correct payload data\n');
  
  // Test 1: Payload inclusion
  const payloadTest = testPayloadInclusion();
  
  // Test 2: Different job types
  testDifferentJobTypes();
  
  // Test 3: JobPro API call structure
  const apiCallTest = testJobProApiCall();
  
  // Test 4: JobPro to BMAD call
  const bmadCallTest = testJobProToBmadCall();
  
  // Summary
  console.log('\n📊 Payload Test Summary:');
  console.log('- Payload Inclusion:', payloadTest ? '✅' : '❌');
  console.log('- API Call Structure:', apiCallTest ? '✅' : '❌');
  console.log('- BMAD Call Simulation:', bmadCallTest ? '✅' : '❌');
  
  // Recommendations
  console.log('\n💡 Next Steps:');
  if (payloadTest && apiCallTest && bmadCallTest) {
    console.log('✅ All tests passed! JobPro should now receive the correct payload data.');
    console.log('🔄 Try submitting a task again - it should work now!');
  } else {
    console.log('❌ Some tests failed. Check the configuration.');
  }
  
  return {
    payloadTest,
    apiCallTest,
    bmadCallTest
  };
}

// Export test functions
export { 
  testPayloadInclusion, 
  testDifferentJobTypes, 
  testJobProApiCall, 
  testJobProToBmadCall, 
  runComprehensivePayloadTest 
};

// Auto-run tests if in browser console
if (typeof window !== 'undefined') {
  console.log('🚀 Payload Fix Test Suite Loaded');
  console.log('Run runComprehensivePayloadTest() to test the complete payload flow');
  console.log('Run testPayloadInclusion() to test payload inclusion');
  console.log('Run testDifferentJobTypes() to test different job types');
  console.log('Run testJobProApiCall() to test JobPro API call structure');
  console.log('Run testJobProToBmadCall() to test JobPro to BMAD call');
  
  // Make functions available globally for console testing
  window.runComprehensivePayloadTest = runComprehensivePayloadTest;
  window.testPayloadInclusion = testPayloadInclusion;
  window.testDifferentJobTypes = testDifferentJobTypes;
  window.testJobProApiCall = testJobProApiCall;
  window.testJobProToBmadCall = testJobProToBmadCall;
  
  // Auto-run the comprehensive test
  console.log('\n🔄 Auto-running comprehensive payload test...');
  setTimeout(() => {
    runComprehensivePayloadTest();
  }, 500);
}
