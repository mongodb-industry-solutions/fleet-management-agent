#!/usr/bin/env python3
"""
MongoDB IST AI Agent Demo with LangGraph, OpenAI and MongoDB Atlas

Agentic Workflow:
  1. A driver complaint or fleet manager query is submitted.
  2. The agent uses OpenAI to generate a chain-of-thought (CoT) based on:
       a. Reading telemetry data.
       b. Generating an embedding for the complaint.
       c. Performing a vector search using the embedding.
       d. Persisting the combined data.
  3. Finally, the agent uses OpenAI LLM to produce a final recommendation.
  4. The agent profile (instructions, rules, and goals) is always retrieved from MongoDB. 
  5. MongoDB is also used as for agent memory and for storing all data related to the agent workflow run.
  
"""

from dotenv import load_dotenv
load_dotenv()

import csv
import io
import os
import datetime
from typing import Any, List, Literal, Optional
from typing_extensions import TypedDict
from bson import ObjectId

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import pymongo
from openai import OpenAI
import voyageai

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.mongodb import MongoDBSaver

# --- Simulated Telemetry Data is in a CSV file ---
# data/telemetry_data.csv

# Initialize clients and paths
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
vo_client = voyageai.Client()
fleet_issues = os.environ.get("DATABASE")
telemetry_path = os.environ.get("TELEMETRY_PATH")
vector_search_index = os.environ.get("VECTOR_SEARCH_INDEX")

# --- Define State Types ---
class TelemetryRecord(TypedDict):
    timestamp: str
    engine_temperature: str
    oil_pressure: str
    avg_fuel_consumption: str

class SimilarIssue(TypedDict):
    issue: str
    recommendation: str

class AgentState(TypedDict):
    issue_report: str
    chain_of_thought: str
    telemetry_data: List[TelemetryRecord]
    embedding_vector: List[float]
    similar_issues_list: List[SimilarIssue]
    recommendation_text: str
    next_step: Literal[
        "reasoning_node", "telemetry_tool", "embedding_node",
        "vector_search_tool", "persistence_node", "recommendation_node", "end"
    ]
    updates: List[str]
    thread_id: Optional[str]

def convert_objectids(item: Any) -> Any:
    if isinstance(item, list):
        return [convert_objectids(i) for i in item]
    elif isinstance(item, dict):
        return {k: convert_objectids(v) for k, v in item.items()}
    elif isinstance(item, ObjectId):
        return str(item)
    else:
        return item

# --- Agent Profile Retrieval ---
def get_agent_profile(agent_id: str) -> dict:
    """Always retrieve (or create if not exists) the agent profile from MongoDB."""
    mongo_uri = os.environ.get("MONGO_URI")
    default_profile = {
        "agent_id": agent_id,
        "profile": "Default Agent Profile",
        "instructions": "Follow diagnostic procedures meticulously.",
        "rules": "Ensure safety; validate sensor data; document all steps.",
        "goals": "Provide accurate diagnostics and actionable recommendations."
    }
    if not mongo_uri:
        return default_profile
    try:
        client_mongo = pymongo.MongoClient(mongo_uri)
        db = client_mongo[fleet_issues]
        collection = db["agent_profiles"]
        profile = collection.find_one({"agent_id": agent_id})
        if not profile:
            collection.insert_one(default_profile)
            profile = default_profile
        client_mongo.close()
        return profile
    except Exception as e:
        print("Error retrieving agent profile:", e)
        return default_profile

