import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import { RefreshCw, Play, Pause, Trash2, Eye, EyeOff } from 'lucide-react';
import jobProService from '../services/jobProService.js';

const JobProStatus = () => {
  const [isEnabled, setIsEnabled] = useState(true);
  const [isConnected, setIsConnected] = useState(false);
  const [queuedJobs, setQueuedJobs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    checkJobProStatus();
    loadQueuedJobs();
    
    // Set up interval to refresh job status
    const interval = setInterval(() => {
      if (isEnabled) {
        loadQueuedJobs();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [isEnabled]);

  const checkJobProStatus = async () => {
    setIsLoading(true);
    try {
      const status = await jobProService.checkJobProStatus();
      setIsConnected(status);
    } catch (error) {
      console.error('Error checking JobPro status:', error);
      setIsConnected(false);
    } finally {
      setIsLoading(false);
    }
  };

  const loadQueuedJobs = () => {
    const jobs = jobProService.getAllQueuedJobs();
    setQueuedJobs(jobs);
  };

  const handleToggleJobPro = (enabled) => {
    setIsEnabled(enabled);
    jobProService.setEnabled(enabled);
  };

  const handleRefresh = () => {
    checkJobProStatus();
    loadQueuedJobs();
  };

  const handleClearAllJobs = () => {
    if (window.confirm('Are you sure you want to clear all queued jobs? This action cannot be undone.')) {
      jobProService.clearAllJobs();
      loadQueuedJobs();
    }
  };

  const getJobStatusColor = (status) => {
    switch (status) {
      case 'queued':
        return 'bg-yellow-500';
      case 'processing':
        return 'bg-blue-500';
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  const getJobTypeDisplayName = (type) => {
    const typeMap = {
      'submit_task': 'Submit Task',
      'resume_workflow': 'Resume Workflow',
      'rerun_workflow': 'Rerun Workflow',
      'upload_files': 'Upload Files',
      'reexecute_requirement_builder': 'Re-execute Requirement Builder'
    };
    return typeMap[type] || type;
  };

  return (
    <Card className="bmad-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">⚡</span>
            <div>
              <CardTitle className="bmad-text-primary">JobPro Queue Status</CardTitle>
              <p className="text-sm bmad-text-muted">
                Manage JobPro integration and monitor queued jobs
              </p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={isLoading}
            >
              <RefreshCw className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* JobPro Connection Status */}
        <div className="flex items-center justify-between p-3 border rounded-lg">
          <div className="flex items-center space-x-3">
            <div className={`w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
            <div>
              <div className="font-medium">JobPro Connection</div>
              <div className="text-sm text-gray-500">
                {isConnected ? 'Connected' : 'Disconnected'}
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Switch
              id="jobpro-toggle"
              checked={isEnabled}
              onCheckedChange={handleToggleJobPro}
            />
            <Label htmlFor="jobpro-toggle">
              {isEnabled ? 'Enabled' : 'Disabled'}
            </Label>
          </div>
        </div>

        {/* Queue Statistics */}
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-3 border rounded-lg">
            <div className="text-2xl font-bold text-blue-600">{queuedJobs.length}</div>
            <div className="text-sm text-gray-500">Total Jobs</div>
          </div>
          <div className="text-center p-3 border rounded-lg">
            <div className="text-2xl font-bold text-yellow-600">
              {queuedJobs.filter(job => job.status === 'queued').length}
            </div>
            <div className="text-sm text-gray-500">Queued</div>
          </div>
          <div className="text-center p-3 border rounded-lg">
            <div className="text-2xl font-bold text-green-600">
              {queuedJobs.filter(job => job.status === 'completed').length}
            </div>
            <div className="text-sm text-gray-500">Completed</div>
          </div>
        </div>

        {/* Queued Jobs List */}
        {queuedJobs.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="font-medium">Queued Jobs</h4>
              <div className="flex items-center space-x-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowDetails(!showDetails)}
                >
                  {showDetails ? <EyeOff className="w-4 h-4 mr-2" /> : <Eye className="w-4 h-4 mr-2" />}
                  {showDetails ? 'Hide Details' : 'Show Details'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleClearAllJobs}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Clear All
                </Button>
              </div>
            </div>
            
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {queuedJobs.map((job, index) => (
                <div key={index} className="p-3 border rounded-lg">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Badge className={getJobStatusColor(job.status)}>
                        {job.status}
                      </Badge>
                      <span className="font-medium">
                        {getJobTypeDisplayName(job.type)}
                      </span>
                      {job.taskId && (
                        <span className="text-sm text-gray-500">
                          Task: {job.taskId}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-gray-400">
                      {new Date(job.timestamp).toLocaleTimeString()}
                    </div>
                  </div>
                  
                  {showDetails && (
                    <div className="mt-2 p-2 bg-gray-50 rounded text-xs">
                      <div className="font-medium">Job Details:</div>
                      <pre className="whitespace-pre-wrap text-gray-600">
                        {JSON.stringify(job, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* No Jobs Message */}
        {queuedJobs.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            <div className="text-lg font-medium">No queued jobs</div>
            <div className="text-sm">Jobs will appear here when you submit tasks or workflows</div>
          </div>
        )}

        {/* Information Panel */}
        <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="text-sm text-blue-800">
            <div className="font-medium mb-1">How JobPro Works:</div>
            <ul className="list-disc list-inside space-y-1 text-xs">
              <li>When you submit a task or workflow, it's sent to JobPro queue</li>
              <li>JobPro processes jobs every 10 seconds and calls BMAD backend APIs</li>
              <li>Jobs are stored locally and can be monitored here</li>
              <li>You can disable JobPro to use direct API calls instead</li>
            </ul>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default JobProStatus;
