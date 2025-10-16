// JobPro Configuration Utility
// This file provides JobPro-specific configuration

// JobPro Production Configuration
const JOBPRO_CONFIG = {
  // JobPro Server Details
  SERVER: {
    IP: '157.66.191.31',
    PORT: '31170',
    PROTOCOL: 'http',
    PATH: '/jobpro/pipiline'
  },
  
  // Connection Settings
  CONNECTION: {
    NAME: 'jobprtal',
    TIMEOUT: 30000,
    RETRY_ATTEMPTS: 3
  },
  
  // Job Processing Settings
  PROCESSING: {
    STATUS_CHECK_INTERVAL: 5000,   // 5 seconds
    MAX_RETRIES: 3,
    RETRY_DELAY: 2000,             // 2 seconds
    BATCH_SIZE: 10
  },
  
  // Storage Settings
  STORAGE: {
    PREFIX: 'jobpro_',
    MAX_JOBS: 100,
    CLEANUP_INTERVAL: 300000       // 5 minutes
  }
};

// Function to get JobPro configuration
export function getJobProConfig() {
  return JOBPRO_CONFIG;
}

// BMAD Configuration from .env (Vite)
// Values can be changed in bmad_frontend/.env
const DEPLOYMENT_ENV_ENV = import.meta.env?.VITE_DEPLOYMENT_ENV || 'production';
const BACKEND_HOST_ENV = import.meta.env?.VITE_BACKEND_HOST || '157.66.191.31';
const BACKEND_PORT_ENV = import.meta.env?.VITE_BACKEND_PORT || '5006';
const FRONTEND_HOST_ENV = import.meta.env?.VITE_FRONTEND_HOST || '157.66.191.31';
const FRONTEND_PORT_ENV = import.meta.env?.VITE_FRONTEND_PORT || '5005';

const BACKEND_URL_ENV = import.meta.env?.VITE_BACKEND_URL || `http://${BACKEND_HOST_ENV}:${BACKEND_PORT_ENV}`;
const FRONTEND_URL_ENV = import.meta.env?.VITE_FRONTEND_URL || `http://${FRONTEND_HOST_ENV}:${FRONTEND_PORT_ENV}`;
const API_BASE_URL_ENV = import.meta.env?.VITE_API_BASE_URL || `${BACKEND_URL_ENV}/api`;

const BMAD_CONFIG = {
  DEPLOYMENT_ENV: DEPLOYMENT_ENV_ENV,
  BACKEND_HOST: BACKEND_HOST_ENV,
  BACKEND_PORT: BACKEND_PORT_ENV,
  BACKEND_URL: BACKEND_URL_ENV,
  FRONTEND_HOST: FRONTEND_HOST_ENV,
  FRONTEND_PORT: FRONTEND_PORT_ENV,
  FRONTEND_URL: FRONTEND_URL_ENV,
  API_BASE_URL: API_BASE_URL_ENV
};

// Function to get BMAD configuration
export function getBmadConfig() {
  return BMAD_CONFIG;
}

// Function to update BMAD configuration (called by deployment script)
export function updateBmadConfig(newConfig) {
  Object.assign(BMAD_CONFIG, newConfig);
  // Update exported values
  Object.assign(bmadConfig, newConfig);
}

// Get specific configuration values
export const jobproConfig = getJobProConfig();
export const bmadConfig = getBmadConfig();

// Export JobPro configuration
export const JOBPRO_ENV = jobproConfig;
export const QUEUE_ENV = {
  PROCESSING: jobproConfig.PROCESSING,
  STORAGE: jobproConfig.STORAGE
};

// Export BMAD configuration
export const API_BASE_URL = bmadConfig.API_BASE_URL;
export const BACKEND_URL = bmadConfig.BACKEND_URL;
export const FRONTEND_URL = bmadConfig.FRONTEND_URL;
export const DEPLOYMENT_ENV = bmadConfig.DEPLOYMENT_ENV;

// Utility function to get full API URL
export function getApiUrl(endpoint) {
  const baseUrl = API_BASE_URL;
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
  return `${baseUrl}${cleanEndpoint}`;
}

// Utility function to check if we're in production
export function isProduction() {
  return DEPLOYMENT_ENV === 'production';
}

// Utility function to check if we're in development
export function isDevelopment() {
  return DEPLOYMENT_ENV === 'development';
}

// Export configuration for debugging
if (typeof window !== 'undefined') {
  window.JOBPRO_CONFIG = jobproConfig;
  window.BMAD_CONFIG = bmadConfig;
  console.log('JobPro Configuration:', jobproConfig);
  console.log('BMAD Configuration:', bmadConfig);
}
