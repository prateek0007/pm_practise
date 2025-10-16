#!/usr/bin/env node

/**
 * Environment Configuration Update Script
 * 
 * This script reads the env.config file and updates all frontend components
 * with the correct API_BASE_URL based on the deployment environment.
 * 
 * Usage:
 *   node scripts/update-env.js [development|production]
 */

const fs = require('fs');
const path = require('path');

// Configuration
const ENV_CONFIG_FILE = path.join(__dirname, '..', 'env.config');
const FRONTEND_DIR = path.join(__dirname, '..', 'bmad_frontend', 'src');
const COMPONENTS_TO_UPDATE = [
  'App.jsx',
  'components/TaskMonitor.jsx',
  'components/WorkflowManager.jsx',
  'components/AgentManager.jsx',
  'components/WorkflowSelector.jsx',
  'components/MCPManager.jsx'
];

function readEnvConfig() {
  try {
    const content = fs.readFileSync(ENV_CONFIG_FILE, 'utf8');
    const lines = content.split('\n');
    const config = {};
    
    lines.forEach(line => {
      const trimmed = line.trim();
      if (trimmed && !trimmed.startsWith('#') && trimmed.includes('=')) {
        const [key, value] = trimmed.split('=', 2);
        config[key.trim()] = value.trim();
      }
    });
    
    return config;
  } catch (error) {
    console.error('Error reading env.config file:', error.message);
    return {};
  }
}

