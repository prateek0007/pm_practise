// Configuration Manager for BMAD System (Production Only)
// Provides easy methods to access configuration settings

import { API_BASE_URL, BACKEND_URL, FRONTEND_URL, DEPLOYMENT_ENV, JOBPRO_ENV, QUEUE_ENV } from './environment.js';
import { JOBPRO_CONFIG } from './jobProConfig.js';

class ConfigManager {
  constructor() {
    this.config = {
      jobpro: JOBPRO_CONFIG,
      bmad: {
        BACKEND_URL: BACKEND_URL,
        FRONTEND_URL: FRONTEND_URL,
        API_BASE_URL: API_BASE_URL
      },
      deployment: DEPLOYMENT_ENV,
      jobproEnv: JOBPRO_ENV,
      queueEnv: QUEUE_ENV
    };
    
    console.log('🔧 ConfigManager initialized for production environment');
  }

  // ============================================================================
  // PRODUCTION CONFIGURATION METHODS
  // ============================================================================

  /**
   * Get current production configuration
   */
  getProductionConfig() {
    return {
      backend: this.config.bmad.BACKEND_URL,
      frontend: this.config.bmad.FRONTEND_URL,
      api: this.config.bmad.API_BASE_URL,
      jobpro: this.config.jobpro.API_URL,
      deployment: this.config.deployment
    };
  }

  /**
   * Get JobPro configuration
   */
  getJobProConfig() {
    return this.config.jobpro;
  }

  /**
   * Get BMAD backend configuration
   */
  getBmadConfig() {
    return this.config.bmad;
  }

  /**
   * Get JobPro API URL
   */
  getJobProApiUrl() {
    return this.config.jobpro.API_URL;
  }

  /**
   * Get BMAD backend URL
   */
  getBmadBackendUrl() {
    return this.config.bmad.BACKEND_URL;
  }

  /**
   * Get API base URL
   */
  getApiBaseUrl() {
    return this.config.bmad.API_BASE_URL;
  }

  /**
   * Get frontend URL
   */
  getFrontendUrl() {
    return this.config.bmad.FRONTEND_URL;
  }

  /**
   * Get deployment environment
   */
  getDeploymentEnv() {
    return this.config.deployment;
  }

  /**
   * Log current configuration
   */
  logCurrentConfig() {
    console.log('🔧 Current Production Configuration:');
    console.log('  Deployment Environment:', this.config.deployment);
    console.log('  Backend URL:', this.config.bmad.BACKEND_URL);
    console.log('  Frontend URL:', this.config.bmad.FRONTEND_URL);
    console.log('  API Base URL:', this.config.bmad.API_BASE_URL);
    console.log('  JobPro API URL:', this.config.jobpro.API_URL);
  }

  /**
   * Validate configuration
   */
  validateConfig() {
    const required = [
      this.config.bmad.BACKEND_URL,
      this.config.bmad.FRONTEND_URL,
      this.config.bmad.API_BASE_URL,
      this.config.jobpro.API_URL
    ];

    const missing = required.filter(url => !url);
    if (missing.length > 0) {
      throw new Error('Missing required configuration values');
    }

    console.log('✅ Configuration validation passed');
    return true;
  }
}

// Create and export singleton instance
const configManager = new ConfigManager();

export default configManager;
