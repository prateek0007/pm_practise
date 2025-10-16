import sqlite3
import json

# Connect to the database
conn = sqlite3.connect('app.db')
cursor = conn.cursor()

# Get all workflows
cursor.execute("SELECT name, agent_sequence FROM workflows")
results = cursor.fetchall()

print("Workflows in database:")
for result in results:
    name, agent_sequence = result
    print(f"  - {name}")
    # Parse the JSON to see the agents
    try:
        agents = json.loads(agent_sequence)
        print(f"    Agents: {agents}")
    except json.JSONDecodeError:
        print("    Could not parse agent sequence as JSON")

conn.close()