function updateFile(filePath, oldApiUrl, newApiUrl) {
  try {
    let content = fs.readFileSync(filePath, 'utf8');
    const originalContent = content;
    
    // Replace API_BASE_URL constant
    content = content.replace(
      /const API_BASE_URL = ['"`][^'"`]*['"`];/g,
      `const API_BASE_URL = '${newApiUrl}';`
    );
    
    // Replace any hardcoded API URLs
    content = content.replace(
      new RegExp(oldApiUrl.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'),
      newApiUrl
    );
    
    if (content !== originalContent) {
      fs.writeFileSync(filePath, content, 'utf8');
      console.log(`✅ Updated: ${filePath}`);
      return true;
    } else {
      console.log(`⏭️  No changes needed: ${filePath}`);
      return false;
    }
  } catch (error) {
    console.error(`❌ Error updating ${filePath}:`, error.message);
    return false;
  }
}

function updateDockerCompose(envConfig) {
  const dockerComposeFile = path.join(__dirname, '..', 'docker-compose.yml');
  
  try {
    let content = fs.readFileSync(dockerComposeFile, 'utf8');
    const originalContent = content;
    
    // Update service names (must be done first)
    if (envConfig.BACKEND_SERVICE_NAME) {
      content = content.replace(
        /^  bmad-backend:/gm,
        `  ${envConfig.BACKEND_SERVICE_NAME}:`
      );
    }
    
    if (envConfig.FRONTEND_SERVICE_NAME) {
      content = content.replace(
        /^  bmad-frontend:/gm,
        `  ${envConfig.FRONTEND_SERVICE_NAME}:`
      );
    }
    
    // Update container names (must be done before general replacement)
    if (envConfig.BACKEND_CONTAINER_NAME) {
      content = content.replace(
        /container_name: bmad-backend/g,
        `container_name: ${envConfig.BACKEND_CONTAINER_NAME}`
      );
    }
    
    if (envConfig.FRONTEND_CONTAINER_NAME) {
      content = content.replace(
        /container_name: bmad-frontend/g,
        `container_name: ${envConfig.FRONTEND_CONTAINER_NAME}`
      );
    }
    
    // Update depends_on references (must be done before general replacement)
    if (envConfig.BACKEND_SERVICE_NAME) {
      content = content.replace(
        /depends_on:\s*\n\s*-\s*bmad-backend/gm,
        `depends_on:\n      - ${envConfig.BACKEND_SERVICE_NAME}`
      );
    }
    
    // Update any remaining references to service names in the file
    if (envConfig.BACKEND_SERVICE_NAME) {
      content = content.replace(
        /bmad-backend/g,
        envConfig.BACKEND_SERVICE_NAME
      );
    }
    
    if (envConfig.FRONTEND_SERVICE_NAME) {
      content = content.replace(
        /bmad-frontend/g,
        envConfig.FRONTEND_SERVICE_NAME
      );
    }
    
    // Update backend port mapping
    content = content.replace(
      /"(\d+):5000"/g,
      `"${envConfig.BACKEND_PORT}:5000"`
    );
    
    // Update frontend port mapping
    content = content.replace(
      /"(\d+):80"/g,
      `"${envConfig.FRONTEND_PORT}:80"`
    );
    
    // Update ZROK_API_ENDPOINT
    content = content.replace(
      /ZROK_API_ENDPOINT=http:\/\/[^:]+:\d+/g,
      `ZROK_API_ENDPOINT=http://${envConfig.BACKEND_HOST}:${envConfig.DOCKER_ZROK_CONTROLLER_PORT || '18080'}`
    );
    
    // Update health check URL
    content = content.replace(
      /http:\/\/[^:]+:\d+\/api\/health/g,
      `http://127.0.0.1:${envConfig.BACKEND_PORT}/api/health`
    );
    
    if (content !== originalContent) {
      fs.writeFileSync(dockerComposeFile, content, 'utf8');
      console.log(`✅ Updated: docker-compose.yml with service names and port mappings`);
      return true;
    } else {
      console.log(`⏭️  No changes needed: docker-compose.yml`);
      return false;
    }
  } catch (error) {
    console.error(`❌ Error updating docker-compose.yml:`, error.message);
    return false;
  }
}

function updateNginxConfig(envConfig) {
  const nginxFile = path.join(__dirname, '..', 'nginx.conf');
  
  try {
    let content = fs.readFileSync(nginxFile, 'utf8');
    const originalContent = content;
    
    // Update backend service name in nginx proxy_pass
    if (envConfig.BACKEND_SERVICE_NAME) {
      content = content.replace(
        /proxy_pass http:\/\/bmad-backend:5000\/api\//g,
        `proxy_pass http://${envConfig.BACKEND_SERVICE_NAME}:5000/api/`
      );
    }
    
    if (content !== originalContent) {
      fs.writeFileSync(nginxFile, content, 'utf8');
      console.log(`✅ Updated: nginx.conf with backend service name: ${envConfig.BACKEND_SERVICE_NAME}`);
      return true;
    } else {
      console.log(`⏭️  No changes needed: nginx.conf`);
      return false;
    }
  } catch (error) {
    console.error(`❌ Error updating nginx.conf:`, error.message);
    return false;
  }
}

function updateEnvironmentConfig(envConfig) {
  const envConfigFile = path.join(__dirname, '..', 'bmad_frontend', 'src', 'config', 'environment.js');
  
  try {
    let content = fs.readFileSync(envConfigFile, 'utf8');
    const originalContent = content;
    
    // Update BMAD_CONFIG object
    content = content.replace(
      /DEPLOYMENT_ENV: ['"`][^'"`]*['"`]/g,
      `DEPLOYMENT_ENV: '${envConfig.DEPLOYMENT_ENV || 'production'}'`
    );
    content = content.replace(
      /BACKEND_HOST: ['"`][^'"`]*['"`]/g,
      `BACKEND_HOST: '${envConfig.BACKEND_HOST}'`
    );
    content = content.replace(
      /BACKEND_PORT: ['"`][^'"`]*['"`]/g,
      `BACKEND_PORT: '${envConfig.BACKEND_PORT}'`
    );
    content = content.replace(
      /BACKEND_URL: ['"`][^'"`]*['"`]/g,
      `BACKEND_URL: 'http://${envConfig.BACKEND_HOST}:${envConfig.BACKEND_PORT}'`
    );
    content = content.replace(
      /FRONTEND_HOST: ['"`][^'"`]*['"`]/g,
      `FRONTEND_HOST: '${envConfig.FRONTEND_HOST}'`
    );
    content = content.replace(
      /FRONTEND_PORT: ['"`][^'"`]*['"`]/g,
      `FRONTEND_PORT: '${envConfig.FRONTEND_PORT}'`
    );
    content = content.replace(
      /FRONTEND_URL: ['"`][^'"`]*['"`]/g,
      `FRONTEND_URL: 'http://${envConfig.FRONTEND_HOST}:${envConfig.FRONTEND_PORT}'`
    );
    content = content.replace(
      /API_BASE_URL: ['"`][^'"`]*['"`]/g,
      `API_BASE_URL: '${envConfig.API_BASE_URL}'`
    );
    
    if (content !== originalContent) {
      fs.writeFileSync(envConfigFile, content, 'utf8');
      console.log(`✅ Updated: environment.js with BMAD config from env.config`);
      return true;
    } else {
      console.log(`⏭️  No changes needed: environment.js`);
      return false;
    }
  } catch (error) {
    console.error(`❌ Error updating environment.js:`, error.message);
    return false;
  }
}

function updateJobProConfig(envConfig) {
  const jobProConfigFile = path.join(__dirname, '..', 'bmad_frontend', 'src', 'config', 'jobProConfig.js');
  
  try {
    let content = fs.readFileSync(jobProConfigFile, 'utf8');
    const originalContent = content;
    
    // Update BMAD_BACKEND_URL in JobPro config
    const newBackendUrl = `http://${envConfig.BACKEND_HOST}:${envConfig.BACKEND_PORT}/api`;
    content = content.replace(
      /BMAD_BACKEND_URL: [`'][^`']*[`']/g,
      `BMAD_BACKEND_URL: \`${newBackendUrl}\``
    );
    
    if (content !== originalContent) {
      fs.writeFileSync(jobProConfigFile, content, 'utf8');
      console.log(`✅ Updated: jobProConfig.js with new backend URL: ${newBackendUrl}`);
      return true;
    } else {
      console.log(`⏭️  No changes needed: jobProConfig.js`);
      return false;
    }
  } catch (error) {
    console.error(`❌ Error updating jobProConfig.js:`, error.message);
    return false;
  }
}

function updateJobProService(envConfig) {
  const jobProServiceFile = path.join(__dirname, '..', 'bmad_frontend', 'src', 'services', 'jobProService.js');
  
  try {
    let content = fs.readFileSync(jobProServiceFile, 'utf8');
    const originalContent = content;
    
    // Force refresh the JobPro service configuration on deployment
    const newBackendUrl = `http://${envConfig.BACKEND_HOST}:${envConfig.BACKEND_PORT}/api`;
    
    // Add a comment to indicate this was updated by deploy script
    const updateComment = `// Updated by deploy script - ${new Date().toISOString()}`;
    
    // Find the constructor and add configuration refresh
    if (content.includes('constructor() {')) {
      content = content.replace(
        /constructor\(\) \{([\s\S]*?)\}/,
        `constructor() {$1
    // Force refresh configuration on deployment
    this.forceRefreshConfiguration();
    ${updateComment}
}`
      );
    }
    
    if (content !== originalContent) {
      fs.writeFileSync(jobProServiceFile, content, 'utf8');
      console.log(`✅ Updated: jobProService.js to force refresh configuration`);
      return true;
    } else {
      console.log(`⏭️  No changes needed: jobProService.js`);
      return false;
    }
  } catch (error) {
    console.error(`❌ Error updating jobProService.js:`, error.message);
    return false;
  }
}

function main() {
  const deploymentEnv = 'production';
  
  console.log(`🚀 Updating environment configuration for: ${deploymentEnv}`);
  
  // Read current env.config
  const envConfig = readEnvConfig();
  
  // Use the values from env.config directly
  const config = { ...envConfig };
  
  console.log('📋 Configuration:');
  console.log(`  API_BASE_URL: ${config.API_BASE_URL}`);
  console.log(`  BACKEND_HOST: ${config.BACKEND_HOST}`);
  console.log(`  BACKEND_PORT: ${config.BACKEND_PORT}`);
  console.log(`  FRONTEND_HOST: ${config.FRONTEND_HOST}`);
  console.log(`  FRONTEND_PORT: ${config.FRONTEND_PORT}`);
  
  // Update frontend components
  console.log('\n📝 Updating frontend components...');
  let updatedFiles = 0;
  
  COMPONENTS_TO_UPDATE.forEach(componentPath => {
    const fullPath = path.join(FRONTEND_DIR, componentPath);
    if (fs.existsSync(fullPath)) {
      const oldApiUrl = '/api';
      if (updateFile(fullPath, oldApiUrl, config.API_BASE_URL)) {
        updatedFiles++;
      }
    } else {
      console.log(`⚠️  File not found: ${componentPath}`);
    }
  });
  
  // Update environment.js
  console.log('\n🔧 Updating environment configuration...');
  updateEnvironmentConfig(config);
  
  // Update JobPro configuration
  console.log('\n⚡ Updating JobPro configuration...');
  updateJobProConfig(config);
  
  // Update JobPro service to force refresh
  console.log('\n🔄 Updating JobPro service...');
  updateJobProService(config);
  
  // Update docker-compose.yml
  console.log('\n🐳 Updating Docker configuration...');
  updateDockerCompose(config);
  
  // Update nginx.conf
  console.log('\n🌐 Updating nginx configuration...');
  updateNginxConfig(config);
  
  console.log(`\n✅ Environment update complete!`);
  console.log(`📊 Files updated: ${updatedFiles + 5} (components + environment.js + jobProConfig.js + jobProService.js + docker-compose.yml + nginx.conf)`);
  console.log(`🎯 Deployment environment: ${deploymentEnv}`);
  console.log(`🔗 API Base URL: ${config.API_BASE_URL}`);
}

if (require.main === module) {
  main();
}

module.exports = { main, updateFile, updateEnvironmentConfig, updateDockerCompose };
