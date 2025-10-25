// JobPro Service for BMAD System
// This service intercepts API calls and sends them to JobPro queue system

import JOBPRO_CONFIG from '../config/jobProConfig.js';

class JobProService {
  constructor() {
    this.jobCounter = 1;
    this.bmadBackendUrl = JOBPRO_CONFIG.BMAD_BACKEND_URL;
    this.isEnabled = true; // Can be toggled on/off
    this._lastConfigCheck = 0;
    this._configCheckInterval = 30000; // Check config every 30 seconds
    this._configCheckTimer = null; // Store interval reference
    
    // Validate the backend URL on initialization
    this.validateBackendUrl();
    
    // Don't start automatic config checking - only check when explicitly needed
    // this._startConfigCheck();
  }

  // Start periodic configuration check
  _startConfigCheck() {
    // Clear any existing timer
    if (this._configCheckTimer) {
      clearInterval(this._configCheckTimer);
    }
    
    this._configCheckTimer = setInterval(() => {
      const now = Date.now();
      if (now - this._lastConfigCheck > this._configCheckInterval) {
        this._lastConfigCheck = now;
        this._checkConfigurationChange();
      }
    }, 5000); // Check every 5 seconds
  }
  
  // Stop periodic configuration check
  _stopConfigCheck() {
    if (this._configCheckTimer) {
      clearInterval(this._configCheckTimer);
      this._configCheckTimer = null;
    }
  }

  // Check if configuration has changed
  _checkConfigurationChange() {
    const currentBackendUrl = JOBPRO_CONFIG.BMAD_BACKEND_URL;
    if (currentBackendUrl !== this.bmadBackendUrl) {
      console.log('🔄 JobPro: Configuration change detected, updating backend URL');
      this.bmadBackendUrl = currentBackendUrl;
      this._validationAttempted = false; // Reset validation state
      this.validateBackendUrl();
    }
  }

  // Enable/disable JobPro integration
  setEnabled(enabled) {
    this.isEnabled = enabled;
    console.log(`JobPro integration ${enabled ? 'enabled' : 'disabled'}`);
  }

  // Check if JobPro is enabled
  isJobProEnabled() {
    return this.isEnabled;
  }

  // Set the BMAD backend URL (can be configured)
  setBmadBackendUrl(url) {
    this.bmadBackendUrl = url;
    this._validationAttempted = false; // Reset validation state
    console.log(`BMAD backend URL set to: ${url}`);
    this.validateBackendUrl();
  }

  // Refresh the backend URL from configuration
  refreshBackendUrl() {
    this.bmadBackendUrl = JOBPRO_CONFIG.BMAD_BACKEND_URL;
    this._validationAttempted = false; // Reset validation state
    console.log(`BMAD backend URL refreshed from config: ${this.bmadBackendUrl}`);
    this.validateBackendUrl();
    return this.bmadBackendUrl;
  }

  // Force refresh all configuration from environment
  forceRefreshConfiguration() {
    console.log('🔄 Force refreshing JobPro configuration...');
    
    // Use synchronous refresh instead of dynamic import to avoid async issues
    this.refreshBackendUrl();
    
    // Also refresh from the current config
    this.bmadBackendUrl = JOBPRO_CONFIG.BMAD_BACKEND_URL;
    console.log('✅ Configuration refreshed:', {
      bmadBackendUrl: this.bmadBackendUrl,
      jobProApiUrl: JOBPRO_CONFIG.API_URL,
      connectionName: JOBPRO_CONFIG.CONNECTION_NAME
    });
    
    // Validate the configuration
    this.validateBackendUrl();
  }

  // Get current backend URL
  getCurrentBackendUrl() {
    return this.bmadBackendUrl;
  }

