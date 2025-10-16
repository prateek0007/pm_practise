import sqlite3
import json
import uuid
from datetime import datetime

def create_workflows_table():
    try:
        # Connect to the database
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()
        
        # Create the workflows table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                agent_sequence TEXT NOT NULL,
                agent_models TEXT,
                agent_temperatures TEXT,
                agent_clis TEXT,
                is_default BOOLEAN DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT DEFAULT 'system'
            )
        ''')
        
        conn.commit()
        print("Workflows table created successfully")
        return True
        
    except Exception as e:
        print(f"Error creating workflows table: {e}")
        return False
    finally:
        conn.close()

def create_flf_workflow():
    try:
        # Connect to the database
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()
        
        # Check if FLF workflow already exists
        cursor.execute("SELECT id FROM workflows WHERE name = ?", ("FLF Workflow",))
        existing = cursor.fetchone()
        
        if existing:
            print("FLF Workflow already exists")
            return True
            
        # Create FLF workflow
        workflow_id = str(uuid.uuid4())
        agent_sequence = json.dumps(["flf-save"])
        agent_models = json.dumps([None])
        agent_temperatures = json.dumps([None])
        agent_clis = json.dumps(["gemini"])
        created_at = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO workflows (
                id, name, description, agent_sequence, agent_models, 
                agent_temperatures, agent_clis, is_default, is_active, 
                created_at, updated_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            workflow_id,
            "FLF Workflow",
            "Field analysis workflow with FLF agent",
            agent_sequence,
            agent_models,
            agent_temperatures,
            agent_clis,
            False,  # is_default
            True,   # is_active
            created_at,
            created_at,
            "system"
        ))
        
        conn.commit()
        print(f"FLF Workflow created successfully with ID: {workflow_id}")
        return True
        
    except Exception as e:
        print(f"Error creating FLF workflow: {e}")
        return False
    finally:
        conn.close()

def list_workflows():
    try:
        # Connect to the database
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()
        
        # Get all workflows
        cursor.execute("SELECT id, name, agent_sequence FROM workflows")
        workflows = cursor.fetchall()
        
        print("\nWorkflows in database:")
        for workflow in workflows:
            workflow_id, name, agent_sequence = workflow
            print(f"  - {name} (ID: {workflow_id})")
            
            # Try to parse agent sequence
            try:
                agents = json.loads(agent_sequence)
                print(f"    Agents: {agents}")
            except:
                print(f"    Agent sequence: {agent_sequence}")
                
        return True
        
    except Exception as e:
        print(f"Error listing workflows: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("Initializing database and creating FLF workflow...")
    
    # Create workflows table
    if create_workflows_table():
        # Create FLF workflow
        if create_flf_workflow():
            # List all workflows
            list_workflows()
            print("\n✅ Database initialization and FLF workflow creation completed!")
        else:
            print("\n❌ Failed to create FLF workflow")
    else:
        print("\n❌ Failed to create workflows table")