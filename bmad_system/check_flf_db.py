import sqlite3
import json

def check_flf_workflow():
    try:
        # Connect to the database
        conn = sqlite3.connect('app.db')
        cursor = conn.cursor()
        
        # Check if the workflows table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("Workflows table does not exist")
            return False
            
        # Get all workflows
        cursor.execute("SELECT id, name, agent_sequence FROM workflows")
        workflows = cursor.fetchall()
        
        print("Workflows in database:")
        flf_found = False
        for workflow in workflows:
            workflow_id, name, agent_sequence = workflow
            print(f"  - {name} (ID: {workflow_id})")
            
            # Try to parse agent sequence
            try:
                agents = json.loads(agent_sequence)
                print(f"    Agents: {agents}")
            except:
                print(f"    Agent sequence: {agent_sequence}")
                
            # Check if this is the FLF workflow
            if name and 'flf' in name.lower():
                print(f"    ^^^ This is the FLF workflow!")
                flf_found = True
                
        conn.close()
        return flf_found
        
    except Exception as e:
        print(f"Error checking FLF workflow: {e}")
        return False

if __name__ == "__main__":
    print("Checking FLF Workflow in Database...")
    success = check_flf_workflow()
    if success:
        print("✅ FLF Workflow found in database!")
    else:
        print("❌ FLF Workflow not found in database!")