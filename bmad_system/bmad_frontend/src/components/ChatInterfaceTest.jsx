import React from 'react';

const ChatInterfaceTest = ({ 
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
  return (
    <div className="flex h-full bg-background">
      <div className="flex-1 p-6">
        <h1 className="text-2xl font-bold text-white">Chat Interface Test</h1>
        <p className="text-gray-400 mt-2">This is a test version to debug the blank screen issue.</p>
        <div className="mt-4 p-4 bg-gray-800 rounded-lg">
          <h2 className="text-lg font-semibold text-white mb-2">Props received:</h2>
          <ul className="text-sm text-gray-300 space-y-1">
            <li>Task: {task ? 'Present' : 'None'}</li>
            <li>Selected Workflow: {selectedWorkflow ? selectedWorkflow.name : 'None'}</li>
            <li>Agents: {agents ? Object.keys(agents).length : 0}</li>
            <li>Selected Files: {selectedFiles ? selectedFiles.length : 0}</li>
          </ul>
        </div>
        <button 
          onClick={onBack}
          className="mt-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
        >
          Back
        </button>
      </div>
    </div>
  );
};

export default ChatInterfaceTest;