# --- Tool Functions (STate Graph Nodes) ---
def get_telemetry_tool(state: dict) -> dict:
    """Reads telemetry data from an external CSV file."""
    message = "[Tool] Retrieved Telemetry Data from file"
    print("\n" + message)
    telemetry_records = []
    with open(telemetry_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            telemetry_records.append(row)
    for record in telemetry_records:
        print(record)
    state.setdefault("updates", []).append(message)
    return {"telemetry_data": telemetry_records, "thread_id": state.get("thread_id", "")}

def vector_search_tool(state: dict) -> dict:
    """Performs a vector search on past issues in MongoDB Atlas."""
    message = "[Tool] Performing MongoDB Atlas Vector Search"
    print("\n" + message)
    state.setdefault("updates", []).append(message)
    embedding = state.get("embedding_vector", [])
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        print("[MongoDB] MONGO_URI not set. Returning dummy vector search results.")
        state.setdefault("updates", []).append("[MongoDB] MONGO_URI not set.")
        similar_issues = [
            {"issue": "Engine knocking when turning", "recommendation": "Inspect spark plugs and engine oil."},
            {"issue": "Suspension noise under load", "recommendation": "Check suspension components for wear."}
        ]
    else:
        try:
            client_mongo = pymongo.MongoClient(mongo_uri)
            db = client_mongo[fleet_issues]
            collection = db["past_issues"]
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": vector_search_index,
                        "path": "embedding",
                        "queryVector": embedding,
                        "numCandidates": 5,
                        "limit": 2
                    }
                }
            ]
            results = list(collection.aggregate(pipeline))
            client_mongo.close()
            for result in results:
                if "_id" in result:
                    result["_id"] = str(result["_id"])
            if results:
                print("[MongoDB] Retrieved similar issues from vector search.")
                state.setdefault("updates", []).append("[MongoDB] Retrieved similar issues.")
                similar_issues = results
            else:
                print("[MongoDB] No similar issues found. Returning default message.")
                state.setdefault("updates", []).append("[MongoDB] No similar issues found.")
                similar_issues = [{"issue": "No similar issues found", "recommendation": "No immediate action based on past data."}]
        except Exception as e:
            print("Error during MongoDB vector search:", e)
            state.setdefault("updates", []).append("Error during vector search.")
            similar_issues = [{"issue": "Vector search error", "recommendation": "Check MongoDB Atlas configuration."}]
    for issue in similar_issues:
        print(issue)
    return {"similar_issues_list": similar_issues}

