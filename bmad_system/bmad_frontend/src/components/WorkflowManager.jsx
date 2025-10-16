import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Alert, AlertDescription } from './ui/alert';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { Separator } from './ui/separator';
import { ScrollArea } from './ui/scroll-area';
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
  Plus, 
  Trash2, 
  GripVertical, 
  Edit, 
  Copy, 
  MoreVertical,
  Save,
  X,
  RotateCcw,
  CheckCircle,
  Clock,
  Maximize2
} from 'lucide-react';
import { API_BASE_URL, getApiUrl } from '../config/environment';

// Backend URL configuration - Use centralized environment config

// Sortable Workflow Item Component
function SortableWorkflowItem({ agentName, index, itemId, localAgents, onRemove, onEditHandoff, onOpenHandoffModal, modelValue, onChangeModel, availableModels, temperatureValue, onChangeTemperature, availableTemperatures, cliValue, onChangeCli, cliOptions }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: itemId });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex flex-col gap-2 p-3 border rounded bg-background transition-colors sortable-item ${isDragging ? 'dragging' : ''}`}
    >
      <div className="flex items-center gap-2">
        <span
          className="cursor-grab"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="w-4 h-4 text-gray-400 grip-handle" />
        </span>
        <div className="flex-1">
          <div className="font-medium">
            {localAgents[agentName]?.display_name || agentName}
          </div>
          <div className="text-sm text-gray-600">
            Step {index + 1}
          </div>
        </div>
        <Button
          size="sm"
          variant="outline"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onRemove(index);
          }}
        >
          <Trash2 className="w-4 h-4" />
        </Button>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-xs">Handoff Prompt (optional)</Label>
            <Button
              size="icon"
              variant="ghost"
              title="Open large editor"
              onClick={() => onOpenHandoffModal(agentName)}
            >
              <Maximize2 className="w-4 h-4" />
            </Button>
          </div>
          <Textarea
            rows={4}
            value={localAgents[agentName]?.handoff_prompt || ''}
            onChange={(e) => onEditHandoff(agentName, e.target.value)}
            placeholder="Enter handoff prompt text that will be prepended to this agent's prompt during execution"
          />
          <div className="text-xs text-gray-500">
            This text is saved per agent and applied in the default workflow execution.
          </div>
        </div>
        <div className="space-y-2">
          <Label className="text-xs">Model for this step</Label>
          <select
            className="w-full border rounded px-2 py-2 bg-background"
            value={modelValue || ''}
            onChange={(e) => onChangeModel(index, e.target.value || null)}
          >
            <option value="">Use default</option>
            {availableModels.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
          <div className="text-xs text-gray-500">
            If set, this agent will run with the selected model.
          </div>
          <Label className="text-xs mt-2 block">CLI for this step</Label>
          <select
            className="w-full border rounded px-2 py-2 bg-background"
            value={cliValue || 'gemini'}
            onChange={(e) => onChangeCli(index, e.target.value)}
          >
            {cliOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <div className="text-xs text-gray-500">
            Choose which CLI to use for this agent.
          </div>
          <Label className="text-xs mt-2 block">Temperature for this step</Label>
          <select
            className="w-full border rounded px-2 py-2 bg-background"
            value={temperatureValue === null || temperatureValue === undefined ? '' : String(temperatureValue)}
            onChange={(e) => {
              const v = e.target.value;
              onChangeTemperature(index, v === '' ? null : parseFloat(v));
            }}
          >
            <option value="">Use default</option>
            {availableTemperatures.map((t) => (
              <option key={t.value} value={String(t.value)}>{t.label}</option>
            ))}
          </select>
          <div className="text-xs text-gray-500">
            Controls randomness: lower is deterministic, higher is creative.
          </div>
        </div>
      </div>
    </div>
  );
}

// Workflow Card Component
function WorkflowCard({ workflow, agents, onEdit, onCopy, onDelete, onSelect }) {
  const [showMenu, setShowMenu] = useState(false);
  const agentSeq = Array.isArray(workflow.agent_sequence)
    ? workflow.agent_sequence
    : (typeof workflow.agent_sequence === 'string'
        ? (() => { try { return JSON.parse(workflow.agent_sequence); } catch { return []; } })()
        : []);

  return (
    <Card className="relative hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg">{workflow.name}</CardTitle>
            <CardDescription className="mt-1">
              {workflow.description || 'No description'}
            </CardDescription>
            <div className="text-xs text-gray-500 font-mono mt-1">wf-id: {workflow.id}</div>
          </div>
          <div className="relative">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowMenu(!showMenu)}
            >
              <MoreVertical className="w-4 h-4" />
            </Button>
            {showMenu && (
              <div className="absolute right-0 top-8 z-10 bg-background border rounded-md shadow-lg min-w-[120px]">
                <button
                  className="w-full px-3 py-2 text-left text-sm hover:bg-accent flex items-center gap-2"
                  onClick={() => {
                    onEdit(workflow);
                    setShowMenu(false);
                  }}
                >
                  <Edit className="w-3 h-3" />
                  Edit
                </button>
                <button
                  className="w-full px-3 py-2 text-left text-sm hover:bg-accent flex items-center gap-2"
                  onClick={() => {
                    onCopy(workflow);
                    setShowMenu(false);
                  }}
                >
                  <Copy className="w-3 h-3" />
                  Copy
                </button>
                <button
                  className="w-full px-3 py-2 text-left text-sm hover:bg-accent flex items-center gap-2 text-red-600"
                  onClick={() => {
                    onDelete(workflow);
                    setShowMenu(false);
                  }}
                >
                  <Trash2 className="w-3 h-3" />
                  Delete
                </button>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 mt-2">
          {workflow.is_default && (
            <Badge variant="default" className="text-xs">
              Default
            </Badge>
          )}
          <Badge variant="outline" className="text-xs">
            {agentSeq.length} agents
          </Badge>
          <span className="text-xs text-gray-500">
            {new Date(workflow.created_at).toLocaleDateString()}
          </span>
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-2">
          {agentSeq.slice(0, 3).map((agentName, index) => (
            <div key={index} className="flex items-center gap-2 text-sm">
              <CheckCircle className="w-3 h-3 text-green-500" />
              <span className="text-gray-600">
                {agents[agentName]?.display_name || agentName}
              </span>
            </div>
          ))}
          {agentSeq.length > 3 && (
            <div className="text-xs text-gray-500">
              +{agentSeq.length - 3} more agents
            </div>
          )}
        </div>
        
      </CardContent>
    </Card>
  );
}

// Workflow Editor Component
function WorkflowEditor({ workflow, agents, onSave, onCancel, onDelete }) {
  const parseMaybeJsonArray = (val, fallback = []) => {
    if (Array.isArray(val)) return val;
    if (typeof val === 'string') {
      try { const arr = JSON.parse(val); return Array.isArray(arr) ? arr : fallback; } catch { return fallback; }
    }
    return fallback;
  };

  const initialSequence = parseMaybeJsonArray(workflow?.agent_sequence, []);
  const initialModels = parseMaybeJsonArray(workflow?.agent_models, Array(initialSequence.length).fill(null));
  const initialTemps = parseMaybeJsonArray(workflow?.agent_temperatures, Array(initialSequence.length).fill(null));
  const initialClis = parseMaybeJsonArray(workflow?.agent_clis, Array(initialSequence.length).fill('gemini'));

  const [name, setName] = useState(workflow?.name || '');
  const [description, setDescription] = useState(workflow?.description || '');
  const [agentSequence, setAgentSequence] = useState(initialSequence);
  const [agentModels, setAgentModels] = useState(initialModels);
  const [agentTemperatures, setAgentTemperatures] = useState(initialTemps);
  const [agentClis, setAgentClis] = useState(initialClis);
  const [availableAgents, setAvailableAgents] = useState([]);
  const [localAgents, setLocalAgents] = useState(agents || {});
  const [llxprtModels, setLlxprtModels] = useState(['qwen/qwen3-coder']);
  const [savingHandoff, setSavingHandoff] = useState(false);
  const [availableSearch, setAvailableSearch] = useState('');
  const [availableMode, setAvailableMode] = useState('agents'); // 'agents' | 'workflows'
  const [availableWorkflows, setAvailableWorkflows] = useState([]);
  const [workflowsLoading, setWorkflowsLoading] = useState(false);
  const [workflowsSearch, setWorkflowsSearch] = useState('');
  const [handoffModalOpen, setHandoffModalOpen] = useState(false);
  const [handoffModalAgent, setHandoffModalAgent] = useState(null);
  const [handoffModalText, setHandoffModalText] = useState('');
  // Groups to summarize added workflows for display (not persisted)
  const [sequenceGroups, setSequenceGroups] = useState([]);
  const [showAgentDetails, setShowAgentDetails] = useState(true);
  // DnD sensors must be declared unconditionally to satisfy React hooks rules
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // When switching which workflow is being edited, reset grouping so we can reconstruct cleanly
  useEffect(() => {
    setSequenceGroups([]);
  }, [workflow?.id]);

  const availableModels = [
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-1.5-pro',
    'gemini-1.5-flash',
    'gemini-1.0-pro'
  ];
  const availableTemperatures = [
    { value: 0.0, label: '0.0 — Most deterministic' },
    { value: 0.2, label: '0.2 — Focused' },
    { value: 0.5, label: '0.5 — Balanced' },
    { value: 0.7, label: '0.7 — Common default' },
    { value: 1.0, label: '1.0 — More diverse' },
    { value: 1.2, label: '1.2 — Very creative' },
    { value: 1.5, label: '1.5 — Very creative' },
    { value: 2.0, label: '2.0 — Max creative' },
  ];

  useEffect(() => {
    // Update local agents when props change
    setLocalAgents(agents || {});
  }, [agents]);

  useEffect(() => {
    // Available agents should include all to allow repeats
    const allAgents = Object.keys(localAgents);
    setAvailableAgents(allAgents);
  }, [agentSequence, localAgents]);

  useEffect(() => {
    if (!localAgents || Object.keys(localAgents).length === 0) {
      fetchAgents();
    }
    // Fetch config to get llxprt default model
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/config`);
        if (res.ok) {
          const cfg = await res.json();
          const m = (cfg && cfg.llxprt && (cfg.llxprt.model_name || cfg.llxprt.model)) || 'qwen/qwen3-coder';
          // For now, single configured model; could extend to array later
          setLlxprtModels([m]);
        }
      } catch (e) {
        // ignore
      }
    })();
    // Fetch workflows for workflow-of-workflows builder
    (async () => {
      try {
        setWorkflowsLoading(true);
        const res = await fetch(`${API_BASE_URL}/workflows`);
        if (res.ok) {
          const data = await res.json();
          setAvailableWorkflows(Array.isArray(data.workflows) ? data.workflows : []);
        } else {
          setAvailableWorkflows([]);
        }
      } catch (_) {
        setAvailableWorkflows([]);
      } finally {
        setWorkflowsLoading(false);
      }
    })();
  }, [localAgents]);

  // Keep agentModels aligned with agentSequence length
  useEffect(() => {
    setAgentModels((prev) => {
      const copy = Array.from(prev || []);
      if (copy.length < agentSequence.length) {
        return copy.concat(Array(agentSequence.length - copy.length).fill(null));
      }
      if (copy.length > agentSequence.length) {
        return copy.slice(0, agentSequence.length);
      }
      return copy;
    });
    setAgentTemperatures((prev) => {
      const copy = Array.from(prev || []);
      if (copy.length < agentSequence.length) {
        return copy.concat(Array(agentSequence.length - copy.length).fill(null));
      }
      if (copy.length > agentSequence.length) {
        return copy.slice(0, agentSequence.length);
      }
      return copy;
    });
    setAgentClis((prev) => {
      const copy = Array.from(prev || []);
      if (copy.length < agentSequence.length) {
        return copy.concat(Array(agentSequence.length - copy.length).fill('gemini'));
      }
      if (copy.length > agentSequence.length) {
        return copy.slice(0, agentSequence.length);
      }
      return copy;
    });
  }, [agentSequence]);

  const fetchAgents = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/agents/prompts`);
      if (response.ok) {
        const data = await response.json();
        setLocalAgents(data.agents || {});
      } else {
        console.error('Failed to fetch agents');
      }
    } catch (error) {
      console.error('Error fetching agents:', error);
    }
  };

  const saveHandoffPrompt = async (agentName, text) => {
    try {
      setSavingHandoff(true);
      const resp = await fetch(`${API_BASE_URL}/agents/handoff/${agentName}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ handoff_prompt: text || '' })
      });
      setSavingHandoff(false);
      return resp.ok;
    } catch (e) {
      setSavingHandoff(false);
      return false;
    }
  };

  const handleEditHandoff = async (agentName, text) => {
    // Optimistically update local state
    setLocalAgents(prev => ({
      ...prev,
      [agentName]: { ...prev[agentName], handoff_prompt: text }
    }));
    // Persist to backend
    const ok = await saveHandoffPrompt(agentName, text);
    if (!ok) {
      console.error('Failed to save handoff prompt');
    }
  };

  const openHandoffModal = (agentName) => {
    const current = (localAgents[agentName]?.handoff_prompt) || '';
    setHandoffModalAgent(agentName);
    setHandoffModalText(current);
    setHandoffModalOpen(true);
  };

  const closeHandoffModal = () => {
    setHandoffModalOpen(false);
    setHandoffModalAgent(null);
    setHandoffModalText('');
  };

  const saveHandoffModal = async () => {
    if (!handoffModalAgent) return;
    const ok = await saveHandoffPrompt(handoffModalAgent, handoffModalText);
    if (ok) {
      setLocalAgents(prev => ({
        ...prev,
        [handoffModalAgent]: { ...prev[handoffModalAgent], handoff_prompt: handoffModalText }
      }));
      closeHandoffModal();
    } else {
      console.error('Failed to save handoff prompt');
    }
  };

  const addAgentToSequence = (agentName) => {
    setAgentSequence([...agentSequence, agentName]);
    setAgentModels((prev) => [...(prev || []), null]);
    setAgentTemperatures((prev) => [...(prev || []), null]);
    setAgentClis((prev) => [...(prev || []), 'gemini']);
  };

  const normalizeSeq = (seq) => {
    if (Array.isArray(seq)) return seq;
    if (typeof seq === 'string') { try { return JSON.parse(seq); } catch { return []; } }
    return [];
  };
  const normalizeArr = (val, fallbackLen = 0, defaultValue = null) => {
    if (Array.isArray(val)) return val;
    if (typeof val === 'string') {
      try { const arr = JSON.parse(val); return Array.isArray(arr) ? arr : Array(fallbackLen).fill(defaultValue); } catch { return Array(fallbackLen).fill(defaultValue); }
    }
    return Array(fallbackLen).fill(defaultValue);
  };

  const addWorkflowToSequence = (wf) => {
    const seq = normalizeSeq(wf?.agent_sequence) || [];
    if (seq.length === 0) return;
    const nextSequence = [...agentSequence];
    const nextModels = Array.from(agentModels || []);
    const nextTemps = Array.from(agentTemperatures || []);
    const nextClis = Array.from(agentClis || []);
    const srcModels = normalizeArr(wf.agent_models, seq.length, null);
    const srcTemps = normalizeArr(wf.agent_temperatures, seq.length, null);
    const srcClis = normalizeArr(wf.agent_clis, seq.length, 'gemini');
    for (const agentName of seq) {
      nextSequence.push(agentName);
      const idx = seq.indexOf(agentName);
      nextModels.push(srcModels[idx] ?? null);
      nextTemps.push(srcTemps[idx] ?? null);
      nextClis.push(srcClis[idx] ?? 'gemini');
    }
    setAgentSequence(nextSequence);
    setAgentModels(nextModels);
    setAgentTemperatures(nextTemps);
    setAgentClis(nextClis);
    // Update groups for display and default to collapse agent details when grouping starts
    setSequenceGroups((prev) => ([...prev, { name: wf.name, count: seq.length }]));
    setShowAgentDetails(false);
  };

  // Attempt to reconstruct grouping for combined workflows editor (legacy and io8)
  useEffect(() => {
    if (!availableWorkflows || availableWorkflows.length === 0) return;
    if (!agentSequence || agentSequence.length === 0) { setSequenceGroups([]); return; }
    // Apply grouping exclusively for combined workflows to avoid affecting other workflows
    const isCombined = (workflow?.name === 'End-to-End Plan + Execute' || workflow?.name === 'io8 Default');
    if (!isCombined) { setSequenceGroups([]); return; }
    // If already grouped by user action, keep it
    if (sequenceGroups && sequenceGroups.length > 0) return;
    try {
      const groups = [];
      let i = 0;
      while (i < agentSequence.length) {
        // Find the longest matching workflow starting at i
        let best = null;
        for (const wf of availableWorkflows) {
          // Exclude the workflow currently being edited to avoid grouping as itself
          if ((workflow?.id && wf.id === workflow.id) || (workflow?.name && wf.name === workflow.name)) {
            continue;
          }
          const seq = normalizeSeq(wf.agent_sequence);
          if (seq.length === 0) continue;
          let matches = true;
          for (let k = 0; k < seq.length; k++) {
            if (agentSequence[i + k] !== seq[k]) { matches = false; break; }
          }
          if (matches) {
            if (!best || seq.length > best.len) {
              best = { name: wf.name, len: seq.length };
            }
          }
        }
        if (best) {
          groups.push({ name: best.name, count: best.len });
          i += best.len;
        } else {
          // No workflow matched; treat single agent as its own group label
          const agentName = agentSequence[i];
          groups.push({ name: agentName, count: 1 });
          i += 1;
        }
      }
      setSequenceGroups(groups);
      setShowAgentDetails(false);
      console.log('Workflow grouping result:', { 
        workflowName: workflow?.name, 
        agentSequence: agentSequence, 
        groups: groups,
        availableWorkflows: availableWorkflows.map(w => ({ name: w.name, sequence: w.agent_sequence }))
      });
    } catch (_) {
      // ignore reconstruction errors
    }
  }, [availableWorkflows, agentSequence, workflow?.name]);

  const removeAgentFromSequence = (index) => {
    const newSequence = agentSequence.filter((_, i) => i !== index);
    setAgentSequence(newSequence);
    setAgentModels((prev) => (prev || []).filter((_, i) => i !== index));
    setAgentTemperatures((prev) => (prev || []).filter((_, i) => i !== index));
    setAgentClis((prev) => (prev || []).filter((_, i) => i !== index));
  };

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over) return;
    if (active.id !== over.id) {
      setAgentSequence((items) => {
        const currentDnd = items.map((n, i) => `${n}::${i}`);
        const oldIndex = currentDnd.indexOf(active.id);
        const newIndex = currentDnd.indexOf(over.id);
        if (oldIndex < 0 || newIndex < 0) return items;
        const moved = arrayMove(items, oldIndex, newIndex);
        // keep models aligned
        setAgentModels((prev) => arrayMove(prev, oldIndex, newIndex));
        setAgentTemperatures((prev) => arrayMove(prev, oldIndex, newIndex));
        setAgentClis((prev) => arrayMove(prev, oldIndex, newIndex));
        return moved;
      });
    }
  };

  const handleChangeModel = (index, value) => {
    setAgentModels((prev) => {
      const next = Array.from(prev || []);
      next[index] = value || null;
      return next;
    });
  };

  const handleChangeTemperature = (index, value) => {
    setAgentTemperatures((prev) => {
      const next = Array.from(prev || []);
      next[index] = value;
      return next;
    });
  };
  const handleChangeCli = (index, value) => {
    setAgentClis((prev) => {
      const next = Array.from(prev || []);
      next[index] = value || 'gemini';
      return next;
    });
  };

  // Unique DnD item IDs per position to allow duplicates
  const dndItems = (Array.isArray(agentSequence) ? agentSequence : []).map((name, idx) => `${name}::${idx}`);

  return (
    <div className="space-y-6">
      <div className="border-b pb-4">
        <h3 className="text-lg font-semibold">
          {workflow ? 'Edit Workflow' : 'Create New Workflow'}
        </h3>
      </div>

      <div className="space-y-4">
        <div>
          <Label htmlFor="workflow-name">Workflow Name</Label>
          <Input
            id="workflow-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Enter workflow name"
            className="mt-1"
          />
        </div>

        <div>
          <Label htmlFor="workflow-description">Description</Label>
          <Textarea
            id="workflow-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Enter workflow description"
            className="mt-1"
            rows={3}
          />
        </div>

        <div className="grid grid-cols-2 gap-6">
          {/* Available Items (Agents / Workflows) */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="font-medium">Available</h4>
              <div className="flex items-center gap-1">
                <Button size="sm" variant={availableMode === 'agents' ? 'default' : 'outline'} onClick={() => setAvailableMode('agents')}>Agents</Button>
                <Button size="sm" variant={availableMode === 'workflows' ? 'default' : 'outline'} onClick={() => setAvailableMode('workflows')}>Workflows</Button>
              </div>
            </div>

            {availableMode === 'agents' ? (
              <>
                <Input
                  placeholder="Search agents..."
                  value={availableSearch}
                  onChange={(e) => setAvailableSearch(e.target.value)}
                />
                <div className="space-y-2">
                  {availableAgents
                    .filter((agentName) => {
                      const q = availableSearch.trim().toLowerCase();
                      if (!q) return true;
                      const meta = localAgents[agentName] || {};
                      const nameMatch = agentName.toLowerCase().includes(q);
                      const displayMatch = (meta.display_name || '').toLowerCase().includes(q);
                      const descMatch = (meta.description || '').toLowerCase().includes(q);
                      return nameMatch || displayMatch || descMatch;
                    })
                    .map((agentName) => (
                      <div key={agentName} className="flex items-center justify-between p-3 border rounded">
                        <div>
                          <div className="font-medium">{localAgents[agentName]?.display_name || agentName}</div>
                          <div className="text-sm text-gray-600">{localAgents[agentName]?.description}</div>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => addAgentToSequence(agentName)}
                        >
                          <Plus className="w-4 h-4" />
                        </Button>
                      </div>
                    ))}
                  {availableAgents.length > 0 && availableAgents.filter((agentName) => {
                    const q = availableSearch.trim().toLowerCase();
                    if (!q) return false;
                    const meta = localAgents[agentName] || {};
                    const nameMatch = agentName.toLowerCase().includes(q);
                    const displayMatch = (meta.display_name || '').toLowerCase().includes(q);
                    const descMatch = (meta.description || '').toLowerCase().includes(q);
                    return nameMatch || displayMatch || descMatch;
                  }).length === 0 && (
                    <div className="text-center py-4 text-gray-500">
                      No matching agents
                    </div>
                  )}
                </div>
              </>
            ) : (
              <>
                <Input
                  placeholder="Search workflows..."
                  value={workflowsSearch}
                  onChange={(e) => setWorkflowsSearch(e.target.value)}
                />
                <div className="space-y-2">
                  {workflowsLoading && (
                    <div className="text-center py-4 text-gray-500">Loading workflows...</div>
                  )}
                  {!workflowsLoading && availableWorkflows
                    .filter((wf) => {
                      const q = (workflowsSearch || '').trim().toLowerCase();
                      if (!q) return true;
                      return (wf.name || '').toLowerCase().includes(q) || (wf.description || '').toLowerCase().includes(q);
                    })
                    .map((wf) => {
                      const seqLen = normalizeSeq(wf.agent_sequence).length || 0;
                      return (
                        <div key={wf.id} className="flex items-center justify-between p-3 border rounded">
                          <div className="min-w-0">
                            <div className="font-medium truncate">{wf.name}</div>
                            <div className="text-sm text-gray-600 truncate">{wf.description || 'No description'}</div>
                            <div className="text-xs text-gray-500 mt-1">{seqLen} agents</div>
                          </div>
                          <Button size="sm" variant="outline" onClick={() => addWorkflowToSequence(wf)}>
                            Add
                          </Button>
                        </div>
                      );
                    })}
                  {!workflowsLoading && availableWorkflows.length === 0 && (
                    <div className="text-center py-4 text-gray-500">No workflows found</div>
                  )}
                </div>
              </>
            )}
          </div>

          {/* Right Column: Show only Agent Sequence (as workflow names when grouped) */}
          <div className="space-y-4">
            {/* Agent Sequence: when workflows are combined (sequenceGroups), show workflow names instead of agent names */}
            {sequenceGroups.length > 0 && (workflow?.name === 'End-to-End Plan + Execute' || workflow?.name === 'io8 Default') ? (
              <div className="space-y-4">
                <h4 className="font-medium">Agent Sequence</h4>
                <div className="space-y-2">
                  {sequenceGroups.map((g, i) => (
                    <div key={`as-${g.name}-${i}`} className="flex items-center justify-between p-3 border rounded bg-background">
                      <div className="min-w-0">
                        <div className="font-medium truncate">{i + 1}. {g.name}</div>
                        <div className="text-xs text-gray-500">{g.count} agents</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
            (showAgentDetails || sequenceGroups.length === 0) && (
              <div className="space-y-4">
                <h4 className="font-medium">Agent Sequence</h4>
                <DndContext
                  sensors={sensors}
                  collisionDetection={closestCenter}
                  onDragEnd={handleDragEnd}
                >
                  <SortableContext
                    items={dndItems}
                    strategy={verticalListSortingStrategy}
                  >
                    <div className="space-y-2">
                      {(Array.isArray(agentSequence) ? agentSequence : []).map((agentName, index) => {
                        const cli = (Array.isArray(agentClis) && agentClis[index]) || 'gemini';
                        const modelOptions = cli === 'llxprt' ? (llxprtModels || []) : (availableModels || []);
                        const cliOptions = [
                          { value: 'gemini', label: 'Gemini CLI' },
                          { value: 'llxprt', label: 'LLXPRT CLI' },
                          { value: 'surecli', label: 'SureCli (Python Parser)' },
                        ];
                        return (
                          <SortableWorkflowItem
                            key={(Array.isArray(dndItems) && dndItems[index]) || `${agentName}::${index}`}
                            itemId={(Array.isArray(dndItems) && dndItems[index]) || `${agentName}::${index}`}
                            agentName={agentName}
                            index={index}
                            localAgents={localAgents}
                            onRemove={removeAgentFromSequence}
                            onEditHandoff={handleEditHandoff}
                            onOpenHandoffModal={openHandoffModal}
                            modelValue={(Array.isArray(agentModels) && agentModels[index]) || null}
                            onChangeModel={handleChangeModel}
                            availableModels={modelOptions}
                            temperatureValue={(Array.isArray(agentTemperatures) && agentTemperatures[index]) ?? null}
                            onChangeTemperature={handleChangeTemperature}
                            availableTemperatures={availableTemperatures}
                            cliValue={cli}
                            onChangeCli={handleChangeCli}
                            cliOptions={cliOptions}
                          />
                        );
                      })}
                      {(!agentSequence || agentSequence.length === 0) && (
                        <div className="text-center py-4 text-gray-500">
                          No agents in sequence
                        </div>
                      )}
                    </div>
                  </SortableContext>
                </DndContext>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <Button onClick={() => onSave({ id: workflow?.id, name: name.trim(), description: description.trim(), agent_sequence: agentSequence, agent_models: agentModels, agent_temperatures: agentTemperatures, agent_clis: agentClis })}>
          <Save className="w-4 h-4 mr-2" />
          {workflow ? 'Update Workflow' : 'Create Workflow'}
        </Button>
        <Button variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        {workflow && !workflow.is_default && (
          <Button variant="outline" onClick={() => onDelete(workflow)}>
            <Trash2 className="w-4 h-4 mr-2" />
            Delete
          </Button>
        )}
      </div>

      {/* Handoff Prompt Modal */}
      {handoffModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/50" onClick={closeHandoffModal} />
          <div className="relative bg-background border rounded-lg shadow-xl w-full max-w-3xl mx-4">
            <div className="p-4 border-b flex items-center justify-between">
              <div>
                <h4 className="font-semibold">Edit Handoff Prompt</h4>
                <p className="text-xs text-gray-500 mt-1">Agent: <span className="font-mono">{handoffModalAgent}</span></p>
              </div>
              <Button variant="ghost" size="icon" onClick={closeHandoffModal}>
                <X className="w-4 h-4" />
              </Button>
            </div>
            <div className="p-4">
              <Label className="text-xs mb-2 block">Handoff Prompt</Label>
              <Textarea
                rows={18}
                value={handoffModalText}
                onChange={(e) => setHandoffModalText(e.target.value)}
                placeholder="Enter the full handoff instructions for this agent..."
              />
              <div className="text-xs text-gray-500 mt-2">
                This text will be prepended to the agent's base prompt during execution.
              </div>
            </div>
            <div className="p-4 border-t flex items-center justify-end gap-2">
              <Button variant="outline" onClick={closeHandoffModal}>Cancel</Button>
              <Button onClick={saveHandoffModal} disabled={savingHandoff}>
                <Save className="w-4 h-4 mr-2" />
                Save
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function WorkflowManager({ agents, onWorkflowSelect }) {
  const [workflows, setWorkflows] = useState([]);
  const [editingWorkflow, setEditingWorkflow] = useState(null);
  const [showEditor, setShowEditor] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notification, setNotification] = useState(null);

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
        const list = data.workflows || [];
        setWorkflows(list);
        // Bootstrap defaults if missing
        if (!Array.isArray(list) || list.length === 0) {
          await createDefaultWorkflows();
          // Re-fetch after creation
          const r2 = await fetch(`${API_BASE_URL}/workflows`);
          if (r2.ok) {
            const d2 = await r2.json();
            setWorkflows(d2.workflows || []);
          }
        } else {
          // Create any missing defaults by name
          await ensureDefaultWorkflowsExist(list);
        }
      } else {
        console.error('Failed to fetch workflows');
      }
    } catch (error) {
      console.error('Error fetching workflows:', error);
    } finally {
      setLoading(false);
    }
  };

  const createDefaultWorkflows = async () => {
    try {
      // Original Workflow 1: Planning Phase (SureCLI)
      const origWf1Agents = ['directory_structure', 'io8codermaster', 'analyst', 'architect', 'pm'];
      const origWf1Clis = origWf1Agents.map(() => 'surecli');
      await fetch(`${API_BASE_URL}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'Planning Phase (SureCLI)',
          description: 'Directory to PM using SureCLI for deterministic planning',
          agent_sequence: origWf1Agents,
          agent_models: origWf1Agents.map(() => null),
          agent_temperatures: origWf1Agents.map(() => null),
          agent_clis: origWf1Clis
        })
      });

      // Original Workflow 2: Execution Phase (Gemini)
      const origWf2Agents = ['sm', 'developer', 'devops'];
      const origWf2Clis = origWf2Agents.map(() => 'gemini');
      await fetch(`${API_BASE_URL}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'Execution Phase (Gemini)',
          description: 'SM, Developer, and DevOps using Gemini CLI',
          agent_sequence: origWf2Agents,
          agent_models: origWf2Agents.map(() => null),
          agent_temperatures: origWf2Agents.map(() => null),
          agent_clis: origWf2Clis
        })
      });

      // Original Workflow 3: End-to-End Plan + Execute
      const origWf3Agents = [...origWf1Agents, ...origWf2Agents];
      const origWf3Clis = [...origWf1Clis, ...origWf2Clis];
      await fetch(`${API_BASE_URL}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'End-to-End Plan + Execute',
          description: 'Planning (SureCLI) followed by Execution (Gemini)',
          agent_sequence: origWf3Agents,
          agent_models: origWf3Agents.map(() => null),
          agent_temperatures: origWf3Agents.map(() => null),
          agent_clis: origWf3Clis
        })
      });

      // New io8 Workflow 1: io8 Plan (SureCLI) with io8project_builder first (Gemini CLI for this agent only)
      const io8Wf1Agents = ['io8project_builder', 'io8directory_structure', 'io8codermaster', 'io8analyst', 'io8architect', 'io8pm'];
      const io8Wf1Clis = io8Wf1Agents.map((a, i) => (i === 0 ? 'gemini' : 'surecli'));
      await fetch(`${API_BASE_URL}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'io8 Plan',
          description: 'io8 planning phase using SureCLI (Directory → PM)',
          agent_sequence: io8Wf1Agents,
          agent_models: io8Wf1Agents.map(() => null),
          agent_temperatures: io8Wf1Agents.map(() => null),
          agent_clis: io8Wf1Clis
        })
      });

      // New io8 Workflow 2: io8 Develop (Gemini)
      const io8Wf2Agents = ['io8sm', 'io8developer'];
      const io8Wf2Clis = io8Wf2Agents.map(() => 'gemini');
      await fetch(`${API_BASE_URL}/workflows`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: 'io8 Develop',
          description: 'io8 development phase using Gemini CLI (SM → Developer)',
          agent_sequence: io8Wf2Agents,
          agent_models: io8Wf2Agents.map(() => null),
          agent_temperatures: io8Wf2Agents.map(() => null),
          agent_clis: io8Wf2Clis
        })
      });

      // New io8 Workflow 3: io8 Deploy (Gemini)
      const io8Wf3Agents = ['io8devops'];
      const io8Wf3Clis = io8Wf3Agents.map(() => 'gemini');
      try {
        const deployResponse = await fetch(`${API_BASE_URL}/workflows`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: 'io8 Deploy',
            description: 'io8 deployment phase using Gemini CLI (DevOps)',
            agent_sequence: io8Wf3Agents,
            agent_models: io8Wf3Agents.map(() => null),
            agent_temperatures: io8Wf3Agents.map(() => null),
            agent_clis: io8Wf3Clis
          })
        });
        if (!deployResponse.ok) {
          console.error('Failed to create io8 Deploy workflow:', deployResponse.statusText);
        }
      } catch (error) {
        console.error('Error creating io8 Deploy workflow:', error);
      }

      // New io8 Workflow 4: io8 Default (combined)
      const io8Wf4Agents = [...io8Wf1Agents, ...io8Wf2Agents, ...io8Wf3Agents];
      const io8Wf4Clis = [...io8Wf1Clis, ...io8Wf2Clis, ...io8Wf3Clis];
      try {
        const defaultResponse = await fetch(`${API_BASE_URL}/workflows`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: 'io8 Default',
            description: 'io8 Plan (SureCLI) followed by io8 Develop (Gemini) and io8 Deploy (Gemini)',
            agent_sequence: io8Wf4Agents,
            agent_models: io8Wf4Agents.map(() => null),
            agent_temperatures: io8Wf4Agents.map(() => null),
            agent_clis: io8Wf4Clis
          })
        });
        if (!defaultResponse.ok) {
          console.error('Failed to create io8 Default workflow:', defaultResponse.statusText);
        }
      } catch (error) {
        console.error('Error creating io8 Default workflow:', error);
      }
    } catch (e) {
      // Non-fatal bootstrap errors
      console.error('Failed to create default workflows', e);
    }
  };

  const ensureDefaultWorkflowsExist = async (existing) => {
    const names = new Set(existing.map(w => (w && w.name) || ''));
    const needed = [];
    // Original set
    if (!names.has('Planning Phase (SureCLI)')) needed.push('orig1');
    if (!names.has('Execution Phase (Gemini)')) needed.push('orig2');
    if (!names.has('End-to-End Plan + Execute')) needed.push('orig3');
    // io8 set
    if (!names.has('io8 Plan')) needed.push('io8_1');
    if (!names.has('io8 Develop')) needed.push('io8_2');
    if (!names.has('io8 Deploy')) needed.push('io8_3');
    if (!names.has('io8 Default')) needed.push('io8_4');
    if (needed.length === 0) return;

    // Build payloads
    const origWf1Agents = ['directory_structure', 'io8codermaster', 'analyst', 'architect', 'pm'];
    const origWf1Clis = origWf1Agents.map(() => 'surecli');
    const origWf2Agents = ['sm', 'developer', 'devops'];
    const origWf2Clis = origWf2Agents.map(() => 'gemini');
    const origWf3Agents = [...origWf1Agents, ...origWf2Agents];
    const origWf3Clis = [...origWf1Clis, ...origWf2Clis];

    const io8Wf1Agents = ['io8project_builder', 'io8directory_structure', 'io8codermaster', 'io8analyst', 'io8architect', 'io8pm'];
    const io8Wf1Clis = io8Wf1Agents.map((a, i) => (i === 0 ? 'gemini' : 'surecli'));
    const io8Wf2Agents = ['io8sm', 'io8developer'];
    const io8Wf2Clis = io8Wf2Agents.map(() => 'gemini');
    const io8Wf3Agents = ['io8devops'];
    const io8Wf3Clis = io8Wf3Agents.map(() => 'gemini');
    const io8Wf4Agents = [...io8Wf1Agents, ...io8Wf2Agents, ...io8Wf3Agents];
    const io8Wf4Clis = [...io8Wf1Clis, ...io8Wf2Clis, ...io8Wf3Clis];

    const payloads = [];
    if (needed.includes('orig1')) payloads.push({
      name: 'Planning Phase (SureCLI)',
      description: 'Directory to PM using SureCLI for deterministic planning',
      agent_sequence: origWf1Agents,
      agent_models: origWf1Agents.map(() => null),
      agent_temperatures: origWf1Agents.map(() => null),
      agent_clis: origWf1Clis
    });
    if (needed.includes('orig2')) payloads.push({
      name: 'Execution Phase (Gemini)',
      description: 'SM, Developer, and DevOps using Gemini CLI',
      agent_sequence: origWf2Agents,
      agent_models: origWf2Agents.map(() => null),
      agent_temperatures: origWf2Agents.map(() => null),
      agent_clis: origWf2Clis
    });
    if (needed.includes('orig3')) payloads.push({
      name: 'End-to-End Plan + Execute',
      description: 'Planning (SureCLI) followed by Execution (Gemini)',
      agent_sequence: origWf3Agents,
      agent_models: origWf3Agents.map(() => null),
      agent_temperatures: origWf3Agents.map(() => null),
      agent_clis: origWf3Clis
    });
    if (needed.includes('io8_1')) payloads.push({
      name: 'io8 Plan',
      description: 'io8 planning phase using SureCLI (Directory → PM)',
      agent_sequence: io8Wf1Agents,
      agent_models: io8Wf1Agents.map(() => null),
      agent_temperatures: io8Wf1Agents.map(() => null),
      agent_clis: io8Wf1Clis
    });
    if (needed.includes('io8_2')) payloads.push({
      name: 'io8 Develop',
      description: 'io8 development phase using Gemini CLI (SM → Developer)',
      agent_sequence: io8Wf2Agents,
      agent_models: io8Wf2Agents.map(() => null),
      agent_temperatures: io8Wf2Agents.map(() => null),
      agent_clis: io8Wf2Clis
    });
    if (needed.includes('io8_3')) payloads.push({
      name: 'io8 Deploy',
      description: 'io8 deployment phase using Gemini CLI (DevOps)',
      agent_sequence: io8Wf3Agents,
      agent_models: io8Wf3Agents.map(() => null),
      agent_temperatures: io8Wf3Agents.map(() => null),
      agent_clis: io8Wf3Clis
    });
    if (needed.includes('io8_4')) payloads.push({
      name: 'io8 Default',
      description: 'io8 Plan (SureCLI) followed by io8 Develop (Gemini) and io8 Deploy (Gemini)',
      agent_sequence: io8Wf4Agents,
      agent_models: io8Wf4Agents.map(() => null),
      agent_temperatures: io8Wf4Agents.map(() => null),
      agent_clis: io8Wf4Clis
    });

    for (const body of payloads) {
      try {
        const response = await fetch(`${API_BASE_URL}/workflows`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        });
        if (!response.ok) {
          console.error(`Failed to create workflow ${body.name}:`, response.statusText);
        }
      } catch (error) {
        console.error(`Error creating workflow ${body.name}:`, error);
      }
    }
  };

  const showNotification = (message, type = 'info') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 5000);
  };

  const handleCreateWorkflow = () => {
    setEditingWorkflow(null);
    setShowEditor(true);
  };

  const handleEditWorkflow = (workflow) => {
    setEditingWorkflow(workflow);
    setShowEditor(true);
  };

  const handleCopyWorkflow = async (workflow) => {
    const newName = prompt('Enter name for the copied workflow:', `${workflow.name} (Copy)`);
    if (!newName) return;

    try {
      const response = await fetch(`${API_BASE_URL}/workflows/${workflow.id}/copy`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ name: newName }),
      });

      if (response.ok) {
        showNotification('Workflow copied successfully', 'success');
        fetchWorkflows();
      } else {
        const error = await response.json();
        showNotification(`Error: ${error.error}`, 'error');
      }
    } catch (error) {
      showNotification('Network error occurred', 'error');
    }
  };

  const handleDeleteWorkflow = async (workflow) => {
    if (!confirm(`Are you sure you want to delete "${workflow.name}"?`)) return;

    try {
      const response = await fetch(`${API_BASE_URL}/workflows/${workflow.id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        showNotification('Workflow deleted successfully', 'success');
        fetchWorkflows();
      } else {
        const error = await response.json();
        showNotification(`Error: ${error.error}`, 'error');
      }
    } catch (error) {
      showNotification('Network error occurred', 'error');
    }
  };

  const handleSaveWorkflow = async (workflowData) => {
    try {
      const url = workflowData.id 
        ? `${API_BASE_URL}/workflows/${workflowData.id}`
        : `${API_BASE_URL}/workflows`;
      
      const method = workflowData.id ? 'PUT' : 'POST';

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(workflowData),
      });

      if (response.ok) {
        showNotification(
          workflowData.id ? 'Workflow updated successfully' : 'Workflow created successfully', 
          'success'
        );
        setShowEditor(false);
        setEditingWorkflow(null);
        fetchWorkflows();
      } else {
        const error = await response.json();
        showNotification(`Error: ${error.error}`, 'error');
      }
    } catch (error) {
      showNotification('Network error occurred', 'error');
    }
  };

  const onSave = (workflowData) => handleSaveWorkflow(workflowData);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Workflows</h2>
        <Button onClick={handleCreateWorkflow}>
          <Plus className="w-4 h-4 mr-2" />
          New Workflow
        </Button>
      </div>

      {notification && (
        <Alert className={notification.type === 'error' ? 'border-red-500' : ''}>
          <AlertDescription>{notification.message}</AlertDescription>
        </Alert>
      )}

      {showEditor ? (
        <WorkflowEditor 
          workflow={editingWorkflow}
          agents={agents}
          onSave={onSave}
          onCancel={() => setShowEditor(false)}
          onDelete={handleDeleteWorkflow}
        />
      ) : (
        <div className="grid md:grid-cols-3 gap-4">
          {workflows.map((workflow) => (
            <div key={workflow.id} onClick={() => onWorkflowSelect && onWorkflowSelect(workflow)}>
              <WorkflowCard 
                workflow={workflow} 
                agents={agents}
                onEdit={handleEditWorkflow}
                onCopy={handleCopyWorkflow}
                onDelete={handleDeleteWorkflow}
                onSelect={onWorkflowSelect}
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
