import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Button } from './ui/button';
import { ScrollArea } from './ui/scroll-area';
import { Activity, Play, Pause, X, Download, RefreshCw } from 'lucide-react';
import jobProService from '../services/jobProService.js';
import { API_BASE_URL, getApiUrl } from '../config/environment';
import SubworkflowSlider from './SubworkflowSlider';

// Backend URL configuration - Use centralized environment config

const TaskMonitor = ({ task, onRefresh }) => {
  const [monitorData, setMonitorData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [autoScrollLogs, setAutoScrollLogs] = useState(false);
  const [visibleLogs, setVisibleLogs] = useState([]);
  const logsEndRef = useRef(null);
  const refreshIntervalRef = useRef(null);
  const lastLogsKeyRef = useRef('');
  const [geminiError, setGeminiError] = useState(null);
  const [frontendUrl, setFrontendUrl] = useState('');
  const [rePrompt, setRePrompt] = useState('');
  const [workflows, setWorkflows] = useState([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState('');
  const [memory, setMemory] = useState({ history: [] });
  const [currentWorkflow, setCurrentWorkflow] = useState(null);
  const [showMemoryModal, setShowMemoryModal] = useState(false);
  const [memoryDraft, setMemoryDraft] = useState('');
  const [savingMemory, setSavingMemory] = useState(false);
  const [creatingShare, setCreatingShare] = useState(false);
  const [shareError, setShareError] = useState(null);
  const [resumingWorkflow, setResumingWorkflow] = useState(false);
  const [resumeError, setResumeError] = useState(null);
  const [canResume, setCanResume] = useState(false);
  const [resumeInfo, setResumeInfo] = useState(null);
  const [immediateStatus, setImmediateStatus] = useState(null);
  const [rerunPending, setRerunPending] = useState(false);
  const [keyRotationStatus, setKeyRotationStatus] = useState(null);
  const [errorCleared, setErrorCleared] = useState(false);
  const [noApiKey, setNoApiKey] = useState(false);
  // Preserve original full workflow sequence and cumulative completed agents
  const originalWorkflowSequenceRef = useRef([]);
  const cumulativeCompletedAgentsRef = useRef(new Set());
  // Error suppression/throttling
  const lastDetectedErrorSigRef = useRef('');
  const lastClearedErrorSigRef = useRef({ sig: '', ts: 0 });
  const lastAutoClearLogTsRef = useRef(0);
  // Resume flow guards
  const resumeRefreshIntervalRef = useRef(null);
  // Key rotation event dedupe
  const lastRotationEventTsRef = useRef('');
  // Resume lock/debounce to prevent multiple rapid resume calls
  const resumeLockRef = useRef(false);
  const lastResumeAtRef = useRef(0);

  const withResumeLock = async (fn) => {
    const now = Date.now();
    // Debounce: ignore if within 10 seconds of last resume
    if (now - (lastResumeAtRef.current || 0) < 10000) {
      return;
    }
    if (resumeLockRef.current) {
      return;
    }
    resumeLockRef.current = true;
    lastResumeAtRef.current = now;
    try {
      await fn();
    } finally {
      // Keep lock for a short grace period to avoid double-submits from re-renders
      setTimeout(() => {
        resumeLockRef.current = false;
      }, 1000);
    }
  };

  const resetWorkflowSequence = () => {
    console.log('🔄 Resetting workflow sequence and progress tracking');
    originalWorkflowSequenceRef.current = [];
    cumulativeCompletedAgentsRef.current.clear();
    // Force a refresh to get the latest sequence from backend
    fetchMonitorData();
  };

  // Check if task is currently running
  const isTaskRunning = () => {
    return currentStatus === 'in_progress' || immediateStatus === 'in_progress';
  };

  const fetchMonitorData = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/monitor`);
      if (!response.ok) {
        throw new Error('Failed to fetch monitor data');
      }
      const data = await response.json();
      // Ensure workflow_sequence is always an array to avoid UI crashes
      const normalizedSequence = Array.isArray(data.workflow_sequence)
        ? data.workflow_sequence
        : (typeof data.workflow_sequence === 'string'
            ? (() => { try { return JSON.parse(data.workflow_sequence); } catch { return []; } })()
            : []);

      // If backend only returns a sliced sequence (e.g., resume from developer),
      // build a display sequence by prepending completed agents so the UI shows full history
      const completedForDisplay = Array.isArray(data.completed_agents) ? data.completed_agents : [];
      let displaySequence = [...normalizedSequence];
      if (completedForDisplay.length > 0) {
        // Prepend completed agents that are not already at the front
        const combined = [...completedForDisplay, ...normalizedSequence];
        const seen = new Set();
        displaySequence = combined.filter(a => {
          if (!a) return false;
          if (seen.has(a)) return false;
          seen.add(a);
          return true;
        });
      }
      data.workflow_sequence = displaySequence;
      
      // Initialize or update original full sequence based on current status
      if (Array.isArray(displaySequence) && displaySequence.length > 0) {
        // If this is a rerun (status changed to in_progress and we have a new sequence), reset the original
        if (data.status === 'in_progress' && 
            immediateStatus === 'in_progress' && 
            originalWorkflowSequenceRef.current.length > 0) {
          // Check if this is a new execution (different sequence or reset progress)
          const isNewExecution = data.current_agent === 'Starting re-execution...' || 
                                data.current_agent === 'Resuming workflow...' ||
                                (data.completed_agents && data.completed_agents.length === 0);
          
          if (isNewExecution) {
            console.log('🔄 New execution detected, checking if workflow sequence changed');
            
            // For rerun, always use the new sequence (should be full sequence)
            if (data.current_agent === 'Starting re-execution...') {
              console.log('🔄 Rerun detected, updating workflow sequence');
              originalWorkflowSequenceRef.current = [...displaySequence];
              cumulativeCompletedAgentsRef.current.clear();
            }
            // For resume, preserve the original sequence but update completed agents
            else if (data.current_agent === 'Resuming workflow...') {
              console.log('🔄 Resume detected, preserving original sequence');
              // Don't change the original sequence
            }
          }
        } else if (originalWorkflowSequenceRef.current.length === 0) {
          // First time loading, initialize the original sequence
          console.log('🔄 First time loading, initializing workflow sequence');
          originalWorkflowSequenceRef.current = [...displaySequence];
        } else {
          // Check if workflow sequence has genuinely changed (e.g., after manual intervention)
          const currentSeq = originalWorkflowSequenceRef.current;
          const newSeq = displaySequence;
          
          // Only update if the sequence is genuinely different (not just a resume slice)
          if (currentSeq.length !== newSeq.length || 
              !currentSeq.every((agent, index) => agent === newSeq[index])) {
            
            // Check if this is just a resume slice (newSeq is subset of currentSeq)
            const isResumeSlice = newSeq.length < currentSeq.length && 
                                 newSeq.every(agent => currentSeq.includes(agent));
            
            if (!isResumeSlice) {
              console.log('🔄 Workflow sequence genuinely changed, updating original sequence');
              console.log('Old sequence:', currentSeq);
              console.log('New sequence:', newSeq);
              originalWorkflowSequenceRef.current = [...newSeq];
              // Clear completed agents when sequence changes
              cumulativeCompletedAgentsRef.current.clear();
            } else {
              console.log('🔄 Detected resume slice, preserving original sequence');
            }
          }
        }
      }
      
      // Accumulate completed agents across runs/resumes
      const completedFromApi = Array.isArray(data.completed_agents) ? data.completed_agents : [];
      if (completedFromApi.length > 0) {
        for (const a of completedFromApi) {
          cumulativeCompletedAgentsRef.current.add(a);
        }
      }
      
      // Compute a lightweight signature of logs to detect changes
      const logs = Array.isArray(data.cli_logs) ? data.cli_logs : [];
      const last = logs.length ? logs[logs.length - 1] : null;
      const newKey = `${logs.length}|${last?.timestamp ?? ''}|${last?.level ?? ''}|${last?.message ?? ''}`;
      if (newKey !== lastLogsKeyRef.current) {
        lastLogsKeyRef.current = newKey;
        setVisibleLogs(data.cli_logs || []);
      }

      // Detect missing API key from CLI logs and set UI flag
      try {
        const lowerLogs = (data.cli_logs || []).map(l => (l.message || '').toLowerCase());
        const missingKey = lowerLogs.some(m =>
          m.includes('no api keys available') ||
          m.includes('please set an auth method') ||
          m.includes('gemini_api_key')
        );
        setNoApiKey(missingKey);
      } catch (_) {}
      
      setMonitorData(data);
      setImmediateStatus(data.status); // Update immediateStatus from backend
      // Clear rerunPending when real progress appears
      try {
        const hasRealProgress = (typeof data.progress_percentage === 'number' && data.progress_percentage > 0);
        const agent = data.current_agent || '';
        if (rerunPending && (hasRealProgress || (agent && agent !== 'Starting re-execution...' && agent !== 'Resuming workflow...'))) {
          setRerunPending(false);
        }
      } catch (_) {}
      
      // Clear immediate status if it matches the actual status
      if (immediateStatus === data.status) {
        setImmediateStatus(null);
      }
      // Compute candidate Gemini error, but suppress repeats immediately after clear
      const candidateErr = extractGeminiError(data.cli_logs);
      const sig = candidateErr ? `${candidateErr.code || ''}:${candidateErr.level || ''}` : '';
      const nowTs = Date.now();
      if (
        candidateErr &&
        lastClearedErrorSigRef.current.sig === sig &&
        (nowTs - lastClearedErrorSigRef.current.ts) < 60000 // suppress for 60s after clear
      ) {
        // Ignore repeated same error right after a clear
        setGeminiError(null);
      } else {
        setGeminiError(candidateErr);
        if (candidateErr) lastDetectedErrorSigRef.current = sig;
      }
      const rotation = detectKeyRotation(data.cli_logs);
      setKeyRotationStatus(rotation);
      // Notify app to refresh config immediately on rotation or exhaustion
      try {
        if (rotation) {
          const sig = `${rotation.timestamp || ''}|${rotation.message || ''}`;
          if (sig && sig !== lastRotationEventTsRef.current) {
            lastRotationEventTsRef.current = sig;
            if (typeof window !== 'undefined' && window.dispatchEvent) {
              if (rotation.type === 'rotation') {
                window.dispatchEvent(new CustomEvent('bmad:key-rotated'));
              } else if (rotation.type === 'exhaustion') {
                window.dispatchEvent(new CustomEvent('bmad:key-exhausted'));
              }
            }
          }
        }
      } catch (_) {}

      // Heuristic: if backend still reports failed but logs show active or completion, override UI status
      try {
        const recent = data.cli_logs?.slice(-15).map(l => (l.message || '').toLowerCase());
        const showsExecution = recent.some(m => m.includes('executing agent') || m.includes('starting io8coder workflow'));
        const showsCompletion = recent.some(m => m.includes('completed successfully') || m.includes('io8codermaster phase completed') || m.includes('sequential phase completed'));
        if (data.status === 'failed') {
          if (showsCompletion) {
            setImmediateStatus('completed');
          } else if (showsExecution) {
            setImmediateStatus('in_progress');
          }
        }
      } catch (_) {}

      // Capture frontend URL if present from backend
      if (typeof data.frontend_url === 'string' && data.frontend_url.startsWith('http')) {
        setFrontendUrl(data.frontend_url);
      }

      // Set current workflow if available
      if (data.workflow_id && workflows.length > 0) {
        const workflow = workflows.find(w => w.id === data.workflow_id);
        console.log('🔍 TaskMonitor Debug - workflow_id:', data.workflow_id);
        console.log('🔍 TaskMonitor Debug - available workflows:', workflows.map(w => ({ id: w.id, name: w.name })));
        console.log('🔍 TaskMonitor Debug - found workflow:', workflow);
        if (workflow) {
          setCurrentWorkflow(workflow);
          console.log('🔍 TaskMonitor Debug - set currentWorkflow:', workflow.name);
        }
      }
    } catch (err) {
      console.error('Error fetching monitor data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchMemory = async () => {
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

  const checkCanResume = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/can-resume`);
      if (res.ok) {
        const data = await res.json();
        setCanResume(data.can_resume);
        setResumeInfo(data);
      } else {
        setCanResume(false);
        setResumeInfo(null);
      }
    } catch (e) {
      setCanResume(false);
      setResumeInfo(null);
    }
  };

  const saveMemory = async () => {
    try {
      setSavingMemory(true);
      const parsed = JSON.parse(memoryDraft);
      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/memory`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ history: parsed.history || [] })
      });
      if (!res.ok) {
        throw new Error('Failed to save memory');
      }
      setShowMemoryModal(false);
      fetchMemory();
    } catch (e) {
      alert(e.message || 'Failed to save memory');
    } finally {
      setSavingMemory(false);
    }
  };

  const scrollToBottom = () => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const extractGeminiError = (logs) => {
    if (!Array.isArray(logs)) return null;
    
    // Detect explicit rotated-quota signal first to enable auto-resume
    for (let i = logs.length - 1; i >= 0; i--) {
      const msg = (logs[i]?.message || '').toLowerCase();
      if (msg.includes('quota_exhausted_rotated') || msg.includes('key rotated due to quota exhaustion')) {
        return {
          code: 'quota_exhausted_rotated',
          level: (logs[i]?.level || 'WARNING'),
          message: 'quota_exhausted_rotated'
        };
      }
    }

    // Check if there are recent successful operations that indicate the error is resolved
    const recentLogs = logs.slice(-5); // Last 5 logs
    const hasRecentSuccess = recentLogs.some(log => 
      log.message?.includes('API key rotated successfully') ||
      log.message?.includes('Session restarted successfully with new API key') ||
      log.message?.includes('Key rotation successful') ||
      log.message?.includes('completed successfully') ||
      log.message?.includes('Task analysis:')
    );
    
    // If there's recent success, don't show the error
    if (hasRecentSuccess) {
      return null;
    }
    
    // Scan newest-first for clear API error signals
    for (let i = logs.length - 1; i >= 0; i--) {
      const msg = (logs[i]?.message || '').toLowerCase();
      const lvl = (logs[i]?.level || '').toLowerCase();
      const isApiErr = msg.includes('apierror') || msg.includes('status: 429') || msg.includes('resource_exhausted') || msg.includes('too many requests') || msg.includes('exceeded your current quota') || msg.includes('quota');
      if (isApiErr) {
        let code = '429';
        if (msg.includes('401') || msg.includes('unauthorized')) code = '401';
        if (msg.includes('403') || msg.includes('forbidden')) code = '403';
        return {
          code,
          level: lvl || 'error',
          message: 'Gemini API error detected. Your API key may be out of quota or rate-limited. Please update the key or wait for quota reset.'
        };
      }
    }
    return null;
  };
  
  const detectKeyRotation = (logs) => {
    if (!Array.isArray(logs)) return null;
    // Scan newest-first for key rotation messages
    for (let i = logs.length - 1; i >= 0; i--) {
      const msg = logs[i]?.message || '';
      const lvl = logs[i]?.level || '';
      const timestamp = logs[i]?.timestamp || '';
      const lower = msg.toLowerCase();
      
      // Look for key rotation messages
      if (msg.includes('API key rotated') || 
          msg.includes('Restarting Gemini CLI session') ||
          msg.includes('Marked API key') ||
          msg.includes('Rotated to API key') ||
          msg.includes('Session restarted successfully with new API key')) {
        return {
          type: 'rotation',
          message: msg,
          timestamp: timestamp,
          level: lvl
        };
      }
      
      // Look for quota exhaustion messages (strict: only from explicit Gemini/API errors)
      if (
        lower.includes('resource_exhausted') ||
        lower.includes('status: 429') ||
        lower.includes('apierror') ||
        lower.includes('too many requests') ||
        lower.includes('exceeded your current quota') ||
        lower.includes('quota exhausted') ||
        lower.includes('quota exhausted')
      ) {
        return {
          type: 'exhaustion',
          message: msg,
          timestamp: timestamp,
          level: lvl
        };
      }
    }
    return null;
  };

  // Auto-resume flow on quota exhausted rotation: cancel current run, then queue resume via JobPro (or direct API)
  useEffect(() => {
    (async () => {
      try {
        if (!geminiError || !task || !task.task_id) return;
        const code = (geminiError.code || '').toLowerCase();
        const msg = (geminiError.message || '').toLowerCase();
        const isRotated = code === 'quota_exhausted_rotated' || msg.includes('quota_exhausted_rotated');
        if (!isRotated) return;

        // Cancel current run
        try {
          await fetch(`${API_BASE_URL}/tasks/${task.task_id}/cancel`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
        } catch (_) {}

        // Queue resume via JobPro only
        const wfSeq = monitorData?.workflow_sequence || undefined;
        const wfId = selectedWorkflowId || undefined;
        if (jobProService.isJobProEnabled()) {
          await jobProService.resumeWorkflow(task.task_id, rePrompt || undefined, wfId, wfSeq);
        }
      } catch (_) {
        // non-fatal
      }
    })();
  }, [geminiError, task?.task_id, monitorData?.workflow_sequence, selectedWorkflowId, rePrompt]);

  // Fallback auto-resume when rotation is detected but no explicit geminiError surfaced
  useEffect(() => {
    (async () => {
      try {
        if (!keyRotationStatus || keyRotationStatus.type !== 'rotation') return;
        if (!task || !task.task_id) return;
        // Debounce using existing lock/time
        await withResumeLock(async () => {
          // Cancel current run first
          try {
            await fetch(`${API_BASE_URL}/tasks/${task.task_id}/cancel`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
          } catch (_) {}

          const wfSeq = monitorData?.workflow_sequence || undefined;
          const wfId = selectedWorkflowId || undefined;
          if (jobProService.isJobProEnabled()) {
            await jobProService.resumeWorkflow(task.task_id, rePrompt || undefined, wfId, wfSeq);
          }
        });
      } catch (_) {
        // non-fatal
      }
    })();
  }, [keyRotationStatus, task?.task_id, monitorData?.workflow_sequence, selectedWorkflowId, rePrompt]);

  useEffect(() => {
    fetchMonitorData();
    fetchMemory();
    // Load available workflows for re-execution selector
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/workflows`);
        if (res.ok) {
          const data = await res.json();
          setWorkflows(Array.isArray(data.workflows) ? data.workflows : []);
        }
      } catch (e) {
        // Non-fatal
      }
    })();
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [task.task_id]);

  useEffect(() => {
    // Check if task can be resumed when there's a Gemini API error
    if (geminiError) {
      // Skip rapid re-checks right after a resume click
      if (Date.now() - (lastResumeAtRef.current || 0) > 10000) {
        checkCanResume();
      }
    } else {
      setCanResume(false);
      setResumeInfo(null);
    }
  }, [geminiError]);

  // Auto-clear Gemini error when key rotation or workflow success is detected
  useEffect(() => {
    if (!geminiError || !monitorData) return;

    // Check for key rotation success
    const hasKeyRotation = monitorData.cli_logs?.some(log => 
      log.message?.includes('API key rotated successfully') ||
      log.message?.includes('Session restarted successfully with new API key') ||
      log.message?.includes('Key rotation successful')
    );

    // Check for workflow success (no more API errors in recent logs)
    const recentLogs = monitorData.cli_logs?.slice(-10) || []; // Last 10 logs
    const hasRecentApiErrors = recentLogs.some(log => {
      const msg = (log.message || '').toLowerCase();
      return msg.includes('apierror') || 
             msg.includes('status: 429') || 
             msg.includes('resource_exhausted') || 
             msg.includes('too many requests') || 
             msg.includes('exceeded your current quota') || 
             msg.includes('quota');
    });

    // Check if task status indicates success
    const isTaskSuccessful = task.status === 'completed' || 
                            task.status === 'in_progress' ||
                            (task.status === 'failed' && !task.error_message?.includes('quota'));

    // Clear error if key rotation succeeded or no recent API errors
    if (hasKeyRotation || (!hasRecentApiErrors && isTaskSuccessful)) {
      const now = Date.now();
      if (now - lastAutoClearLogTsRef.current > 15000) { // throttle console log to every 15s
        console.log('🔄 Auto-clearing Gemini error - key rotation success or no recent API errors detected');
        lastAutoClearLogTsRef.current = now;
      }
      setGeminiError(null);
      setErrorCleared(true);
      // Remember last cleared signature to suppress immediate re-detection
      if (lastDetectedErrorSigRef.current) {
        lastClearedErrorSigRef.current = { sig: lastDetectedErrorSigRef.current, ts: now };
      }
      
      // Also clear exhaustion banner if present and no recent API errors
      setKeyRotationStatus((prev) => {
        if (!prev) return prev;
        if (prev.type === 'exhaustion') return null;
        return prev;
      });

      // Reset the error cleared state after 5 seconds
      setTimeout(() => setErrorCleared(false), 5000);
    }
  }, [geminiError, monitorData, task.status, task.error_message]);

  // Auto-clear Gemini error when task status changes to success
  useEffect(() => {
    if (!geminiError) return;

    // Clear error if task is now running successfully
    if (task.status === 'in_progress' || task.status === 'completed') {
      const now = Date.now();
      if (now - lastAutoClearLogTsRef.current > 15000) { // throttle console log to every 15s
        console.log('🔄 Auto-clearing Gemini error - task is now running successfully');
        lastAutoClearLogTsRef.current = now;
      }
      setGeminiError(null);
      setErrorCleared(true);
      if (lastDetectedErrorSigRef.current) {
        lastClearedErrorSigRef.current = { sig: lastDetectedErrorSigRef.current, ts: now };
      }
      
      // Reset the error cleared state after 5 seconds
      setTimeout(() => setErrorCleared(false), 5000);
    }
  }, [task.status, geminiError]);

  useEffect(() => {
    // Check if task can be resumed regardless of API errors
    // This allows resuming from any status where there's a current agent
    // Don't check for cancelled tasks as they cannot be resumed
    const status = monitorData?.status || task.status;
    if (status !== 'cancelled') {
      if (Date.now() - (lastResumeAtRef.current || 0) > 10000) {
        checkCanResume();
      }
    } else {
      setCanResume(false);
      setResumeInfo(null);
    }
  }, [task.task_id, monitorData?.current_agent, monitorData?.status, task.status]);

  useEffect(() => {
    // Auto-refresh every 2 seconds if task is in progress (prefer monitor status if available)
    const status = monitorData?.status || task.status;
    // Stop polling for all terminal states: completed, failed, cancelled, paused
    const terminalStates = ['completed', 'failed', 'cancelled', 'paused'];
    const isTerminalState = terminalStates.includes(status);
    
    if (autoRefresh && status === 'in_progress' && !isTerminalState) {
      if (!refreshIntervalRef.current) {
        refreshIntervalRef.current = setInterval(() => { fetchMonitorData(); fetchMemory(); }, 2000);
      }
    } else {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
        refreshIntervalRef.current = null;
      }
    }
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
        refreshIntervalRef.current = null;
      }
    };
  }, [autoRefresh, monitorData?.status, task.status]);

  useEffect(() => {
    if (autoScrollLogs) {
      scrollToBottom();
    }
    return () => {
      if (resumeRefreshIntervalRef.current) {
        clearInterval(resumeRefreshIntervalRef.current);
        resumeRefreshIntervalRef.current = null;
      }
    };
  }, [visibleLogs]);

  const currentStatus = immediateStatus || monitorData?.status || task.status;

  // Derived progress model: full sequence and cumulative completed agents
  const fullWorkflowSequence = (
    (originalWorkflowSequenceRef.current && originalWorkflowSequenceRef.current.length > 0)
      ? originalWorkflowSequenceRef.current
      : (monitorData?.workflow_sequence || [])
  );
  
  // Determine if this is a rerun or resume operation
  const isRerun = monitorData?.current_agent === 'Starting re-execution...';
  const isResume = monitorData?.current_agent === 'Resuming workflow...';
  
  const cumulativeCompletedAgents = (() => {
    // For rerun, start fresh (no completed agents)
    if (isRerun) {
      return [];
    }
    
    // For resume, we need to get the completed agents from the backend
    // The backend should return the full sequence and completed agents
    if (isResume) {
      // Use the completed agents from the backend response
      const backendCompleted = Array.isArray(monitorData?.completed_agents) ? monitorData.completed_agents : [];
      if (backendCompleted.length > 0) {
        return backendCompleted;
      }
      
      // Fallback: if no backend completed agents, try to determine from the sequence
      // This happens when the backend doesn't return completed_agents properly
      const fullSeq = fullWorkflowSequence;
      const currentAgent = monitorData?.current_agent;
      if (fullSeq.length > 0 && currentAgent && fullSeq.includes(currentAgent)) {
        const currentIndex = fullSeq.indexOf(currentAgent);
        return fullSeq.slice(0, currentIndex);
      }
      
      return [];
    }
    
    // For normal execution, accumulate completed agents
    const apiCompleted = Array.isArray(monitorData?.completed_agents) ? monitorData.completed_agents : [];
    const set = new Set(cumulativeCompletedAgentsRef.current);
    for (const a of apiCompleted) set.add(a);
    // Intersect with full sequence to avoid counting unknown agents
    const seqSet = new Set(fullWorkflowSequence || []);
    return Array.from(set).filter(a => seqSet.has(a));
  })();
  
  // Compute safe progress percentage
  const computedProgressPct = (() => {
    if (rerunPending) return 0;
    const total = (fullWorkflowSequence && fullWorkflowSequence.length) ? fullWorkflowSequence.length : 0;
    if (!total) return 0;
    
    // For rerun, always start from 0%
    if (isRerun) {
      return 0;
    }
    
    // For resume, calculate based on completed agents
    if (isResume) {
      const done = Math.min(cumulativeCompletedAgents.length, total);
      const pct = Math.round((done / total) * 100);
      return Math.max(0, Math.min(100, pct));
    }
    
    // For normal execution, use cumulative completed agents
    const done = Math.min(cumulativeCompletedAgents.length, total);
    const pct = Math.round((done / total) * 100);
    return Math.max(0, Math.min(100, pct));
  })();
  
  const backendPct = typeof monitorData?.progress_percentage === 'number' ? monitorData.progress_percentage : 0;
  const safeBackendPct = Math.max(0, Math.min(100, Math.round(backendPct)));
  
  // Use the most appropriate progress percentage
  const overallProgressPct = (() => {
    if (rerunPending) return 0;
    if (isRerun) {
      return 0; // Always start from 0% for rerun
    }
    if (isResume) {
      return Math.max(safeBackendPct, computedProgressPct);
    }
    return Math.max(safeBackendPct, computedProgressPct);
  })();

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'bg-green-500';
      case 'in_progress': return 'bg-blue-500';
      case 'failed': return 'bg-red-500';
      case 'cancelled': return 'bg-orange-500';
      case 'paused': return 'bg-yellow-500';
      default: return 'bg-gray-500';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return '✅';
      case 'in_progress': return '🔄';
      case 'failed': return '❌';
      case 'cancelled': return '⏹️';
      case 'paused': return '⏸️';
      default: return '⏳';
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '';
    return new Date(timestamp).toLocaleTimeString();
  };

  const getLogLevelColor = (level) => {
    switch (level?.toLowerCase()) {
      case 'error': return 'text-red-400';
      case 'warning': return 'text-yellow-400';
      case 'info': return 'text-blue-400';
      case 'debug': return 'text-gray-400';
      default: return 'text-gray-300';
    }
  };

  const getAgentIcon = (agentName) => {
    const icons = {
      'analyst': '📊',
      'architect': '🏗️',
      'pm': '📋',
      'sm': '📅',
      'developer': '💻',
      'devops': '🚀',
      'tester': '🧪',
      'po': '👤',
      'io8codermaster': '🧠',
      'directory_structure': '🗂️'
    };
    return icons[agentName] || '🤖';
  };

  const memorySummary = (() => {
    const hist = Array.isArray(memory.history) ? memory.history : [];
    if (hist.length === 0) return 'No memory yet';
    const last = hist[hist.length - 1];
    const completed = (last.agents_progress?.completed || []).length;
    const remaining = (last.agents_progress?.remaining || []).length;
    return `Last prompt: "${(last.prompt || '').slice(0, 80)}" — ${completed} done, ${remaining} remaining`;
  })();

  if (loading && !monitorData) {
    return (
      <Card className="bmad-card">
        <CardContent className="p-6">
          <div className="flex items-center justify-center space-x-2">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>Loading monitor data...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="bmad-card border-red-200">
        <CardContent className="p-6">
          <div className="text-red-600">
            <p>Error loading monitor data: {error}</p>
            <Button onClick={fetchMonitorData} className="mt-2">
              <RefreshCw className="w-4 h-4 mr-2" />
              Retry
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Gemini API Error Banner */}
      {geminiError && (
        <Card className="border-red-500/40 bg-red-500/10">
          <CardContent className="p-4">
            <div className="flex items-start space-x-3">
              <span className="text-red-400 text-xl">⚠️</span>
              <div>
                <p className="font-semibold text-red-400">Gemini API Error {geminiError.code}</p>
                <p className="text-sm text-red-300">
                  {geminiError.message}
                </p>
                <p className="text-xs text-red-300 mt-1">
                  Tip: Rotate/update your API key in settings, or wait for quota reset. Large context requests are minimized via code-tree manifests.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Success Message when Error is Auto-Cleared */}
      {errorCleared && (
        <Card className="border-green-500/40 bg-green-500/10">
          <CardContent className="p-4">
            <div className="flex items-start space-x-3">
              <span className="text-green-400 text-xl">✅</span>
              <div>
                <p className="font-semibold text-green-400">API Issue Resolved</p>
                <p className="text-sm text-green-300">
                  The Gemini API error has been automatically resolved through key rotation or workflow success.
                </p>
                <p className="text-xs text-green-300 mt-1">
                  Your workflow is now running normally. This message will disappear in a few seconds.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Key Rotation Status Banner */}
      {keyRotationStatus && (
        <Card className={`${
          keyRotationStatus.type === 'rotation' 
            ? 'border-green-500/40 bg-green-500/10' 
            : 'border-yellow-500/40 bg-yellow-500/10'
        }`}>
          <CardContent className="p-4">
            <div className="flex items-start space-x-3">
              <span className={`text-xl ${
                keyRotationStatus.type === 'rotation' ? 'text-green-400' : 'text-yellow-400'
              }`}>
                {keyRotationStatus.type === 'rotation' ? '🔄' : '⚠️'}
              </span>
              <div>
                <p className={`font-semibold ${
                  keyRotationStatus.type === 'rotation' ? 'text-green-400' : 'text-yellow-400'
                }`}>
                  {keyRotationStatus.type === 'rotation' ? 'API Key Rotation' : 'API Key Exhaustion'}
                </p>
                <p className={`text-sm ${
                  keyRotationStatus.type === 'rotation' ? 'text-green-300' : 'text-yellow-300'
                }`}>
                  {keyRotationStatus.message}
                </p>
                <p className={`text-xs ${
                  keyRotationStatus.type === 'rotation' ? 'text-green-300' : 'text-yellow-300'
                } mt-1`}>
                  {keyRotationStatus.type === 'rotation' 
                    ? '✅ System automatically rotated to a new API key and restarted the session.'
                    : '🔄 System will automatically rotate to the next available API key.'
                  }
                </p>
                {keyRotationStatus.timestamp && (
                  <p className={`text-xs ${
                    keyRotationStatus.type === 'rotation' ? 'text-green-300' : 'text-yellow-300'
                  } mt-1 opacity-75`}>
                    Time: {new Date(keyRotationStatus.timestamp).toLocaleString()}
                  </p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Manual Intervention Required Banner */}
      {task.error_message && task.error_message.includes('No additional API keys available') && (
        <Card className="border-red-500/40 bg-red-500/10">
          <CardContent className="p-4">
            <div className="flex items-start space-x-3">
              <span className="text-red-400 text-xl">🛑</span>
              <div>
                <p className="font-semibold text-red-400">Manual Intervention Required</p>
                <p className="text-sm text-red-300">
                  API quota exhausted and no additional API keys are available for automatic rotation.
                </p>
                <p className="text-xs text-red-300 mt-1">
                  <strong>Action Required:</strong> Please add a new API key in the settings, then manually resume the workflow.
                </p>
                <div className="mt-2 text-xs text-red-300">
                  <p>1. Go to Settings → Gemini API Keys</p>
                  <p>2. Add a new API key</p>
                  <p>3. Return here and click "Resume from Current Agent"</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}



      {/* Re-execute Controls */}
      <Card className="bmad-card">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">🔁</span>
              <div>
                <CardTitle className="bmad-text-primary">Re-run Workflow on This Task</CardTitle>
                <p className="text-sm bmad-text-muted">Choose a workflow and apply a new prompt to modify/fix in-place. Runs in the same project folder.</p>
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Button variant="outline" size="sm" onClick={() => { setMemoryDraft(JSON.stringify({ history: memory.history }, null, 2)); setShowMemoryModal(true); }}>
                View/Edit Memory
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="text-xs bmad-text-muted">{memorySummary}</div>
          <div className="grid md:grid-cols-3 gap-3">
            <div className="md:col-span-2">
              <textarea
                className="w-full bmad-input h-20"
                placeholder="Enter modification/fix prompt (e.g., Update navbar color and fix login API error)"
                value={rePrompt || ''}
                onChange={(e) => setRePrompt(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm bmad-text-muted">Workflow</label>
              <select
                className="w-full bmad-input"
                value={selectedWorkflowId || ''}
                onChange={(e) => setSelectedWorkflowId(e.target.value)}
              >
                <option value="">Default Workflow</option>
                {(workflows || []).map((wf) => (
                  <option key={wf.id} value={wf.id}>{wf.name}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            {/* 
              Note: These buttons stop the current session directly, then:
              - If JobPro is enabled: queue the new run via JobPro
              - If JobPro is disabled: call backend API directly
            */}

            {/* Missing API Key warning */}
            {noApiKey && (
              <div className="w-full mb-3 p-3 bg-red-50 border border-red-300 rounded-lg text-sm text-red-700">
                <strong>Gemini API key is not configured.</strong> Please add your API key in Settings before running workflows.
              </div>
            )}
            
            {/* Status indicator for running tasks */}
            {isTaskRunning() && (
              <div className="w-full mb-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center text-sm text-blue-700">
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  <span>
                    <strong>Task is currently running.</strong> Clicking the buttons below will:
                    <br />
                    • Cancel the current execution immediately (direct call)
                    <br />
                    • Start the new execution via JobPro (or direct API if disabled)
                  </span>
                </div>
              </div>
            )}
            
            <Button
              disabled={noApiKey}
              onClick={async () => {
                if (!rePrompt || !rePrompt.trim()) return;
                try {
                  // Step 1: Cancel the current run immediately via direct API
                  try {
                    await fetch(`${API_BASE_URL}/tasks/${task.task_id}/cancel`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' }
                    });
                  } catch (_) {}
                  
                  // Step 2: Queue the rerun via JobPro if enabled, else direct API
                  const wfSeq = monitorData?.workflow_sequence || undefined;
                  const wfId = selectedWorkflowId || undefined;
                  if (jobProService.isJobProEnabled()) {
                    console.log('🔄 Rerunning workflow through JobPro after cancel');
                    const result = await jobProService.rerunWorkflow(
                      task.task_id,
                      rePrompt,
                      wfId,
                      wfSeq
                    );
                    if (!result.success) {
                      throw new Error(result.error || 'Failed to queue rerun workflow');
                    }
                  } else {
                    console.log('JobPro disabled, calling backend directly for rerun');
                    const body = { user_prompt: rePrompt };
                    if (wfId) body.workflow_id = wfId;
                    if (wfSeq) body.workflow_sequence = wfSeq;
                    const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/reexecute`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify(body)
                    });
                    if (!res.ok) {
                      const err = await res.json().catch(() => ({}));
                      throw new Error(err.error || 'Failed to start re-execution');
                    }
                  }
                  
                  setError(null);
                  setRePrompt('');
                  setSelectedWorkflowId('');
                  setImmediateStatus('in_progress');
                  setRerunPending(true);
                  // Clear local completed markers so UI shows 0%
                  try { cumulativeCompletedAgentsRef.current.clear(); } catch (_) {}
                  if (monitorData) {
                    setMonitorData(prev => ({
                      ...prev,
                      status: 'in_progress',
                      current_agent: 'Starting re-execution...'
                    }));
                  }
                  onRefresh && onRefresh();
                  fetchMonitorData();
                  fetchMemory();
                } catch (e) {
                  console.error('Re-execution failed:', e);
                  setError(e.message || 'Failed to start re-execution');
                }
              }}
              className="bmad-button-primary"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              {isTaskRunning() ? 'Cancel & Restart with New Prompt' : 'Run with New Prompt'}
            </Button>
            {true && canResume && (
              <Button
                disabled={noApiKey || resumingWorkflow || selectedWorkflowId !== ''}
                onClick={async () => {
                  await withResumeLock(async () => {
                    try {
                      setResumingWorkflow(true);
                      setResumeError(null);
                      
                      // Step 1: Cancel the current run immediately via direct API
                      try {
                        await fetch(`${API_BASE_URL}/tasks/${task.task_id}/cancel`, {
                          method: 'POST',
                          headers: { 'Content-Type': 'application/json' }
                        });
                      } catch (_) {}
                      
                      // Step 2: Queue the resume via JobPro only
                      const wfSeq = monitorData?.workflow_sequence || undefined;
                      const wfId = selectedWorkflowId || undefined;
                      if (jobProService.isJobProEnabled()) {
                        console.log('🔄 Resuming workflow through JobPro after cancel');
                        const result = await jobProService.resumeWorkflow(
                          task.task_id,
                          rePrompt || undefined,
                          wfId,
                          wfSeq
                        );
                        if (!result.success) {
                          throw new Error(result.error || 'Failed to queue resume workflow');
                        }
                      } else {
                        throw new Error('JobPro is disabled. Enable JobPro to use Resume.');
                      }
                      
                      setError(null);
                      setRePrompt('');
                      setSelectedWorkflowId('');
                      setImmediateStatus('in_progress');
                      if (monitorData) {
                        setMonitorData(prev => ({
                          ...prev,
                          status: 'in_progress',
                          current_agent: 'Resuming workflow...'
                        }));
                      }
                      onRefresh && onRefresh();
                      fetchMonitorData();
                      fetchMemory();
                      
                      if (resumeRefreshIntervalRef.current) {
                        clearInterval(resumeRefreshIntervalRef.current);
                      }
                      resumeRefreshIntervalRef.current = setInterval(() => {
                        fetchMonitorData();
                        fetchMemory();
                      }, 2000);
                      setTimeout(() => {
                        if (resumeRefreshIntervalRef.current) {
                          clearInterval(resumeRefreshIntervalRef.current);
                          resumeRefreshIntervalRef.current = null;
                        }
                      }, 30000);
                    } catch (e) {
                      console.error('Resume workflow failed:', e);
                      setResumeError(e.message || 'Failed to resume workflow');
                    } finally {
                      setResumingWorkflow(false);
                    }
                  });
                }}
                className="bg-orange-600 hover:bg-orange-700 text-white border-orange-500"
              >
                {resumingWorkflow ? (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                    Resuming...
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-4 h-4 mr-2" />
                    {isTaskRunning() ? 'Cancel & Resume from Current Agent' : 'Resume from Current Agent'}
                  </>
                )}
              </Button>
            )}
            <Button variant="outline" onClick={() => { fetchMonitorData(); fetchMemory(); }}>
              <RefreshCw className="w-4 h-4 mr-2" /> Refresh Monitor
            </Button>
          </div>
          {resumeError && (
            <div className="mt-2 p-2 rounded border border-red-500/30 bg-red-500/10">
              <div className="text-red-300 text-sm">{resumeError}</div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Task Header */}
      <Card className="bmad-card">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <span className="text-2xl">{getStatusIcon(currentStatus)}</span>
              <div>
                <CardTitle className="bmad-text-primary">
                  Task {task.task_id.slice(0, 8)}
                </CardTitle>
                <p className="text-sm bmad-text-muted">{task.prompt}</p>
              </div>
            </div>
            <div className="flex items-center space-x-3">
              <Badge 
                variant="outline" 
                className={`${getStatusColor(currentStatus)} text-white`}
              >
                {currentStatus}
              </Badge>
              {frontendUrl && (
                <Badge 
                  variant="outline" 
                  className="bg-green-500/20 text-green-300 border-green-400"
                >
                  🌐 Public Access
                </Badge>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAutoRefresh(!autoRefresh)}
                className={autoRefresh ? 'bg-blue-500 text-white' : ''}
              >
                <RefreshCw className={`w-4 h-4 ${autoRefresh && currentStatus === 'in_progress' ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
        {frontendUrl && (
          <CardContent className="pt-0">
            <div className="mt-2 p-4 rounded-lg border-2 border-green-500/40 bg-gradient-to-r from-green-500/20 to-emerald-500/20">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
                  <span className="font-bold text-green-300 text-lg">🚀 Deployed App Access</span>
                </div>
                <Badge variant="outline" className="bg-green-500/20 text-green-300 border-green-400">
                  Zrok Share
                </Badge>
              </div>
              <div className="space-y-2">
                <div className="text-sm text-green-200">
                  <span className="font-semibold">Public URL: </span>
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
                  ✅ This URL provides external access to your deployed application via zrok
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <div className="text-xs text-green-300/70">
                  Share this URL with users to access your app from anywhere
                </div>
                <Button
                  size="sm"
                  className="bg-green-600 hover:bg-green-700 text-white border-green-500"
                  onClick={async () => {
                    try {
                      const res = await fetch(`${API_BASE_URL}/tasks/${task.task_id}/deploy/refresh-link`, { 
                        method: 'POST', 
                        headers: { 'Content-Type': 'application/json' }
                      });
                      if (res.ok) {
                        const d = await res.json();
                        if (d.frontend_url) setFrontendUrl(d.frontend_url);
                      }
                    } catch (e) {}
                  }}
                >
                  🔄 Refresh Link
                </Button>
              </div>
            </div>
          </CardContent>
        )}

        {/* Show when no frontend URL is available */}
        {!frontendUrl && currentStatus === 'completed' && (
          <CardContent className="pt-0">
            <div className="mt-2 p-4 rounded-lg border-2 border-blue-500/40 bg-gradient-to-r from-blue-500/20 to-cyan-500/20">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <div className="w-3 h-3 bg-blue-400 rounded-full animate-pulse"></div>
                  <span className="font-bold text-blue-300 text-lg">🌐 Create Public Access</span>
                </div>
                <Badge variant="outline" className="bg-blue-500/20 text-blue-300 border-blue-400">
                  Ready to Share
                </Badge>
              </div>
              <div className="space-y-2">
                <div className="text-sm text-blue-200">
                  Your application has been deployed successfully! Create a public zrok share to provide external access.
                </div>
                <div className="text-xs text-blue-300/80">
                  💡 This will generate a public URL that users can access from anywhere
                </div>
              </div>
              <div className="mt-3 flex items-center justify-between">
                <div className="text-xs text-blue-300/70">
                  Click the button below to create a zrok share automatically
                </div>
                <Button
                  size="sm"
                  className="bg-blue-600 hover:bg-blue-700 text-white border-blue-500"
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
                      } else {
                        const errorText = await res.text();
                        let errorData = {};
                        try { errorData = JSON.parse(errorText); } catch {}
                        setShareError(errorData.error || 'Failed to create zrok share');
                      }
                    } catch (e) {
                      console.error('Failed to create auto-share:', e);
                      setShareError('Network error: ' + e.message);
                    } finally {
                      setCreatingShare(false);
                    }
                  }}
                  disabled={creatingShare}
                >
                  {creatingShare ? '🔄 Creating...' : '🚀 Create Zrok Share'}
                </Button>
              </div>
            </div>
          </CardContent>
        )}
      </Card>

      {/* Progress Section */}
      {monitorData && (
        <>
          {/* Use SubworkflowSlider for workflow3, regular progress for others */}
          {(() => {
            console.log('🔍 TaskMonitor Debug - currentWorkflow:', currentWorkflow);
            console.log('🔍 TaskMonitor Debug - currentWorkflow name:', currentWorkflow?.name);
            console.log('🔍 TaskMonitor Debug - is combined workflow?', currentWorkflow && (currentWorkflow.name === 'End-to-End Plan + Execute' || currentWorkflow.name === 'io8 Default'));
            return currentWorkflow && (currentWorkflow.name === 'End-to-End Plan + Execute' || currentWorkflow.name === 'io8 Default');
          })() ? (
            <SubworkflowSlider
              workflow={currentWorkflow}
              agents={{}}
              currentStatus={currentStatus}
              currentAgent={monitorData?.current_agent || task.current_agent}
              completedAgents={cumulativeCompletedAgents}
            />
          ) : (
            <Card className="bmad-card overflow-hidden">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="bmad-text-primary text-lg">Progress</CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={resetWorkflowSequence}
                    className="text-xs"
                    title="Reset workflow sequence display if it gets out of sync"
                  >
                    <RefreshCw className="w-3 h-3 mr-1" />
                    Reset Display
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Enhanced Progress Bar */}
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="bmad-text-muted">Overall Progress</span>
                    <span className="bmad-text-primary font-semibold">{overallProgressPct}%</span>
                  </div>
                  <div className="relative overflow-hidden">
                    <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
                      <div 
                        className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-blue-600 rounded-full transition-all duration-1000 ease-out relative"
                        style={{ 
                          width: `${overallProgressPct}%`,
                          backgroundSize: '200% 100%',
                          animation: overallProgressPct > 0 && currentStatus === 'in_progress' ? 'shimmer 2s ease-in-out infinite' : 'none'
                        }}
                      >
                        {/* Shimmer effect */}
                        <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent transform -skew-x-12 animate-pulse"></div>
                      </div>
                    </div>
                    {/* Progress indicator dots (no overflow outside) */}
                    {fullWorkflowSequence && fullWorkflowSequence.length > 0 && (
                      <div className="relative mt-2 h-10 overflow-hidden px-2">
                        {fullWorkflowSequence.map((agent, index) => {
                          const isCompleted = cumulativeCompletedAgents.includes(agent);
                          const isCurrent = (() => {
                            // For rerun, highlight the first agent
                            if (isRerun && index === 0) {
                              return true;
                            }
                            // For resume, highlight the current agent from backend
                            if (isResume) {
                              return agent === (monitorData?.current_agent || task.current_agent);
                            }
                            // For normal execution, use the standard logic
                            return agent === (monitorData?.current_agent || task.current_agent);
                          })();
                          
                          const lastIndex = fullWorkflowSequence.length - 1;
                          const denom = Math.max(1, lastIndex);
                          const leftPct = (index / denom) * 100;
                          // Clamp first and last positions so labels stay inside container
                          const posStyle =
                            index === 0
                              ? { left: '0%', transform: 'translateX(0%)' }
                              : index === lastIndex
                              ? { left: '100%', transform: 'translateX(-100%)' }
                              : { left: `${leftPct}%`, transform: 'translateX(-50%)' };
                          const alignClass = index === 0 ? 'text-left' : index === lastIndex ? 'text-right' : 'text-center';
                          
                          // Determine the visual state of each agent indicator
                          let indicatorState = 'pending';
                          if (isCompleted) {
                            indicatorState = 'completed';
                          } else if (isCurrent) {
                            indicatorState = 'current';
                          } else if (isRerun && index === 0) {
                            // For rerun, show first agent as current even if not explicitly marked
                            indicatorState = 'current';
                          }
                          
                          return (
                            <div
                              key={agent}
                              className={`absolute top-0 flex flex-col items-center ${
                                indicatorState === 'completed' ? 'text-green-400' : 
                                indicatorState === 'current' ? 'text-blue-400' : 'text-gray-500'
                              }`}
                              style={posStyle}
                            >
                              <div
                                className={`w-3 h-3 rounded-full border-2 transition-all duration-300 ${
                                  indicatorState === 'completed'
                                    ? 'bg-green-500 border-green-400'
                                    : indicatorState === 'current'
                                    ? 'bg-blue-500 border-blue-400 animate-pulse'
                                    : 'bg-gray-600 border-gray-500'
                                }`}
                              />
                              <span className={`text-xs mt-1 ${alignClass}`}>
                                {agent}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
                
                {/* Debug Information */}
                <div className="text-xs text-gray-400 space-y-1">
                  <div className="flex justify-between">
                    <span>Workflow Sequence:</span>
                    <span className="font-mono">
                      {fullWorkflowSequence.length > 0 
                        ? fullWorkflowSequence.join(' → ') 
                        : 'Not available'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Completed Agents:</span>
                    <span className="font-mono">
                      {cumulativeCompletedAgents.length > 0 
                        ? cumulativeCompletedAgents.join(', ') 
                        : 'None'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Current Agent:</span>
                    <span className="font-mono">
                      {monitorData?.current_agent || 'Unknown'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Progress:</span>
                    <span className="font-mono">
                      {overallProgressPct}% ({cumulativeCompletedAgents.length}/{fullWorkflowSequence.length})
                    </span>
                  </div>
                  {isRerun && (
                    <div className="text-blue-400 font-semibold">
                      🔄 Rerunning workflow from start
                    </div>
                  )}
                  {isResume && (
                    <div className="text-orange-400 font-semibold">
                      🔄 Resuming workflow from current agent
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Deployment Information Section */}
      {currentStatus === 'completed' && (
        <Card className="bmad-card">
          <CardHeader className="pb-3">
            <CardTitle className="bmad-text-primary text-lg">🚀 Deployment Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Deployment Status */}
              <div className="p-4 rounded-lg border border-green-500/30 bg-green-500/10">
                <div className="flex items-center space-x-2 mb-2">
                  <div className="w-2 h-2 bg-green-400 rounded-full"></div>
                  <span className="font-semibold text-green-300">Status</span>
                </div>
                <div className="text-green-200 text-sm">
                  ✅ Application deployed successfully
                </div>
                <div className="text-green-300/70 text-xs mt-1">
                  Ready for external access via zrok
                </div>
              </div>

              {/* Zrok Status */}
              <div className="p-4 rounded-lg border border-blue-500/30 bg-blue-500/10">
                <div className="flex items-center space-x-2 mb-2">
                  <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
                  <span className="font-semibold text-blue-300">Zrok Integration</span>
                </div>
                <div className="text-blue-200 text-sm">
                  {frontendUrl ? '🔗 Public URL Created' : '⏳ Ready to Create'}
                </div>
                <div className="text-blue-300/70 text-xs mt-1">
                  {frontendUrl ? 'External access enabled' : 'Click to create public share'}
                </div>
              </div>
            </div>

            {/* Quick Actions */}
            <div className="flex flex-wrap gap-2">
              {!frontendUrl && (
                <Button
                  size="sm"
                  className="bg-blue-600 hover:bg-blue-700 text-white border-blue-500"
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
                      } else {
                        const errorText = await res.text();
                        let errorData = {};
                        try { errorData = JSON.parse(errorText); } catch {}
                        setShareError(errorData.error || 'Failed to create zrok share');
                      }
                    } catch (e) {
                      console.error('Failed to create auto-share:', e);
                      setShareError('Network error: ' + e.message);
                    } finally {
                      setCreatingShare(false);
                    }
                  }}
                  disabled={creatingShare}
                >
                  {creatingShare ? '🔄 Creating...' : '🚀 Create Zrok Share'}
                </Button>
              )}
              {frontendUrl && (
                <Button
                  size="sm"
                  variant="outline"
                  className="border-green-500 text-green-300 hover:bg-green-500/20"
                  onClick={() => {
                    const clean = String(frontendUrl || '').replace(/\"/g, '').replace(/",".*$/,'').replace(/["\]}]+$/,'').trim();
                    if (clean) navigator.clipboard.writeText(clean);
                    // You could add a toast notification here
                  }}
                >
                  📋 Copy URL
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                className="border-gray-500 text-gray-300 hover:bg-gray-500/20"
                onClick={() => {
                  const clean = String(frontendUrl || '').replace(/\"/g, '').replace(/",".*$/,'').replace(/["\]}]+$/,'').trim();
                  if (clean) window.open(clean, '_blank');
                }}
                disabled={!frontendUrl}
              >
                🌐 Open App
              </Button>
            </div>

            {/* Error Display */}
            {shareError && (
              <div className="mt-3 p-3 rounded-lg border border-red-500/30 bg-red-500/10">
                <div className="flex items-center space-x-2">
                  <div className="w-2 h-2 bg-red-400 rounded-full"></div>
                  <span className="text-red-300 text-sm font-medium">Share Creation Failed</span>
                </div>
                <div className="text-red-200 text-sm mt-1">{shareError}</div>
                <div className="text-red-300/70 text-xs mt-2">
                  💡 Make sure zrok is properly configured and running on the backend
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Deployment Instructions for DevOps Agent */}
      {currentStatus === 'completed' && (
        <Card className="bmad-card">
          <CardHeader className="pb-3">
            <CardTitle className="bmad-text-primary text-lg">📋 DevOps Instructions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-4 rounded-lg border border-yellow-500/30 bg-yellow-500/10">
              <div className="flex items-center space-x-2 mb-2">
                <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
                <span className="font-semibold text-yellow-300">Zrok Share Commands</span>
              </div>
              <div className="text-yellow-200 text-sm space-y-2">
                <p>✅ <strong>Automatic Port Detection:</strong> The system now automatically detects the frontend port from docker-compose.yml and creates deploy.json.</p>
                <p>After successful deployment, you can create public access using:</p>
                <div className="bg-gray-800 p-3 rounded font-mono text-xs">
                  <div className="text-green-400"># Check zrok status</div>
                  <div className="text-gray-300">zrok status</div>
                  <br/>
                  <div className="text-green-400"># Create zrok share (port auto-detected)</div>
                  <div className="text-gray-300">curl -X POST http://157.66.191.31:9191http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006/api/tasks/{task.task_id}/deploy/auto-share</div>
                  <br/>
                  <div className="text-green-400"># Or use the manual endpoint</div>
                  <div className="text-gray-300">curl -X POST http://157.66.191.31:9191http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006http://157.66.191.31:5006/api/tasks/{task.task_id}/deploy/frontend/share</div>
                </div>
                <p className="text-green-300/80 text-xs mt-2">
                  🎉 <strong>New Feature:</strong> The system automatically detects the correct frontend port from docker-compose.yml and creates deploy.json with the right port information for zrok sharing.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Logs Section */}
      <Card className="bmad-card">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="bmad-text-primary text-lg">Real-time Logs</CardTitle>
            <div className="flex items-center space-x-2">
              <span className="text-sm bmad-text-muted">
                {visibleLogs?.length || 0} logs
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={fetchMonitorData}
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
              <Button
                variant={autoScrollLogs ? 'default' : 'outline'}
                size="sm"
                onClick={() => setAutoScrollLogs(!autoScrollLogs)}
              >
                {autoScrollLogs ? 'Auto-scroll On' : 'Auto-scroll Off'}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <ScrollArea className="h-96 w-full">
            <div className="p-4 space-y-2">
              {visibleLogs && visibleLogs.length > 0 ? (
                visibleLogs.map((log, index) => (
                  <div
                    key={index}
                    className={`text-sm font-mono p-2 rounded ${
                      log.level === 'ERROR' 
                        ? 'bg-red-500/10 border border-red-500/20' 
                        : log.level === 'WARNING'
                        ? 'bg-yellow-500/10 border border-yellow-500/20'
                        : 'bg-gray-500/10 border border-gray-500/20'
                    }`}
                  >
                    <div className="flex items-start space-x-2">
                      <span className={`text-xs ${getLogLevelColor(log.level)}`}>
                        [{log.level || 'INFO'}]
                      </span>
                      <span className="text-xs bmad-text-muted">
                        {formatTimestamp(log.timestamp)}
                      </span>
                    </div>
                    <div className={`mt-1 ${getLogLevelColor(log.level)}`}>
                      {log.message}
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 bmad-text-muted">
                  <Activity className="w-8 h-8 mx-auto mb-2" />
                  <p>No logs available yet</p>
                </div>
              )}
              <div ref={logsEndRef} />
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Memory Modal */}
      {showMemoryModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-gray-700 rounded-lg w-full max-w-2xl p-4">
            <div className="flex items-center justify-between mb-2">
              <CardTitle className="bmad-text-primary">Task Memory</CardTitle>
              <Button variant="outline" size="sm" onClick={() => setShowMemoryModal(false)}>
                Close
              </Button>
            </div>
            <p className="text-xs bmad-text-muted mb-2">Edit as JSON. Only user prompts and agent progress are stored.</p>
            <textarea
              className="w-full h-72 bmad-input font-mono"
              value={memoryDraft}
              onChange={(e) => setMemoryDraft(e.target.value)}
            />
            <div className="mt-3 flex items-center justify-end space-x-2">
              <Button variant="outline" onClick={() => setMemoryDraft(JSON.stringify({ history: memory.history }, null, 2))}>Reset</Button>
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

export default TaskMonitor;