# --- State Processing Functions ---
def generate_chain_of_thought(state: AgentState) -> AgentState:
    print("\n[LLM Chain-of-Thought Reasoning]")
    profile = get_agent_profile("default_agent")
    issue_report = state["issue_report"]
    prompt = f"""
Agent Profile:
Instructions: {profile['instructions']}
Rules: {profile['rules']}
Goals: {profile['goals']}

You are an AI agent designed to diagnose vehicle issues. Given the issue report:
"{issue_report}"
generate a detailed chain-of-thought reasoning that outlines the following steps:
1. Consume telemetry data.
2. Generate an embedding for the complaint using OpenAI's embedding API.
3. Perform a vector search on past issues in MongoDB Atlas.
4. Persist telemetry data into MongoDB.
5. Use OpenAI's ChatCompletion to generate a final summary and recommendation.
Please provide your chain-of-thought as a numbered list with explanations for each step.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a chain-of-thought generator."},
                {"role": "user", "content": prompt}
            ]
        )
        chain_of_thought = response.choices[0].message.content.strip()
    except Exception as e:
        print("Error generating chain-of-thought reasoning:", e)
        chain_of_thought = (
            "1. Consume telemetry data.\n"
            "2. Generate an embedding for the complaint.\n"
            "3. Perform a vector search on past issues using the embedding.\n"
            "4. Persist telemetry data into MongoDB.\n"
            "5. Generate a final summary and recommendation."
        )
    print(chain_of_thought)
    state.setdefault("updates", []).append("Chain-of-thought generated.")
    return {**state, "chain_of_thought": chain_of_thought, "next_step": "telemetry_tool"}

def process_telemetry(state: AgentState) -> AgentState:
    state.setdefault("updates", []).append("Telemetry data processed.")
    state["next_step"] = "embedding_node"
    return state

def get_complaint_embedding(state: AgentState) -> AgentState:
    print("\n[Action] Generating Complaint Embedding...")
    state.setdefault("updates", []).append("Generating complaint embedding...")
    complaint = state["issue_report"]    
    try:
        #response = client.embeddings.create(model="text-embedding-ada-002", input=complaint)
        #embedding = response.data[0].embedding
        response = vo_client.embed(complaint,model="voyage-3-large",input_type="query")
        embedding = response.embeddings[0]
        state.setdefault("updates", []).append("Complaint embedding generated.")
        print("Voyage AI generated complaint embedding.")
    except Exception as e:
        print("Error generating embedding:", e)
        state.setdefault("updates", []).append("Error generating embedding; using dummy vector.")
        embedding = [0.0] * 1024
    return {**state, "embedding_vector": embedding, "next_step": "vector_search_tool"}

def process_vector_search(state: AgentState) -> AgentState:
    state.setdefault("updates", []).append("Vector search results processed.")
    state["next_step"] = "persistence_node"
    return state

def persist_data_to_mongodb(state: AgentState) -> AgentState:
    state.setdefault("updates", []).append("Persisting data to MongoDB...")
    print("\n[Action] Persisting Data to MongoDB...")
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        state.setdefault("updates", []).append("MONGO_URI not set; skipping persistence.")
        print("[MongoDB] MONGO_URI not set. Skipping data persistence.")
        return {**state, "next_step": "recommendation_node"}
    combined_data = {
        "issue_report": state["issue_report"],
        "telemetry": state["telemetry_data"],
        "similar_issues": state["similar_issues_list"],
        "thread_id": state.get("thread_id", "")
    }
    try:
        client_mongo = pymongo.MongoClient(mongo_uri)
        db = client_mongo[fleet_issues]
        if "telemetry_data" not in db.list_collection_names():
            print("[MongoDB] Creating time series collection 'telemetry_data'.")
            db.create_collection("telemetry_data", timeseries={"timeField": "timestamp", "granularity": "minutes"})
        telemetry_coll = db["telemetry_data"]
        for record in combined_data["telemetry"]:
            try:
                record["timestamp"] = datetime.datetime.strptime(record["timestamp"], "%Y-%m-%dT%H:%M:%SZ")
            except Exception as e:
                print("Error parsing timestamp:", e)
            record["thread_id"] = state.get("thread_id", "")
            record = convert_objectids(record)
            telemetry_coll.insert_one(record)
        print("[MongoDB] Telemetry data persisted in 'telemetry_data' collection.")
        logs_collection = db["logs"]
        log_entry = {
            "thread_id": state.get("thread_id", ""),
            "issue_report": combined_data["issue_report"],
            "similar_issues": combined_data["similar_issues"],
            "created_at": datetime.datetime.utcnow()
        }
        log_entry = convert_objectids(log_entry)
        logs_collection.insert_one(log_entry)
        client_mongo.close()
        state.setdefault("updates", []).append("Data persisted to MongoDB.")
    except Exception as e:
        print("Error persisting data to MongoDB:", e)
        state.setdefault("updates", []).append("Error persisting data to MongoDB.")
    return {**state, "next_step": "recommendation_node"}

def get_llm_recommendation(state: AgentState) -> AgentState:
    state.setdefault("updates", []).append("Generating final recommendation...")
    print("\n[Final Answer] Generating Recommendation...")
    telemetry_data = state["telemetry_data"]
    similar_issues = state["similar_issues_list"]
    if not telemetry_data:
        state.setdefault("updates", []).append("No telemetry data; using default values.")
        print("[Warning] No telemetry data available. Using default values.")
        telemetry_data = [{
            "timestamp": "2025-02-19T13:15:00Z",
            "engine_temperature": "95",
            "oil_pressure": "32",
            "avg_fuel_consumption": "8.8"
        }]
    critical_conditions = []
    for record in telemetry_data:
        try:
            engine_temp = float(record["engine_temperature"])
            oil_pressure = float(record["oil_pressure"])
            if engine_temp > 100:
                critical_conditions.append(f"Critical engine temperature: {engine_temp}°C")
            if oil_pressure < 30:
                critical_conditions.append(f"Low oil pressure: {oil_pressure} PSI")
        except (ValueError, KeyError) as e:
            print(f"[Warning] Error parsing telemetry values: {e}")
    critical_info = "CRITICAL ALERT: " + ", ".join(critical_conditions) + "\n\n" if critical_conditions else ""
    prompt = f"""
