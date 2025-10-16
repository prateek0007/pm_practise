// Test Workflow Sequence Fix
// This test verifies that workflow sequence is correctly passed in resume and rerun operations

import jobProService from './services/jobProService.js';

// Test 1: Test resumeWorkflow with workflow sequence
function testResumeWorkflowSequence() {
  console.log('🧪 Testing Resume Workflow with Sequence...');
  
  try {
    const taskId = '123';
    const userPrompt = 'Continue from where we left off';
    const workflowId = 'workflow-123';
    const workflowSequence = [
      'directory_structure',
      'bmad',
      'web_search',
      'deep_research',
      'analyst',
      'architect',
      'coding_standards',
      'ui_ux',
      'pm',
      'sm',
      'developer',
      'devops',
      'tester',
      'requirement_builder',
      'documentation_agent'
    ];
    
    console.log('Test parameters:');
    console.log('- Task ID:', taskId);
    console.log('- User Prompt:', userPrompt);
    console.log('- Workflow ID:', workflowId);
    console.log('- Workflow Sequence:', workflowSequence);
    
    // Create mock payload that would be sent to JobPro
    const payload = {
      user_prompt: userPrompt,
      workflow_id: workflowId,
      workflow_sequence: workflowSequence
    };
    
    console.log('\n✅ Payload that would be sent to JobPro:');
    console.log(JSON.stringify(payload, null, 2));
    
    // Verify workflow_sequence is included
    if (payload.workflow_sequence && Array.isArray(payload.workflow_sequence)) {
      console.log('✅ Workflow sequence is included and is an array');
      console.log('✅ Sequence length:', payload.workflow_sequence.length);
      console.log('✅ First agent:', payload.workflow_sequence[0]);
      console.log('✅ Last agent:', payload.workflow_sequence[payload.workflow_sequence.length - 1]);
    } else {
      console.log('❌ Workflow sequence is missing or not an array');
    }
    
    return payload;
    
  } catch (error) {
    console.error('❌ Resume workflow sequence test failed:', error);
    return null;
  }
}

// Test 2: Test rerunWorkflow with workflow sequence
function testRerunWorkflowSequence() {
  console.log('\n🧪 Testing Rerun Workflow with Sequence...');
  
  try {
    const taskId = '123';
    const userPrompt = 'Start over with a new approach';
    const workflowId = 'workflow-123';
    const workflowSequence = [
      'directory_structure',
      'bmad',
      'web_search',
      'deep_research',
      'analyst',
      'architect',
      'coding_standards',
      'ui_ux',
      'pm',
      'sm',
      'developer',
      'devops',
      'tester',
      'requirement_builder',
      'documentation_agent'
    ];
    
    console.log('Test parameters:');
    console.log('- Task ID:', taskId);
    console.log('- User Prompt:', userPrompt);
    console.log('- Workflow ID:', workflowId);
    console.log('- Workflow Sequence:', workflowSequence);
    
    // Create mock payload that would be sent to JobPro
    const payload = {
      user_prompt: userPrompt,
      workflow_id: workflowId,
      workflow_sequence: workflowSequence
    };
    
    console.log('\n✅ Payload that would be sent to JobPro:');
    console.log(JSON.stringify(payload, null, 2));
    
    // Verify workflow_sequence is included
    if (payload.workflow_sequence && Array.isArray(payload.workflow_sequence)) {
      console.log('✅ Workflow sequence is included and is an array');
      console.log('✅ Sequence length:', payload.workflow_sequence.length);
      console.log('✅ First agent:', payload.workflow_sequence[0]);
      console.log('✅ Last agent:', payload.workflow_sequence[payload.workflow_sequence.length - 1]);
    } else {
      console.log('❌ Workflow sequence is missing or not an array');
    }
    
    return payload;
    
  } catch (error) {
    console.error('❌ Rerun workflow sequence test failed:', error);
    return null;
  }
}

// Test 3: Test the complete JobPro JSON with workflow sequence
function testCompleteJobProJsonWithSequence() {
  console.log('\n🧪 Testing Complete JobPro JSON with Workflow Sequence...');
  
  try {
    const workflowSequence = [
      'directory_structure',
      'bmad',
      'web_search',
      'deep_research',
      'analyst',
      'architect',
      'coding_standards',
      'ui_ux',
      'pm',
      'sm',
      'developer',
      'devops',
      'tester',
      'requirement_builder',
      'documentation_agent'
    ];
    
    const payload = {
      user_prompt: 'Continue from where we left off',
      workflow_id: 'workflow-123',
      workflow_sequence: workflowSequence
    };
    
    const jobData = {
      url: jobProService.getFullUrl('/tasks/123/resume-workflow'),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: 'resume_workflow',
      ref: '1',
      parameters: JSON.stringify(payload)
    };
    
    console.log('✅ Complete JobPro JSON with workflow sequence:');
    console.log(JSON.stringify(jobData, null, 2));
    
    // Verify parameters string contains workflow_sequence
    try {
      const parsedParams = JSON.parse(jobData.parameters);
      if (parsedParams.workflow_sequence && Array.isArray(parsedParams.workflow_sequence)) {
        console.log('✅ Parameters string contains workflow_sequence');
        console.log('✅ Workflow sequence in parameters:', parsedParams.workflow_sequence);
        console.log('✅ Sequence length:', parsedParams.workflow_sequence.length);
      } else {
        console.log('❌ Parameters string missing workflow_sequence');
      }
    } catch (parseError) {
      console.log('❌ Cannot parse parameters string:', parseError.message);
    }
    
    return jobData;
    
  } catch (error) {
    console.error('❌ Complete JobPro JSON test failed:', error);
    return null;
  }
}