  // Debug method to show current configuration
  debugConfiguration() {
    console.log('🔍 JobPro Service Configuration Debug:');
    console.log('Enabled:', this.isEnabled);
    console.log('BMAD Backend URL:', this.bmadBackendUrl);
    console.log('JobPro API URL:', JOBPRO_CONFIG.API_URL);
    console.log('Connection Name:', JOBPRO_CONFIG.CONNECTION_NAME);
    
    // Test URL construction
    try {
      const testUrl = this.getFullUrl('/tasks');
      console.log('✅ Test URL construction successful:', testUrl);
    } catch (error) {
      console.log('❌ Test URL construction failed:', error.message);
    }
    
    // Validate configuration
    const isValid = this.validateBackendUrl();
    console.log('Configuration valid:', isValid);
    
    return {
      enabled: this.isEnabled,
      bmadBackendUrl: this.bmadBackendUrl,
      jobProApiUrl: JOBPRO_CONFIG.API_URL,
      connectionName: JOBPRO_CONFIG.CONNECTION_NAME,
      isValid: isValid
    };
  }

  // Validate that the backend URL is absolute
  validateBackendUrl() {
    if (!this.bmadBackendUrl) {
      console.error('❌ BMAD backend URL is not set');
      return false;
    }
    
    if (!this.bmadBackendUrl.startsWith('http://') && !this.bmadBackendUrl.startsWith('https://')) {
      console.error('❌ BMAD backend URL must be absolute (start with http:// or https://)');
      console.error('Current URL:', this.bmadBackendUrl);
      
      // Only try to fix once to prevent infinite loops
      if (!this._validationAttempted) {
        this._validationAttempted = true;
        console.log('🔄 Attempting to fix URL by refreshing configuration...');
        this.refreshBackendUrl();
        
        // Check again after refresh
        if (this.bmadBackendUrl && (this.bmadBackendUrl.startsWith('http://') || this.bmadBackendUrl.startsWith('https://'))) {
          console.log('✅ URL fixed after refresh:', this.bmadBackendUrl);
          this._validationAttempted = false; // Reset for next time
          return true;
        }
      }
      
      return false;
    }
    
    // Reset validation flag on successful validation
    this._validationAttempted = false;
    console.log('✅ BMAD backend URL is valid:', this.bmadBackendUrl);
    return true;
  }
  
  // Check if the service is properly configured and ready to use
  isReady() {
    return this.isEnabled && this.validateBackendUrl();
  }

  // Get the full absolute URL for JobPro
  getFullUrl(apiPath) {
    // Ensure apiPath starts with /
    if (!apiPath.startsWith('/')) {
      apiPath = '/' + apiPath;
    }
    
    // Construct full URL
    const fullUrl = `${this.bmadBackendUrl}${apiPath}`;
    
    // Validate the constructed URL
    if (!fullUrl.startsWith('http://') && !fullUrl.startsWith('https://')) {
      console.error('❌ Constructed URL is not absolute:', fullUrl);
      throw new Error(`Invalid URL constructed: ${fullUrl}`);
    }
    
    console.log('🔗 Constructed URL for JobPro:', fullUrl);
    return fullUrl;
  }

  // Determine combined workflow type by workflowId
  async _getCombinedWorkflowType(workflowId) {
    try {
      if (!workflowId) return null;
      const fullUrl = this.getFullUrl('/workflows');
      const res = await fetch(fullUrl, { method: 'GET' });
      if (!res.ok) return null;
      const data = await res.json();
      const list = Array.isArray(data.workflows) ? data.workflows : [];
      const wf = list.find(w => w.id === workflowId);
      if (!wf || !wf.name) return null;
      if (wf.name === 'End-to-End Plan + Execute') return 'legacy';
      if (wf.name === 'io8 Default') return 'io8';
      return null;
    } catch (_) { return null; }
  }

  // Generate a unique reference number
  generateRef() {
    return (this.jobCounter++).toString();
  }

  // Get current timestamp for createdBy/updatedBy
  getCurrentTimestamp() {
    return new Date().getFullYear().toString();
  }