You are a vehicle maintenance advisor.

{critical_info}Given the following telemetry data and past similar issues, please analyze the data and recommend an immediate action (continue driving, pull off the road, or schedule maintenance) with a clear explanation.

Telemetry Data: {telemetry_data}

Similar Past Issues: {similar_issues}
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a vehicle maintenance advisor."},
                {"role": "user", "content": prompt}
            ]
        )
        recommendation = response.choices[0].message.content.strip()
    except Exception as e:
        print("Error generating LLM recommendation:", e)
        recommendation = "Unable to generate recommendation at this time."
    print(recommendation)
    state.setdefault("updates", []).append("Final recommendation generated.")
    mongo_uri = os.environ.get("MONGO_URI")
    if mongo_uri:
        try:
            client_mongo = pymongo.MongoClient(mongo_uri)
            db = client_mongo[fleet_issues]
            recommendations_collection = db["historical_recommendations"]
            recommendation_record = {
                "thread_id": state.get("thread_id", ""),
                "timestamp": datetime.datetime.utcnow(),
                "issue_report": state["issue_report"],
                "telemetry_data": state["telemetry_data"],
                "similar_issues": state["similar_issues_list"],
                "recommendation": recommendation
            }
            recommendation_record = convert_objectids(recommendation_record)
            recommendations_collection.insert_one(recommendation_record)
            client_mongo.close()
            state.setdefault("updates", []).append("Recommendation stored in MongoDB.")
            print("[MongoDB] Recommendation stored in historical records")
        except Exception as e:
            print(f"[MongoDB] Error storing recommendation: {e}")
            state.setdefault("updates", []).append("Error storing recommendation in MongoDB.")
    return {**state, "recommendation_text": recommendation, "next_step": "end"}

# --- Conditional Routing ---
def route_by_telemetry_severity(state: AgentState) -> str:
    for record in state["telemetry_data"]:
        if float(record["engine_temperature"]) > 110:
            state.setdefault("updates", []).append("Critical engine temperature detected; bypassing normal flow.")
            print("\n[Alert] Critical engine temperature detected, bypassing normal flow...")
            return "recommendation_node"
    return "embedding_node"

# --- Create MongoDB Saver ---
def create_mongodb_saver():
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        print("[MongoDB] MONGO_URI not set. State saving will be disabled.")
        return None
    try:
        return MongoDBSaver.from_conn_string(mongo_uri)
    except Exception as e:
        print(f"[MongoDB] Error initializing MongoDB saver: {e}")
        return None

def list_available_sessions():
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        print("[MongoDB] MONGO_URI not set. Cannot retrieve sessions.")
        return False
    try:
        client_mongo = pymongo.MongoClient(mongo_uri)
        db = client_mongo[fleet_issues]
        sessions_collection = db["agent_sessions"]
        recent_sessions = list(sessions_collection.find().sort("created_at", -1).limit(10))
        if not recent_sessions:
            print("No previous sessions found.")
            client_mongo.close()
            return False
        print("\n=== Recent Diagnostic Sessions ===")
        print("ID | Time | Issue | Status")
        print("-" * 70)
        for session in recent_sessions:
            thread_id = session.get("thread_id", "unknown")
            created_at = session.get("created_at", "unknown")
            issue = session.get("issue_report", "unknown")
            status = session.get("status", "unknown")
            if len(issue) > 30:
                issue = issue[:27] + "..."
            if isinstance(created_at, datetime.datetime):
                created_at = created_at.strftime("%Y-%m-%d %H:%M")
            print(f"{thread_id} | {created_at} | {issue} | {status}")
        client_mongo.close()
        return True
    except Exception as e:
        print(f"[MongoDB] Error retrieving sessions: {e}")
        return False



