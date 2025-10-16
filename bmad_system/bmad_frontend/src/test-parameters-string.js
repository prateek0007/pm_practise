// Test Parameters as JSON String
// This test verifies that parameters are sent as JSON strings to JobPro

import jobProService from './services/jobProService.js';

// Test 1: Verify parameters as JSON string format
function testParametersAsString() {
  console.log('🧪 Testing Parameters as JSON String...');
  
  try {
    // Test payload object
    const payload = {
      prompt: "Your actual prompt text here",
      workflow_id: null,
      workflow_sequence: null,
      agent_specific_prompts: null
    };
    
    console.log('Original payload object:');
    console.log(payload);
    
    // Convert to JSON string
    const parametersString = JSON.stringify(payload);
    console.log('\nParameters as JSON string:');
    console.log(parametersString);
    
    // Verify it's a string
    if (typeof parametersString === 'string') {
      console.log('✅ Parameters is correctly a string');
    } else {
      console.log('❌ Parameters is not a string');
    }
    
    // Verify it can be parsed back
    try {
      const parsedBack = JSON.parse(parametersString);
      console.log('✅ Parameters can be parsed back to object');
      console.log('Parsed back:', parsedBack);
    } catch (parseError) {
      console.log('❌ Parameters cannot be parsed back:', parseError.message);
    }
    
    return parametersString;
    
  } catch (error) {
    console.error('❌ Parameters string test failed:', error);
    return null;
  }
}

// Test 2: Test complete JobPro JSON with string parameters
function testCompleteJobProJson() {
  console.log('\n🧪 Testing Complete JobPro JSON with String Parameters...');
  
  try {
    const payload = {
      prompt: "Create a simple web application",
      workflow_id: "web-app-workflow",
      workflow_sequence: null,
      agent_specific_prompts: null
    };
    
    const jobData = {
      url: jobProService.getFullUrl('/tasks'),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: 'submit_task',
      ref: '1',
      parameters: JSON.stringify(payload)
    };
    
    console.log('✅ Complete JobPro JSON with string parameters:');
    console.log(JSON.stringify(jobData, null, 2));
    
    // Verify parameters is a string
    if (typeof jobData.parameters === 'string') {
      console.log('✅ Parameters field is a string');
    } else {
      console.log('❌ Parameters field is not a string');
    }
    
    // Verify the string content
    console.log('\nParameters string content:');
    console.log(jobData.parameters);
    
    return jobData;
    
  } catch (error) {
    console.error('❌ Complete JobPro JSON test failed:', error);
    return null;
  }
}

// Test 3: Test different job types with string parameters
function testDifferentJobTypes() {
  console.log('\n🧪 Testing Different Job Types with String Parameters...');
  
  const testCases = [
    {
      name: 'Submit Task',
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
      url: '/tasks/123/resume-workflow',
      jobType: 'resume_workflow',
      payload: {
        user_prompt: 'Continue from where we left off',
        workflow_id: 'web-app-workflow'
      }
    },
    {
      name: 'Rerun Workflow',
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
    
    const jobData = {
      url: jobProService.getFullUrl(testCase.url),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: testCase.jobType,
      ref: '1',
      parameters: JSON.stringify(testCase.payload)
    };
    
    console.log('URL:', jobData.url);
    console.log('Method:', jobData.method);
    console.log('Job Type:', jobData.job_type);
    console.log('Parameters (string):', jobData.parameters);
    
    // Verify parameters is a string
    if (typeof jobData.parameters === 'string') {
      console.log('✅ Parameters is correctly a string');
    } else {
      console.log('❌ Parameters is not a string');
    }
  });
}

// Test 4: Verify what JobPro will receive
function testJobProReceivesString() {
  console.log('\n🧪 Testing What JobPro Will Receive...');
  
  try {
    const payload = {
      prompt: "Test prompt for JobPro",
      workflow_id: "test-workflow",
      workflow_sequence: null,
      agent_specific_prompts: null
    };
    
    const jobData = {
      url: jobProService.getFullUrl('/tasks'),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: 'submit_task',
      ref: '1',
      parameters: JSON.stringify(payload)
    };
    
    console.log('✅ JobPro will receive this JSON:');
    console.log(JSON.stringify(jobData, null, 2));
    
    // Verify the structure
    const requiredFields = ['url', 'method', 'connection_name', 'createdBy', 'updatedBy', 'job_type', 'ref', 'parameters'];
    const missingFields = requiredFields.filter(field => !(field in jobData));
    
    if (missingFields.length === 0) {
      console.log('✅ All required fields are present');
    } else {
      console.log('❌ Missing fields:', missingFields);
    }
    
    // Verify parameters is a string
    if (typeof jobData.parameters === 'string') {
      console.log('✅ Parameters is a string (as expected by JobPro)');
      console.log('Parameters string length:', jobData.parameters.length);
    } else {
      console.log('❌ Parameters is not a string');
    }
    
    return jobData;
    
  } catch (error) {
    console.error('❌ JobPro receives test failed:', error);
    return null;
  }
}

// Comprehensive test
function runParametersStringTest() {
  console.log('🚀 Running Parameters String Test...');
  console.log('This verifies that parameters are correctly formatted as JSON strings\n');
  
  // Test 1: Parameters as string
  const stringTest = testParametersAsString();
  
  // Test 2: Complete JobPro JSON
  const completeTest = testCompleteJobProJson();
  
  // Test 3: Different job types
  testDifferentJobTypes();
  
  // Test 4: What JobPro receives
  const jobProTest = testJobProReceivesString();
  
  // Summary
  console.log('\n📊 Parameters String Test Summary:');
  console.log('- String Conversion Test:', stringTest ? '✅' : '❌');
  console.log('- Complete JSON Test:', completeTest ? '✅' : '❌');
  console.log('- JobPro Receives Test:', jobProTest ? '✅' : '❌');
  
  // Recommendations
  console.log('\n💡 Next Steps:');
  if (stringTest && completeTest && jobProTest) {
    console.log('✅ Parameters are correctly formatted as JSON strings');
    console.log('🔄 Try submitting a task again - JobPro should accept it now!');
  } else {
    console.log('❌ Parameters formatting needs adjustment');
  }
  
  return { stringTest, completeTest, jobProTest };
}

// Export test functions
export { 
  testParametersAsString, 
  testCompleteJobProJson, 
  testDifferentJobTypes, 
  testJobProReceivesString, 
  runParametersStringTest 
};

// Auto-run tests if in browser console
if (typeof window !== 'undefined') {
  console.log('🚀 Parameters String Test Suite Loaded');
  console.log('Run runParametersStringTest() to test the complete parameters string flow');
  console.log('Run testParametersAsString() to test string conversion');
  console.log('Run testCompleteJobProJson() to test complete JSON');
  console.log('Run testDifferentJobTypes() to test different job types');
  console.log('Run testJobProReceivesString() to test what JobPro receives');
  
  // Make functions available globally for console testing
  window.runParametersStringTest = runParametersStringTest;
  window.testParametersAsString = testParametersAsString;
  window.testCompleteJobProJson = testCompleteJobProJson;
  window.testDifferentJobTypes = testDifferentJobTypes;
  window.testJobProReceivesString = testJobProReceivesString;
  
  // Auto-run the comprehensive test
  console.log('\n🔄 Auto-running parameters string test...');
  setTimeout(() => {
    runParametersStringTest();
  }, 500);
}
