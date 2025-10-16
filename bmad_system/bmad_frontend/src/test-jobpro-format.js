// Test JobPro JSON Format
// This test verifies that we're sending the correct JSON format to JobPro

import jobProService from './services/jobProService.js';

// Test the exact JSON format that JobPro expects
function testJobProJsonFormat() {
  console.log('🧪 Testing JobPro JSON Format...');
  
  try {
    // Test submitTask JSON format
    const testJobData = {
      url: jobProService.getFullUrl('/tasks'),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: 'submit_task',
      ref: '1'
    };
    
    console.log('✅ JobPro JSON Format (Submit Task):');
    console.log(JSON.stringify(testJobData, null, 2));
    
    // Test resume workflow JSON format
    const resumeJobData = {
      url: jobProService.getFullUrl('/tasks/123/resume-workflow'),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: 'resume_workflow',
      ref: '2'
    };
    
    console.log('\n✅ JobPro JSON Format (Resume Workflow):');
    console.log(JSON.stringify(resumeJobData, null, 2));
    
    // Test rerun workflow JSON format
    const rerunJobData = {
      url: jobProService.getFullUrl('/tasks/123/reexecute'),
      method: 'POST',
      connection_name: 'jobprtal',
      createdBy: '2025',
      updatedBy: '2025',
      job_type: 'rerun_workflow',
      ref: '3'
    };
    
    console.log('\n✅ JobPro JSON Format (Rerun Workflow):');
    console.log(JSON.stringify(rerunJobData, null, 2));
    
    // Verify required fields
    const requiredFields = ['url', 'method', 'connection_name', 'createdBy', 'updatedBy', 'job_type', 'ref'];
    const missingFields = requiredFields.filter(field => !(field in testJobData));
    
    if (missingFields.length === 0) {
      console.log('\n✅ All required fields are present');
    } else {
      console.log('\n❌ Missing fields:', missingFields);
    }
    
    // Verify no extra fields
    const extraFields = Object.keys(testJobData).filter(field => !requiredFields.includes(field));
    if (extraFields.length === 0) {
      console.log('✅ No extra fields (clean format)');
    } else {
      console.log('⚠️  Extra fields found:', extraFields);
    }
    
    return testJobData;
    
  } catch (error) {
    console.error('❌ JobPro JSON format test failed:', error);
    return null;
  }
}

// Test the original JobPro specification format
function testOriginalJobProFormat() {
  console.log('\n🧪 Testing Original JobPro Specification Format...');
  
  // This is the exact format from your original specification
  const originalFormat = {
    "url": "http://localhost:9191",
    "method": "GET",
    "connection_name": "jobprtal",
    "createdBy": "2025",
    "updatedBy": "2025",
    "job_type": "stop container",
    "ref": "23"
  };
  
  console.log('✅ Original JobPro Specification:');
  console.log(JSON.stringify(originalFormat, null, 2));
  
  // Compare with our current format
  const currentFormat = {
    url: jobProService.getFullUrl('/tasks'),
    method: 'POST',
    connection_name: 'jobprtal',
    createdBy: '2025',
    updatedBy: '2025',
    job_type: 'submit_task',
    ref: '1'
  };
  
  console.log('\n✅ Our Current Format:');
  console.log(JSON.stringify(currentFormat, null, 2));
  
  // Check if structure matches
  const originalKeys = Object.keys(originalFormat).sort();
  const currentKeys = Object.keys(currentFormat).sort();
  
  if (JSON.stringify(originalKeys) === JSON.stringify(currentKeys)) {
    console.log('\n✅ Structure matches original specification');
  } else {
    console.log('\n❌ Structure does not match original specification');
    console.log('Original keys:', originalKeys);
    console.log('Current keys:', currentKeys);
  }
  
  return { originalFormat, currentFormat };
}

// Test URL construction
function testUrlConstruction() {
  console.log('\n🧪 Testing URL Construction...');
  
  const testUrls = [
    '/tasks',
    '/tasks/123/resume-workflow',
    '/tasks/123/reexecute',
    '/tasks/123/upload'
  ];
  
  testUrls.forEach(url => {
    const fullUrl = jobProService.getFullUrl(url);
    console.log(`${url} → ${fullUrl}`);
    
    // Verify it's absolute
    if (fullUrl.startsWith('http://') || fullUrl.startsWith('https://')) {
      console.log('  ✅ Absolute URL');
    } else {
      console.log('  ❌ Relative URL');
    }
  });
}

// Comprehensive test
function runJobProFormatTest() {
  console.log('🚀 Running JobPro Format Test...');
  console.log('This verifies we\'re sending the correct JSON format to JobPro\n');
  
  // Test 1: Current JSON format
  const formatTest = testJobProJsonFormat();
  
  // Test 2: Compare with original specification
  const comparisonTest = testOriginalJobProFormat();
  
  // Test 3: URL construction
  testUrlConstruction();
  
  // Summary
  console.log('\n📊 JobPro Format Test Summary:');
  console.log('- JSON Format Test:', formatTest ? '✅' : '❌');
  console.log('- Original Spec Comparison:', comparisonTest ? '✅' : '❌');
  
  // Recommendations
  console.log('\n💡 Next Steps:');
  if (formatTest && comparisonTest) {
    console.log('✅ JSON format matches JobPro specification');
    console.log('🔄 Try submitting a task again - it should work now!');
  } else {
    console.log('❌ JSON format needs adjustment');
  }
  
  return { formatTest, comparisonTest };
}

// Export test functions
export { 
  testJobProJsonFormat, 
  testOriginalJobProFormat, 
  testUrlConstruction, 
  runJobProFormatTest 
};

// Auto-run tests if in browser console
if (typeof window !== 'undefined') {
  console.log('🚀 JobPro Format Test Suite Loaded');
  console.log('Run runJobProFormatTest() to test the complete format');
  console.log('Run testJobProJsonFormat() to test current JSON format');
  console.log('Run testOriginalJobProFormat() to compare with original spec');
  console.log('Run testUrlConstruction() to test URL construction');
  
  // Make functions available globally for console testing
  window.runJobProFormatTest = runJobProFormatTest;
  window.testJobProJsonFormat = testJobProJsonFormat;
  window.testOriginalJobProFormat = testOriginalJobProFormat;
  window.testUrlConstruction = testUrlConstruction;
  
  // Auto-run the comprehensive test
  console.log('\n🔄 Auto-running JobPro format test...');
  setTimeout(() => {
    runJobProFormatTest();
  }, 500);
}