# --- Create LangGraph StateGraph ---
def create_workflow_graph(checkpointer=None):
    graph = StateGraph(AgentState)
    graph.add_node("reasoning_node", generate_chain_of_thought)
    graph.add_node("telemetry_tool", get_telemetry_tool)
    graph.add_node("process_telemetry", process_telemetry)
    graph.add_node("embedding_node", get_complaint_embedding)
    graph.add_node("vector_search_tool", vector_search_tool)
    graph.add_node("process_vector_search", process_vector_search)
    graph.add_node("persistence_node", persist_data_to_mongodb)
    graph.add_node("recommendation_node", get_llm_recommendation)
    graph.add_edge("reasoning_node", "telemetry_tool")
    graph.add_edge("telemetry_tool", "process_telemetry")
    graph.add_conditional_edges("process_telemetry", route_by_telemetry_severity)
    graph.add_edge("embedding_node", "vector_search_tool")
    graph.add_edge("vector_search_tool", "process_vector_search")
    graph.add_edge("process_vector_search", "persistence_node")
    graph.add_edge("persistence_node", "recommendation_node")
    graph.add_edge("recommendation_node", END)
    graph.set_entry_point("reasoning_node")
    if checkpointer:
        return graph.compile(checkpointer=checkpointer)
    else:
        return graph.compile()


def format_document(item: Any, max_array_length: int = 10) -> Any:
    """
    Recursively convert ObjectIds to strings and, if the item is a list that
    exceeds `max_array_length`, only return the first max_array_length items with
    a summary string indicating how many items were omitted.
    """
    if isinstance(item, list):
        if len(item) > max_array_length:
            truncated = [format_document(i, max_array_length) for i in item[:max_array_length]]
            return truncated 
        else:
            return [format_document(i, max_array_length) for i in item]
    elif isinstance(item, dict):
        return {k: format_document(v, max_array_length) for k, v in item.items()}
    elif isinstance(item, ObjectId):
        return str(item)
    elif isinstance(item, bytes):
        # Convert binary data to a hex string
        return item.hex()
    else:
        return item


# --- FastAPI Application ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/run-agent")
async def run_agent(issue_report: str = Query("I am hearing knocking sound while turning at low speeds", description="Issue report text")):
    initial_state: AgentState = {
        "issue_report": issue_report,
        "chain_of_thought": "",
        "telemetry_data": [],
        "embedding_vector": [],
        "similar_issues_list": [],
        "recommendation_text": "",
        "next_step": "reasoning_node",
        "updates": [],
        "thread_id": ""
    }
    thread_id = f"thread_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    initial_state["thread_id"] = thread_id
    config = {"configurable": {"thread_id": thread_id}}
    mongodb_saver = create_mongodb_saver()
    try:
        if mongodb_saver:
            with mongodb_saver as checkpointer:
                workflow = create_workflow_graph(checkpointer=checkpointer)
                final_state = workflow.invoke(initial_state, config=config)
                final_state = convert_objectids(final_state)
        else:
            workflow = create_workflow_graph()
            final_state = workflow.invoke(initial_state, config=config)
            final_state = convert_objectids(final_state)
        final_state["thread_id"] = thread_id
        mongo_uri = os.environ.get("MONGO_URI")
        if mongo_uri:
            try:
                client_mongo = pymongo.MongoClient(mongo_uri)
                db = client_mongo[fleet_issues]
                sessions_collection = db["agent_sessions"]
                session_metadata = {
                    "thread_id": thread_id,
                    "issue_report": issue_report,
                    "created_at": datetime.datetime.utcnow(),
                    "status": "completed",
                    "recommendation": final_state["recommendation_text"]
                }
                session_metadata = convert_objectids(session_metadata)
                sessions_collection.insert_one(session_metadata)
                client_mongo.close()
                return final_state
            except Exception as e:
                print(f"[MongoDB] Error storing session metadata: {e}")
                return final_state
    except Exception as e:
        print(f"\n[Error] An error occurred during execution: {e}")
        print(f"You can resume this session later using thread ID: {thread_id}")
        mongo_uri = os.environ.get("MONGO_URI")
        if mongo_uri:
            try:
                client_mongo = pymongo.MongoClient(mongo_uri)
                db = client_mongo[fleet_issues]
                sessions_collection = db["agent_sessions"]
                session_metadata = {
                    "thread_id": thread_id,
                    "issue_report": issue_report,
                    "created_at": datetime.datetime.utcnow(),
                    "status": "error",
                    "error_message": str(e)
                }
                session_metadata = convert_objectids(session_metadata)
                sessions_collection.insert_one(session_metadata)
                client_mongo.close()
                print("[MongoDB] Error state recorded in session metadata")
            except Exception as db_error:
                print(f"[MongoDB] Error storing session error state: {db_error}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/resume-agent")
