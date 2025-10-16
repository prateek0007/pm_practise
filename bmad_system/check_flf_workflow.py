import sqlite3
import json

# Connect to the database
conn = sqlite3.connect('app.db')
cursor = conn.cursor()

# Check if FLF Workflow exists
cursor.execute("SELECT name, agent_sequence FROM workflows WHERE name = 'FLF Workflow'")
result = cursor.fetchone()

if result:
    name, agent_sequence = result
    print(f"FLF Workflow exists: {name}")
    print(f"Agent sequence: {agent_sequence}")
    # Parse the JSON to see the agents
    try:
        agents = json.loads(agent_sequence)
        print(f"Agents in sequence: {agents}")
    except json.JSONDecodeError:
        print("Could not parse agent sequence as JSON")
else:
    print("FLF Workflow not found in database")

conn.close()