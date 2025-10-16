// JobPro Configuration for Production
import { JOBPRO_ENV, QUEUE_ENV, BACKEND_URL } from './environment.js';

// Production JobPro Configuration
export const JOBPRO_CONFIG = {
  // JobPro server details for production
  SERVER: JOBPRO_ENV.SERVER,
  
  // JobPro API endpoint
  API_URL: `${JOBPRO_ENV.SERVER.PROTOCOL}://${JOBPRO_ENV.SERVER.IP}:${JOBPRO_ENV.SERVER.PORT}${JOBPRO_ENV.SERVER.PATH}`,
  
  // BMAD Backend URL (should include /api for JobPro)
  BMAD_BACKEND_URL: `${BACKEND_URL}/api`,
  
  // Connection settings
  CONNECTION_NAME: JOBPRO_ENV.CONNECTION.NAME,
  CONNECTION_TIMEOUT: JOBPRO_ENV.CONNECTION.TIMEOUT,
  MAX_RETRIES: JOBPRO_ENV.CONNECTION.RETRY_ATTEMPTS,
  
  // Job types mapping
  JOB_TYPES: {
    SUBMIT_TASK: 'submit_task',
    RESUME_WORKFLOW: 'resume_workflow',
    RERUN_WORKFLOW: 'rerun_workflow',
    UPLOAD_FILES: 'upload_files',
    REEXECUTE_REQUIREMENT_BUILDER: 'reexecute_requirement_builder'
  },
  
  // HTTP Methods
  METHODS: {
    GET: 'GET',
    POST: 'POST',
    PUT: 'PUT',
    DELETE: 'DELETE'
  },
  
  // Local storage settings
  STORAGE_PREFIX: QUEUE_ENV.STORAGE.PREFIX,
  MAX_JOBS: QUEUE_ENV.STORAGE.MAX_JOBS,
  CLEANUP_INTERVAL: QUEUE_ENV.STORAGE.CLEANUP_INTERVAL,
  
  // Processing settings
  STATUS_CHECK_INTERVAL: QUEUE_ENV.PROCESSING.STATUS_CHECK_INTERVAL,
  RETRY_DELAY: QUEUE_ENV.PROCESSING.RETRY_DELAY,
  BATCH_SIZE: QUEUE_ENV.PROCESSING.BATCH_SIZE
};

export default JOBPRO_CONFIG;