async def resume_agent(thread_id: str = Query(..., description="Thread ID to resume session")):
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise HTTPException(status_code=500, detail="MONGO_URI not set")
    try:
        client_mongo = pymongo.MongoClient(mongo_uri)
        db = client_mongo[fleet_issues]
        sessions_collection = db["agent_sessions"]
        session = sessions_collection.find_one({"thread_id": thread_id})
        client_mongo.close()
        if session:
            session = convert_objectids(session)
            return session
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get-sessions")
async def get_sessions():
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise HTTPException(status_code=500, detail="MONGO_URI not set")
    try:
        client_mongo = pymongo.MongoClient(mongo_uri)
        db = client_mongo[fleet_issues]
        sessions_collection = db["agent_sessions"]
        sessions = list(sessions_collection.find().sort("created_at", -1).limit(10))
        sessions = convert_objectids(sessions)
        client_mongo.close()
        return sessions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/get-run-documents")
async def get_run_documents(thread_id: str = Query(..., description="Thread ID of the agent run")):
    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise HTTPException(status_code=500, detail="MONGO_URI not set")
    try:
        client_mongo = pymongo.MongoClient(mongo_uri)
        db = client_mongo[fleet_issues]
        docs = {}

        # For collections where thread_id is stored with extra characters, use regex to find the right data
        query = {"thread_id": {"$regex": f"^{thread_id}"}}

        # Retrieve agent_sessions document
        session = db["agent_sessions"].find_one(query)
        docs["agent_sessions"] = format_document(session) if session else {}

        # Retrieve historical_recommendations for the run
        historical = db["historical_recommendations"].find_one(query)
        docs["historical_recommendations"] = format_document(historical) if historical else {}

        # Retrieve telemetry_data for the run
        telemetry = db["telemetry_data"].find_one(query)
        docs["telemetry_data"] = format_document(telemetry) if telemetry else {}

        # Retrieve logs for the run
        log = db["logs"].find_one(query)
        docs["logs"] = format_document(log) if log else {}

        # Retrieve the default agent profile (not run-specific)
        profile = db["agent_profiles"].find_one({"agent_id": "default_agent"})
        docs["agent_profiles"] = format_document(profile) if profile else {}

        # Retrieve one sample past_issues document (most recent)
        past_issue = db["past_issues"].find_one(sort=[("created_at", -1)])
        docs["past_issues"] = format_document(past_issue) if past_issue else {}

        client_mongo.close()

        # Connect to "checkpointing_db" and get the last document from the "checkpoints" collection
        client_checkpoint = pymongo.MongoClient(mongo_uri)
        checkpoint_db = client_checkpoint["checkpointing_db"]
        checkpoint_collection = checkpoint_db["checkpoints"]
        last_checkpoint = checkpoint_collection.find_one(sort=[("created_at", -1)])
        docs["checkpoints"] = format_document(last_checkpoint) if last_checkpoint else {}
        client_checkpoint.close()

        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
