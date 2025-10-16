import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './components/ui/card';
import { Button } from './components/ui/button';
import { Input } from './components/ui/input';
import { Textarea } from './components/ui/textarea';
import { Label } from './components/ui/label';
import { Badge } from './components/ui/badge';
import { Alert, AlertDescription } from './components/ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select';
import { Separator } from './components/ui/separator';
import { ScrollArea } from './components/ui/scroll-area';
import WorkflowManager from './components/WorkflowManager';
import WorkflowSelector from './components/WorkflowSelector';
import AgentManager from './components/AgentManager';
import TaskMonitor from './components/TaskMonitor';
import MCPManager from './components/MCPManager';
import ChatInterface from './components/ChatInterface';
import ErrorBoundary from './components/ErrorBoundary';
import jobProService from './services/jobProService.js';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import {
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { 
  Play, 
  Pause, 
  Square, 
  Upload, 
  Settings, 
  Users, 
  Workflow, 
  FileText, 
  Activity, 
  CheckCircle, 
  XCircle, 
  Clock,
  Save,
  RotateCcw,
  Plus,
  Trash2,
  GripVertical,
  Edit,
  Eye,
  Loader2,
  MessageSquare,
  Bot,
  Send,
  Menu,
  X,
  ChevronRight,
  History,
  RefreshCw
} from 'lucide-react';
import './App.css';
import { API_BASE_URL, getApiUrl } from './config/environment';

// Backend URL configuration - Use centralized environment config

// Sortable Workflow Item Component
function SortableWorkflowItem({ agentName, index, agents, onRemove }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: agentName });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-2 p-3 border rounded bg-background transition-colors sortable-item ${isDragging ? 'dragging' : ''}`}
      {...attributes}
      {...listeners}
    >
      <GripVertical className="w-4 h-4 text-gray-400 grip-handle" />
      <div className="flex-1">
        <div className="font-medium">
          {agents[agentName]?.display_name || agentName}
        </div>
        <div className="text-sm text-gray-600">
          Step {index + 1}
        </div>
      </div>
      <Button
        size="sm"
        variant="outline"
        onClick={(e) => {
          e.stopPropagation();
          onRemove(index);
        }}
      >
        <Trash2 className="w-4 h-4" />
      </Button>
    </div>
  );
}

function App() {
  // State management
  const [activeSection, setActiveSection] = useState('chat');
  const [isSwitching, setIsSwitching] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [userPrompt, setUserPrompt] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [currentTask, setCurrentTask] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [config, setConfig] = useState({});
  const [usage, setUsage] = useState({});
  const [agents, setAgents] = useState({});
  const [defaultWorkflow, setDefaultWorkflow] = useState([]);
  const [customWorkflow, setCustomWorkflow] = useState([]);
  const [customAgentPrompts, setCustomAgentPrompts] = useState({});
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notification, setNotification] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [otherKey1, setOtherKey1] = useState('');
  const [otherKey2, setOtherKey2] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [llxprtApiKey, setLlxprtApiKey] = useState('');
  const [keyRotationEvents, setKeyRotationEvents] = useState([]);
  const [lastKeyStatus, setLastKeyStatus] = useState(null);
  const [llxprtModel, setLlxprtModel] = useState('qwen/qwen3-coder');
  const [llxprtBaseUrl, setLlxprtBaseUrl] = useState('https://openrouter.aihttp://157.66.191.31:9191http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006/api/v1');
  const [llxprtProvider, setLlxprtProvider] = useState('openai');
  const [editingAgent, setEditingAgent] = useState(null);
  const [editingPrompt, setEditingPrompt] = useState('');
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [showWorkflowSelector, setShowWorkflowSelector] = useState(false);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isPublic, setIsPublic] = useState(false);
  const [newTaskMode, setNewTaskMode] = useState(false);
  // FLF workflow state
  const [flfUrl, setFlfUrl] = useState('');
  const [flfFolderName, setFlfFolderName] = useState('');
  const [isWaitingForTask, setIsWaitingForTask] = useState(false);
  const [waitingTaskPrompt, setWaitingTaskPrompt] = useState('');
  const [waitingStartTime, setWaitingStartTime] = useState(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [fetchingTasks, setFetchingTasks] = useState(false);
  const [lastFetchTime, setLastFetchTime] = useState(0);
  const [initialLoading, setInitialLoading] = useState(true);
  const fileInputRef = useRef(null);
  const globalRefreshRef = useRef(null);

  // Helper function to check if io8 Default workflow is selected
  const isIo8DefaultWorkflow = () => {
    return selectedWorkflow && selectedWorkflow.name === 'io8 Default';
  };

  const handleAddSelectedFiles = (fileList) => {
    const newFiles = Array.from(fileList || []);
    if (newFiles.length === 0) return;
    // Deduplicate by name+size (basic heuristic)
    setSelectedFiles((prev) => {
      const seen = new Set(prev.map(f => `${f.name}:${f.size}`));
      const appended = [...prev];
      for (const f of newFiles) {
        const key = `${f.name}:${f.size}`;
        if (!seen.has(key)) {
          appended.push(f);
          seen.add(key);
        }
      }
      return appended;
    });
  };

  const handleRemoveSelectedFile = (index) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  // Drag and drop sensors
  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Available models
  const availableModels = [
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-1.5-pro',
    'gemini-1.5-flash',
    'gemini-1.0-pro'
  ];

  // Navigation items
  const navigationItems = [
    { id: 'chat', label: 'Chat', icon: MessageSquare, description: 'Create and manage tasks' },
    { id: 'agents', label: 'Agents', icon: Users, description: 'Manage agent prompts' },
    { id: 'workflows', label: 'Workflows', icon: Workflow, description: 'Configure workflows' },
    { id: 'mcp', label: 'MCP', icon: Settings, description: 'Manage MCP servers' },
    { id: 'monitor', label: 'Monitor', icon: Activity, description: 'Track task progress' },
    { id: 'settings', label: 'Settings', icon: Settings, description: 'System configuration' }
  ];

  // Fetch data on component mount
  useEffect(() => {
    const initializeData = async () => {
      try {
        setInitialLoading(true);
        
        // JobPro configuration is handled automatically by the service
        // No need to force refresh on every app load
        
        await Promise.all([
          fetchTasks(),
          fetchConfig(),
          fetchUsage(),
          fetchAgents(),
          fetchDefaultWorkflow()
        ]);
      } catch (error) {
        console.error('❌ Error initializing data:', error);
      } finally {
        setInitialLoading(false);
      }
    };
    
    initializeData();
    
    // Cleanup function
    return () => {
      // No cleanup needed for global refresh
    };
  }, []);
  
  // Monitor API key rotation events
  useEffect(() => {
    if (config.gemini_api_keys_status && lastKeyStatus) {
      const currentStatus = config.gemini_api_keys_status;
      
      // Check if key rotation occurred
      if (currentStatus.current_key_index !== lastKeyStatus.current_key_index) {
        const oldKeyIndex = lastKeyStatus.current_key_index;
        const newKeyIndex = currentStatus.current_key_index;
        
        // Find the old and new keys
        const oldKey = lastKeyStatus.keys?.[oldKeyIndex];
        const newKey = currentStatus.keys?.[newKeyIndex];
        
        if (oldKey && newKey) {
          const rotationEvent = {
            id: Date.now(),
            timestamp: new Date().toISOString(),
            type: 'key_rotation',
            message: `🔄 API key rotated from Key ${oldKeyIndex + 1} to Key ${newKeyIndex + 1}`,
            details: {
              from: `Key ${oldKeyIndex + 1}`,
              to: `Key ${newKeyIndex + 1}`,
              reason: oldKey.is_exhausted ? 'Quota exhausted' : 'Manual rotation',
              oldKeyStatus: oldKey.is_exhausted ? 'Exhausted' : 'Active',
              newKeyStatus: 'Active'
            }
          };
          
          setKeyRotationEvents(prev => [rotationEvent, ...prev.slice(0, 9)]); // Keep last 10 events
          
          // Show enhanced notification
          showKeyRotationNotification(rotationEvent);
        }
      }
      
      // Check for new exhausted keys
      if (currentStatus.keys && lastKeyStatus.keys) {
        currentStatus.keys.forEach((key, index) => {
          const lastKey = lastKeyStatus.keys?.[index];
          if (lastKey && !lastKey.is_exhausted && key.is_exhausted) {
            const exhaustionEvent = {
              id: Date.now(),
              timestamp: new Date().toISOString(),
              type: 'key_exhausted',
              message: `⚠️ API Key ${index + 1} marked as exhausted`,
              details: {
                keyIndex: index + 1,
                reason: key.exhaustion_reason || 'Unknown',
                timestamp: key.exhausted_at
              }
            };
            
            setKeyRotationEvents(prev => [exhaustionEvent, ...prev.slice(0, 9)]);
            showKeyRotationNotification(exhaustionEvent);
          }
        });
      }
      
      // Update last status
      setLastKeyStatus(currentStatus);
    } else if (config.gemini_api_keys_status) {
      // First time loading
      setLastKeyStatus(config.gemini_api_keys_status);
    }
    }, [config.gemini_api_keys_status]);
  
  // Periodic config refresh to detect key rotation events
  useEffect(() => {
    const interval = setInterval(() => {
      // Only refresh if we're on the settings page or if there are active tasks
      // Include cancelled tasks to ensure we stop polling for them
      const hasActiveTasks = tasks.some(task => 
        task.status === 'in_progress' || task.status === 'cancelled'
      );
      if (activeSection === 'settings' || hasActiveTasks) {
        fetchConfig();
      }
    }, 10000); // Refresh every 10 seconds
    
    return () => clearInterval(interval);
  }, [activeSection, tasks]);
  
  // Immediate config refresh when key rotation is detected in TaskMonitor
  useEffect(() => {
    const handler = () => {
      try {
        fetchConfig();
      } catch (e) {}
    };
    const delayed = () => {
      try {
        // Some backends mark exhaustion slightly after rotation; re-fetch after short delay
        setTimeout(() => fetchConfig(), 1500);
        setTimeout(() => fetchConfig(), 4000);
      } catch (e) {}
    };
    if (typeof window !== 'undefined' && window.addEventListener) {
      window.addEventListener('bmad:key-rotated', handler);
      window.addEventListener('bmad:key-rotated', delayed);
      window.addEventListener('bmad:key-exhausted', handler);
      window.addEventListener('bmad:key-exhausted', delayed);
    }
    return () => {
      if (typeof window !== 'undefined' && window.removeEventListener) {
        window.removeEventListener('bmad:key-rotated', handler);
        window.removeEventListener('bmad:key-rotated', delayed);
        window.removeEventListener('bmad:key-exhausted', handler);
        window.removeEventListener('bmad:key-exhausted', delayed);
      }
    };
  }, []);
  
  // Debug section changes
  useEffect(() => {
    console.log('Active section changed to:', activeSection);
    console.log('Current state:', {
      tasks: tasks.length,
      chatHistory: chatHistory.length,
      agents: Object.keys(agents).length,
      isSubmitting
    });
  }, [activeSection, tasks, chatHistory, agents, isSubmitting]);

  // Global automatic refresh when waiting for task (works regardless of active section)
  useEffect(() => {
    if (isWaitingForTask) {
      console.log('🔄 Starting global automatic refresh for task creation...');
      if (!globalRefreshRef.current) {
        globalRefreshRef.current = setInterval(() => {
          console.log('🔄 Global auto-refreshing tasks...');
          fetchTasks().catch(error => {
            console.error('Error during global auto-refresh:', error);
          });
        }, 1000);
        // Immediate fetch
        fetchTasks().catch(error => {
          console.error('Error during global immediate fetch:', error);
        });
      }
    } else {
      if (globalRefreshRef.current) {
        clearInterval(globalRefreshRef.current);
        globalRefreshRef.current = null;
      }
    }
    return () => {
      if (globalRefreshRef.current) {
        clearInterval(globalRefreshRef.current);
        globalRefreshRef.current = null;
      }
    };
  }, [isWaitingForTask]);

  // Automatic refresh when waiting for task creation (monitor section specific)
  useEffect(() => {
    if (isWaitingForTask && activeSection === 'monitor') {
      console.log('🔄 Monitor section active, ensuring refresh is working...');
      
      // The global refresh should already be running, just ensure we're on monitor
      // and show the UI properly
    } else if (activeSection !== 'monitor' && isWaitingForTask) {
      console.log('🔄 Switched away from monitor, but global refresh continues...');
    }
  }, [isWaitingForTask, activeSection]);



  // Check if waiting task has been created
  useEffect(() => {
    if (isWaitingForTask && tasks.length > 0) {
      console.log('🔍 Checking for matching task...', {
        isWaitingForTask,
        waitingTaskPrompt,
        tasksCount: tasks.length,
        tasks: tasks.map(t => ({ id: t.task_id, prompt: t.prompt, status: t.status }))
      });
      
      // Check if any task matches the waiting prompt (more flexible matching)
      const matchingTask = tasks.find(task => {
        // Check if task was created recently (within last 2 minutes)
        const taskCreatedRecently = task.created_at && 
          (Date.now() - new Date(task.created_at).getTime()) < 2 * 60 * 1000;
        
        // Check if prompt matches (case-insensitive, partial match)
        const promptMatches = task.prompt && waitingTaskPrompt &&
          (task.prompt.toLowerCase().includes(waitingTaskPrompt.toLowerCase()) ||
           waitingTaskPrompt.toLowerCase().includes(task.prompt.toLowerCase()));
        
        // Check if status indicates the task is active
        const isActiveStatus = task.status === 'in_progress' || task.status === 'queued' || task.status === 'pending';
        
        console.log('🔍 Task check:', {
          taskId: task.task_id,
          taskPrompt: task.prompt,
          waitingPrompt: waitingTaskPrompt,
          promptMatches,
          isActiveStatus,
          taskCreatedRecently,
          created_at: task.created_at
        });
        
        return (promptMatches || taskCreatedRecently) && isActiveStatus;
      });
      
      if (matchingTask) {
        console.log('✅ Task created successfully:', matchingTask.task_id);
        setIsWaitingForTask(false);
        setWaitingTaskPrompt('');
        setWaitingStartTime(null);
        setElapsedTime(0);
        setSelectedTaskId(matchingTask.task_id);
        setCurrentTask(matchingTask); // Set current task for split-screen interface
        
        // Show success notification
        showNotification(`Task created successfully! Task ID: ${matchingTask.task_id.slice(0, 8)}`, 'success');
      } else {
        // Fallback: if we have tasks but none match, check if any were created recently
        const recentTasks = tasks.filter(task => {
          const taskCreatedRecently = task.created_at && 
            (Date.now() - new Date(task.created_at).getTime()) < 2 * 60 * 1000;
          const isActiveStatus = task.status === 'in_progress' || task.status === 'queued' || task.status === 'pending';
          return taskCreatedRecently && isActiveStatus;
        });
        
        if (recentTasks.length > 0) {
          console.log('🔄 Fallback: Found recent tasks, assuming one is ours:', recentTasks[0]);
          const fallbackTask = recentTasks[0];
          setIsWaitingForTask(false);
          setWaitingTaskPrompt('');
          setWaitingStartTime(null);
          setElapsedTime(0);
          setSelectedTaskId(fallbackTask.task_id);
          setCurrentTask(fallbackTask); // Set current task for split-screen interface
          
          // Show success notification
          showNotification(`Task detected! Task ID: ${fallbackTask.task_id.slice(0, 8)}`, 'success');
        }
      }
    }
  }, [tasks, isWaitingForTask, waitingTaskPrompt]);

  // Cleanup waiting state when switching sections
  useEffect(() => {
    if (activeSection !== 'monitor') {
      // Don't stop the waiting state when switching sections
      // Only stop if we're explicitly done waiting
      console.log('🔄 Switched away from monitor, keeping waiting state active');
    }
  }, [activeSection]);

  // Timeout for waiting state (5 minutes)
  useEffect(() => {
    if (isWaitingForTask) {
      const timeout = setTimeout(() => {
        console.log('⏰ Waiting timeout reached (5 minutes)');
        setIsWaitingForTask(false);
        setWaitingTaskPrompt('');
        setWaitingStartTime(null);
        setElapsedTime(0);
        showNotification('Task creation timeout reached. Please check JobPro status or try again.', 'warning');
      }, 5 * 60 * 1000); // 5 minutes
      
      return () => clearTimeout(timeout);
    }
  }, [isWaitingForTask]);

  // Additional timeout for when tasks exist but none match (2 minutes)
  useEffect(() => {
    if (isWaitingForTask && tasks.length > 0) {
      const timeout = setTimeout(() => {
        console.log('⏰ Task detection timeout reached (2 minutes)');
        // Check if we have any recent tasks that might be ours
        const recentTasks = tasks.filter(task => {
          const taskCreatedRecently = task.created_at && 
            (Date.now() - new Date(task.created_at).getTime()) < 5 * 60 * 1000; // 5 minutes
          const isActiveStatus = task.status === 'in_progress' || task.status === 'queued' || task.status === 'pending';
          return taskCreatedRecently && isActiveStatus;
        });
        
        if (recentTasks.length > 0) {
          console.log('🔄 Timeout fallback: Using most recent task:', recentTasks[0]);
          const fallbackTask = recentTasks[0];
          setIsWaitingForTask(false);
          setWaitingTaskPrompt('');
          setWaitingStartTime(null);
          setElapsedTime(0);
          setSelectedTaskId(fallbackTask.task_id);
          setCurrentTask(fallbackTask); // Set current task for split-screen interface
          
          showNotification(`Task detected via timeout fallback! Task ID: ${fallbackTask.task_id.slice(0, 8)}`, 'info');
        } else {
          console.log('⏰ No recent tasks found, stopping waiting state');
          setIsWaitingForTask(false);
          setWaitingTaskPrompt('');
          setWaitingStartTime(null);
          setElapsedTime(0);
          showNotification('No matching task found. Please check JobPro status or try again.', 'warning');
        }
      }, 2 * 60 * 1000); // 2 minutes
      
      return () => clearTimeout(timeout);
    }
  }, [isWaitingForTask, tasks]);

  // Update elapsed time every second when waiting
  useEffect(() => {
    if (isWaitingForTask && waitingStartTime) {
      const interval = setInterval(() => {
        setElapsedTime(Math.floor((Date.now() - waitingStartTime) / 1000));
      }, 1000);
      
      return () => clearInterval(interval);
    } else {
      setElapsedTime(0);
    }
  }, [isWaitingForTask, waitingStartTime]);

  // API functions
  const fetchTasks = async () => {
    try {
      // Debounce: prevent fetching if last fetch was less than 1 second ago
      const now = Date.now();
      if (now - lastFetchTime < 1000) {
        console.log('⏭️ Skipping fetchTasks - too soon since last fetch');
        return;
      }
      
      console.log('📡 fetchTasks called at:', new Date().toLocaleTimeString());
      setFetchingTasks(true);
      setLastFetchTime(now);
      console.log('Fetching tasks from:', `${API_BASE_URL}/tasks`);
      const response = await fetch(`${API_BASE_URL}/tasks`);
      console.log('Tasks response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Tasks data received:', {
          count: data.tasks?.length || 0,
          tasks: data.tasks?.map(t => ({ id: t.task_id, prompt: t.prompt, status: t.status, created_at: t.created_at }))
        });
        setTasks(data.tasks || []);
        
        // Auto-select first active task if no current task is set and we're not in New Task mode
        if (!newTaskMode && !currentTask && data.tasks && data.tasks.length > 0) {
          const activeTask = data.tasks.find(task => 
            task.status === 'in_progress' || task.status === 'queued' || task.status === 'pending'
          );
          if (activeTask) {
            setCurrentTask(activeTask);
            setSelectedTaskId(activeTask.task_id);
          }
        }
      } else {
        console.error('Failed to fetch tasks:', response.status);
        setTasks([]);
      }
    } catch (error) {
      console.error('Error fetching tasks:', error);
      setTasks([]);
    } finally {
      setFetchingTasks(false);
    }
  };

  const fetchConfig = async () => {
    try {
      console.log('Fetching config from:', `${API_BASE_URL}/config`);
      const response = await fetch(`${API_BASE_URL}/config`);
      console.log('Config response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Config data:', data);
        setConfig(data);
        setSelectedModel(data.current_model || 'gemini-2.5-flash');
        
        // Handle Gemini API keys
        if (data.gemini_api_keys_status && data.gemini_api_keys_status.keys) {
          const keys = data.gemini_api_keys_status.keys;
          // Set primary key (first available key)
          if (keys.length > 0) {
            setApiKey(''); // Don't preload secrets
          }
          // Note: We don't preload the other keys for security
        }
        
        if (data.llxprt) {
          setLlxprtApiKey(''); // do not preload secrets into inputs
          setLlxprtModel(data.llxprt.model_name || 'qwen/qwen3-coder');
          setLlxprtBaseUrl(data.llxprt.base_url || 'https://openrouter.aihttp://157.66.191.31:9191http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006/api/v1');
          setLlxprtProvider(data.llxprt.provider || 'openai');
        }
      } else {
        console.error('Failed to fetch config:', response.status);
      }
    } catch (error) {
      console.error('Error fetching config:', error);
    }
  };

  const fetchUsage = async () => {
    try {
      console.log('Fetching usage from:', `${API_BASE_URL}/usage/summary`);
      const response = await fetch(`${API_BASE_URL}/usage/summary`);
      console.log('Usage response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Usage data:', data);
        setUsage(data);
      } else {
        console.error('Failed to fetch usage:', response.status);
      }
    } catch (error) {
      console.error('Error fetching usage:', error);
    }
  };

  const fetchAgents = async () => {
    try {
      console.log('Fetching agents from:', `${API_BASE_URL}/agents/prompts`);
      const response = await fetch(`${API_BASE_URL}/agents/prompts`);
      console.log('Agents response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Agents data:', data);
        setAgents(data.agents || {});
      } else {
        console.error('Failed to fetch agents:', response.status);
      }
    } catch (error) {
      console.error('Error fetching agents:', error);
    }
  };

  const fetchDefaultWorkflow = async () => {
    try {
      console.log('Fetching workflow from:', `${API_BASE_URL}/workflows/default`);
      const response = await fetch(`${API_BASE_URL}/workflows/default`);
      console.log('Workflow response status:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Workflow data:', data);
        setDefaultWorkflow(data.workflow_sequence || []);
        setCustomWorkflow(data.workflow_sequence || []);
      } else {
        console.error('Failed to fetch workflow:', response.status);
      }
    } catch (error) {
      console.error('Error fetching default workflow:', error);
    }
  };

  // Notification helper
  const showNotification = (message, type = 'info', duration = 5000) => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), duration);
  };
  
  // Enhanced notification for key rotation events
  const showKeyRotationNotification = (event) => {
    const message = event.type === 'key_rotation' 
      ? `🔄 API key rotated: ${event.details.from} → ${event.details.to}`
      : `⚠️ API key exhausted: ${event.details.keyIndex}`;
    
    const type = event.type === 'key_rotation' ? 'info' : 'warning';
    const duration = event.type === 'key_rotation' ? 8000 : 10000; // Longer duration for important events
    
    showNotification(message, type, duration);
  };

  // Task submission
  const handleSubmitTask = async () => {
    // Check if this is FLF workflow and validate inputs
    const isFlfWorkflow = selectedWorkflow && selectedWorkflow.name && selectedWorkflow.name.toLowerCase().includes('flf');
    if (isFlfWorkflow && (!flfUrl.trim() || !flfFolderName.trim())) {
      showNotification('Please enter both repository URL and folder name for the FLF workflow.', 'error');
      return;
    }
    
    // For FLF workflow, modify the user prompt to include both URL and folder name
    let finalUserPrompt = userPrompt.trim();
    if (isFlfWorkflow && flfUrl.trim() && flfFolderName.trim()) {
      finalUserPrompt = `First, clone the repository from ${flfUrl}. Then, analyze the field patterns in ${flfFolderName} using the Universal Field Analysis Context Guide`;
    }
    
    if (!finalUserPrompt) {
      showNotification('Please enter a prompt', 'error');
      return;
    }
    

    setIsSubmitting(true);
    try {
      const normalizedSelectedSequence = selectedWorkflow && selectedWorkflow.agent_sequence
        ? (Array.isArray(selectedWorkflow.agent_sequence)
            ? selectedWorkflow.agent_sequence
            : (typeof selectedWorkflow.agent_sequence === 'string'
                ? (() => { try { return JSON.parse(selectedWorkflow.agent_sequence); } catch { return []; } })()
                : []))
        : null;

      // Check if JobPro is enabled
      if (jobProService.isJobProEnabled()) {
        console.log('Submitting task through JobPro queue');
        
        // Submit task to JobPro
        
        const result = await jobProService.submitTask(
          finalUserPrompt,
          selectedWorkflow?.id || null,
          normalizedSelectedSequence || (customWorkflow.length > 0 ? customWorkflow : null),
          Object.keys(customAgentPrompts).length > 0 ? customAgentPrompts : null,
        );

        if (result.success) {
          showNotification(`Task queued successfully! JobPro will process it shortly.`, 'success');
          
          // Add to chat history
          const newChatItem = {
            id: `queued-${Date.now()}`,
            type: 'user',
            content: userPrompt,
            timestamp: new Date(),
            taskId: 'queued'
          };
          
          const botResponse = {
            id: `bot-queued-${Date.now()}`,
            type: 'bot',
            content: `Task queued successfully! JobPro will process your request using ${selectedWorkflow?.name || 'Default'} workflow. Check the JobPro status panel for queue information.`,
            timestamp: new Date(),
            taskId: 'queued'
          };
          
          setChatHistory(prev => [...prev, newChatItem, botResponse]);
          setUserPrompt('');
          setFlfUrl('');
          setFlfFolderName('');
          setCustomAgentPrompts({});
          setSelectedWorkflow(null);
          setSelectedFiles([]);
          
          // If files are selected, queue upload jobs
          if (selectedFiles && selectedFiles.length > 0) {
            // Note: File uploads will be uploaded when JobPro processes the main task
            console.log('Files will be uploaded when JobPro processes the main task');
          }
          
          // Set waiting state for automatic refresh
          setIsWaitingForTask(true);
          setWaitingTaskPrompt(userPrompt);
          setWaitingStartTime(Date.now());
          setNewTaskMode(false);
          
          // Stay in chat section but wait for task creation
          // The task will be automatically detected and currentTask will be set
        } else {
          throw new Error(result.error || 'Failed to queue task');
        }
      } else {
        // Fallback to direct API call if JobPro is disabled
        console.log('JobPro disabled, using direct API call');
        
        const payload = {
          prompt: finalUserPrompt,
          workflow_id: selectedWorkflow?.id || null,
          workflow_sequence: normalizedSelectedSequence || (customWorkflow.length > 0 ? customWorkflow : null),
          agent_specific_prompts: Object.keys(customAgentPrompts).length > 0 ? customAgentPrompts : null
        };
        

        console.log('Submitting task with payload:', payload);
        console.log('API URL:', `${API_BASE_URL}/tasks`);

        const response = await fetch(`${API_BASE_URL}/tasks`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        });

        console.log('Response status:', response.status);
        console.log('Response ok:', response.ok);

        if (response.ok) {
          const data = await response.json();
          console.log('Task created successfully:', data);
          
          // Upload any selected files to the task's uploads folder
          if (selectedFiles && selectedFiles.length > 0) {
            for (const file of selectedFiles) {
              const formData = new FormData();
              formData.append('file', file);
              try {
                await fetch(`${API_BASE_URL}/tasks/${data.task_id}/upload`, {
                  method: 'POST',
                  body: formData,
                });
              } catch (e) {
                console.warn('Upload failed for file', file?.name, e);
              }
            }
            // After uploads complete, trigger requirement_builder to extract from .sureai/uploads
            try {
              await fetch(`${API_BASE_URL}/tasks/${data.task_id}/reexecute`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  user_prompt: 'Analyze all files in .sureai/uploads and for each file create a strict per-file JSON next to it (<basename>.json). Also create an index at .sureai/requirements_extracted.json listing the per-file outputs.',
                  workflow_sequence: ['requirement_builder']
                })
              });
            } catch (e) {
              console.warn('Could not trigger requirement builder re-execution', e);
            }
          }
          
          showNotification(`Task created successfully: ${data.task_id}`, 'success');
          
          // Add to chat history
          const newChatItem = {
            id: data.task_id,
            type: 'user',
            content: finalUserPrompt,
            timestamp: new Date(),
            taskId: data.task_id
          };
          
          const botResponse = {
            id: `bot-${data.task_id}`,
            type: 'bot',
            content: `Task created successfully! Task ID: ${data.task_id}. SureAi is now processing your request using ${selectedWorkflow?.name || 'Default'} workflow.`,
            timestamp: new Date(),
            taskId: data.task_id
          };
          
          setChatHistory(prev => [...prev, newChatItem, botResponse]);
          setUserPrompt('');
          setFlfUrl('');
          setFlfFolderName('');
          setCustomAgentPrompts({});
          setSelectedWorkflow(null);
          setSelectedFiles([]);
          
          // Set the current task to show the split-screen interface
          setCurrentTask(data);
          setNewTaskMode(false);
          
          // Refresh tasks list
          fetchTasks();
        } else {
          const errorData = await response.json().catch(() => ({ error: 'Unknown error occurred' }));
          console.error('Task creation failed:', errorData);
          showNotification(`Error: ${errorData.error || 'Failed to create task'}`, 'error');
        }
      }
    } catch (error) {
      console.error('Task submission error:', error);
      showNotification(`Error: ${error.message || 'Failed to submit task'}`, 'error');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Configuration update
  const handleUpdateConfig = async () => {
    try {
      const payload = {};
      
      // Handle Gemini API keys with position-based updates
      if (apiKey.trim()) {
        // Update primary key at position 0
        const addPrimaryResponse = await fetch(`${API_BASE_URL}/config/gemini/keys`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            api_key: apiKey.trim(),
            position: 0  // Primary key position
          }),
        });
        
        if (!addPrimaryResponse.ok) {
          const error = await addPrimaryResponse.json();
          showNotification(`Error updating primary API key: ${error.error}`, 'error');
          return;
        }
      }
      
      // Update other keys if provided
      if (otherKey1.trim()) {
        const addOther1Response = await fetch(`${API_BASE_URL}/config/gemini/keys`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            api_key: otherKey1.trim(),
            position: 1  // Other key 1 position
          }),
        });
        
        if (!addOther1Response.ok) {
          const error = await addOther1Response.json();
          showNotification(`Error updating other API key 1: ${error.error}`, 'error');
          return;
        }
      }
      
      if (otherKey2.trim()) {
        const addOther2Response = await fetch(`${API_BASE_URL}/config/gemini/keys`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            api_key: otherKey2.trim(),
            position: 2  // Other key 2 position
          }),
        });
        
        if (!addOther2Response.ok) {
          const error = await addOther2Response.json();
          showNotification(`Error updating other API key 2: ${error.error}`, 'error');
          return;
        }
      }
      
      // Update other configuration
      if (selectedModel) payload.current_model = selectedModel;
      const llxprtPayload = {};
      if (llxprtApiKey.trim()) llxprtPayload.api_key = llxprtApiKey.trim();
      if (llxprtModel && llxprtModel.trim()) llxprtPayload.model = llxprtModel.trim();
      if (llxprtBaseUrl && llxprtBaseUrl.trim()) llxprtPayload.base_url = llxprtBaseUrl.trim();
      if (llxprtProvider && llxprtProvider.trim()) llxprtPayload.provider = llxprtProvider.trim();
      if (Object.keys(llxprtPayload).length > 0) payload.llxprt = llxprtPayload;

      // Update other config if there's anything to update
      if (Object.keys(payload).length > 0) {
        const response = await fetch(`${API_BASE_URL}/config`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        
        if (!response.ok) {
          const error = await response.json();
          showNotification(`Error updating configuration: ${error.error}`, 'error');
          return;
        }
      }
      
      showNotification('Configuration updated successfully', 'success');
      setApiKey('');
      setOtherKey1('');
      setOtherKey2('');
      setLlxprtApiKey('');
      fetchConfig();
      
    } catch (error) {
      showNotification('Network error occurred', 'error');
    }
  };

  // Agent prompt management
  const handleUpdateAgentPrompt = async (agentName, newPrompt) => {
    try {
      const response = await fetch(`${API_BASE_URL}/agents/prompts/${agentName}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ prompt: newPrompt }),
      });

      if (response.ok) {
        showNotification(`Updated prompt for ${agentName}`, 'success');
        fetchAgents();
        setEditingAgent(null);
        setEditingPrompt('');
      } else {
        const error = await response.json();
        showNotification(`Error: ${error.error}`, 'error');
      }
    } catch (error) {
      showNotification('Network error occurred', 'error');
    }
  };

  const handleResetAgentPrompt = async (agentName) => {
    try {
      const response = await fetch(`${API_BASE_URL}/agents/prompts/${agentName}/reset`, {
        method: 'POST',
      });

      if (response.ok) {
        showNotification(`Reset prompt for ${agentName} to default`, 'success');
        fetchAgents();
      } else {
        const error = await response.json();
        showNotification(`Error: ${error.error}`, 'error');
      }
    } catch (error) {
      showNotification('Network error occurred', 'error');
    }
  };

  // Workflow management
  const addAgentToWorkflow = (agentName) => {
    setCustomWorkflow([...customWorkflow, agentName]);
  };

  const removeAgentFromWorkflow = (index) => {
    const newWorkflow = customWorkflow.filter((_, i) => i !== index);
    setCustomWorkflow(newWorkflow);
  };

  const resetWorkflow = () => {
    setCustomWorkflow([...defaultWorkflow]);
  };

  // Filter out unwanted agents
  const filteredAgents = Object.fromEntries(
    Object.entries(agents).filter(
      ([agentName]) => agentName !== 'beastmode' && agentName !== 'design_architect'
    )
  );

  const filteredWorkflow = customWorkflow.filter(
    (agentName) => agentName !== 'beastmode' && agentName !== 'design_architect'
  );

  // Drag and drop handlers
  const handleDragEnd = (event) => {
    const { active, over } = event;

    if (active.id !== over.id) {
      setCustomWorkflow((items) => {
        const oldIndex = items.indexOf(active.id);
        const newIndex = items.indexOf(over.id);

        return arrayMove(items, oldIndex, newIndex);
      });
      showNotification('Workflow order updated', 'success');
    }
  };

  const handleDragStart = (event) => {
    console.log('Drag started:', event.active.id);
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'in_progress':
      case 'received':
        return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
      case 'paused':
        return <Pause className="w-4 h-4 text-yellow-500" />;
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Clock className="w-4 h-4 text-gray-400" />;
    }
  };

  // Render chat interface
  const renderChatInterface = () => {
    try {
      console.log('renderChatInterface called with:', { currentTask, selectedWorkflow });
      
      // If we have a current task, show the split-screen chat interface
      if (currentTask) {
        return (
          <ChatInterface
            task={currentTask}
            onBack={() => {
              setCurrentTask(null);
              setSelectedTaskId(null);
              setNewTaskMode(true);
            }}
            onRefresh={fetchTasks}
            selectedWorkflow={selectedWorkflow}
            onWorkflowSelect={(workflow) => {
              console.log('App.jsx onWorkflowSelect called with:', workflow);
              setSelectedWorkflow(workflow);
            }}
            agents={filteredAgents}
            selectedFiles={selectedFiles}
            onFileSelect={handleAddSelectedFiles}
            onFileRemove={handleRemoveSelectedFile}
          />
        );
      }
      
      // If we have any tasks but no current task, show new task interface only (recent tasks are in sidebar)
      if (tasks.length > 0 && !currentTask) {
        return (
          <div className="flex flex-col h-full bg-background">
            {/* Chat Header */}
            <div className="border-b border-border p-6 bg-card">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <img src="/logo.png" alt="SureAi" className="h-8 w-auto" />
                  <div>
                    <h2 className="text-lg font-semibold bmad-text-primary">SureAi Assistant</h2>
                    <p className="text-sm bmad-text-muted">Type it. Get it. Deployed. That's Sure AI.</p>
                  </div>
                </div>
              </div>
              
              {/* Workflow selector */}
              <div className="mt-4">
                <WorkflowSelector
                  onWorkflowSelect={(workflow) => {
                    setSelectedWorkflow(workflow);
                  }}
                  selectedWorkflow={selectedWorkflow}
                  agents={filteredAgents}
                />
              </div>
              
            </div>

            {/* New Task Section */}
            <div className="flex-1 overflow-y-auto p-4">
              <div className="max-w-2xl mx-auto">
                <h3 className="text-lg font-semibold bmad-text-primary mb-4">Create New Task</h3>
                <div className="space-y-4">
                  <Textarea
                    placeholder="Describe what you want to build. For example: 'Create a React todo app with authentication and data persistence'"
                    value={userPrompt}
                    onChange={(e) => setUserPrompt(e.target.value)}
                    className="min-h-[80px] resize-none bmad-input"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSubmitTask();
                      }
                    }}
                  />
                  
                  {/* File Upload */}
                  <div className="flex items-center gap-2">
                    <input
                      id="new-task-file-upload"
                      type="file"
                      multiple
                      onChange={(e) => {
                        handleAddSelectedFiles(e.target.files);
                        e.target.value = null;
                      }}
                      className="sr-only"
                      ref={fileInputRef}
                    />
                    <label htmlFor="new-task-file-upload">
                      <Button variant="outline" size="sm" asChild>
                        <span className="inline-flex items-center">
                          <Upload className="w-4 h-4 mr-2" /> Attach Files
                        </span>
                      </Button>
                    </label>
                    {selectedFiles?.length > 0 && (
                      <span className="text-xs bmad-text-muted">{selectedFiles.length} file(s) selected</span>
                    )}
                  </div>

                  {/* Selected Files */}
                  {selectedFiles?.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {selectedFiles.map((f, idx) => (
                        <div key={`${f.name}:${f.size}:${idx}`} className="flex items-center gap-2 px-3 py-1 rounded border bmad-card text-sm">
                          <span className="truncate max-w-[200px]" title={`${f.name} (${(f.size/1024).toFixed(1)} KB)`}>
                            {f.name}
                          </span>
                          <button
                            className="text-red-400 hover:text-red-500"
                            onClick={() => handleRemoveSelectedFile(idx)}
                            aria-label={`Remove ${f.name}`}
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* FLF Workflow Inputs */}
                  {selectedWorkflow && selectedWorkflow.name && selectedWorkflow.name.toLowerCase().includes('flf') && (
                    <div className="space-y-3 border border-green-500 p-3 rounded">
                      <div className="text-xs text-green-500 font-medium">FLF Workflow Inputs</div>
                      <div className="space-y-2">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Repository URL</label>
                          <Input
                            placeholder="Enter repository URL to clone..."
                            value={flfUrl}
                            onChange={(e) => setFlfUrl(e.target.value)}
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">Folder Name</label>
                          <Input
                            placeholder="Enter folder name to analyze..."
                            value={flfFolderName}
                            onChange={(e) => setFlfFolderName(e.target.value)}
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  <Button 
                    onClick={handleSubmitTask} 
                    disabled={(!userPrompt.trim() && !(selectedWorkflow && selectedWorkflow.name && selectedWorkflow.name.toLowerCase().includes('flf'))) || 
                             (selectedWorkflow && selectedWorkflow.name && selectedWorkflow.name.toLowerCase().includes('flf') && (!flfFolderName.trim() || !flfUrl.trim())) || 
                             isSubmitting}
                    className="w-full bmad-button-primary"
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Creating Task...
                      </>
                    ) : (
                      <>
                        <Send className="w-4 h-4 mr-2" />
                        Create Task
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          </div>
        );
      }
      
      // If no tasks exist, show simple new task interface
      return (
        <div className="flex flex-col h-full bg-background">
          {/* Chat Header */}
          <div className="border-b border-border p-6 bg-card">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <img src="/logo.png" alt="SureAi" className="h-8 w-auto" />
                <div>
                  <h2 className="text-lg font-semibold bmad-text-primary">SureAi Assistant</h2>
                  <p className="text-sm bmad-text-muted">Type it. Get it. Deployed. That's Sure AI.</p>
                </div>
              </div>
            </div>
            
            {/* Workflow selector */}
            <div className="mt-4">
              <WorkflowSelector
                onWorkflowSelect={(workflow) => {
                  setSelectedWorkflow(workflow);
                  // Reset base project selection when workflow changes
                }}
                selectedWorkflow={selectedWorkflow}
                agents={filteredAgents}
              />
            </div>
                          
          </div>

          {/* New Task Section */}
          <div className="flex-1 flex items-center justify-center p-6">
            <div className="max-w-2xl w-full space-y-6">
              <div className="text-center">
                <Bot className="w-16 h-16 mx-auto mb-4 bmad-text-muted" />
                <h3 className="text-xl font-semibold bmad-text-primary mb-2">Create Your First Task</h3>
                <p className="bmad-text-muted">Describe what you want to build and we'll get started</p>
              </div>
              
              <div className="space-y-4">
                <Textarea
                  placeholder="Describe what you want to build. For example: 'Create a React todo app with authentication and data persistence'"
                  value={userPrompt}
                  onChange={(e) => setUserPrompt(e.target.value)}
                  className="min-h-[100px] resize-none bmad-input"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmitTask();
                    }
                  }}
                />
                
                {/* File Upload */}
                <div className="flex items-center gap-2">
                  <input
                    id="first-task-file-upload"
                    type="file"
                    multiple
                    onChange={(e) => {
                      handleAddSelectedFiles(e.target.files);
                      e.target.value = null;
                    }}
                    className="sr-only"
                    ref={fileInputRef}
                  />
                  <label htmlFor="first-task-file-upload">
                    <Button variant="outline" size="sm" asChild>
                      <span className="inline-flex items-center">
                        <Upload className="w-4 h-4 mr-2" /> Attach Files
                      </span>
                    </Button>
                  </label>
                  {selectedFiles?.length > 0 && (
                    <span className="text-xs bmad-text-muted">{selectedFiles.length} file(s) selected</span>
                  )}
                </div>

                {/* Selected Files */}
                {selectedFiles?.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {selectedFiles.map((f, idx) => (
                      <div key={`${f.name}:${f.size}:${idx}`} className="flex items-center gap-2 px-3 py-1 rounded border bmad-card text-sm">
                        <span className="truncate max-w-[200px]" title={`${f.name} (${(f.size/1024).toFixed(1)} KB)`}>
                          {f.name}
                        </span>
                        <button
                          className="text-red-400 hover:text-red-500"
                          onClick={() => handleRemoveSelectedFile(idx)}
                          aria-label={`Remove ${f.name}`}
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                {/* FLF Workflow Inputs */}
                {selectedWorkflow && selectedWorkflow.name && selectedWorkflow.name.toLowerCase().includes('flf') && (
                  <div className="space-y-3 border border-green-500 p-3 rounded">
                    <div className="text-xs text-green-500 font-medium">FLF Workflow Inputs</div>
                    <div className="space-y-2">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Repository URL</label>
                        <Input
                          placeholder="Enter repository URL to clone..."
                          value={flfUrl}
                          onChange={(e) => setFlfUrl(e.target.value)}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Folder Name</label>
                        <Input
                          placeholder="Enter folder name to analyze..."
                          value={flfFolderName}
                          onChange={(e) => setFlfFolderName(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                )}

                <Button 
                  onClick={handleSubmitTask} 
                  disabled={(!userPrompt.trim() && !(selectedWorkflow && selectedWorkflow.name && selectedWorkflow.name.toLowerCase().includes('flf'))) || 
                           (selectedWorkflow && selectedWorkflow.name && selectedWorkflow.name.toLowerCase().includes('flf') && (!flfFolderName.trim() || !flfUrl.trim())) || 
                           isSubmitting}
                  className="w-full bmad-button-primary"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Creating Task...
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4 mr-2" />
                      Create Task
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        </div>
      );
    } catch (error) {
      console.error('Error rendering chat interface:', error);
      return (
        <div className="flex flex-col h-full items-center justify-center bg-background">
          <div className="text-center bmad-text-muted">
            <Bot className="w-12 h-12 mx-auto mb-4 bmad-text-muted" />
            <p>Error loading chat interface</p>
            <button 
              onClick={() => window.location.reload()}
              className="mt-4 bmad-button-primary"
            >
              Reload Page
            </button>
          </div>
        </div>
      );
    }
  };

  // Render agents section
  const renderAgentsSection = () => (
    <div className="space-y-6">
      <AgentManager />
    </div>
  );

  // Render workflows section
  const renderWorkflowsSection = () => (
    <div className="space-y-6">
      <WorkflowManager 
        agents={filteredAgents} 
        onWorkflowSelect={(workflow) => {
          setSelectedWorkflow(workflow);
          const seq = Array.isArray(workflow.agent_sequence)
            ? workflow.agent_sequence
            : (typeof workflow.agent_sequence === 'string'
                ? (() => { try { return JSON.parse(workflow.agent_sequence); } catch { return []; } })()
                : []);
          setCustomWorkflow(seq);
        }}
      />
    </div>
  );

  // Render monitor section
  const renderMonitorSection = () => {
    try {
      return (
        <div className="space-y-6">
          <div className="border-b pb-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold bmad-text-primary">Task Monitor</h2>
                <p className="bmad-text-muted">Track the progress of your development tasks</p>
              </div>
              {isWaitingForTask && (
                <div className="flex items-center space-x-2 text-blue-400">
                  <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                  <span className="text-sm">Global auto-refresh every 1s</span>
                </div>
              )}
            </div>
          </div>
          
          {/* Waiting for JobPro to create task */}
          {isWaitingForTask && (!tasks || tasks.length === 0) && (
            <Card className="bmad-card border-blue-500/40 bg-blue-500/10">
              <CardContent className="p-6">
                <div className="text-center space-y-4">
                  <div className="flex items-center justify-center space-x-2">
                    <RefreshCw className="w-6 h-6 animate-spin text-blue-400" />
                    <span className="text-lg font-semibold text-blue-300">Securing VM and Processing Request</span>
                  </div>
                  <div className="space-y-2">
                    <p className="text-blue-200">
                      Your request has been queued with JobPro and is being processed.
                    </p>
                    <p className="text-sm text-blue-300/80">
                      Prompt: "{waitingTaskPrompt}"
                    </p>
                    <p className="text-xs text-blue-300/60">
                      The system will automatically refresh every 1 second to detect when your task is created.
                    </p>
                  </div>
                  <div className="flex items-center justify-center space-x-2 text-xs text-blue-300/60">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                    <span>Waiting for JobPro to process your request...</span>
                  </div>
                  {elapsedTime > 0 && (
                    <div className="text-xs text-blue-300/50">
                      Elapsed time: {elapsedTime}s
                    </div>
                  )}
                  <div className="text-xs text-blue-300/40 mt-2">
                    Debug: Auto-refresh active • Checking every 1s • Global refresh enabled
                  </div>
                  
                  {/* Debug Panel */}
                  {process.env.NODE_ENV === 'development' && (
                    <div className="mt-4 p-3 bg-blue-500/20 border border-blue-500/30 rounded-lg">
                      <div className="text-xs text-blue-300 font-mono">
                        <div>Waiting: {isWaitingForTask ? 'Yes' : 'No'}</div>
                        <div>Prompt: "{waitingTaskPrompt}"</div>
                        <div>Tasks Count: {tasks.length}</div>
                        <div>Global Refresh: {isWaitingForTask ? 'Active' : 'Inactive'}</div>
                        <div>Elapsed: {elapsedTime}s</div>
                        <div>Section: {activeSection}</div>
                        <div>Last Fetch: {lastFetchTime ? new Date(lastFetchTime).toLocaleTimeString() : 'Never'}</div>
                      </div>
                      <div className="mt-2 flex items-center space-x-2">
                        <div className={`w-2 h-2 rounded-full ${isWaitingForTask ? 'bg-green-400 animate-pulse' : 'bg-red-400'}`}></div>
                        <span className="text-xs text-blue-300">
                          {isWaitingForTask ? 'Global auto-refresh running' : 'Auto-refresh stopped'}
                        </span>
                      </div>
                    </div>
                  )}
                  
                  {/* Manual Refresh Button */}
                  <div className="mt-4 pt-2 border-t border-blue-500/30">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        console.log('🔄 Manual refresh triggered');
                        fetchTasks();
                        showNotification('Manually refreshing task list...', 'info');
                      }}
                      className="border-blue-400 text-blue-300 hover:bg-blue-500/20"
                    >
                      <RefreshCw className="w-4 h-4 mr-2" />
                      Check Now
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* Loading indicator when fetching tasks */}
          {fetchingTasks && !isWaitingForTask && (
            <Card className="bmad-card border-blue-500/40 bg-blue-500/10">
              <CardContent className="p-6">
                <div className="flex items-center justify-center space-x-2">
                  <RefreshCw className="w-6 h-6 animate-spin text-blue-400" />
                  <span className="text-blue-300">Refreshing task list...</span>
                </div>
              </CardContent>
            </Card>
          )}
          
          {/* Task Cards Selector */}
          {tasks && tasks.length > 0 && (
            <div className="grid md:grid-cols-3 gap-3">
              {tasks.map((t) => (
                <Card key={`card-${t.task_id}`} className={`bmad-card cursor-pointer ${selectedTaskId === t.task_id ? 'ring-2 ring-primary' : ''}`}
                  onClick={() => setSelectedTaskId(selectedTaskId === t.task_id ? null : t.task_id)}>
                  <div className="p-3">
                    <div className="flex items-center justify-between">
                      <div className="font-medium bmad-text-primary">Task {t.task_id.slice(0,8)}</div>
                      <div className="text-xs bmad-text-muted">{(t.status || '').replace('_',' ')}</div>
                    </div>
                    <div className="text-xs bmad-text-muted truncate mt-1">{t.prompt}</div>
                  </div>
                </Card>
              ))}
            </div>
          )}
          
          {!tasks || tasks.length === 0 ? (
            <div className="text-center py-8 bmad-text-muted">
              <Activity className="w-12 h-12 mx-auto mb-4 bmad-text-muted" />
              <p>No tasks created yet. Create your first task to get started.</p>
            </div>
          ) : (
            (selectedTaskId ? tasks.filter((t) => t.task_id === selectedTaskId) : tasks).map((task) => {
              try {
                return (
                  <TaskMonitor 
                    key={task.task_id} 
                    task={task} 
                    onRefresh={fetchTasks}
                  />
                );
              } catch (taskError) {
                console.error('Error rendering task:', task, taskError);
                return (
                  <Card key={task.task_id} className="p-4 bmad-card border-red-200">
                    <div className="text-red-600">
                      <p>Error displaying task: {task.task_id}</p>
                      <p className="text-xs">{taskError.message}</p>
                    </div>
                  </Card>
                );
              }
            })
          )}
        </div>
      );
    } catch (error) {
      console.error('Error rendering monitor section:', error);
      return (
        <div className="space-y-6">
          <div className="border-b pb-4">
            <h2 className="text-2xl font-bold bmad-text-primary">Task Monitor</h2>
            <p className="bmad-text-muted">Track the progress of your development tasks</p>
          </div>
          
          <div className="text-center py-8 bmad-text-muted">
            <Activity className="w-12 h-12 mx-auto mb-4 bmad-text-muted" />
            <p>Error loading task monitor</p>
            <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
              <p className="text-red-300 text-sm mb-2">Error details: {error.message}</p>
              <Button 
                onClick={() => {
                  fetchTasks();
                  showNotification('Refreshing task list...', 'info');
                }}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Retry
              </Button>
            </div>
          </div>
        </div>
      );
    }
  };

  // Render settings section
  const renderSettingsSection = () => (
    <div className="space-y-6">
      <div className="border-b pb-4">
        <h2 className="text-2xl font-bold bmad-text-primary">System Configuration</h2>
        <p className="bmad-text-muted">Configure API keys, models, and system settings</p>
      </div>
      
      <div className="grid gap-6">
        {/* API Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="bmad-text-primary">API Configuration</CardTitle>
            <CardDescription className="bmad-text-muted">Configure your Gemini API settings with multiple keys for automatic rotation</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="apiKey" className="bmad-text-primary">Primary Gemini API Key</Label>
              <Input
                id="apiKey"
                type="password"
                placeholder="Enter your primary Gemini API key"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="bmad-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="otherKey1" className="bmad-text-muted">Other API Key 1</Label>
              <Input
                id="otherKey1"
                type="password"
                placeholder="Enter another Gemini API key (optional)"
                value={otherKey1}
                onChange={(e) => setOtherKey1(e.target.value)}
                className="bmad-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="otherKey2" className="bmad-text-muted">Other API Key 2</Label>
              <Input
                id="otherKey2"
                type="password"
                placeholder="Enter another Gemini API key (optional)"
                value={otherKey2}
                onChange={(e) => setOtherKey2(e.target.value)}
                className="bmad-input"
              />
            </div>
            
            {/* API Key Status Display */}
            {config.gemini_api_keys_status && (
              <div className="space-y-3 p-4 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <Label className="bmad-text-primary font-semibold">Current API Key Status</Label>
                  <div className="flex gap-2">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={async () => {
                        try {
                          const response = await fetch(`${API_BASE_URL}/config/gemini/keys/reset`, { method: 'POST' });
                          if (response.ok) {
                            showNotification('Exhausted keys reset successfully', 'success');
                            fetchConfig();
                          } else {
                            const error = await response.json();
                            showNotification(`Error: ${error.error}`, 'error');
                          }
                        } catch (error) {
                          showNotification('Network error occurred', 'error');
                        }
                      }}
                    >
                      Reset Exhausted
                    </Button>
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={async () => {
                        try {
                          const response = await fetch(`${API_BASE_URL}/config/gemini/keys/rotate`, { method: 'POST' });
                          if (response.ok) {
                            showNotification('API key rotated successfully', 'success');
                            fetchConfig();
                          } else {
                            const error = await response.json();
                            showNotification(`Error: ${error.error}`, 'error');
                          }
                        } catch (error) {
                          showNotification('Network error occurred', 'error');
                        }
                      }}
                    >
                      Rotate Key
                    </Button>
                  </div>
                </div>
                <div className="grid gap-2 text-sm">
                  <div className="flex justify-between">
                    <span className="bmad-text-muted">Total Keys:</span>
                    <span className="font-medium">{config.gemini_api_keys_status.total_keys || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="bmad-text-muted">Available Keys:</span>
                    <span className="font-medium">{config.gemini_api_keys_status.available_keys_count || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="bmad-text-muted">Current Key:</span>
                    <span className="font-medium">
                      {config.gemini_api_keys_status.current_key_index !== undefined 
                        ? `Key ${(config.gemini_api_keys_status.current_key_index + 1)}` 
                        : 'None'}
                    </span>
                  </div>
                  
                  {/* Real-time rotation status */}
                  {keyRotationEvents.length > 0 && keyRotationEvents[0]?.type === 'key_rotation' && (
                    <div className="mt-2 p-2 bg-green-100 dark:bg-green-900/20 rounded border border-green-300 dark:border-green-600">
                      <div className="flex items-center gap-2 text-xs text-green-800 dark:text-green-200">
                        <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                        <span className="font-medium">🔄 Key rotation in progress...</span>
                      </div>
                      <div className="text-xs text-green-700 dark:text-green-300 mt-1">
                        {keyRotationEvents[0]?.details?.from} → {keyRotationEvents[0]?.details?.to}
                      </div>
                    </div>
                  )}
                </div>
                {config.gemini_api_keys_status.keys && config.gemini_api_keys_status.keys.length > 0 && (
                  <div className="space-y-2">
                    <Label className="bmad-text-muted text-xs">Key Details:</Label>
                    {config.gemini_api_keys_status.keys.map((key, index) => (
                      <div key={index} className="flex items-center justify-between text-xs p-2 bg-gray-100 dark:bg-gray-800 rounded border border-gray-200 dark:border-gray-700">
                        <span className="bmad-text-muted">
                          Key {index + 1} {key.is_current ? '(Current)' : ''}
                        </span>
                        <div className="flex items-center gap-2">
                          {key.is_exhausted ? (
                            <Badge variant="destructive" className="text-xs">Exhausted</Badge>
                          ) : (
                            <Badge variant="default" className="text-xs">Active</Badge>
                          )}
                          {key.last_4_chars && (
                            <span className="text-gray-600 dark:text-gray-400 font-mono">...{key.last_4_chars}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            
            {/* Key Rotation Events Display */}
            {keyRotationEvents.length > 0 && (
              <div className="space-y-3 p-4 bg-blue-100 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-700">
                <div className="flex items-center justify-between">
                  <Label className="bmad-text-primary font-semibold">🔔 Recent Key Events</Label>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => setKeyRotationEvents([])}
                  >
                    Clear Events
                  </Button>
                </div>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {keyRotationEvents.map((event) => (
                    <div key={event.id} className={`p-3 rounded-lg border text-sm ${
                      event.type === 'key_rotation' 
                        ? 'bg-green-100 dark:bg-green-900/20 border-green-200 dark:border-green-700' 
                        : 'bg-yellow-100 dark:bg-yellow-900/20 border-yellow-200 dark:border-yellow-700'
                    }`}>
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900 dark:text-gray-100">
                            {event.message}
                          </div>
                          <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                            {new Date(event.timestamp).toLocaleString()}
                          </div>
                          {event.details && (
                            <div className="mt-2 text-xs text-gray-700 dark:text-gray-300">
                              {event.type === 'key_rotation' ? (
                                <div>
                                  <span className="font-medium">From:</span> {event.details.from} ({event.details.oldKeyStatus})<br/>
                                  <span className="font-medium">To:</span> {event.details.to} ({event.details.newKeyStatus})<br/>
                                  <span className="font-medium">Reason:</span> {event.details.reason}
                                </div>
                              ) : (
                                <div>
                                  <span className="font-medium">Key:</span> {event.details.keyIndex}<br/>
                                  <span className="font-medium">Reason:</span> {event.details.reason}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="ml-2">
                          {event.type === 'key_rotation' ? (
                            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                          ) : (
                            <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            <div className="space-y-2">
              <Label htmlFor="model" className="bmad-text-primary">Model Selection</Label>
              <Select value={selectedModel} onValueChange={setSelectedModel}>
                <SelectTrigger className="bmad-input">
                  <SelectValue placeholder="Select a model" />
                </SelectTrigger>
                <SelectContent>
                  {availableModels.map((model) => (
                    <SelectItem key={model} value={model}>
                      {model}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <Separator className="my-2" />
            <div className="space-y-1">
              <CardTitle className="text-base bmad-text-primary">LLXPRT (OpenRouter) Configuration</CardTitle>
              <CardDescription className="bmad-text-muted">Use OpenRouter-compatible models with LLXPRT CLI</CardDescription>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="llxprtApiKey" className="bmad-text-primary">OpenRouter API Key</Label>
                <Input
                  id="llxprtApiKey"
                  type="password"
                  placeholder="Enter your OpenRouter API key"
                  value={llxprtApiKey}
                  onChange={(e) => setLlxprtApiKey(e.target.value)}
                  className="bmad-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="llxprtModel" className="bmad-text-primary">Model</Label>
                <Input
                  id="llxprtModel"
                  placeholder="qwen/qwen3-coder"
                  value={llxprtModel}
                  onChange={(e) => setLlxprtModel(e.target.value)}
                  className="bmad-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="llxprtBaseUrl" className="bmad-text-primary">Base URL</Label>
                <Input
                  id="llxprtBaseUrl"
                  placeholder="https://openrouter.aihttp://157.66.191.31:9191http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006/api/v1"
                  value={llxprtBaseUrl}
                  onChange={(e) => setLlxprtBaseUrl(e.target.value)}
                  className="bmad-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="llxprtProvider" className="bmad-text-primary">Provider</Label>
                <Input
                  id="llxprtProvider"
                  placeholder="openai"
                  value={llxprtProvider}
                  onChange={(e) => setLlxprtProvider(e.target.value)}
                  className="bmad-input"
                />
              </div>
            </div>
            <Button onClick={handleUpdateConfig}>
              <Save className="w-4 h-4 mr-2" />
              Update Configuration
            </Button>
          </CardContent>
        </Card>
        
        {/* System Status */}
        <Card>
          <CardHeader>
            <CardTitle className="bmad-text-primary">System Status</CardTitle>
            <CardDescription className="bmad-text-muted">Current system configuration and usage statistics</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="bmad-text-primary">Current Model</Label>
                <div className="p-2 bmad-card rounded">
                  <span className="bmad-text-primary">{config.current_model || 'Not configured'}</span>
                </div>
              </div>
              <div className="space-y-2">
                <Label className="bmad-text-primary">API Status</Label>
                <div className="p-2 bmad-card rounded">
                  <span className="bmad-text-primary">{config.api_key_configured ? 'Configured' : 'Not configured'}</span>
                </div>
              </div>
            </div>
            
            {/* Usage Statistics */}
            <div className="space-y-2">
              <Label className="bmad-text-primary">Usage Statistics</Label>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bmad-card rounded">
                  <div className="text-sm bmad-accent">Total Requests</div>
                  <div className="text-lg font-semibold bmad-text-primary">{usage.total_requests || 0}</div>
                </div>
                <div className="p-3 bmad-card rounded">
                  <div className="text-sm bmad-accent">Total Tokens</div>
                  <div className="text-lg font-semibold bmad-text-primary">{usage.total_tokens || 0}</div>
                </div>
                <div className="p-3 bmad-card rounded">
                  <div className="text-sm bmad-accent">Total Cost</div>
                  <div className="text-lg font-semibold bmad-text-primary">${(usage.total_cost || 0).toFixed(4)}</div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );

  return (
    <div className="app dark-theme">
      {/* Top Navigation per provided UI */}
      {/* Top brand bar removed per request */}
      {/* Notification */}
      {notification && (
        <div className="fixed top-4 right-4 z-50">
          <Alert className={`bmad-card ${notification.type === 'error' ? 'border-red-500' : 
                                   notification.type === 'success' ? 'border-green-500' : 
                                   'border-blue-500'}`}>
            <AlertDescription className="bmad-text-primary">
              {notification.message}
            </AlertDescription>
          </Alert>
        </div>
      )}
      
      {/* Key Rotation Banner */}
      {keyRotationEvents.length > 0 && keyRotationEvents[0]?.type === 'key_rotation' && (
        <div className="fixed top-4 left-1/2 transform -translate-x-1/2 z-40">
          <Alert className="bmad-card border-green-500 bg-green-50">
            <AlertDescription className="bmad-text-primary">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                <span className="font-medium">
                  🔄 API Key Rotation: {keyRotationEvents[0]?.details?.from} → {keyRotationEvents[0]?.details?.to}
                </span>
              </div>
            </AlertDescription>
          </Alert>
        </div>
      )}

      {/* Debug Info - Remove in production */}
      {process.env.NODE_ENV === 'development' && (
        <div className="fixed top-4 left-4 z-40 bmad-card p-2 rounded border text-xs">
          <div className="bmad-text-primary">Active Section: {activeSection}</div>
          <div className="bmad-text-primary">Tasks: {tasks.length}</div>
          <div className="bmad-text-primary">Chat History: {chatHistory.length}</div>
        </div>
      )}

      <div className="flex h-full">
        {/* Sidebar */}
        <div className={`${sidebarOpen ? 'w-64' : 'w-16'} bmad-sidebar transition-all duration-300 flex flex-col`}>
          {/* Sidebar Header */}
          <div className="p-4 border-b border-sidebar-border">
            <div className="flex items-center justify-between">
              {sidebarOpen && (
                <div>
                  <h1 className="text-xl font-bold bmad-text-primary">SureAi</h1>
                  <p className="text-xs bmad-text-muted">Multi-Agent System</p>
                </div>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="bmad-button-secondary"
              >
                {sidebarOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
              </Button>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-2">
            <div className="space-y-1">
              {navigationItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    onClick={() => {
                      setIsSwitching(true);
                      setTimeout(() => {
                        setActiveSection(item.id);
                        setTimeout(() => setIsSwitching(false), 300);
                      }, 0);
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium smooth-transition ${
                      activeSection === item.id
                        ? 'bmad-button-primary'
                        : 'bmad-button-secondary hover:bg-accent'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {sidebarOpen && (
                      <div className="flex-1 text-left">
                        <div className="bmad-text-primary">{item.label}</div>
                        {sidebarOpen && (
                          <div className="text-xs bmad-text-muted truncate">
                            {item.description}
                          </div>
                        )}
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
          </nav>

          {/* Chat History */}
          {sidebarOpen && activeSection === 'chat' && (
            <div className="border-t border-sidebar-border p-4">
              <div className="flex items-center gap-2 mb-3">
                <History className="w-4 h-4 bmad-text-primary" />
                <span className="text-sm font-medium bmad-text-primary">Recent Tasks</span>
              </div>
              {/* Missing API key notice */}
              {config && config.api_key_configured === false && (
                <div className="mb-3 p-2 rounded border border-red-500/40 bg-red-500/10 text-xs text-red-300">
                  No API key configured. Go to Settings → API Configuration to add keys.
                </div>
              )}
              <ScrollArea className="h-32">
                <div className="space-y-2">
                  {tasks.slice(0, 5).map((task) => (
                    <button
                      key={task.task_id}
                      onClick={() => {
                        setCurrentTask(task);
                        setSelectedTaskId(task.task_id);
                        setActiveSection('chat');
                        setNewTaskMode(false);
                      }}
                      className="w-full text-left p-2 rounded text-xs bmad-button-secondary hover:bg-accent transition-colors"
                    >
                      <div className="font-medium truncate bmad-text-primary">
                        Task {task.task_id.slice(0, 8)}
                      </div>
                      <div className="bmad-text-muted truncate">
                        {typeof task.prompt === 'string' ? task.prompt.substring(0, 50) + '...' : 'No prompt available'}
                      </div>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="flex-1 flex flex-col bg-background">
          {/* Initial Loading State */}
          {initialLoading && (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-4">
                <RefreshCw className="w-12 h-12 animate-spin text-blue-400 mx-auto" />
                <div className="space-y-2">
                  <h2 className="text-xl font-semibold text-blue-300">Initializing SureAI System</h2>
                  <p className="text-blue-200 text-sm">Loading configuration and connecting to services...</p>
                </div>
              </div>
            </div>
          )}
          
          {/* Content Area */}
          {!initialLoading && (
            <div className={`flex-1 overflow-hidden ${isSwitching ? 'fade-slide-in' : 'fade-slide-in'}`}>
              {activeSection === 'chat' && (
                <div className="h-full overflow-y-auto bg-background smooth-transition">
                  <ErrorBoundary>
                    {renderChatInterface()}
                  </ErrorBoundary>
                </div>
              )}
              {activeSection === 'agents' && (
                <div className="h-full overflow-y-auto p-6 bg-background">
                  {(() => {
                    try {
                      return renderAgentsSection();
                    } catch (error) {
                      console.error('Error rendering agents section:', error);
                      return (
                        <div className="text-center py-8 bmad-text-muted">
                          <p>Error loading agents section</p>
                          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                            <p className="text-red-300 text-sm mb-2">Error details: {error.message}</p>
                            <Button 
                              onClick={() => {
                                fetchAgents();
                                showNotification('Refreshing agents...', 'info');
                              }}
                              className="bg-red-600 hover:bg-red-700 text-white"
                            >
                              <RefreshCw className="w-4 h-4 mr-2" />
                              Retry
                            </Button>
                          </div>
                        </div>
                      );
                    }
                  })()}
                </div>
              )}
              {activeSection === 'workflows' && (
                <div className="h-full overflow-y-auto p-6 bg-background">
                  {(() => {
                    try {
                      return renderWorkflowsSection();
                    } catch (error) {
                      console.error('Error rendering workflows section:', error);
                      return (
                        <div className="text-center py-8 bmad-text-muted">
                          <p>Error loading workflows section</p>
                          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                            <p className="text-red-300 text-sm mb-2">Error details: {error.message}</p>
                            <Button 
                              onClick={() => {
                                // Refresh workflows data
                                showNotification('Refreshing workflows...', 'info');
                              }}
                              className="bg-red-600 hover:bg-red-700 text-white"
                            >
                              <RefreshCw className="w-4 h-4 mr-2" />
                              Retry
                            </Button>
                          </div>
                        </div>
                      );
                    }
                  })()}
                </div>
              )}
              {activeSection === 'mcp' && (
                <div className="h-full overflow-y-auto p-6 bg-background">
                  <MCPManager />
                </div>
              )}
              {activeSection === 'monitor' && (
                <div className="h-full overflow-y-auto p-6 bg-background">
                  {(() => {
                    try {
                      return renderMonitorSection();
                    } catch (error) {
                      console.error('Error rendering monitor section:', error);
                      return (
                        <div className="text-center py-8 bmad-text-muted">
                          <p>Error loading monitor section</p>
                          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                            <p className="text-red-300 text-sm mb-2">Error details: {error.message}</p>
                            <Button 
                              onClick={() => {
                                fetchTasks();
                                showNotification('Refreshing task list...', 'info');
                              }}
                              className="bg-red-600 hover:bg-red-700 text-white"
                            >
                              <RefreshCw className="w-4 h-4 mr-2" />
                              Retry
                            </Button>
                          </div>
                        </div>
                      );
                    }
                  })()}
                </div>
              )}
              {activeSection === 'settings' && (
                <div className="h-full overflow-y-auto p-6 bg-background">
                  {(() => {
                    try {
                      return renderSettingsSection();
                    } catch (error) {
                      console.error('Error rendering settings section:', error);
                      return (
                        <div className="text-center py-8 bmad-text-muted">
                          <p>Error loading settings section</p>
                          <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                            <p className="text-red-300 text-sm mb-2">Error details: {error.message}</p>
                            <Button 
                              onClick={() => {
                                fetchConfig();
                                showNotification('Refreshing configuration...', 'info');
                              }}
                              className="bg-red-600 hover:bg-red-700 text-white"
                            >
                              <RefreshCw className="w-4 h-4 mr-2" />
                              Retry
                            </Button>
                          </div>
                        </div>
                      );
                    }
                  })()}
                </div>
              )}
              {/* Fallback for unknown sections */}
              {!['chat', 'agents', 'workflows', 'mcp', 'monitor', 'settings'].includes(activeSection) && (
                <div className="h-full overflow-y-auto p-6 bg-background">
                  <div className="text-center py-8 bmad-text-muted">
                    <p>Unknown section: {activeSection}</p>
                    <Button 
                      onClick={() => setActiveSection('chat')}
                      className="mt-4 bg-blue-600 hover:bg-blue-700 text-white"
                    >
                      Go to Chat
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;