  // Send job to JobPro
  async sendToJobPro(bmadApiUrl, method, jobType, ref, payload = null) {
    if (!this.isReady()) {
      console.log('JobPro is not ready, skipping job submission');
      return { success: false, error: 'JobPro service is not properly configured' };
    }

    // Add rate limiting to prevent repeated calls
    const now = Date.now();
    const lastCallKey = `lastJobProCall_${jobType}`;
    const lastCall = this[lastCallKey] || 0;
    const timeSinceLastCall = now - lastCall;
    
    if (timeSinceLastCall < 2000) { // 2 second minimum between calls of same type
      console.log(`⏭️ JobPro rate limiting: Skipping ${jobType} call (${timeSinceLastCall}ms since last call)`);
      return { success: false, error: 'Rate limited: Please wait before submitting another job' };
    }
    
    this[lastCallKey] = now;

    // Precompute payload and URL once
    const fullUrl = this.getFullUrl(bmadApiUrl);
    const jobData = {
      url: fullUrl,
      method: method,
      connection_name: JOBPRO_CONFIG.CONNECTION_NAME,
      createdBy: this.getCurrentTimestamp(),
      updatedBy: this.getCurrentTimestamp(),
      job_type: jobType,
      ref: ref
    };
    if (payload) jobData.parameters = JSON.stringify(payload);

    console.log('🚀 Sending job to JobPro:', {
      jobType,
      ref,
      url: fullUrl,
      jobProApiUrl: JOBPRO_CONFIG.API_URL,
      timestamp: new Date().toISOString()
    });

    // Small retry loop to avoid transient "Failed to fetch"
    const maxAttempts = 3;
    let lastErr = null;
    for (let attempt = 1; attempt <= maxAttempts; attempt++) {
      try {
        const response = await fetch(JOBPRO_CONFIG.API_URL, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(jobData),
        });
        if (response.ok) {
          console.log(`Job sent to JobPro successfully for ${jobType} (attempt ${attempt})`);
          return { success: true, message: 'Job queued successfully', ref };
        }
        const text = await response.text().catch(() => '');
        let errorData = {};
        try { errorData = JSON.parse(text); } catch {}
        const msg = errorData.error || text || `HTTP ${response.status}`;
        lastErr = new Error(msg);
        console.warn(`JobPro responded with error (attempt ${attempt}/${maxAttempts}):`, msg);
      } catch (error) {
        lastErr = error;
        console.warn(`Network error sending job to JobPro (attempt ${attempt}/${maxAttempts}):`, error?.message || error);
      }
      // brief backoff between attempts
      await new Promise(r => setTimeout(r, attempt * 400));
      // Re-validate URL in case config changed
      this._checkConfigurationChange();
      this.validateBackendUrl();
    }
    return { success: false, error: lastErr?.message || 'JobPro request failed after retries' };
  }

  // Submit new task (chat prompt)
  async submitTask(prompt, workflowId, workflowSequence, agentSpecificPrompts, baseProjectData = {}) {
    // Check if JobPro is ready to use
    if (!this.isReady()) {
      console.log('⏭️ JobPro: Service is not ready, skipping task submission');
      return { success: false, error: 'JobPro service is not properly configured' };
    }
    
    // Check for duplicate submissions within last 5 seconds
    const now = Date.now();
    const lastSubmitKey = 'lastSubmitTask';
    const lastSubmit = this[lastSubmitKey] || 0;
    
    if (now - lastSubmit < 5000) {
      console.log('⏭️ JobPro: Preventing duplicate task submission (too soon after last submission)');
      return { success: false, error: 'Please wait before submitting another task' };
    }
    
    this[lastSubmitKey] = now;
    
    // Execute complete workflow in a single call - no splitting
    const combinedType = await this._getCombinedWorkflowType(workflowId);
    if (combinedType) {
      // Execute the complete workflow sequence in a single call
      const ref = this.generateRef();
      const payload = {
        prompt: prompt,
        workflow_id: workflowId || null,
        workflow_sequence: workflowSequence || null,
        agent_specific_prompts: agentSpecificPrompts || null,
        ...baseProjectData
      };

      const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}task_${ref}`;
      localStorage.setItem(jobKey, JSON.stringify({ payload: payload, timestamp: new Date().toISOString(), type: JOBPRO_CONFIG.JOB_TYPES.SUBMIT_TASK, status: 'queued' }));

      return this.sendToJobPro('/tasks', JOBPRO_CONFIG.METHODS.POST, JOBPRO_CONFIG.JOB_TYPES.SUBMIT_TASK, ref, payload);
    }

    const ref = this.generateRef();
    const payload = {
      prompt: prompt,
      workflow_id: workflowId || null,
      workflow_sequence: workflowSequence || null,
      agent_specific_prompts: agentSpecificPrompts || null,
      ...baseProjectData
    };

    const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}task_${ref}`;
    localStorage.setItem(jobKey, JSON.stringify({ payload: payload, timestamp: new Date().toISOString(), type: JOBPRO_CONFIG.JOB_TYPES.SUBMIT_TASK, status: 'queued' }));

    return this.sendToJobPro('/tasks', JOBPRO_CONFIG.METHODS.POST, JOBPRO_CONFIG.JOB_TYPES.SUBMIT_TASK, ref, payload);
  }

  // Resume workflow
  async resumeWorkflow(taskId, userPrompt, workflowId, workflowSequence = null) {
    const ref = this.generateRef();
    const payload = {
      user_prompt: userPrompt || undefined,
      workflow_id: workflowId || undefined,
      workflow_sequence: workflowSequence || undefined
    };

    // Store the payload in localStorage for JobPro to access
    const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}resume_${ref}`;
    localStorage.setItem(jobKey, JSON.stringify({
      payload: payload,
      taskId: taskId,
      timestamp: new Date().toISOString(),
      type: JOBPRO_CONFIG.JOB_TYPES.RESUME_WORKFLOW,
      status: 'queued'
    }));

    return this.sendToJobPro(`/tasks/${taskId}/resume-workflow`, JOBPRO_CONFIG.METHODS.POST, JOBPRO_CONFIG.JOB_TYPES.RESUME_WORKFLOW, ref, payload);
  }

  // Re-run workflow
  async rerunWorkflow(taskId, userPrompt, workflowId, workflowSequence = null, baseProjectData = {}) {
    const combinedType = await this._getCombinedWorkflowType(workflowId);
    if (combinedType) {
      // Execute the complete workflow sequence in a single call
      const ref = this.generateRef();
      const payload = {
        user_prompt: userPrompt,
        workflow_id: workflowId || undefined,
        workflow_sequence: workflowSequence || undefined,
        ...baseProjectData
      };

      const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}rerun_${ref}`;
      localStorage.setItem(jobKey, JSON.stringify({ payload: payload, taskId: taskId, timestamp: new Date().toISOString(), type: JOBPRO_CONFIG.JOB_TYPES.RERUN_WORKFLOW, status: 'queued' }));

      return this.sendToJobPro(`/tasks/${taskId}/reexecute`, JOBPRO_CONFIG.METHODS.POST, JOBPRO_CONFIG.JOB_TYPES.RERUN_WORKFLOW, ref, payload);
    }

    const ref = this.generateRef();
    const payload = {
      user_prompt: userPrompt,
      workflow_id: workflowId || undefined,
      workflow_sequence: workflowSequence || undefined,
      ...baseProjectData
    };

    const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}rerun_${ref}`;
    localStorage.setItem(jobKey, JSON.stringify({ payload: payload, taskId: taskId, timestamp: new Date().toISOString(), type: JOBPRO_CONFIG.JOB_TYPES.RERUN_WORKFLOW, status: 'queued' }));

    return this.sendToJobPro(`/tasks/${taskId}/reexecute`, JOBPRO_CONFIG.METHODS.POST, JOBPRO_CONFIG.JOB_TYPES.RERUN_WORKFLOW, ref, payload);
  }

  // Wait until the BMAD backend reports the task as completed (or failed/cancelled)
  async _waitForTaskCompletion(taskId, timeoutMs = 1800000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      try {
        const res = await fetch(`${this.bmadBackendUrl}/tasks/${taskId}/monitor`);
        if (res.ok) {
          const data = await res.json();
          const status = data.status;
          if (status === 'completed') return true;
          if (['failed', 'cancelled', 'paused'].includes(status)) {
            throw new Error(`Phase ended with status: ${status}`);
          }
        }
      } catch (_) {}
      await new Promise(r => setTimeout(r, 3000));
    }
    throw new Error('Timeout waiting for phase completion');
  }

  // Upload files to task
  async uploadFiles(taskId, files) {
    const ref = this.generateRef();
    
    // Store the files data in localStorage for JobPro to access
    const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}upload_${ref}`;
    localStorage.setItem(jobKey, JSON.stringify({
      taskId: taskId,
      files: Array.from(files).map(file => ({
        name: file.name,
        size: file.size,
        type: file.type
      })),
      timestamp: new Date().toISOString(),
      type: JOBPRO_CONFIG.JOB_TYPES.UPLOAD_FILES,
      status: 'queued'
    }));

    return this.sendToJobPro(`/tasks/${taskId}/upload`, JOBPRO_CONFIG.METHODS.POST, JOBPRO_CONFIG.JOB_TYPES.UPLOAD_FILES, ref, null);
  }

  // Re-execute requirement builder
  async reexecuteRequirementBuilder(taskId) {
    const ref = this.generateRef();
    const payload = {
      user_prompt: 'Analyze all files in .sureai/uploads and for each file create a strict per-file JSON next to it (<basename>.json). Also create an index at .sureai/requirements_extracted.json listing the per-file outputs.',
      workflow_sequence: ['requirement_builder']
    };

    // Store the payload in localStorage for JobPro to access
    const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}reexecute_${ref}`;
    localStorage.setItem(jobKey, JSON.stringify({
      payload: payload,
      taskId: taskId,
      timestamp: new Date().toISOString(),
      type: JOBPRO_CONFIG.JOB_TYPES.REEXECUTE_REQUIREMENT_BUILDER,
      status: 'queued'
    }));

    return this.sendToJobPro(`/tasks/${taskId}/reexecute`, JOBPRO_CONFIG.METHODS.POST, JOBPRO_CONFIG.JOB_TYPES.REEXECUTE_REQUIREMENT_BUILDER, ref, payload);
  }

  // Check if JobPro is available
  async checkJobProStatus() {
    try {
      const response = await fetch(JOBPRO_CONFIG.API_URL, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      return response.ok;
    } catch (error) {
      console.error('JobPro status check failed:', error);
      return false;
    }
  }

  // Get job status from localStorage
  getJobStatus(ref) {
    const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}${ref}`;
    const jobData = localStorage.getItem(jobKey);
    return jobData ? JSON.parse(jobData) : null;
  }

  // Update job status
  updateJobStatus(ref, status, result = null) {
    const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}${ref}`;
    const existingData = this.getJobStatus(ref);
    if (existingData) {
      existingData.status = status;
      existingData.updatedAt = new Date().toISOString();
      if (result) {
        existingData.result = result;
      }
      localStorage.setItem(jobKey, JSON.stringify(existingData));
    }
  }

  // Clean up completed jobs
  cleanupCompletedJob(ref) {
    const jobKey = `${JOBPRO_CONFIG.STORAGE_PREFIX}${ref}`;
    localStorage.removeItem(jobKey);
  }

  // Get all queued jobs
  getAllQueuedJobs() {
    const jobs = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(JOBPRO_CONFIG.STORAGE_PREFIX)) {
        const jobData = this.getJobStatus(key.replace(JOBPRO_CONFIG.STORAGE_PREFIX, ''));
        if (jobData) {
          jobs.push(jobData);
        }
      }
    }
    return jobs;
  }

  // Clear all jobs (for testing/reset)
  clearAllJobs() {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith(JOBPRO_CONFIG.STORAGE_PREFIX)) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach(key => localStorage.removeItem(key));
    console.log(`Cleared ${keysToRemove.length} jobs from localStorage`);
  }
}

// Create singleton instance
const jobProService = new JobProService();

export default jobProService;
