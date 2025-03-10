# Agentic AI Based Connected Fleet Incident Advisor Demo

This demo is about an AI-powered Connected Fleet Advisor built using MongoDB Atlas, Voyage AI, OpenAI and LangGraph.

The system receives driver complaints or fleet manager queries, processes vehicle telemetry data, generates a chain-of-thought, performs a vector search for similar issues, persists the data in MongoDB and finally produces a diagnostic recommendation using OpenAI LLM.

## Features

- **Multi-Step Diagnostic Workflow:**  
  The agent processes an issue report by:
  1. **Reading Telemetry Data:** Ingests vehicle sensor data from a CSV file (In a production setup, this will be replaced by an API).
  2. **Generating an Embedding:** Uses Voyage AI embedding API to convert the complaint text into a numerical representation.
  3. **Atlas Vector Search:** Searches for similar issues in MongoDB Atlas using the generated embedding.
  4. **Data Persistence:** Saves telemetry data, session logs, and recommendations in MongoDB Atlas.
  5. **Final Recommendation:** Uses OpenAI chat API to produce actionable diagnostic advice.
  
- **Agent Profile Management:**  
  Automatically retrieves (or creates if missing) a default agent profile from MongoDB that contains instructions, rules, and goals.

- **Session & Run Document Tracking:**  
  Each diagnostic run is assigned a unique thread ID and logged. Specific run documents from various collections (eg. agent_sessions, historical_recommendations, telemetry_data, logs, agent_profiles, past_issues and checkpoints) can be retrieved for detailed analysis.

- **User-Friendly Frontend:**  
  A dashboard displays the agent’s real-time workflow updates (chain-of-thought, final recommendation, update messages) in one column, and the corresponding MongoDB run documents in the other column.
  

## Repository Structure

/agent 

-backend 

--main.py 

--data # Contains telematics csv file 

--requirements.txt

-frontend 

--app 

---page.jsx 

---api 

----get-run-documents 

----get-sessions

----resume-agent

----run-agent-sse # not used yet

---public 

---package.json # Frontend configuration


<img width="1191" alt="image" src="https://github.com/user-attachments/assets/ce2ad3cc-c714-49c8-811d-b7856828172e" />


## Setup Instructions

### Prerequisites

- **Python 3.11+** (backend)
- **Node.js** (for the Next.js frontend)
- **MongoDB Atlas connection URI** 
- **OpenAI API Key**
- **Voyage AI API Key**

### Backend Setup

1. **Clone the repository** and navigate to the backend directory:
   ```bash
   cd agent/backend

2. Create and activate a virtual environment:

   ```bash
    python -m venv venv
    source venv/bin/activate   # On Windows: venv\Scripts\activate
    
3. Install dependencies:

   ```bash
    pip install -r requirements.txt


4. Configure environment variables:
    
    Create a .env file in the backend directory with the following content:

   ```bash
    OPENAI_API_KEY=your_openai_api_key_here
    VOYAGE_API_KEY=your_voyage_api_key_here
    MONGO_URI=your_mongo_uri_here
    DATABASE=fleet_issues
    TELEMETRY_PATH=data/telemetry_data.csv
    VECTOR_SEARCH_INDEX=issues_index

5. Run `create_issue_embeddings.py` to create and store embeddings in MongoDB.

6. Create a Atlas Vector Search index with name `issues_index` and path `embeddings`. 

7. Run the backend server:

   ```bash
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

8. Frontend Setup

    Navigate to the frontend directory:

   ```bash
    cd ../frontend

9. Install dependencies:

   ```bash
    npm install
    

10. Run the Next.js development server:

    ```bash
    npm run dev


The frontend should now be accessible at http://localhost:3000.

11. Feel free to adjust the prompt in main.py or update the telemetry data in the telemetry_data.csv file

## Demo Presentation & Talk Track

### Overview

The Connected Fleet Advisor Demo showcases an AI-driven diagnostic system for vehicles. The demo integrates several key technologies:
  
- **Backend:**  
  Implements a multi-step diagnostic workflow using LangGraph. The backend reads telemetry data from a CSV file (simulating vehicle sensor inputs), generates text embeddings using Voyage AI, performs vector searches to identify similar past issues from MongoDB, persists session and run data, and finally generates a diagnostic recommendation.

- **MongoDB:**  
  The flexible document model database stores agent profiles, historical recommendations, telemetry data, session logs, and more. This persistent storage not only logs every step of the diagnostic process for traceability but also enables efficient querying and reusability of past data.

- **Next.js Frontend:**  
  Provides a two-column view:
  - **Left Column:** Displays the real-time agent workflow updates such as the chain-of-thought reasoning, update messages, and final recommendations.
  - **Right Column:** Shows the documents inserted into MongoDB during the agent run, including session details, telemetry logs, historical recommendations, agent profiles and sample past issues.


**System Architecture:**  
   - **Backend Workflow:**  
     - The agent receives a user’s issue report (e.g., "My vehicle’s fuel consumption has increased significantly over the past week. What might be wrong with the engine or fuel system?").
     - It first retrieves telemetry data (simulated here via a CSV file) and logs the update.
     - Next, it generates an embedding for the complaint using Voyage AI voyage-3-large embedding API.
     - The system then performs a vector search against historical issues in MongoDB to find similar cases.
     - All data (telemetry, embeddings, session logs) are persisted in MongoDB for traceability.
     - Finally, the agent uses OpenAI’s ChatCompletion API to produce a final recommendation.
   - **MongoDB Role:**  
     - MongoDB stores everything: the agent profile, session logs, telemetry data, historical recommendations, and even checkpoints. This makes the system highly traceable and scalable.
   - **Frontend Interface:**  
     - The two-column UI shows both the real-time workflow and the relevant MongoDB documents that validate each step.


### Demo Presentation Flow

3. **Live Demonstration (takes about 5-7 minutes):**  
   - **Starting a New Diagnosis:**  
     - Open the frontend and choose “New Diagnosis.”
     - Enter an issue report in the text box (e.g., the sample complaint about a knocking sound).
     - Example prompts
        - I am hearing knocking sound while turning at low speeds
        - My car is making a persistent rattling noise when I accelerate at low speeds.
        - I noticed a sudden drop in oil pressure along with a slight rise in engine temperature
        - My vehicle’s fuel consumption has increased significantly over the past week. What might be wrong with the engine or fuel system?
        - A warning light recently appeared on my dashboard, and the car is struggling to accelerate
     - Click the “Run Agent” button and **wait** for a few mins as the agent finishes its run 
   - **Viewing Workflow:**  
     - The workflow , chain-of-thought output, and the final recommendation is shown in the left column.
     - The workflow is being generated in real time, giving transparency into the agent's decision-making process.

   - **Reviewing MongoDB Documents:**  
     - In the right column, the documents shown are the records inserted during the current agent run.
       - **agent_sessions:** Contains session metadata and the thread ID.
       - **historical_recommendations:** Stores the final recommendations and related diagnostics.
       - **telemetry_data:** Holds the telemetry sensor readings.
       - **logs:** Contains log entries for the diagnostic process.
       - **agent_profiles:** Shows the agent's profile that was used during diagnosis.
       - **past_issues:** (If available) Displays a sample of historical issues.
       - **checkpoints:** (From the checkpointing database) Shows the last saved state for potential recovery.
   - **Resume Functionality:**  
     - Optionally, we can demonstrate the "Resume Diagnosis" feature by entering a thread ID and showing how the system retrieves the corresponding session.



feedback and suggestions: humza.akhtar@mongodb.com


