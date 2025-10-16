// Test file for JobPro integration
// Run this in the browser console to test JobPro functionality

import jobProService from './services/jobProService.js';

// Test JobPro service
async function testJobProIntegration() {
  console.log('🧪 Testing JobPro Integration...');
  
  try {
    // Test 1: Check JobPro status
    console.log('\n1. Testing JobPro connection...');
    const isConnected = await jobProService.checkJobProStatus();
    console.log('✅ JobPro connected:', isConnected);
    
    // Test 2: Check if JobPro is enabled
    console.log('\n2. Testing JobPro enabled status...');
    const isEnabled = jobProService.isJobProEnabled();
    console.log('✅ JobPro enabled:', isEnabled);
    
    // Test 3: Submit a test task
    console.log('\n3. Testing task submission...');
    const submitResult = await jobProService.submitTask(
      'Test task for JobPro integration',
      'test-workflow-123',
      ['analyst', 'architect'],
      { 'analyst': 'Test analyst prompt' }
    );
    console.log('✅ Task submission result:', submitResult);
    
    // Test 4: Check queued jobs
    console.log('\n4. Testing queued jobs...');
    const queuedJobs = jobProService.getAllQueuedJobs();
    console.log('✅ Queued jobs:', queuedJobs);
    
    // Test 5: Test resume workflow
    console.log('\n5. Testing resume workflow...');
    const resumeResult = await jobProService.resumeWorkflow(
      'test-task-456',
      'Continue with test workflow',
      'test-workflow-789'
    );
    console.log('✅ Resume workflow result:', resumeResult);
    
    // Test 6: Test rerun workflow
    console.log('\n6. Testing rerun workflow...');
    const rerunResult = await jobProService.rerunWorkflow(
      'test-task-456',
      'Rerun with modifications',
      'test-workflow-789'
    );
    console.log('✅ Rerun workflow result:', rerunResult);
    
    // Test 7: Check updated job count
    console.log('\n7. Checking updated job count...');
    const updatedJobs = jobProService.getAllQueuedJobs();
    console.log('✅ Updated queued jobs:', updatedJobs);
    
    // Test 8: Test JobPro disable/enable
    console.log('\n8. Testing JobPro disable/enable...');
    jobProService.setEnabled(false);
    console.log('✅ JobPro disabled:', !jobProService.isJobProEnabled());
    
    jobProService.setEnabled(true);
    console.log('✅ JobPro re-enabled:', jobProService.isJobProEnabled());
    
    // Test 9: Test custom backend URL
    console.log('\n9. Testing custom backend URL...');
    jobProService.setBmadBackendUrl('http://custom-server:9191/api');
    console.log('✅ Custom backend URL set');
    
    // Test 10: Cleanup test jobs
    console.log('\n10. Cleaning up test jobs...');
    jobProService.clearAllJobs();
    const finalJobs = jobProService.getAllQueuedJobs();
    console.log('✅ Final job count:', finalJobs.length);
    
    console.log('\n🎉 All JobPro integration tests completed successfully!');
    
  } catch (error) {
    console.error('❌ JobPro integration test failed:', error);
  }
}

// Test individual functions
function testJobProService() {
  console.log('🔧 Testing JobPro Service Methods...');
  
  // Test reference generation
  const ref1 = jobProService.generateRef();
  const ref2 = jobProService.generateRef();
  console.log('✅ Generated refs:', ref1, ref2);
  
  // Test timestamp generation
  const timestamp = jobProService.getCurrentTimestamp();
  console.log('✅ Current timestamp:', timestamp);
  
  // Test job status management
  const testRef = 'test-ref-123';
  jobProService.updateJobStatus(testRef, 'processing', { step: 'testing' });
  const status = jobProService.getJobStatus(testRef);
  console.log('✅ Job status updated:', status);
  
  // Test cleanup
  jobProService.cleanupCompletedJob(testRef);
  const cleanedStatus = jobProService.getJobStatus(testRef);
  console.log('✅ Job cleaned up:', cleanedStatus);
}

// Export test functions
export { testJobProIntegration, testJobProService };

// Auto-run tests if in browser console
if (typeof window !== 'undefined') {
  console.log('🚀 JobPro Integration Test Suite Loaded');
  console.log('Run testJobProIntegration() to test the full integration');
  console.log('Run testJobProService() to test individual service methods');
  
  // Make functions available globally for console testing
  window.testJobProIntegration = testJobProIntegration;
  window.testJobProService = testJobProService;
}
