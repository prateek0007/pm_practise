import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { RefreshCw, Save, RotateCcw, Download, Upload, Server, Settings } from 'lucide-react';
import configManager from '../config/configManager.js';

const ConfigManager = () => {
  const [config, setConfig] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });
  const [editingConfig, setEditingConfig] = useState({});

  useEffect(() => {
    loadCurrentConfig();
  }, []);

  const loadCurrentConfig = () => {
    setIsLoading(true);
    try {
      const currentConfig = {
        jobpro: configManager.getJobProServerConfig(),
        connection: {
          name: configManager.config.jobpro.CONNECTION.NAME,
          timeout: configManager.config.jobpro.CONNECTION.TIMEOUT,
          retries: configManager.config.jobpro.CONNECTION.RETRY_ATTEMPTS
        },
        queue: {
          statusInterval: configManager.config.queue.PROCESSING.STATUS_CHECK_INTERVAL,
          retryDelay: configManager.config.queue.PROCESSING.RETRY_DELAY,
          maxRetries: configManager.config.queue.PROCESSING.MAX_RETRIES
        }
      };
      setConfig(currentConfig);
      setEditingConfig(currentConfig);
    } catch (error) {
      showMessage('error', `Failed to load configuration: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const showMessage = (type, text) => {
    setMessage({ type, text });
    setTimeout(() => setMessage({ type: '', text: '' }), 5000);
  };

  const handleInputChange = (section, key, value) => {
    setEditingConfig(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }));
  };

  const handleSaveConfig = async () => {
    setIsLoading(true);
    try {
      // Update JobPro server configuration
      configManager.updateJobProServer(editingConfig.jobpro);
      
      // Update connection settings
      configManager.updateConnectionName(editingConfig.connection.name);
      configManager.updateConnectionTimeout(editingConfig.connection.timeout);
      configManager.updateRetryAttempts(editingConfig.connection.retries);
      
      // Update queue settings
      configManager.updateStatusCheckInterval(editingConfig.queue.statusInterval);
      configManager.updateRetryDelay(editingConfig.queue.retryDelay);
      
      showMessage('success', 'Configuration updated successfully!');
      loadCurrentConfig(); // Reload to show updated values
    } catch (error) {
      showMessage('error', `Failed to update configuration: ${error.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetConfig = () => {
    if (window.confirm('Are you sure you want to reset all configuration to defaults?')) {
      try {
        configManager.resetToDefaults();
        showMessage('success', 'Configuration reset to defaults!');
        loadCurrentConfig();
      } catch (error) {
        showMessage('error', `Failed to reset configuration: ${error.message}`);
      }
    }
  };

  const handleExportConfig = () => {
    try {
      const configJson = configManager.exportConfig();
      const blob = new Blob([configJson], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'bmad-config.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showMessage('success', 'Configuration exported successfully!');
    } catch (error) {
      showMessage('error', `Failed to export configuration: ${error.message}`);
    }
  };

  const handleImportConfig = (event) => {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const configJson = e.target.result;
        configManager.importConfig(configJson);
        showMessage('success', 'Configuration imported successfully!');
        loadCurrentConfig();
      } catch (error) {
        showMessage('error', `Failed to import configuration: ${error.message}`);
      }
    };
    reader.readAsText(file);
  };

  const validateConfig = () => {
    try {
      const isValid = configManager.validateConfig();
      if (isValid) {
        showMessage('success', 'Configuration is valid!');
      } else {
        showMessage('error', 'Configuration validation failed!');
      }
    } catch (error) {
      showMessage('error', `Validation error: ${error.message}`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">Configuration Manager</h1>
          <p className="text-gray-600 dark:text-gray-400">Manage JobPro server settings and system configuration</p>
        </div>
        <div className="flex items-center space-x-2">
          <Button onClick={loadCurrentConfig} disabled={isLoading} variant="outline">
            <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
          <Button onClick={validateConfig} variant="outline">
            <Settings className="w-4 h-4 mr-2" />
            Validate
          </Button>
        </div>
      </div>

      {/* Message Display */}
      {message.text && (
        <div className={`p-4 rounded-lg border ${
          message.type === 'success' 
            ? 'bg-green-50 border-green-200 text-green-800' 
            : 'bg-red-50 border-red-200 text-red-800'
        }`}>
          {message.text}
        </div>
      )}

      {/* JobPro Server Configuration */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Server className="w-5 h-5" />
            <span>JobPro Server Configuration</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="jobpro-ip">Server IP Address</Label>
              <Input
                id="jobpro-ip"
                value={editingConfig.jobpro?.IP || ''}
                onChange={(e) => handleInputChange('jobpro', 'IP', e.target.value)}
                placeholder="192.168.1.100"
              />
            </div>
            <div>
              <Label htmlFor="jobpro-port">Server Port</Label>
              <Input
                id="jobpro-port"
                value={editingConfig.jobpro?.PORT || ''}
                onChange={(e) => handleInputChange('jobpro', 'PORT', e.target.value)}
                placeholder="8080"
              />
            </div>
            <div>
              <Label htmlFor="jobpro-protocol">Protocol</Label>
              <select
                id="jobpro-protocol"
                value={editingConfig.jobpro?.PROTOCOL || 'http'}
                onChange={(e) => handleInputChange('jobpro', 'PROTOCOL', e.target.value)}
                className="w-full p-2 border border-gray-300 rounded-md"
              >
                <option value="http">HTTP</option>
                <option value="https">HTTPS</option>
              </select>
            </div>
            <div>
              <Label htmlFor="jobpro-path">API Path</Label>
              <Input
                id="jobpro-path"
                value={editingConfig.jobpro?.PATH || ''}
                onChange={(e) => handleInputChange('jobpro', 'PATH', e.target.value)}
                placeholder="/api/jobs"
              />
            </div>
          </div>
          
          <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="text-sm text-blue-800">
              <strong>Current API URL:</strong> {configManager.getJobProApiUrl()}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Connection Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Connection Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="connection-name">Connection Name</Label>
              <Input
                id="connection-name"
                value={editingConfig.connection?.name || ''}
                onChange={(e) => handleInputChange('connection', 'name', e.target.value)}
                placeholder="jobprtal"
              />
            </div>
            <div>
              <Label htmlFor="connection-timeout">Timeout (ms)</Label>
              <Input
                id="connection-timeout"
                type="number"
                value={editingConfig.connection?.timeout || ''}
                onChange={(e) => handleInputChange('connection', 'timeout', e.target.value)}
                placeholder="30000"
              />
            </div>
            <div>
              <Label htmlFor="connection-retries">Retry Attempts</Label>
              <Input
                id="connection-retries"
                type="number"
                value={editingConfig.connection?.retries || ''}
                onChange={(e) => handleInputChange('connection', 'retries', e.target.value)}
                placeholder="3"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Queue Settings */}
      <Card>
        <CardHeader>
          <CardTitle>Queue Processing Settings</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <Label htmlFor="queue-interval">Status Check Interval (ms)</Label>
              <Input
                id="queue-interval"
                type="number"
                value={editingConfig.queue?.statusInterval || ''}
                onChange={(e) => handleInputChange('queue', 'statusInterval', e.target.value)}
                placeholder="5000"
              />
            </div>
            <div>
              <Label htmlFor="queue-retry-delay">Retry Delay (ms)</Label>
              <Input
                id="queue-retry-delay"
                type="number"
                value={editingConfig.queue?.retryDelay || ''}
                onChange={(e) => handleInputChange('queue', 'retryDelay', e.target.value)}
                placeholder="2000"
              />
            </div>
            <div>
              <Label htmlFor="queue-max-retries">Max Retries</Label>
              <Input
                id="queue-max-retries"
                type="number"
                value={editingConfig.queue?.maxRetries || ''}
                onChange={(e) => handleInputChange('queue', 'maxRetries', e.target.value)}
                placeholder="3"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Action Buttons */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Button onClick={handleSaveConfig} disabled={isLoading} className="bg-blue-600 hover:bg-blue-700">
                <Save className="w-4 h-4 mr-2" />
                Save Configuration
              </Button>
              <Button onClick={handleResetConfig} variant="outline" className="text-red-600 hover:text-red-700">
                <RotateCcw className="w-4 h-4 mr-2" />
                Reset to Defaults
              </Button>
            </div>
            
            <div className="flex items-center space-x-2">
              <Button onClick={handleExportConfig} variant="outline">
                <Download className="w-4 h-4 mr-2" />
                Export Config
              </Button>
              <div className="relative">
                <input
                  type="file"
                  accept=".json"
                  onChange={handleImportConfig}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                />
                <Button variant="outline">
                  <Upload className="w-4 h-4 mr-2" />
                  Import Config
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Configuration Status */}
      <Card>
        <CardHeader>
          <CardTitle>Configuration Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span>JobPro Server:</span>
              <Badge variant={configManager.validateConfig() ? 'default' : 'destructive'}>
                {configManager.validateConfig() ? 'Valid' : 'Invalid'}
              </Badge>
            </div>
            <div className="flex items-center justify-between">
              <span>Environment:</span>
              <Badge variant="outline">{process.env.NODE_ENV || 'development'}</Badge>
            </div>
            <div className="flex items-center justify-between">
              <span>BMAD Backend:</span>
              <Badge variant="outline">{configManager.getBmadBackendUrl()}</Badge>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default ConfigManager;
