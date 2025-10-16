import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { CheckCircle, Clock, MoreVertical } from 'lucide-react';
import { API_BASE_URL, getApiUrl } from '../config/environment';

// Backend URL configuration - Use centralized environment config

function WorkflowSelector({ onWorkflowSelect, selectedWorkflow, agents, compact = false, selectedWorkflowSequence = [], onWorkflowSequenceChange }) {
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showSelector, setShowSelector] = useState(false);
  const [search, setSearch] = useState('');
  const containerRef = useRef(null);

  // Fetch workflows on component mount
  useEffect(() => {
    fetchWorkflows();
  }, []);

  const fetchWorkflows = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/workflows`);
      if (response.ok) {
        const data = await response.json();
        console.log('Fetched workflows:', data.workflows);
        setWorkflows(data.workflows || []);
      } else {
        console.error('Failed to fetch workflows');
      }
    } catch (error) {
      console.error('Error fetching workflows:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleWorkflowSelect = (workflow) => {
    console.log('Selected workflow:', workflow);
    onWorkflowSelect(workflow);
    setShowSelector(false);
  };

  // Multi-select helpers for sequencing workflows
  const addToSequence = (wf) => {
    if (!onWorkflowSequenceChange) return;
    const exists = (selectedWorkflowSequence || []).some(w => w.id === wf.id);
    if (exists) return;
    onWorkflowSequenceChange([...(selectedWorkflowSequence || []), wf]);
  };
  const removeFromSequence = (idx) => {
    if (!onWorkflowSequenceChange) return;
    const next = (selectedWorkflowSequence || []).filter((_, i) => i !== idx);
    onWorkflowSequenceChange(next);
  };
  const moveInSequence = (from, to) => {
    if (!onWorkflowSequenceChange) return;
    const arr = Array.from(selectedWorkflowSequence || []);
    if (to < 0 || to >= arr.length) return;
    const [item] = arr.splice(from, 1);
    arr.splice(to, 0, item);
    onWorkflowSequenceChange(arr);
  };

  const normalizeSeq = (seq) => {
    if (Array.isArray(seq)) return seq;
    if (typeof seq === 'string') {
      try { return JSON.parse(seq); } catch { return []; }
    }
    return [];
  };

  const getSelectedWorkflowDisplay = () => {
    console.log('getSelectedWorkflowDisplay called with:', { selectedWorkflow, workflows });
    
    if (!selectedWorkflow) {
      const defaultWf = workflows.find(w => w.is_default);
      const count = defaultWf ? normalizeSeq(defaultWf.agent_sequence).length : 9;
      return {
        name: 'Default Workflow',
        description: 'Standard SureAi workflow with all agents',
        agentCount: count
      };
    }
    
    // Debug the workflow name
    console.log('Selected workflow name:', selectedWorkflow.name);
    console.log('Selected workflow type:', typeof selectedWorkflow.name);
    if (selectedWorkflow.name && typeof selectedWorkflow.name === 'string') {
      console.log('Selected workflow lowercase:', selectedWorkflow.name.toLowerCase());
      console.log('Contains flf:', selectedWorkflow.name.toLowerCase().includes('flf'));
    }
    
    return {
      name: selectedWorkflow.name,
      description: selectedWorkflow.description || 'No description',
      agentCount: normalizeSeq(selectedWorkflow.agent_sequence).length || 0
    };
  };

  const display = getSelectedWorkflowDisplay();

  // Close selector when receiving a global custom event
  useEffect(() => {
    const onClose = () => setShowSelector(false);
    document.addEventListener('close-workflow-selector', onClose);
    return () => document.removeEventListener('close-workflow-selector', onClose);
  }, []);

  // Close when clicking outside the component
  useEffect(() => {
    if (!showSelector) return;
    const handleClickOutside = (ev) => {
      const root = containerRef.current;
      if (root && !root.contains(ev.target)) {
        setShowSelector(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('touchstart', handleClickOutside, { passive: true });
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('touchstart', handleClickOutside);
    };
  }, [showSelector]);

  return (
    <div ref={containerRef} className="relative" data-workflow-selector-open={showSelector ? 'true' : 'false'}>
      {/* Workflow Display */}
      <div className="mb-3">
        {!compact && (
          <label className="block text-sm font-medium text-gray-700 mb-2">Selected Workflow</label>
        )}
        <Card
          className={`cursor-pointer hover:shadow-md transition-shadow ${compact ? 'max-w-[460px] mx-auto' : ''}`}
          onClick={() => setShowSelector(!showSelector)}
        >
          <CardContent className={`${compact ? 'p-2' : 'p-4'}`}>
            <div className="flex items-center justify-between">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 min-w-0">
                  <h4 className={`font-medium truncate ${compact ? 'text-sm' : ''}`}>{display.name}</h4>
                  {selectedWorkflow?.is_default && (
                    <Badge variant="default" className="text-[10px]">
                      Default
                    </Badge>
                  )}
                  <Badge variant="outline" className="text-[10px] whitespace-nowrap">
                    {display.agentCount} agents
                  </Badge>
                  {compact && (
                    <span className="text-[10px] text-gray-500">Change</span>
                  )}
                </div>
                <p className={`mt-1 truncate ${compact ? 'text-[11px] text-gray-500' : 'text-sm text-gray-600'}`}>
                  {display.description}
                </p>
              </div>
              <MoreVertical className="w-4 h-4 text-gray-400 flex-shrink-0" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Workflow Selector Dropdown */}
      {showSelector && (
        <div className={`absolute top-full left-0 right-0 z-40 bg-background border rounded-lg shadow-lg overflow-y-auto ${compact ? 'max-h-96' : 'max-h-[34rem]'}`}>
          <div className="p-4 border-b">
            <h3 className="font-medium">Choose a Workflow</h3>
            <p className="text-sm text-gray-600">Select the workflow for this task</p>
          </div>
          
          <div className="p-2">
            {/* Simple filter */}
            <input
              className={`w-full border rounded px-2 py-2 bg-background mb-2 ${compact ? 'text-xs' : 'text-sm'}`}
              placeholder="Filter workflows..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />

            {/* Optional sequencing UI */}
            {onWorkflowSequenceChange && (
              <div className="mb-3 p-2 border rounded">
                <div className="flex items-center justify-between mb-2">
                  <div className="font-medium text-sm">Workflow Sequence</div>
                  <div className="text-xs text-gray-500">Execute in order</div>
                </div>
                <div className="space-y-2">
                  {(selectedWorkflowSequence || []).length === 0 && (
                    <div className="text-xs text-gray-500">No workflows selected</div>
                  )}
                  {(selectedWorkflowSequence || []).map((wf, idx) => (
                    <div key={`${wf.id}-${idx}`} className="flex items-center justify-between p-2 border rounded bg-background">
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{idx + 1}. {wf.name}</div>
                        <div className="text-xs text-gray-500 truncate">{wf.description || 'No description'}</div>
                      </div>
                      <div className="flex items-center gap-1 ml-2">
                        <button className="px-2 py-1 text-xs border rounded" onClick={(e) => { e.stopPropagation(); moveInSequence(idx, idx - 1); }}>↑</button>
                        <button className="px-2 py-1 text-xs border rounded" onClick={(e) => { e.stopPropagation(); moveInSequence(idx, idx + 1); }}>↓</button>
                        <button className="px-2 py-1 text-xs border rounded" onClick={(e) => { e.stopPropagation(); removeFromSequence(idx); }}>✕</button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {loading ? (
              <div className="text-center py-8">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-gray-900 mx-auto"></div>
                <p className="mt-2 text-sm text-gray-600">Loading workflows...</p>
              </div>
            ) : workflows.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-gray-600">No workflows available</p>
              </div>
            ) : (
              <div className="space-y-2">
                {workflows
                  .filter((w) => {
                    const q = (search || '').trim().toLowerCase();
                    if (!q) return true;
                    return (w.name || '').toLowerCase().includes(q) || (w.description || '').toLowerCase().includes(q);
                  })
                  .map((workflow) => (
                  <Card
                    key={workflow.id}
                    className={`cursor-pointer hover:shadow-md transition-shadow ${
                      selectedWorkflow?.id === workflow.id ? 'ring-2 ring-primary' : ''
                    }`}
                    onClick={() => handleWorkflowSelect(workflow)}
                  >
                    <CardContent className="p-3">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <h4 className="font-medium text-sm">{workflow.name}</h4>
                            {workflow.is_default && (
                              <Badge variant="default" className="text-xs">
                                Default
                              </Badge>
                            )}
                          </div>
                          <p className="text-xs text-gray-600 mt-1 line-clamp-2">
                            {workflow.description || 'No description'}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            <Badge variant="outline" className="text-xs">
                              {normalizeSeq(workflow.agent_sequence).length || 0} agents
                            </Badge>
                            {Array.isArray(workflow.agent_models) && workflow.agent_models.filter(Boolean).length > 0 && (
                              <Badge variant="outline" className="text-xs">
                                {workflow.agent_models.filter(Boolean).length} model overrides
                              </Badge>
                            )}
                            <span className="text-xs text-gray-500">
                              {new Date(workflow.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {onWorkflowSequenceChange && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={(e) => { e.stopPropagation(); addToSequence(workflow); }}
                            >
                              Add
                            </Button>
                          )}
                          {selectedWorkflow?.id === workflow.id && (
                            <CheckCircle className="w-4 h-4 text-primary" />
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Removed full-screen overlay to allow page scrolling and interactions */}
    </div>
  );
}

export default WorkflowSelector;
