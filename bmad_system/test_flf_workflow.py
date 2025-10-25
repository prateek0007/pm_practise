import sys
import os

# Add the backend src directory to the Python path
backend_path = os.path.join(os.path.dirname(__file__), 'bmad_backend', 'src')
sys.path.insert(0, backend_path)

# Set the Python path for imports
os.environ['PYTHONPATH'] = backend_path

# Change to the backend directory to ensure proper imports
os.chdir(os.path.join(os.path.dirname(__file__), 'bmad_backend'))

# Import modules directly
import importlib.util
user_spec = importlib.util.spec_from_file_location("user", os.path.join(backend_path, "models", "user.py"))
user_module = importlib.util.module_from_spec(user_spec)
user_spec.loader.exec_module(user_module)

workflow_spec = importlib.util.spec_from_file_location("workflow", os.path.join(backend_path, "models", "workflow.py"))
workflow_module = importlib.util.module_from_spec(workflow_spec)
workflow_spec.loader.exec_module(workflow_module)

from flask import Flask
import sqlite3
import json

# Connect to the database
conn = sqlite3.connect('app.db')
cursor = conn.cursor()

# Check if FLF Workflow exists
cursor.execute("SELECT id, name, agent_sequence FROM workflows WHERE name = 'FLF Workflow'")
result = cursor.fetchone()

if result:
    workflow_id, name, agent_sequence = result
    print("FLF Workflow found:")
    print(f"  ID: {workflow_id}")
    print(f"  Name: {name}")
    print(f"  Agent sequence: {agent_sequence}")
    # Parse the JSON to see the agents
    try:
        agents = json.loads(agent_sequence)
        print(f"  Agents: {agents}")
    except json.JSONDecodeError:
        print("  Could not parse agent sequence as JSON")
else:
    print("FLF Workflow not found in database")

conn.close()

# Create a Flask app for testing
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
user_module.init_db(app)

# Check if FLF workflow exists
with app.app_context():
    flf_workflow = workflow_module.Workflow.query.filter_by(name="FLF Workflow").first()
    if flf_workflow:
        print("FLF Workflow found:")
        print(f"  ID: {flf_workflow.id}")
        print(f"  Name: {flf_workflow.name}")
        print(f"  Description: {flf_workflow.description}")
        print(f"  Agent Sequence: {flf_workflow.agent_sequence}")
        try:
            agents = json.loads(flf_workflow.agent_sequence)
            print(f"  Agents: {agents}")
        except:
            print("  Could not parse agent sequence")
    else:
        print("FLF Workflow not found in database")
        
    # List all workflows
    print("\nAll Workflows:")
    workflows = workflow_module.Workflow.get_active_workflows()
    for workflow in workflows:
        print(f"  - {workflow.name} (ID: {workflow.id})")