import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { ScrollArea } from './ui/scroll-area';
import { Textarea } from './ui/textarea';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { 
  ArrowLeft, 
  Send, 
  Eye, 
  EyeOff, 
  RefreshCw, 
  Play, 
  RotateCcw, 
  X,
  Activity,
  CheckCircle,
  Clock,
  FileText,
  Bot,
  Upload,
  Folder,
  ExternalLink,
  X as CloseIcon
} from 'lucide-react';
import ChatMessage from './ChatMessage';
import WorkflowSelector from './WorkflowSelector';
import { API_BASE_URL } from '../config/environment';
import jobProService from '../services/jobProService.js';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogTrigger, DialogClose } from './ui/dialog';
import SubworkflowSlider from './SubworkflowSlider';

const ChatInterface = ({ 
  task, 
  onBack, 
  onRefresh, 
  selectedWorkflow, 
  onWorkflowSelect,
  agents,
  selectedFiles,
  onFileSelect,
  onFileRemove
}) => {
  console.log('ChatInterface mounted with selectedWorkflow:', selectedWorkflow);
  const [showRightPanel, setShowRightPanel] = useState(true); // Default to showing right panel
  const [monitorData, setMonitorData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [visibleLogs, setVisibleLogs] = useState([]);
  const logsBufferRef = useRef([]);
  const lastSeqRef = useRef(0);
  const [userPrompt, setUserPrompt] = useState('');
  const [flfFolderName, setFlfFolderName] = useState(''); // New state for FLF folder name
  const [flfUrl, setFlfUrl] = useState(''); // New state for FLF URL
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [tokenCounts, setTokenCounts] = useState({
    input: 0,
    output: 0,
    total: 0
  });
  const [taskProgress, setTaskProgress] = useState({
    completed: 0,
    total: 15,
    percentage: 0
  });
  const [environmentStatus, setEnvironmentStatus] = useState([]);
  const [fileBrowser, setFileBrowser] = useState([]);
  const [rootFileBrowser, setRootFileBrowser] = useState([]);
  const [allFilesIndex, setAllFilesIndex] = useState([]);
  const [fileSearchQuery, setFileSearchQuery] = useState('');
  const [notification, setNotification] = useState(null);
  const [showFileDialog, setShowFileDialog] = useState(false);
  const [fileDialogPath, setFileDialogPath] = useState('');
  const [fileDialogEntries, setFileDialogEntries] = useState([]);
  const [fileDialogLoading, setFileDialogLoading] = useState(false);
  const [fileContentPath, setFileContentPath] = useState('');
  const [fileContent, setFileContent] = useState('');
  const [frontendUrl, setFrontendUrl] = useState('');
  const [creatingShare, setCreatingShare] = useState(false);
  const [shareError, setShareError] = useState(null);
  const [apiStatus, setApiStatus] = useState({
    quotaExhausted: false,
    keyRotation: false,
    noKeysAvailable: false,
    retryAttempts: 0,
    lastError: null
  });
  const [memory, setMemory] = useState({ history: [] });
  const [showMemoryModal, setShowMemoryModal] = useState(false);
  const [memoryDraft, setMemoryDraft] = useState('');
  const [savingMemory, setSavingMemory] = useState(false);
  
  const logsEndRef = useRef(null);
  const refreshIntervalRef = useRef(null);
  const fileInputRef = useRef(null);
  const lastLogsKeyRef = useRef('');
  const [autoScrollLogs, setAutoScrollLogs] = useState(true);
  // New: allow multi-workflow sequencing
  const [selectedWorkflowSequence, setSelectedWorkflowSequence] = useState([]);
  // Sub-workflow navigation
  const [currentGroupIndex, setCurrentGroupIndex] = useState(0);

  // Build combined sequence and sub-workflow ranges for UI labeling
  const buildCombinedSequenceInfo = () => {
    const groups = (selectedWorkflowSequence && selectedWorkflowSequence.length > 0)
      ? selectedWorkflowSequence.map((wf) => ({
          id: wf.id,
          name: wf.name,
          seq: normalizeSequence(wf.agent_sequence)
        }))
      : [];
    let combined = groups.flatMap(g => g.seq);
    
    // Check if the selected workflow itself has sub-workflows (like End-to-End Plan + Execute)
    if (selectedWorkflow && selectedWorkflow.agent_sequence) {
      const seq = normalizeSequence(selectedWorkflow.agent_sequence);
      console.log('Checking workflow sequence:', seq, 'for workflow:', selectedWorkflow.name);
      if (seq && seq.length > 0) {
        // Check if this looks like a combined workflow by checking for known patterns
        const hasPlanningPhase = (seq.includes('directory_structure') && seq.includes('io8codermaster') && seq.includes('analyst')) ||
                                (seq.includes('io8directory_structure') && seq.includes('io8codermaster') && seq.includes('io8analyst'));
        const hasExecutionPhase = (seq.includes('sm') && seq.includes('developer') && seq.includes('devops')) ||
                                  (seq.includes('io8sm') && seq.includes('io8developer'));
        
        console.log('Has planning phase:', hasPlanningPhase, 'Has execution phase:', hasExecutionPhase);
        
        if (hasPlanningPhase && hasExecutionPhase) {
          // Determine if this is io8 or legacy workflow
          const isIo8 = seq.includes('io8directory_structure') || seq.includes('io8analyst') || seq.includes('io8architect') || seq.includes('io8pm') || seq.includes('io8developer') || seq.includes('io8devops');
          
          if (isIo8) {
            // io8 workflows: Split into 3 sub-workflows
            const planningEnd = seq.findIndex(agent => agent === 'io8pm') + 1;
            const developmentStart = planningEnd;
            const developmentEnd = seq.findIndex(agent => agent === 'io8devops');
            
            const wf1 = { name: 'io8 Plan (SureCLI)', seq: seq.slice(0, planningEnd) };
            const wf2 = { name: 'io8 Develop (Gemini)', seq: developmentEnd >= 0 ? seq.slice(developmentStart, developmentEnd) : seq.slice(developmentStart) };
            const wf3 = { name: 'io8 Deploy (Gemini)', seq: developmentEnd >= 0 ? seq.slice(developmentEnd) : [] };
            
            const synthetic = developmentEnd >= 0 && wf3.seq.length > 0 ? [wf1, wf2, wf3] : [wf1, wf2];
            combined = synthetic.flatMap(g => g.seq);
            let pos = 0;
            const ranges = synthetic.map(g => { const r = { name: g.name, start: pos, end: pos + g.seq.length - 1, length: g.seq.length }; pos += g.seq.length; return r; });
            console.log('Created synthetic ranges:', ranges);
            return { combined, ranges };
          } else {
            // Legacy workflows: Split into 2 sub-workflows
            const planningEnd = seq.findIndex(agent => agent === 'pm') + 1;
            const wf1 = { name: 'Planning Phase (SureCLI)', seq: seq.slice(0, planningEnd) };
            const wf2 = { name: 'Execution Phase (Gemini)', seq: seq.slice(planningEnd) };
            const synthetic = [wf1, wf2];
            combined = synthetic.flatMap(g => g.seq);
            let pos = 0;
            const ranges = synthetic.map(g => { const r = { name: g.name, start: pos, end: pos + g.seq.length - 1, length: g.seq.length }; pos += g.seq.length; return r; });
            console.log('Created synthetic ranges:', ranges);
            return { combined, ranges };
          }
        }
      }
    }
    
    // Fallback: if a single selected workflow is the default combined, build synthetic groups
    if ((!combined || combined.length === 0) && selectedWorkflow && (selectedWorkflow.name === 'End-to-End Plan + Execute' || selectedWorkflow.name === 'io8 Default')) {
      const isIo8 = selectedWorkflow.name === 'io8 Default';
      
      if (isIo8) {
        // io8 Default: 3 subworkflows
        const wf1 = { name: 'io8 Plan (SureCLI)', seq: ['io8project_builder', 'io8directory_structure', 'io8codermaster', 'io8analyst', 'io8architect', 'io8pm'] };
        const wf2 = { name: 'io8 Develop (Gemini)', seq: ['io8sm', 'io8developer'] };
        const wf3 = { name: 'io8 Deploy (Gemini)', seq: ['io8devops'] };
        const synthetic = [wf1, wf2, wf3];
        combined = synthetic.flatMap(g => g.seq);
        let pos = 0;
        const ranges = synthetic.map(g => { const r = { name: g.name, start: pos, end: pos + g.seq.length - 1, length: g.seq.length }; pos += g.seq.length; return r; });
        return { combined, ranges };
      } else {
        // End-to-End Plan + Execute: 2 subworkflows
        const wf1 = { name: 'Planning Phase (SureCLI)', seq: ['directory_structure', 'io8codermaster', 'analyst', 'architect', 'pm'] };
        const wf2 = { name: 'Execution Phase (Gemini)', seq: ['sm', 'developer', 'devops'] };
        const synthetic = [wf1, wf2];
        combined = synthetic.flatMap(g => g.seq);
        let pos = 0;
        const ranges = synthetic.map(g => { const r = { name: g.name, start: pos, end: pos + g.seq.length - 1, length: g.seq.length }; pos += g.seq.length; return r; });
        return { combined, ranges };
      }
    }
    
    let start = 0;
    const ranges = groups.map((g) => {
      const len = (g.seq || []).length;
      const r = { name: g.name, start, end: start + len - 1, length: len };
      start += len;
      return r;
    });
    return { combined, ranges };
  };

  // Derive groups via memo to reduce flicker
  const groups = React.useMemo(() => {
    const { ranges } = buildCombinedSequenceInfo();
    console.log('Groups detected:', ranges, 'Selected workflow:', selectedWorkflow?.name);
    return ranges || [];
  }, [selectedWorkflowSequence, selectedWorkflow]);

  // Reset group index when workflow changes
  React.useEffect(() => {
    setCurrentGroupIndex(0);
  }, [selectedWorkflow, selectedWorkflowSequence]);


  const groupAgents = React.useMemo(() => {
    const { combined, ranges } = buildCombinedSequenceInfo();
    if (!ranges || ranges.length === 0 || currentGroupIndex < 0 || currentGroupIndex >= ranges.length) return combined || [];
    const r = ranges[currentGroupIndex];
    return (combined || []).slice(r.start, r.end + 1);
  }, [selectedWorkflowSequence, selectedWorkflow, currentGroupIndex]);

  // Normalize a workflow sequence value into an array
  const normalizeSequence = (seq) => {
    if (Array.isArray(seq)) return seq;
    if (typeof seq === 'string') {
      try { return JSON.parse(seq); } catch { return []; }
    }
    return [];
  };

  // Initialize chat history when task changes
  useEffect(() => {
    console.log('useEffect triggered with task:', task);
    console.log('Selected workflow in useEffect:', selectedWorkflow);
    
    // Additional debugging for FLF workflow
    if (selectedWorkflow) {
      console.log('Workflow name:', selectedWorkflow.name);
      console.log('Workflow name type:', typeof selectedWorkflow.name);
      if (selectedWorkflow.name && typeof selectedWorkflow.name === 'string') {
        console.log('Lowercase workflow name:', selectedWorkflow.name.toLowerCase());
        console.log('Contains flf:', selectedWorkflow.name.toLowerCase().includes('flf'));
      }
    }
    
    if (task) {
      // Initialize with task creation message
      const initialMessage = {
        id: `task-${task.task_id}`,
        type: 'assistant',
        content: `Task "${task.prompt || task.user_prompt || 'New Task'}" has been created and is now in progress.`,
        timestamp: new Date(task.created_at || Date.now())
      };
      setChatHistory([initialMessage]);
      
      // Show right panel by default when a task is selected
      setShowRightPanel(true);
      
      // Start monitoring
      fetchMonitorData();
    }
  }, [task]);

  // Auto-refresh monitor data
  useEffect(() => {
    if (autoRefresh && task) {
      // Kick off immediately to populate buffers
      fetchMonitorData();
      // Poll monitor and logs incrementally
      refreshIntervalRef.current = setInterval(() => {
        // Only fetch if we're not already loading to prevent overlapping calls
        if (!loading) {
          fetchMonitorData();
          fetchLogsIncremental();
        }
      }, 2000); // Increased interval to 2 seconds to reduce load
      return () => {
        if (refreshIntervalRef.current) {
          clearInterval(refreshIntervalRef.current);
        }
      };
    }
  }, [autoRefresh, task, loading]);

  // Monitor logs for API status changes
  useEffect(() => {
    updateApiStatusFromLogs();
  }, [visibleLogs]);

  const fetchMonitorData = async () => {
    if (!task) return;
    
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/monitor`);
      if (!response.ok) {
        throw new Error('Failed to fetch monitor data');
      }
      const data = await response.json();
      
      setMonitorData(data);
      // Incremental logs fetch (after_seq)
      await fetchLogsIncremental();
      
      // Update token counts
      await updateTokenCounts(data);
      
      // Update task progress
      updateTaskProgress(data);
      
      // Update environment status
      updateEnvironmentStatus(data);
      
      // Update file browser
      await updateFileBrowser(data);
      
      // Capture frontend URL if present from backend
      if (typeof data.frontend_url === 'string' && data.frontend_url.startsWith('http')) {
        setFrontendUrl(data.frontend_url);
      }
      
      // Monitor API status from logs
      updateApiStatusFromLogs();
      
      // Fetch memory data
      await fetchMemory();
      
    } catch (err) {
      console.error('Error fetching monitor data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchMemory = async () => {
    if (!task) return;
    try {
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/memory`);
      if (res.ok) {
        const data = await res.json();
        setMemory({ history: Array.isArray(data.history) ? data.history : [] });
      }
    } catch (e) {
      // non-fatal
    }
  };

  const saveMemory = async () => {
    if (!task) return;
    setSavingMemory(true);
    try {
      const data = JSON.parse(memoryDraft);
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/memory`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (res.ok) {
        setMemory(data);
        setShowMemoryModal(false);
        showNotification('Memory updated successfully', 'success');
      } else {
        throw new Error('Failed to save memory');
      }
    } catch (e) {
      showNotification(`Failed to save memory: ${e.message}`, 'error');
    } finally {
      setSavingMemory(false);
    }
  };

  const fetchLogsIncremental = async () => {
    if (!task) return;
    try {
      const params = new URLSearchParams({ limit: '200', after_seq: String(lastSeqRef.current || 0) });
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/cli-logs?${params.toString()}`);
      if (!res.ok) return;
      const data = await res.json();
      const newLogs = Array.isArray(data.cli_logs) ? data.cli_logs : [];
      if (newLogs.length === 0) return;
      // Append and dedupe by seq
      const combined = [...(logsBufferRef.current || []), ...newLogs]
        .filter((l) => l && (typeof l.seq === 'number' || typeof l.seq === 'string'))
        .sort((a, b) => (Number(a.seq || 0) - Number(b.seq || 0)));
      // Deduplicate by seq
      const deduped = [];
      const seen = new Set();
      for (const l of combined) {
        const k = Number(l.seq || 0);
        if (seen.has(k)) continue;
        seen.add(k);
        deduped.push(l);
      }
      // Keep last 1000 logs max
      const trimmed = deduped.slice(-1000);
      logsBufferRef.current = trimmed;
      lastSeqRef.current = Number(data.last_seq || trimmed[trimmed.length - 1]?.seq || lastSeqRef.current || 0);
      setVisibleLogs(trimmed);
    } catch (e) {
      // ignore transient errors
    }
  };

  // Auto-scroll logs to bottom when enabled, but not during API errors
  useEffect(() => {
    if (autoScrollLogs && !apiStatus.quotaExhausted && !apiStatus.keyRotation && !apiStatus.noKeysAvailable) {
      logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [visibleLogs, autoScrollLogs, apiStatus.quotaExhausted, apiStatus.keyRotation, apiStatus.noKeysAvailable]);

  const updateTokenCounts = async (data) => {
    if (!task) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/tokens`);
      if (response.ok) {
        const tokenData = await response.json();
        const inputTokens = (
          tokenData.input ??
          tokenData.input_tokens ??
          tokenData.total_input_tokens ??
          0
        );
        const outputTokens = (
          tokenData.output ??
          tokenData.output_tokens ??
          tokenData.total_output_tokens ??
          0
        );
        const totalTokens = tokenData.total ?? tokenData.total_tokens ?? (inputTokens + outputTokens);
        setTokenCounts({
          input: Number(inputTokens) || 0,
          output: Number(outputTokens) || 0,
          total: Number(totalTokens) || (Number(inputTokens) + Number(outputTokens)) || 0
        });
      } else {
        // Fallback to mock data if API fails
        const mockTokens = {
          input: Math.floor(Math.random() * 1000) + 500,
          output: Math.floor(Math.random() * 2000) + 1000,
          total: 0
        };
        mockTokens.total = mockTokens.input + mockTokens.output;
        setTokenCounts(mockTokens);
      }
    } catch (err) {
      console.error('Error fetching token usage:', err);
      // Fallback to mock data
      const mockTokens = {
        input: Math.floor(Math.random() * 1000) + 500,
        output: Math.floor(Math.random() * 2000) + 1000,
        total: 0
      };
      mockTokens.total = mockTokens.input + mockTokens.output;
      setTokenCounts(mockTokens);
    }
  };

  const updateTaskProgress = (data) => {
    // Calculate progress based on completed agents vs total workflow
    const workflowSequence = Array.isArray(data.workflow_sequence) ? data.workflow_sequence : [];
    const completedAgents = Array.isArray(data.completed_agents) ? data.completed_agents : [];
    
    const total = workflowSequence.length || 15;
    const completed = completedAgents.length || 0;
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
    
    setTaskProgress({ completed, total, percentage });
  };

  const updateEnvironmentStatus = (data) => {
    // Mock environment status - implement based on actual backend data
    const status = [
      { step: 'Securing VM', completed: true, message: 'VM secured and ready' },
      { step: 'Environment Setup', completed: true, message: 'Dependencies installed' },
      { step: 'Workflow Initialization', completed: data.status === 'in_progress', message: 'Workflow started' }
    ];
    setEnvironmentStatus(status);
  };

  const updateFileBrowser = async (data) => {
    if (!task) return;
    
    try {
      // Fetch root-only for default view
      const rootRes = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/files?recursive=0&include_hidden=1`);
      // Fetch recursive for search index
      const allRes = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/files?recursive=1&include_hidden=1`);
      if (rootRes.ok) {
        const rootData = await rootRes.json();
        if (rootData.files && Array.isArray(rootData.files)) {
          const rootFormatted = rootData.files.map(file => {
            const sizeBytes = file.size_bytes || 0;
            let size = `${sizeBytes} B`;
            if (sizeBytes >= 1024 && sizeBytes < 1024 * 1024) size = `${(sizeBytes/1024).toFixed(1)} KB`;
            if (sizeBytes >= 1024 * 1024) size = `${(sizeBytes/(1024*1024)).toFixed(1)} MB`;
            return {
              name: file.name,
              type: file.type,
              path: file.path || file.name,
              size,
              modified: file.modified ? new Date(file.modified) : new Date()
            };
          });
          setRootFileBrowser(rootFormatted);
        } else {
          setRootFileBrowser([]);
        }
      }
      if (allRes.ok) {
        const allData = await allRes.json();
        const allFormatted = (allData.files || []).map(file => ({
          name: file.name,
          type: file.type,
          path: file.path || file.name,
          size_bytes: file.size_bytes || 0,
          modified: file.modified || null
        }));
        setAllFilesIndex(allFormatted);
      }
      // Decide what to show (root by default, or filtered search across all files)
      const q = (fileSearchQuery || '').trim().toLowerCase();
      if (q) {
        const filtered = allFilesIndex
          .filter(f => (f.name || '').toLowerCase().includes(q) || (f.path || '').toLowerCase().includes(q))
          .map(f => ({
            name: f.name,
            type: f.type,
            path: f.path,
            size: f.size_bytes >= 1024 * 1024 ? `${(f.size_bytes/(1024*1024)).toFixed(1)} MB` : (f.size_bytes >= 1024 ? `${(f.size_bytes/1024).toFixed(1)} KB` : `${f.size_bytes} B`),
            modified: f.modified ? new Date(f.modified) : new Date()
          }));
        setFileBrowser(filtered);
      } else {
        setFileBrowser(rootFileBrowser);
      }
      if (!rootRes.ok && !allRes.ok) {
        // Fallback to mock data if API fails
        const mockFiles = [
          { name: 'task_list.md', type: 'file', size: '2.1 KB', modified: new Date() },
          { name: 'requirements.txt', type: 'file', size: '156 B', modified: new Date() },
          { name: 'main.py', type: 'file', size: '4.2 KB', modified: new Date() },
          { name: '.sureai', type: 'file', size: '0 B', modified: new Date() },
          { name: 'deploy.json', type: 'file', size: '892 B', modified: new Date() }
        ];
        setRootFileBrowser(mockFiles);
        setFileBrowser(mockFiles);
      }
    } catch (err) {
      console.error('Error fetching task files:', err);
      // Fallback to mock data
      const mockFiles = [
        { name: 'task_list.md', type: 'file', size: '2.1 KB', modified: new Date() },
        { name: 'requirements.txt', type: 'file', size: '156 B', modified: new Date() },
        { name: 'main.py', type: 'file', size: '4.2 KB', modified: new Date() },
        { name: '.sureai', type: 'file', size: '0 B', modified: new Date() },
        { name: 'deploy.json', type: 'file', size: '892 B', modified: new Date() }
      ];
      setRootFileBrowser(mockFiles);
      setFileBrowser(mockFiles);
    }
  };

  const fetchDialogListing = async (path = '') => {
    if (!task) return;
    setFileDialogLoading(true);
    try {
      const params = new URLSearchParams({ path, recursive: '0', include_hidden: '1' });
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/files?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to list files');
      const data = await res.json();
      const entries = (data.files || []).map(e => ({
        name: e.name,
        path: e.path,
        type: e.type,
        size_bytes: e.size_bytes || 0,
        modified: e.modified
      }));
      setFileDialogEntries(entries);
      setFileDialogPath(path);
    } catch (e) {
      console.error('Dialog list error', e);
      setFileDialogEntries([]);
    } finally {
      setFileDialogLoading(false);
    }
  };

  const openFileDialog = async () => {
    setShowFileDialog(true);
    setFileContent('');
    setFileContentPath('');
    await fetchDialogListing('');
  };

  // Quick actions: create io8 project and commit to Gitea via prompts
  const getProjectFolderName = () => {
    const folder = (monitorData && monitorData.project_path) || '';
    if (!folder) return '';
    const name = folder.split('/').filter(Boolean).slice(-1)[0] || folder;
    return name;
  };

  const triggerPromptAction = async (promptText) => {
    if (!task) return;
    try {
      if (jobProService.isJobProEnabled()) {
        await jobProService.rerunWorkflow(task.task_id, promptText, selectedWorkflow?.id || undefined, undefined);
      } else {
        await fetch(`${API_BASE_URL}/tasks/${task.task_id}/reexecute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_prompt: promptText })
        });
      }
      return true;
    } catch (_) {
      return false;
    }
  };

  const handleCreateIo8Project = async () => {
    const projectName = getProjectFolderName();
    if (!projectName) { showNotification('Folder name unavailable yet', 'error'); return; }
    await ensureRepoIfMissing();
    const io8Prompt = `process_user_prompt(userPrompt='create io8 project with project name "${projectName}", visibility "Private", backend "Spring Boot", database "MySQL", and frontend "Angular Clarity"')`;
    let ok = false;
    try {
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/gemini/single`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: io8Prompt, agent_name: 'developer' })
      });
      ok = res.ok;
    } catch (e) {
      ok = false;
    }
    const msg = ok ? `io8 project created: ${projectName}` : `Failed to create io8 project: ${projectName}`;
    setChatHistory(prev => [...prev, { id: `sys-${Date.now()}`, type: ok ? 'assistant' : 'error', content: msg, timestamp: new Date() }]);
    if (ok) showNotification('io8 project creation triggered', 'success'); else showNotification('io8 project creation failed', 'error');
  };

  const handleCommitToGitea = async () => {
    const projectName = getProjectFolderName();
    if (!projectName) { showNotification('Folder name unavailable yet', 'error'); return; }
    // Use the exact folder name (including timestamp and underscores) for the Gitea repo URL
    const repoUrl = `http://157.66.191.31:3000/risadmin_prod/${projectName}.git`;
    const gitPrompt = `process_user_prompt(userPrompt='run_shell_command(command="git init && git remote remove origin || true && git remote add origin http://risadmin_prod:adminprod1234@157.66.191.31:3000/risadmin_prod/${projectName}.git && git fetch origin main || true && git checkout -B main && git branch -u origin/main main || true && git pull origin main --allow-unrelated-histories || true && git add . && (git diff --cached --quiet || git commit -m \"Initial commit of io8 project\") && (git push -u origin main || git push -u origin main --force-with-lease)", description="Initialize git, reconcile with remote if it exists, and push changes reliably.")')`;
    let ok = false;
    try {
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/gemini/single`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: gitPrompt, agent_name: 'developer' })
      });
      ok = res.ok;
    } catch (e) {
      ok = false;
    }
    const msg = ok ? `Code committed to Gitea: ${projectName}` : `Failed to commit to Gitea: ${projectName}`;
    setChatHistory(prev => [...prev, { id: `sys-${Date.now()}`, type: ok ? 'assistant' : 'error', content: msg, timestamp: new Date() }]);
    if (ok) showNotification('Gitea commit triggered', 'success'); else showNotification('Gitea commit failed', 'error');
  };

  const navigateUp = async () => {
    if (!fileDialogPath) return;
    const parts = fileDialogPath.split('/').filter(Boolean);
    parts.pop();
    await fetchDialogListing(parts.join('/'));
  };

  const handleEntryClick = async (entry) => {
    if (entry.type === 'dir') {
      await fetchDialogListing(entry.path);
      return;
    }
    // file: fetch content
    try {
      const params = new URLSearchParams({ path: entry.path, max_bytes: '400000' });
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/files/content?${params.toString()}`);
      if (!res.ok) throw new Error('Failed to read file');
      const data = await res.json();
      setFileContentPath(data.path || entry.path);
      setFileContent(data.content || '');
    } catch (e) {
      console.error('Read file error', e);
      setFileContent('Failed to load file');
    }
  };

  const handleSubmitMessage = async () => {
    // Debug log
    console.log(' handleSubmitMessage called');
    console.log('selectedWorkflow:', selectedWorkflow);
    console.log('flfUrl:', flfUrl);
    console.log('flfFolderName:', flfFolderName);
    
    // More robust FLF workflow detection
    const isFlfWorkflow = selectedWorkflow && 
      selectedWorkflow.name && 
      typeof selectedWorkflow.name === 'string' && 
      selectedWorkflow.name.toLowerCase().includes('flf');
    
    // For FLF workflow, we need both URL and folder name
    if (isFlfWorkflow && (!flfUrl.trim() || !flfFolderName.trim())) {
      console.log('FLF workflow detected but missing inputs');
      // Add error message to chat
      const errorMessage = {
        id: `error-${Date.now()}`,
        type: 'error',
        content: 'Please enter both repository URL and folder name for the FLF workflow.',
        timestamp: new Date()
      };
      setChatHistory(prev => [...prev, errorMessage]);
      return;
    }
    
    // For FLF workflow, modify the user prompt to include both URL and folder name
    let finalUserPrompt = userPrompt.trim();
    if (isFlfWorkflow && flfUrl.trim() && flfFolderName.trim()) {
      finalUserPrompt = `First, clone the repository from ${flfUrl}. Then, analyze the field patterns in ${flfFolderName} using the Universal Field Analysis Context Guide`;
      console.log('Modified prompt for FLF workflow:', finalUserPrompt);
    }
    
    if (!finalUserPrompt) return;
    
    setIsSubmitting(true);
    
    // Add user message to chat
    const userMessage = {
      id: `user-${Date.now()}`,
      type: 'user',
      content: finalUserPrompt,
      timestamp: new Date()
    };
    
    setChatHistory(prev => [...prev, userMessage]);

    try {
      // Prefer JobPro if enabled
      const selectedWorkflowId = selectedWorkflow?.id || undefined;
      // Build combined sequence from multi-selection if present, else single selection
      const combinedSeq = (selectedWorkflowSequence && selectedWorkflowSequence.length > 0)
        ? selectedWorkflowSequence.flatMap(wf => normalizeSequence(wf.agent_sequence))
        : (selectedWorkflow ? normalizeSequence(selectedWorkflow.agent_sequence) : undefined);


      if (jobProService.isJobProEnabled()) {
        // Check if task is already being processed
        if (task.status === 'in_progress') {
          console.log('⏭️ Task is already in progress, skipping JobPro call');
          const assistantMessage = {
            id: `assistant-${Date.now()}`,
            type: 'assistant',
            content: 'Task is already in progress. Please wait for it to complete before making changes.',
            timestamp: new Date()
          };
          setChatHistory(prev => [...prev, assistantMessage]);
          setIsSubmitting(false);
          setUserPrompt('');
          setFlfFolderName(''); // Clear FLF folder name
          setFlfUrl(''); // Clear FLF URL
          return;
        }
        
        const result = await jobProService.rerunWorkflow(
          task.task_id,
          finalUserPrompt,
          selectedWorkflowId,
          combinedSeq,
        );
        if (!result.success) {
          throw new Error(result.error || 'Failed to queue modification via JobPro');
        }
        const assistantMessage = {
          id: `assistant-${Date.now()}`,
          type: 'assistant',
          content: 'Your instruction was queued via JobPro. The workflow will update shortly.',
          timestamp: new Date()
        };
        setChatHistory(prev => [...prev, assistantMessage]);
      } else {
        // Fallback: direct API call
        const response = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/reexecute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ 
            user_prompt: finalUserPrompt,
            workflow_id: selectedWorkflowId,
            workflow_sequence: combinedSeq,
          })
        });
        if (!response.ok) {
          const errorData = await response.json().catch(() => ({ error: 'Failed to submit modification' }));
          throw new Error(errorData.error || 'Failed to submit modification');
        }
        const data = await response.json();
        const assistantMessage = {
          id: `assistant-${Date.now()}`,
          type: 'assistant',
          content: data.message || 'Modification request submitted successfully. The workflow will continue with your changes.',
          timestamp: new Date()
        };
        setChatHistory(prev => [...prev, assistantMessage]);
      }
    } catch (err) {
      // Add error message to chat
      const errorMessage = {
        id: `error-${Date.now()}`,
        type: 'error',
        content: `Error: ${err.message}`,
        timestamp: new Date()
      };
      
      setChatHistory(prev => [...prev, errorMessage]);
      // Show right panel even on error to see what happened
      setShowRightPanel(true);
    } finally {
      setIsSubmitting(false);
      setUserPrompt('');
      setFlfFolderName(''); // Clear FLF folder name
      setFlfUrl(''); // Clear FLF URL
    }
  };

  const handleResumeTask = async () => {
    console.log('handleResumeTask called');
    console.log('selectedWorkflow:', selectedWorkflow);
    console.log('flfUrl:', flfUrl);
    console.log('flfFolderName:', flfFolderName);
    
    if (!task) return;

    // More robust FLF workflow detection
    const isFlfWorkflow = selectedWorkflow && 
      selectedWorkflow.name && 
      typeof selectedWorkflow.name === 'string' && 
      selectedWorkflow.name.toLowerCase().includes('flf');

    // For FLF workflow, we need both URL and folder name
    if (isFlfWorkflow && (!flfUrl.trim() || !flfFolderName.trim())) {
      console.log('FLF workflow detected but missing inputs in resume');
      showNotification('Please enter both repository URL and folder name for the FLF workflow.', 'error');
      return;
    }

    try {
      // Ensure memory is up to date before resuming
      await fetchMemory();

      // Resume workflow - backend handles cancellation internally
      // Prioritize new user prompt from chat input
      let resumePrompt = userPrompt.trim() || task.prompt || task.user_prompt || undefined;
      
      // For FLF workflow, modify the user prompt to include both URL and folder name
      if (isFlfWorkflow && flfUrl.trim() && flfFolderName.trim()) {
        resumePrompt = `First, clone the repository from ${flfUrl}. Then, analyze the field patterns in ${flfFolderName} using the Universal Field Analysis Context Guide`;
        console.log('Modified resume prompt for FLF workflow:', resumePrompt);
      }
      
      const wfId = selectedWorkflow?.id || undefined;

      console.log('🔄 Attempting resume');
      console.log('Resume parameters:', { taskId: task.task_id, prompt: resumePrompt, workflowId: wfId });
      console.log('Current memory:', memory);

      // Reset progress to show resuming state
      setTaskProgress({ completed: 0, total: 15, percentage: 0 });

      // Resume strictly via JobPro only
      if (!jobProService.isJobProEnabled()) {
        throw new Error('JobPro is disabled or not configured. Enable JobPro to use Resume.');
      }
      // Ensure configuration is fresh and valid before sending
      jobProService.forceRefreshConfiguration();
      if (!jobProService.isReady()) {
        throw new Error('JobPro service is not ready. Check JobPro API URL and backend URL settings.');
      }
      console.log('🔄 Resuming via JobPro');
      const result = await jobProService.resumeWorkflow(
        task.task_id,
        resumePrompt,
        wfId,
        null // Backend determines resume sequence
      );
      if (!result?.success) {
        throw new Error(result?.error || 'Failed to queue resume via JobPro');
      }

      // Immediate UI feedback
      setChatHistory(prev => [...prev, {
        id: `assistant-${Date.now()}`,
        type: 'assistant',
        content: 'Resume requested. The workflow will continue from the current pending agent.',
        timestamp: new Date()
      }]);

      showNotification('Task resumed successfully', 'success');
      // Clear the user prompt since it's been used for resume
      setUserPrompt('');
      setFlfFolderName(''); // Clear FLF folder name
      setFlfUrl(''); // Clear FLF URL
      // Refresh monitor data and memory to show new progress
      fetchMonitorData();
      fetchMemory();
    } catch (err) {
      showNotification(`Failed to resume task: ${err.message}`, 'error');
    }
  };

  const handleRestartTask = async () => {
    console.log('handleRestartTask called');
    console.log('selectedWorkflow:', selectedWorkflow);
    console.log('flfUrl:', flfUrl);
    console.log('flfFolderName:', flfFolderName);
    
    if (!task) return;
    
    // More robust FLF workflow detection
    const isFlfWorkflow = selectedWorkflow && 
      selectedWorkflow.name && 
      typeof selectedWorkflow.name === 'string' && 
      selectedWorkflow.name.toLowerCase().includes('flf');

    // For FLF workflow, we need both URL and folder name
    if (isFlfWorkflow && (!flfUrl.trim() || !flfFolderName.trim())) {
      console.log('FLF workflow detected but missing inputs in restart');
      showNotification('Please enter both repository URL and folder name for the FLF workflow.', 'error');
      return;
    }

    try {
      // Ensure memory is up to date before restarting
      await fetchMemory();
      
      // Restart workflow - backend handles cancellation internally
      // Prioritize new user prompt from chat input
      let restartPrompt = userPrompt.trim() || task.prompt || task.user_prompt || 'Restarting workflow from beginning';
      
      // For FLF workflow, modify the user prompt to include both URL and folder name
      if (isFlfWorkflow && flfUrl.trim() && flfFolderName.trim()) {
        restartPrompt = `First, clone the repository from ${flfUrl}. Then, analyze the field patterns in ${flfFolderName} using the Universal Field Analysis Context Guide`;
        console.log('Modified restart prompt for FLF workflow:', restartPrompt);
      }
      
      const wfSeq = monitorData?.workflow_sequence || undefined;
      const wfId = selectedWorkflow?.id || undefined;
      
      console.log('🔄 Restarting workflow through JobPro');
      console.log('Restart parameters:', { taskId: task.task_id, prompt: restartPrompt, workflowId: wfId, workflowSequence: wfSeq });
      console.log('Current memory:', memory);
      
      // Reset progress to show restarting state
      setTaskProgress({ completed: 0, total: 15, percentage: 0 });
      
      let result;
      if (jobProService.isJobProEnabled()) {
        result = await jobProService.rerunWorkflow(
          task.task_id,
          restartPrompt,
          wfId,
          wfSeq
        );
        console.log('Restart result:', result);
        
        if (!result.success) {
          throw new Error(result.error || 'Failed to queue restart workflow');
        }
      } else {
        // Fallback: Direct API call if JobPro is disabled
        console.log('JobPro disabled, calling backend directly for restart');
        const body = { user_prompt: restartPrompt };
        if (wfId) body.workflow_id = wfId;
        if (wfSeq) body.workflow_sequence = wfSeq;
        
        const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/reexecute`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.error || 'Failed to restart workflow');
        }
        
        result = { success: true, message: 'Restart workflow started directly' };
      }
      
      showNotification('Task restarted successfully', 'success');
      // Clear the user prompt since it's been used for restart
      setUserPrompt('');
      setFlfFolderName(''); // Clear FLF folder name
      setFlfUrl(''); // Clear FLF URL
      // Refresh monitor data and memory to show new progress
      fetchMonitorData();
      fetchMemory();
    } catch (err) {
      console.error('Restart error:', err);
      showNotification(`Failed to restart task: ${err.message}`, 'error');
    }
  };

  const showNotification = (message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const updateApiStatusFromLogs = () => {
    // Check recent logs for API quota and key rotation messages
    const recentLogs = visibleLogs.slice(-20); // Check last 20 logs
    let newStatus = {
      quotaExhausted: false,
      keyRotation: false,
      noKeysAvailable: false,
      retryAttempts: 0,
      lastError: null
    };

    const looksLike429 = (msg) => {
      const m = (msg || '').toLowerCase();
      return (
        m.includes('status 429') ||
        m.includes('429 too many requests') ||
        m.includes('quota exceeded') ||
        m.includes('quota_exceeded') ||
        m.includes('rate limit')
      );
    };

    const isGeminiOrGoogle = (msg) => {
      const m = (msg || '').toLowerCase();
      return (
        m.includes('gemini cli') ||
        m.includes('google gen ai') ||
        m.includes('google genai') ||
        m.includes('vertex ai') ||
        m.includes('generative ai')
      );
    };

    recentLogs.forEach(log => {
      const message = log.message?.toLowerCase() || '';

      // Only set quotaExhausted when we clearly see a 429-ish message AND it came from Gemini/Google context
      if (looksLike429(message) && isGeminiOrGoogle(message)) {
        newStatus.quotaExhausted = true;
        newStatus.lastError = log.message;
      }

      if (message.includes('key rotation') || message.includes('rotating')) {
        newStatus.keyRotation = true;
      }

      if (message.includes('no more keys available') || message.includes('no usable api key') || message.includes('workflow termination required') || message.includes('no_keys_available')) {
        newStatus.noKeysAvailable = true;
      }

      if (message.includes('retrying') || message.includes('attempt')) {
        newStatus.retryAttempts = Math.max(newStatus.retryAttempts, 1);
      }
    });

    setApiStatus(newStatus);
  };

  const getWorkflowProgressionDots = () => {
    const defaultAgents = ['directory_structure', 'io8codermaster', 'analyst', 'architect', 'pm', 'sm', 'developer', 'devops', 'tester'];
    // Prefer current group's agents if present
    const agents = (groupAgents && groupAgents.length > 0) ? groupAgents : defaultAgents;
    const currentAgent = monitorData?.current_agent || '';
    const completedAgents = Array.isArray(monitorData?.completed_agents) ? monitorData.completed_agents : [];
    
    return agents.map((agent, index) => {
      const isCompleted = completedAgents.includes(agent);
      const isCurrent = currentAgent === agent;
      const isPending = !isCompleted && !isCurrent;
      
      let color = 'bg-gray-400';
      if (isCompleted) color = 'bg-green-500';
      else if (isCurrent) color = 'bg-blue-500 animate-pulse';
      else if (isPending) color = 'bg-gray-400';
      
      return (
        <div key={agent} className="flex flex-col items-center space-y-1">
          <div className={`w-3 h-3 rounded-full ${color} transition-colors duration-300`}></div>
          <span className="text-xs text-gray-400 text-center max-w-[60px] leading-tight">
            {agent.replace('_', ' ')}
          </span>
        </div>
      );
    });
  };

  const getActiveSubWorkflowLabel = () => {
    const { combined, ranges } = buildCombinedSequenceInfo();
    if (!combined || combined.length === 0 || !ranges || ranges.length === 0) return null;
    const r = ranges[Math.min(Math.max(currentGroupIndex, 0), ranges.length - 1)];
    // Compute position inside group using completed agents
    const completed = Array.isArray(monitorData?.completed_agents) ? monitorData.completed_agents : [];
    const groupList = (combined || []).slice(r.start, r.end + 1);
    const done = groupList.filter(a => completed.includes(a)).length;
    // Try to highlight current agent if within group
    const current = monitorData?.current_agent || '';
    const position = current && groupList.includes(current) ? (groupList.indexOf(current) + 1) : Math.min(Math.max(done, 0), r.length) || 1;
    return { name: r.name, position, total: r.length };
  };

  const ensureRepoIfMissing = async () => {
    const projectName = getProjectFolderName();
    if (!projectName) return false;
    const repoUrl = `http://157.66.191.31:3000/risadmin_prod/${projectName}.git`;
    try {
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/git/clone-if-missing`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ repo_url: repoUrl, username: 'risadmin_prod', password: 'adminprod1234' })
      });
      return res.ok;
    } catch (_) { return false; }
  };

  if (!task) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Bot className="w-12 h-12 mx-auto mb-4 text-gray-400" />
          <p className="text-gray-400">No task selected</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full bg-background">
      {/* Notification */}
      {notification && (
        <div className="fixed top-4 right-4 z-50">
          <Alert className={`${
            notification.type === 'error' ? 'border-red-500 bg-red-500/10' :
            notification.type === 'success' ? 'border-green-500 bg-green-500/10' :
            notification.type === 'warning' ? 'border-yellow-500 bg-yellow-500/10' :
            'border-blue-500 bg-blue-500/10'
          }`}>
            <AlertDescription className={
              notification.type === 'error' ? 'text-red-300' :
              notification.type === 'success' ? 'text-green-300' :
              notification.type === 'warning' ? 'text-yellow-300' :
              'text-blue-300'
            }>
              {notification.message}
            </AlertDescription>
          </Alert>
        </div>
      )}
      
      {/* Main Chat Interface - Full width when right panel hidden, 30% when shown */}
      <div className={`flex flex-col transition-all duration-300 flex-1 ${
        showRightPanel ? 'max-w-[30%] border-r border-border' : 'max-w-full'
      }`}>
        {/* Chat Header */}
        <div className="border-b border-border p-4 bg-card">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Button
                variant="ghost"
                size="sm"
                onClick={onBack}
                className="p-2"
              >
                <ArrowLeft className="w-4 h-4" />
              </Button>
              <div className="flex items-center space-x-2">
                <div className="w-2 h-2 bg-red-500 rounded-full"></div>
                <div>
                  <h3 className="font-medium text-sm truncate max-w-[200px]" title={task.prompt}>
                    {task.prompt}
                  </h3>
                  <p className="text-xs text-gray-500">Task ID: {task.task_id}</p>
                  {(() => {
                    const folder = (monitorData && monitorData.project_path) || '';
                    if (!folder) return null;
                    const name = folder.split('/').filter(Boolean).slice(-1)[0] || folder;
                    return (
                      <p className="text-[10px] text-gray-400">Folder: <span className="font-mono">{name}</span></p>
                    );
                  })()}
                </div>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Badge variant="outline" className="text-xs">
                In Progress
              </Badge>
              <Button
                variant="ghost"
                size="sm"
                onClick={onRefresh}
                className="p-2"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
              {/* Buttons moved to footer Quick Actions section to avoid overlap */}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowRightPanel(!showRightPanel)}
                className="p-2"
              >
                {showRightPanel ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => onBack()}
                className="text-xs px-2 py-1"
              >
                New Task
              </Button>
            </div>
          </div>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-4">
          <ScrollArea className="h-full">
            <div className="space-y-4">
              {chatHistory.map((message, index) => (
                <ChatMessage key={message.id || index} message={message} index={index} />
              ))}
            </div>
          </ScrollArea>
        </div>

        {/* Workflow Selector */}
        <div className="p-4 border-t border-border">
          <WorkflowSelector
            onWorkflowSelect={onWorkflowSelect}
            selectedWorkflow={selectedWorkflow}
            agents={agents}
            compact={true}
            selectedWorkflowSequence={selectedWorkflowSequence}
            onWorkflowSequenceChange={setSelectedWorkflowSequence}
          />
          
        </div>

        {/* Zrok URL Display */}
        {(frontendUrl || (monitorData?.status === 'completed' && !frontendUrl)) && (
          <div className="px-4 pb-4 border-t border-border">
            {frontendUrl ? (
              <div className="p-3 rounded-lg border-2 border-green-500/40 bg-gradient-to-r from-green-500/20 to-emerald-500/20">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    <span className="font-bold text-green-300 text-sm">🚀 Public Access</span>
                  </div>
                  <Badge variant="outline" className="bg-green-500/20 text-green-300 border-green-400 text-xs">
                    Zrok Share
                  </Badge>
                </div>
                <div className="space-y-2">
                  <div className="text-xs text-green-200">
                    <span className="font-semibold">URL: </span>
                    <a 
                      href={frontendUrl} 
                      target="_blank" 
                      rel="noreferrer" 
                      className="underline text-green-300 break-all hover:text-green-100 transition-colors"
                    >
                      {String(frontendUrl || '').replace(/\"/g, '').replace(/",".*$/,'').replace(/["\]}]+$/,'').trim()}
                    </a>
                  </div>
                  <div className="text-xs text-green-300/80">
                    ✅ External access via zrok
                  </div>
                </div>
                <div className="mt-2 flex items-center justify-between">
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-green-500 text-green-300 hover:bg-green-500/20 text-xs px-2 py-1 h-6"
                    onClick={() => {
                      const clean = String(frontendUrl || '').replace(/\"/g, '').replace(/",".*$/,'').replace(/["\]}]+$/,'').trim();
                      if (clean) navigator.clipboard.writeText(clean);
                      showNotification('URL copied to clipboard', 'success');
                    }}
                  >
                    📋 Copy
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-gray-500 text-gray-300 hover:bg-gray-500/20 text-xs px-2 py-1 h-6"
                    onClick={() => {
                      const clean = String(frontendUrl || '').replace(/\"/g, '').replace(/",".*$/,'').replace(/["\]}]+$/,'').trim();
                      if (clean) window.open(clean, '_blank');
                    }}
                  >
                    🌐 Open
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-blue-500 text-blue-300 hover:bg-blue-500/20 text-xs px-2 py-1 h-6"
                    onClick={async () => {
                      try {
                        setCreatingShare(true);
                        setShareError(null);
                        const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/deploy/auto-share`, { 
                          method: 'POST', 
                          headers: { 'Content-Type': 'application/json' }
                        });
                        if (res.ok) {
                          const d = await res.json().catch(() => ({}));
                          if (d.frontend_url) setFrontendUrl(d.frontend_url);
                          showNotification('Zrok share refreshed', 'success');
                        } else {
                          const errorText = await res.text();
                          let errorData = {};
                          try { errorData = JSON.parse(errorText); } catch {}
                          setShareError(errorData.error || 'Failed to refresh zrok share');
                          showNotification('Failed to refresh zrok share', 'error');
                        }
                      } catch (e) {
                        console.error('Failed to refresh auto-share:', e);
                        setShareError('Network error: ' + e.message);
                        showNotification('Network error: ' + e.message, 'error');
                      } finally {
                        setCreatingShare(false);
                      }
                    }}
                    disabled={creatingShare}
                  >
                    {creatingShare ? '🔄' : '🔄 Refresh'}
                  </Button>
                </div>
                {shareError && (
                  <div className="mt-2 p-2 rounded border border-red-500/30 bg-red-500/10">
                    <div className="text-red-300 text-xs">{shareError}</div>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-3 rounded-lg border-2 border-blue-500/40 bg-gradient-to-r from-blue-500/20 to-cyan-500/20">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                    <span className="font-bold text-blue-300 text-sm">🚀 Create Public Access</span>
                  </div>
                  <Badge variant="outline" className="bg-blue-500/20 text-blue-300 border-blue-400 text-xs">
                    Zrok Ready
                  </Badge>
                </div>
                <div className="space-y-2">
                  <div className="text-xs text-blue-200">
                    Your application has been deployed successfully! Create a public zrok share to provide external access.
                  </div>
                  <div className="text-xs text-blue-300/80">
                    💡 This will generate a public URL that users can access from anywhere
                  </div>
                </div>
                <div className="mt-2 flex justify-center">
                  <Button
                    size="sm"
                    className="bg-blue-600 hover:bg-blue-700 text-white border-blue-500 text-xs px-3 py-1 h-6"
                    onClick={async () => {
                      try {
                        setCreatingShare(true);
                        setShareError(null);
                        const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/deploy/auto-share`, { 
                          method: 'POST', 
                          headers: { 'Content-Type': 'application/json' }
                        });
                        if (res.ok) {
                          const d = await res.json().catch(() => ({}));
                          if (d.frontend_url) setFrontendUrl(d.frontend_url);
                          showNotification('Zrok share created successfully', 'success');
                        } else {
                          const errorText = await res.text();
                          let errorData = {};
                          try { errorData = JSON.parse(errorText); } catch {}
                          setShareError(errorData.error || 'Failed to create zrok share');
                          showNotification('Failed to create zrok share', 'error');
                        }
                      } catch (e) {
                        console.error('Failed to create auto-share:', e);
                        setShareError('Network error: ' + e.message);
                        showNotification('Network error: ' + e.message, 'error');
                      } finally {
                        setCreatingShare(false);
                      }
                    }}
                    disabled={creatingShare}
                  >
                    {creatingShare ? '🔄 Creating...' : '🚀 Create Zrok Share'}
                  </Button>
                </div>
                {shareError && (
                  <div className="mt-2 p-2 rounded border border-red-500/30 bg-red-500/10">
                    <div className="text-red-300 text-xs">{shareError}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* API Status Display */}
        {(apiStatus.quotaExhausted || apiStatus.keyRotation || apiStatus.noKeysAvailable) && (
          <div className="px-4 pb-4 border-t border-border">
            {apiStatus.quotaExhausted && (
              <div className="p-3 rounded-lg border-2 border-red-500/40 bg-gradient-to-r from-red-500/20 to-orange-500/20">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-red-400 rounded-full animate-pulse"></div>
                    <span className="font-bold text-red-300 text-sm">⚠️ API Quota Exceeded</span>
                  </div>
                  <Badge variant="outline" className="bg-red-500/20 text-red-300 border-red-400 text-xs">
                    Status 429
                  </Badge>
                </div>
                <div className="space-y-2">
                  <div className="text-xs text-red-200">
                    API quota has been exceeded. The system is attempting to rotate to a new key.
                  </div>
                  {apiStatus.lastError && (
                    <div className="text-xs text-red-300/80 font-mono">
                      {apiStatus.lastError}
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {apiStatus.keyRotation && (
              <div className="p-3 rounded-lg border-2 border-yellow-500/40 bg-gradient-to-r from-yellow-500/20 to-amber-500/20">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse"></div>
                    <span className="font-bold text-yellow-300 text-sm">🔄 Key Rotation in Progress</span>
                  </div>
                  <Badge variant="outline" className="bg-yellow-500/20 text-yellow-300 border-yellow-400 text-xs">
                    Rotating
                  </Badge>
                </div>
                <div className="space-y-2">
                  <div className="text-xs text-yellow-200">
                    The system is automatically rotating to a new API key to continue the workflow.
                  </div>
                  {apiStatus.retryAttempts > 0 && (
                    <div className="text-xs text-yellow-300/80">
                      Retry attempts: {apiStatus.retryAttempts}
                    </div>
                  )}
                </div>
              </div>
            )}
            
            {apiStatus.noKeysAvailable && (
              <div className="p-3 rounded-lg border-2 border-red-500/40 bg-gradient-to-r from-red-500/20 to-pink-500/20">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 bg-red-400 rounded-full animate-pulse"></div>
                    <span className="font-bold text-red-300 text-sm">❌ No API Keys Available</span>
                  </div>
                  <Badge variant="outline" className="bg-red-500/20 text-red-300 border-red-400 text-xs">
                    Critical
                  </Badge>
                </div>
                <div className="space-y-2">
                  <div className="text-xs text-red-200">
                    All API keys have been exhausted. Please add new keys via the API Keys Manager.
                  </div>
                  <div className="text-xs text-red-300/80">
                    💡 Go to Settings → API Keys to add more keys
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Chat Input */}
        <div className="p-4 border-t border-border bg-card">
          <div className="space-y-3">
            {/* Action Buttons */}
            <div className="flex items-center justify-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleResumeTask}
                className="text-xs px-2 py-1 h-7"
              >
                <RefreshCw className="w-3 h-3 mr-1" />
                Resume
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleRestartTask}
                className="text-xs px-2 py-1 h-7"
              >
                <RotateCcw className="w-3 h-3 mr-1" />
                Restart
              </Button>
            </div>
            
            {/* File Upload */}
            <div className="flex items-center space-x-2">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={(e) => onFileSelect(e.target.files)}
                className="sr-only"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                className="flex-1"
              >
                <Upload className="w-4 h-4 mr-2" />
                Attach Files
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => { 
                  setMemoryDraft(JSON.stringify({ history: memory.history }, null, 2)); 
                  setShowMemoryModal(true); 
                }}
                className="flex-1"
              >
                <FileText className="w-4 h-4 mr-2" />
                View/Edit Memory
              </Button>
            </div>

            {/* Quick Actions (relocated from header) */}
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                title="Create io8 project now"
                onClick={handleCreateIo8Project}
                className="text-xs px-2 py-1"
              >
                Create io8 Project
              </Button>
              <Button
                variant="outline"
                size="sm"
                title="Commit code to Gitea now"
                onClick={handleCommitToGitea}
                className="text-xs px-2 py-1"
              >
                Commit to Gitea
              </Button>
            </div>
            
            {/* Message Input */}
            <div className="flex space-x-2">
              <div className="flex-1 space-y-2">
                {/* Debug: Show workflow info */}
                {process.env.NODE_ENV === 'development' && selectedWorkflow && (
                  <div className="text-xs text-gray-500 p-2 bg-gray-800 rounded">
                    Debug: Selected workflow - Name: "{selectedWorkflow.name}" | ID: "{selectedWorkflow.id}" | Type: {typeof selectedWorkflow.name}
                    {selectedWorkflow.name && selectedWorkflow.name.toLowerCase && (
                      <div>Contains 'flf': {selectedWorkflow.name.toLowerCase().includes('flf') ? 'Yes' : 'No'}</div>
                    )}
                  </div>
                )}
                {/* Show URL and folder name inputs for FLF workflow */}
                {(() => {
                  // More robust FLF workflow detection
                  const isFlfWorkflow = selectedWorkflow && 
                    selectedWorkflow.name && 
                    typeof selectedWorkflow.name === 'string' && 
                    selectedWorkflow.name.toLowerCase().includes('flf');
                  
                  console.log('FLF Workflow Detection:', {
                    selectedWorkflowName: selectedWorkflow?.name,
                    isFlfWorkflow: isFlfWorkflow,
                    workflowType: typeof selectedWorkflow?.name
                  });
                  
                  return isFlfWorkflow && (
                    <div className="space-y-2 border border-green-500 p-2 rounded">
                      <div className="text-xs text-green-500">FLF Workflow Inputs Active</div>
                      <div className="flex items-center space-x-2">
                        <ExternalLink className="w-4 h-4 text-gray-500" />
                        <Input
                          placeholder="Enter repository URL to clone..."
                          value={flfUrl}
                          onChange={(e) => setFlfUrl(e.target.value)}
                          className="flex-1"
                        />
                      </div>
                      <div className="flex items-center space-x-2">
                        <Folder className="w-4 h-4 text-gray-500" />
                        <Input
                          placeholder="Enter folder name to analyze..."
                          value={flfFolderName}
                          onChange={(e) => setFlfFolderName(e.target.value)}
                          className="flex-1"
                        />
                      </div>
                    </div>
                  );
                })()}
                <Textarea
                  placeholder="Type your message..."
                  value={userPrompt}
                  onChange={(e) => setUserPrompt(e.target.value)}
                  className="min-h-[60px] max-h-[120px] resize-none"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSubmitMessage();
                    }
                  }}
                />
              </div>
              <Button
                onClick={handleSubmitMessage}
                disabled={(() => {
                  // More robust FLF workflow detection
                  const isFlfWorkflow = selectedWorkflow && 
                    selectedWorkflow.name && 
                    typeof selectedWorkflow.name === 'string' && 
                    selectedWorkflow.name.toLowerCase().includes('flf');
                  
                  const hasUserPrompt = userPrompt.trim();
                  const hasFlfInputs = flfFolderName.trim() && flfUrl.trim();
                  const result = (!hasUserPrompt && !isFlfWorkflow) || 
                                (isFlfWorkflow && !hasFlfInputs) || 
                                isSubmitting;
                  
                  // Debug logging
                  if (isFlfWorkflow) {
                    console.log('FLF Workflow Button State:', {
                      isFlfWorkflow,
                      hasUserPrompt,
                      hasFlfInputs,
                      flfFolderName: flfFolderName.trim(),
                      flfUrl: flfUrl.trim(),
                      isSubmitting,
                      finalResult: result
                    });
                  }
                  
                  return result;
                })()}
                size="icon"
                className="self-end"
              >
                <Send className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel - Monitor (70%) */}
      {showRightPanel && (
        <div className="w-[70%] flex flex-col bg-card overflow-hidden">
          <div className="flex-1 p-4 overflow-hidden">
            <div className="space-y-4 h-full">
              {/* Progress Bar / Subworkflow View */}
              {(selectedWorkflow && (selectedWorkflow.name === 'End-to-End Plan + Execute' || selectedWorkflow.name === 'io8 Default')) ||
               (Array.isArray(monitorData?.workflow_sequence) && (() => {
                 const seq = monitorData.workflow_sequence;
                 const planning = ['directory_structure','bmad','analyst','architect','pm'];
                 const execution = ['sm','developer','devops'];
                 const joined = [...planning, ...execution];
                 if (seq.length === joined.length && joined.every((a,i)=>seq[i]===a)) return true;
                 const iPm = seq.indexOf('pm');
                 const iSm = seq.indexOf('sm');
                 return iPm >= 0 && iSm > iPm;
               })()) ? (
                <SubworkflowSlider
                  workflow={selectedWorkflow || { name: 'End-to-End Plan + Execute', description: 'Planning followed by Execution', agent_sequence: Array.isArray(monitorData?.workflow_sequence) ? monitorData.workflow_sequence : [] }}
                  agents={agents || {}}
                  currentStatus={(monitorData?.status || task.status)}
                  currentAgent={monitorData?.current_agent}
                  completedAgents={Array.isArray(monitorData?.completed_agents) ? monitorData.completed_agents : []}
                />
              ) : (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Workflow Progress</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {/* Debug info */}
                  {process.env.NODE_ENV === 'development' && (
                    <div className="text-xs text-gray-500 mb-2">
                      Debug: Groups: {groups.length}, Current: {currentGroupIndex}, Workflow: {selectedWorkflow?.name}
                    </div>
                  )}
                  
                  {/* Sub-workflow navigation controls */}
                  {groups && groups.length > 1 && (
                    <div className="flex items-center justify-between text-xs mb-2 p-2 bg-gray-800 rounded border">
                      <button
                        className={`px-3 py-1 border rounded text-sm font-medium ${currentGroupIndex <= 0 ? 'opacity-50 cursor-not-allowed bg-gray-700' : 'hover:bg-gray-600 bg-gray-700'}`}
                        disabled={currentGroupIndex <= 0}
                        onClick={() => setCurrentGroupIndex((i) => Math.max(0, i - 1))}
                        title="Previous sub-workflow"
                      >
                        ← Previous
                      </button>
                      <div className="font-medium text-gray-200 truncate px-2">
                        {groups[currentGroupIndex]?.name || ''} ({currentGroupIndex + 1}/{groups.length})
                      </div>
                      <button
                        className={`px-3 py-1 border rounded text-sm font-medium ${currentGroupIndex >= groups.length - 1 ? 'opacity-50 cursor-not-allowed bg-gray-700' : 'hover:bg-gray-600 bg-gray-700'}`}
                        disabled={currentGroupIndex >= groups.length - 1}
                        onClick={() => setCurrentGroupIndex((i) => Math.min(groups.length - 1, i + 1))}
                        title="Next sub-workflow"
                      >
                        Next →
                      </button>
                    </div>
                  )}
                  {/* Sub-workflow active label */}
                  {(() => {
                    const label = getActiveSubWorkflowLabel();
                    if (!label) return null;
                    return (
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-gray-400">Executing</span>
                        <span className="font-medium text-gray-200">{label.name} ({label.position}/{label.total})</span>
                      </div>
                    );
                  })()}
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>
                        {groups && groups.length > 1 ? 
                          `${groups[currentGroupIndex]?.name || 'Workflow'}: ${monitorData?.current_agent || 'Initializing...'}` :
                          `Current Agent: ${monitorData?.current_agent || 'Initializing...'}`
                        }
                      </span>
                      <span>{taskProgress.percentage}%</span>
                    </div>
                    <Progress value={taskProgress.percentage} className="h-2" />
                  </div>
                  
                  {/* Workflow Progression Dots */}
                  <div className="flex justify-between items-center py-2">
                    {getWorkflowProgressionDots()}
                  </div>
                </CardContent>
              </Card>
              )}

              {/* Token Counters */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Token Usage</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-3 gap-2">
                    <div className="text-center p-1 bg-blue-500/10 rounded border border-blue-500/30">
                      <div className="text-sm font-bold text-blue-400 leading-none">{tokenCounts.input}</div>
                      <div className="text-[10px] text-blue-300 mt-1">Input</div>
                    </div>
                    <div className="text-center p-1 bg-green-500/10 rounded border border-green-500/30">
                      <div className="text-sm font-bold text-green-400 leading-none">{tokenCounts.output}</div>
                      <div className="text-[10px] text-green-300 mt-1">Output</div>
                    </div>
                    <div className="text-center p-1 bg-purple-500/10 rounded border border-purple-500/30">
                      <div className="text-sm font-bold text-purple-400 leading-none">{tokenCounts.total}</div>
                      <div className="text-[10px] text-purple-300 mt-1">Total</div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Task Progress */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Task Progress</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <div className="flex justify-between items-center text-sm">
                      <span>Tasks Completed:</span>
                      <span className="font-mono">{taskProgress.completed} of {taskProgress.total}</span>
                    </div>
                    <div className="flex justify-between items-center text-sm">
                      <span>Plan Progress:</span>
                      <span className="font-mono">{taskProgress.percentage}%</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Environment Status */}
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">Environment Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-1">
                    {environmentStatus.map((step, index) => (
                      <div key={index} className="flex items-center space-x-2 text-sm">
                        {step.completed ? (
                          <CheckCircle className="w-3 h-3 text-green-500" />
                        ) : (
                          <Clock className="w-3 h-3 text-yellow-500" />
                        )}
                        <span className="text-xs">{step.step}</span>
                        {step.completed && (
                          <span className="text-xs text-gray-500">({step.message})</span>
                        )}
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              {/* File Browser */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">File Browser</CardTitle>
                    <Button size="sm" variant="outline" onClick={openFileDialog} className="h-7 px-2">
                      <ExternalLink className="w-3 h-3 mr-1" /> Open
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2">
                    <Input
                      value={fileSearchQuery}
                      onChange={(e) => {
                        const q = e.target.value;
                        setFileSearchQuery(q);
                        // Apply search against all files index (includes .sureai)
                        const query = (q || '').trim().toLowerCase();
                        if (query) {
                          const filtered = allFilesIndex
                            .filter(f => (f.name || '').toLowerCase().includes(query) || (f.path || '').toLowerCase().includes(query))
                            .map(f => ({
                              name: f.name,
                              type: f.type,
                              path: f.path,
                              size: f.size_bytes >= 1024 * 1024 ? `${(f.size_bytes/(1024*1024)).toFixed(1)} MB` : (f.size_bytes >= 1024 ? `${(f.size_bytes/1024).toFixed(1)} KB` : `${f.size_bytes} B`),
                              modified: f.modified ? new Date(f.modified) : new Date()
                            }));
                          setFileBrowser(filtered);
                        } else {
                          setFileBrowser(rootFileBrowser);
                        }
                      }}
                      placeholder="Search files (searches whole project incl. .sureai)"
                      className="h-7 text-xs"
                    />
                    <ScrollArea className="h-48 pr-2">
                      <div className="space-y-1 pr-2">
                        {fileBrowser
                          .filter((f) => {
                            const q = fileSearchQuery.toLowerCase();
                            if (!q) return true;
                            return (f.name || '').toLowerCase().includes(q);
                          })
                          .map((file, index) => (
                            <div key={index} className="flex items-center space-x-2 p-1 rounded hover:bg-gray-700/50">
                              {file.type === 'dir' ? (
                                <Folder className="w-3 h-3 text-amber-400" />
                              ) : (
                                <FileText className="w-3 h-3 text-blue-400" />
                              )}
                              <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium truncate">{file.name}</div>
                                {file.type !== 'dir' && (
                                  <div className="text-[10px] text-gray-500">{file.size}</div>
                                )}
                              </div>
                            </div>
                          ))}
                        {fileBrowser.length === 0 && (
                          <div className="text-xs text-gray-500">No files</div>
                        )}
                      </div>
                    </ScrollArea>
                  </div>
                </CardContent>
              </Card>

              {/* File Browser Dialog */}
              <Dialog open={showFileDialog} onOpenChange={setShowFileDialog}>
                <DialogContent className="w-[75vw] max-w-[1400px] sm:max-w-[1400px]">
                  <DialogHeader>
                    <DialogTitle className="flex items-center justify-between">
                      <span>Project Files</span>
                      <div className="flex items-center gap-2">
                        <Button size="sm" variant="outline" onClick={navigateUp} className="h-7 px-2">Up</Button>
                        <DialogClose asChild>
                          <Button size="sm" variant="ghost" className="h-7 px-2"><CloseIcon className="w-4 h-4" /></Button>
                        </DialogClose>
                      </div>
                    </DialogTitle>
                  </DialogHeader>
                  <div className="flex flex-col md:flex-row gap-4">
                    {/* Fixed-width file tree */}
                    <div className="border rounded p-2 w-full md:w-[280px] md:flex-none">
                      <div className="mb-2 flex items-center gap-2">
                        <Input
                          placeholder="Search in folder..."
                          className="h-8 text-xs"
                          onChange={(e) => {
                            const q = (e.target.value || '').toLowerCase();
                            if (!q) {
                              // reload current folder to reset
                              fetchDialogListing(fileDialogPath);
                              return;
                            }
                            const filtered = fileDialogEntries.filter(e2 => (e2.name || '').toLowerCase().includes(q) || (e2.path || '').toLowerCase().includes(q));
                            setFileDialogEntries(filtered);
                          }}
                        />
                      </div>
                      <div className="text-xs text-gray-400 mb-2 truncate">/{fileDialogPath}</div>
                      <ScrollArea className="h-[60vh] pr-2">
                        <div className="space-y-1">
                          {fileDialogLoading && (
                            <div className="text-xs text-gray-500">Loading...</div>
                          )}
                          {!fileDialogLoading && fileDialogEntries.map((e, idx) => (
                            <div key={idx} className="flex items-center gap-2 p-1 rounded hover:bg-gray-700/40 cursor-pointer" onClick={() => handleEntryClick(e)}>
                              {e.type === 'dir' ? (
                                <Folder className="w-4 h-4 text-amber-400" />
                              ) : (
                                <FileText className="w-4 h-4 text-blue-400" />
                              )}
                              <div className="flex-1 min-w-0">
                                <div className="text-xs font-medium truncate">{e.name}</div>
                                <div className="text-[10px] text-gray-500 truncate">{e.path}</div>
                              </div>
                            </div>
                          ))}
                          {!fileDialogLoading && fileDialogEntries.length === 0 && (
                            <div className="text-xs text-gray-500">No entries</div>
                          )}
                        </div>
                      </ScrollArea>
                    </div>
                    {/* Flexible file viewer */}
                    <div className="border rounded p-2 md:flex-1">
                      <div className="text-xs text-gray-400 mb-2 truncate">{fileContentPath || 'Select a file to view'}</div>
                      <ScrollArea className="h-[60vh] pr-2">
                        <pre className="text-xs whitespace-pre-wrap break-words p-3">{fileContent}</pre>
                      </ScrollArea>
                    </div>
                  </div>
                </DialogContent>
              </Dialog>

              {/* Real-time Logs */}
              <Card className="h-[40vh]">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Real-time Logs</CardTitle>
                    <Button variant={autoScrollLogs ? 'default' : 'outline'} size="sm" onClick={() => setAutoScrollLogs(!autoScrollLogs)}>
                      {autoScrollLogs ? 'Auto-scroll On' : 'Auto-scroll Off'}
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="h-[calc(40vh-44px)]">
                  <ScrollArea className="h-full pr-2">
                    <div className="space-y-1">
                    {visibleLogs && visibleLogs.length > 0 ? (
                      visibleLogs.map((log, index) => (
                        <div
                          key={index}
                          className={`text-xs font-mono p-1 rounded ${
                            log.level === 'ERROR' 
                              ? 'bg-red-500/10 border border-red-500/20' 
                              : log.level === 'WARNING'
                              ? 'bg-yellow-500/10 border border-yellow-500/20'
                              : 'bg-gray-500/10 border border-gray-500/20'
                          }`}
                        >
                          <div className="flex items-start space-x-2">
                            <span className={`text-xs ${
                              log.level === 'ERROR' ? 'text-red-400' :
                              log.level === 'WARNING' ? 'text-yellow-400' :
                              'text-gray-400'
                            }`}>
                              [{log.level || 'INFO'}]
                            </span>
                            <span className="text-xs text-gray-500">
                              {new Date(log.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          <div className={`mt-1 text-xs ${
                            log.level === 'ERROR' ? 'text-red-300' :
                            log.level === 'WARNING' ? 'text-yellow-300' :
                            'text-gray-300'
                          }`}>
                            {log.message}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div className="text-center py-4 text-gray-400">
                        <Activity className="w-6 h-6 mx-auto mb-1" />
                        <p className="text-xs">No logs available yet</p>
                      </div>
                    )}
                    {visibleLogs && visibleLogs.length > 8 && (
                      <div className="text-xs text-gray-500 text-center py-1">
                        +{visibleLogs.length - 8} more logs
                      </div>
                    )}
                    <div ref={logsEndRef} />
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      )}

      {/* Memory Modal */}
      {showMemoryModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-2xl p-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-lg font-semibold text-white">Task Memory</h3>
              <Button variant="outline" size="sm" onClick={() => setShowMemoryModal(false)}>
                Close
              </Button>
            </div>
            <p className="text-xs text-gray-400 mb-2">Edit as JSON. Only user prompts and agent progress are stored.</p>
            <textarea
              className="w-full h-72 bg-gray-800 border border-gray-600 rounded p-3 text-white font-mono text-sm"
              value={memoryDraft}
              onChange={(e) => setMemoryDraft(e.target.value)}
            />
            <div className="mt-3 flex items-center justify-end space-x-2">
              <Button 
                variant="outline" 
                onClick={() => setMemoryDraft(JSON.stringify({ history: memory.history }, null, 2))}
              >
                Reset
              </Button>
              <Button onClick={saveMemory} disabled={savingMemory}>
                {savingMemory ? 'Saving…' : 'Save Memory'}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatInterface;