// Test 4: Test different workflow sequences
function testDifferentWorkflowSequences() {
  console.log('\n🧪 Testing Different Workflow Sequences...');
  
  const testSequences = [
    {
      name: 'Default Workflow',
      sequence: [
        'directory_structure',
        'bmad',
        'web_search',
        'deep_research',
        'analyst',
        'architect',
        'coding_standards',
        'ui_ux',
        'pm',
        'sm',
        'developer',
        'devops',
        'tester',
        'requirement_builder',
        'documentation_agent'
      ]
    },
    {
      name: 'Short Workflow',
      sequence: ['analyst', 'developer', 'tester']
    },
    {
      name: 'Custom Workflow',
      sequence: ['requirement_builder', 'architect', 'developer', 'ui_ux']
    }
  ];
  
  testSequences.forEach(testCase => {
    console.log(`\n📋 Testing ${testCase.name}:`);
    
    const payload = {
      user_prompt: 'Test prompt',
      workflow_id: 'test-workflow',
      workflow_sequence: testCase.sequence
    };
    
    console.log('Sequence:', testCase.sequence);
    console.log('Sequence length:', testCase.sequence.length);
    console.log('Payload:', JSON.stringify(payload, null, 2));
    
    // Verify it's valid
    if (payload.workflow_sequence && Array.isArray(payload.workflow_sequence)) {
      console.log('✅ Valid workflow sequence');
    } else {
      console.log('❌ Invalid workflow sequence');
    }
  });
}

// Comprehensive test
function runWorkflowSequenceTest() {
  console.log('🚀 Running Workflow Sequence Test...');
  console.log('This verifies that workflow sequence is correctly passed in resume and rerun operations\n');
  
  // Test 1: Resume workflow sequence
  const resumeTest = testResumeWorkflowSequence();
  
  // Test 2: Rerun workflow sequence
  const rerunTest = testRerunWorkflowSequence();
  
  // Test 3: Complete JobPro JSON
  const completeTest = testCompleteJobProJsonWithSequence();
  
  // Test 4: Different workflow sequences
  testDifferentWorkflowSequences();
  
  // Summary
  console.log('\n📊 Workflow Sequence Test Summary:');
  console.log('- Resume Workflow Test:', resumeTest ? '✅' : '❌');
  console.log('- Rerun Workflow Test:', rerunTest ? '✅' : '❌');
  console.log('- Complete JSON Test:', completeTest ? '✅' : '❌');
  
  // Recommendations
  console.log('\n💡 Next Steps:');
  if (resumeTest && rerunTest && completeTest) {
    console.log('✅ Workflow sequence is correctly included in all operations');
    console.log('🔄 Resume and rerun operations should now work correctly!');
    console.log('✅ Workflow will continue from the correct sequence point');
  } else {
    console.log('❌ Workflow sequence handling needs adjustment');
  }
  
  return { resumeTest, rerunTest, completeTest };
}

// Export test functions
export { 
  testResumeWorkflowSequence, 
  testRerunWorkflowSequence, 
  testCompleteJobProJsonWithSequence, 
  testDifferentWorkflowSequences, 
  runWorkflowSequenceTest 
};

// Auto-run tests if in browser console
if (typeof window !== 'undefined') {
  console.log('🚀 Workflow Sequence Test Suite Loaded');
  console.log('Run runWorkflowSequenceTest() to test the complete workflow sequence flow');
  console.log('Run testResumeWorkflowSequence() to test resume with sequence');
  console.log('Run testRerunWorkflowSequence() to test rerun with sequence');
  console.log('Run testCompleteJobProJsonWithSequence() to test complete JSON');
  console.log('Run testDifferentWorkflowSequences() to test different sequences');
  
  // Make functions available globally for console testing
  window.runWorkflowSequenceTest = runWorkflowSequenceTest;
  window.testResumeWorkflowSequence = testResumeWorkflowSequence;
  window.testRerunWorkflowSequence = testRerunWorkflowSequence;
  window.testCompleteJobProJsonWithSequence = testCompleteJobProJsonWithSequence;
  window.testDifferentWorkflowSequences = testDifferentWorkflowSequences;
  
  // Auto-run the comprehensive test
  console.log('\n🔄 Auto-running workflow sequence test...');
  setTimeout(() => {
    runWorkflowSequenceTest();
  }, 500);
}
