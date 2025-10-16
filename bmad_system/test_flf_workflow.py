import sys
import os

# Add the backend src directory to the Python path
backend_path = os.path.join(os.path.dirname(__file__), 'bmad_backend', 'src')
sys.path.insert(0, backend_path)

# Set the Python path for imports
import os
os.environ['PYTHONPATH'] = backend_path

from models.user import db, init_db
from models.workflow import Workflow
from flask import Flask
import json

# Create a Flask app for testing
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize the database
init_db(app)

# Check if FLF workflow exists
with app.app_context():
    flf_workflow = Workflow.query.filter_by(name="FLF Workflow").first()
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
    workflows = Workflow.get_active_workflows()
    for workflow in workflows:
        print(f"  - {workflow.name} (ID: {workflow.id})")