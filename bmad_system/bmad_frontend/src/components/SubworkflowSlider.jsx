import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ChevronLeft, ChevronRight, Play, Pause } from 'lucide-react';

const SubworkflowSlider = ({ 
  workflow, 
  agents, 
  currentStatus, 
  currentAgent, 
  completedAgents = [], 
  onWorkflowChange 
}) => {
  const [currentSubworkflowIndex, setCurrentSubworkflowIndex] = useState(0);
  const [subworkflows, setSubworkflows] = useState([]);

  // Define the subworkflows for io8 Default (Plan + Develop + Deploy)
  useEffect(() => {
    if (workflow && (workflow.name === 'io8 Default' || workflow.name === 'End-to-End Plan + Execute')) {
      // io8 Plan, io8 Develop, and io8 Deploy
      const isIo8 = workflow.name === 'io8 Default';
      const workflow1 = isIo8
        ? {
            name: 'io8 Plan',
            description: 'io8 planning phase using SureCLI (Directory → PM)',
            agents: ['io8project_builder', 'io8directory_structure', 'io8codermaster', 'io8analyst', 'io8architect', 'io8pm'],
            cli: 'surecli'
          }
        : {
            name: 'Planning Phase (SureCLI)',
            description: 'Directory to PM using SureCLI for deterministic planning',
            agents: ['directory_structure', 'io8codermaster', 'analyst', 'architect', 'pm'],
            cli: 'surecli'
          };

      const workflow2 = isIo8
        ? {
            name: 'io8 Develop',
            description: 'io8 development phase using Gemini CLI (SM → Developer)',
            agents: ['io8sm', 'io8developer'],
            cli: 'gemini'
          }
        : {
            name: 'Execution Phase (Gemini)',
            description: 'SM, Developer, and DevOps using Gemini CLI',
            agents: ['sm', 'developer', 'devops'],
            cli: 'gemini'
          };

      const workflow3 = isIo8
        ? {
            name: 'io8 Deploy',
            description: 'io8 deployment phase using Gemini CLI (DevOps)',
            agents: ['io8devops'],
            cli: 'gemini'
          }
        : null;
      
      const subworkflows = isIo8 ? [workflow1, workflow2, workflow3] : [workflow1, workflow2];
      setSubworkflows(subworkflows);
    } else {
      // For other workflows, show as single subworkflow
      const agentSequence = Array.isArray(workflow?.agent_sequence) 
        ? workflow.agent_sequence 
        : (typeof workflow?.agent_sequence === 'string'
            ? (() => { try { return JSON.parse(workflow.agent_sequence); } catch { return []; } })()
            : []);
      
      setSubworkflows([{
        name: workflow?.name || 'Workflow',
        description: workflow?.description || 'No description',
        agents: agentSequence,
        cli: 'mixed'
      }]);
    }
  }, [workflow]);

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (subworkflows.length <= 1) return; // Only enable for multiple subworkflows
      
      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        handlePrevious();
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        handleNext();
      }
    };

    // Add event listener when component mounts
    document.addEventListener('keydown', handleKeyDown);
    
    // Cleanup event listener when component unmounts
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [currentSubworkflowIndex, subworkflows.length]);

  const handlePrevious = () => {
    if (currentSubworkflowIndex > 0) {
      setCurrentSubworkflowIndex(currentSubworkflowIndex - 1);
    }
  };

  const handleNext = () => {
    if (currentSubworkflowIndex < subworkflows.length - 1) {
      setCurrentSubworkflowIndex(currentSubworkflowIndex + 1);
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
      'bmad': '🧠',
      'directory_structure': '🗂️'
    };
    return icons[agentName] || '🤖';
  };

  const getAgentStatus = (agentName) => {
    if (completedAgents.includes(agentName)) {
      return 'completed';
    } else if (currentAgent === agentName) {
      return 'current';
    }
    return 'pending';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return 'text-green-400';
      case 'current': return 'text-blue-400';
      default: return 'text-gray-500';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return '✅';
      case 'current': return '🔄';
      default: return '⏳';
    }
  };

  const currentSubworkflow = subworkflows[currentSubworkflowIndex];

  if (!currentSubworkflow) {
    return null;
  }

  return (
    <Card className="bmad-card">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">🔄</span>
            <div>
              <CardTitle className="bmad-text-primary text-lg">
                {workflow?.name || 'Workflow'} - Subworkflow View
              </CardTitle>
              <p className="text-sm bmad-text-muted">
                {subworkflows.length > 1 
                  ? `Showing subworkflow ${currentSubworkflowIndex + 1} of ${subworkflows.length}`
                  : 'Single workflow view'
                }
              </p>
            </div>
          </div>
          
          {/* Navigation arrows */}
          {subworkflows.length > 1 && (
            <div className="flex items-center space-x-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrevious}
                disabled={currentSubworkflowIndex === 0}
                className="p-2"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-sm text-gray-400 min-w-[60px] text-center">
                {currentSubworkflowIndex + 1} / {subworkflows.length}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={handleNext}
                disabled={currentSubworkflowIndex === subworkflows.length - 1}
                className="p-2"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="space-y-4">
        {/* Current Subworkflow Info */}
        <div className="p-4 rounded-lg border border-blue-500/30 bg-blue-500/10">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-blue-400 rounded-full"></div>
              <span className="font-semibold text-blue-300">
                {currentSubworkflow.name}
              </span>
              <Badge variant="outline" className="text-xs">
                {currentSubworkflow.cli}
              </Badge>
            </div>
            <div className="text-xs text-blue-300/70">
              {currentSubworkflow.agents.length} agents
            </div>
          </div>
          <p className="text-sm text-blue-200">
            {currentSubworkflow.description}
          </p>
        </div>

        {/* Progress Bar for Current Subworkflow */}
        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="bmad-text-muted">Subworkflow Progress</span>
            <span className="bmad-text-primary font-semibold">
              {Math.round((completedAgents.filter(agent => 
                currentSubworkflow.agents.includes(agent)
              ).length / currentSubworkflow.agents.length) * 100)}%
            </span>
          </div>
          
          <div className="relative overflow-hidden">
            <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
              <div 
                className="h-full bg-gradient-to-r from-blue-500 via-purple-500 to-blue-600 rounded-full transition-all duration-1000 ease-out relative"
                style={{ 
                  width: `${Math.round((completedAgents.filter(agent => 
                    currentSubworkflow.agents.includes(agent)
                  ).length / currentSubworkflow.agents.length) * 100)}%`,
                  backgroundSize: '200% 100%',
                  animation: currentStatus === 'in_progress' ? 'shimmer 2s ease-in-out infinite' : 'none'
                }}
              >
                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent transform -skew-x-12 animate-pulse"></div>
              </div>
            </div>
            
            {/* Agent indicators for current subworkflow only */}
            <div className="relative mt-2 h-10 overflow-hidden px-2">
              {currentSubworkflow.agents.map((agent, index) => {
                const status = getAgentStatus(agent);
                const lastIndex = currentSubworkflow.agents.length - 1;
                const denom = Math.max(1, lastIndex);
                const leftPct = (index / denom) * 100;
                
                const posStyle = index === 0
                  ? { left: '0%', transform: 'translateX(0%)' }
                  : index === lastIndex
                  ? { left: '100%', transform: 'translateX(-100%)' }
                  : { left: `${leftPct}%`, transform: 'translateX(-50%)' };
                
                const alignClass = index === 0 ? 'text-left' : index === lastIndex ? 'text-right' : 'text-center';
                
                return (
                  <div
                    key={agent}
                    className={`absolute top-0 flex flex-col items-center ${
                      status === 'completed' ? 'text-green-400' : 
                      status === 'current' ? 'text-blue-400' : 'text-gray-500'
                    }`}
                    style={posStyle}
                  >
                    <div
                      className={`w-3 h-3 rounded-full border-2 transition-all duration-300 ${
                        status === 'completed'
                          ? 'bg-green-500 border-green-400'
                          : status === 'current'
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
          </div>
        </div>

        {/* Agent List for Current Subworkflow */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium bmad-text-primary">Agents in this subworkflow:</h4>
          <div className="grid grid-cols-1 gap-2">
            {currentSubworkflow.agents.map((agent, index) => {
              const status = getAgentStatus(agent);
              return (
                <div
                  key={agent}
                  className={`flex items-center space-x-3 p-2 rounded border ${
                    status === 'completed' 
                      ? 'border-green-500/30 bg-green-500/10' 
                      : status === 'current'
                      ? 'border-blue-500/30 bg-blue-500/10'
                      : 'border-gray-500/30 bg-gray-500/10'
                  }`}
                >
                  <span className="text-lg">{getAgentIcon(agent)}</span>
                  <div className="flex-1">
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-medium">{agent}</span>
                      <span className="text-xs text-gray-400">Step {index + 1}</span>
                    </div>
                    <div className="text-xs text-gray-500">
                      {agents[agent]?.display_name || agent}
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-sm">{getStatusIcon(status)}</span>
                    <span className={`text-xs ${getStatusColor(status)}`}>
                      {status === 'completed' ? 'Completed' : 
                       status === 'current' ? 'Running' : 'Pending'}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Subworkflow Overview */}
        {subworkflows.length > 1 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium bmad-text-primary">All Subworkflows:</h4>
            <div className="flex space-x-2">
              {subworkflows.map((subwf, index) => {
                const isActive = index === currentSubworkflowIndex;
                const completedCount = completedAgents.filter(agent => 
                  subwf.agents.includes(agent)
                ).length;
                const progress = Math.round((completedCount / subwf.agents.length) * 100);
                
                return (
                  <div
                    key={index}
                    className={`flex-1 p-3 rounded border cursor-pointer transition-all duration-200 ${
                      isActive
                        ? 'border-blue-500/50 bg-blue-500/20 ring-2 ring-blue-500/30'
                        : 'border-gray-500/30 bg-gray-500/10 hover:bg-gray-500/20 hover:border-gray-400/50'
                    }`}
                    onClick={() => setCurrentSubworkflowIndex(index)}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="text-xs font-medium truncate">{subwf.name}</div>
                      {isActive && <span className="text-xs text-blue-400">●</span>}
                    </div>
                    <div className="text-xs text-gray-400 mb-2">
                      {subwf.agents.length} agents • {progress}% complete
                    </div>
                    <div className="w-full bg-gray-600 rounded-full h-1">
                      <div 
                        className="h-1 bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all duration-300"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="text-xs text-gray-500 text-center mt-2">
              💡 Use arrow keys (← →) to navigate between subworkflows
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default SubworkflowSlider;
