#!/usr/bin/env python3
"""
Script to generate vector embeddings for sample vehicle issues and store them in MongoDB.

This script uses Voyage AI's voyage-3-large model to generate embeddings
for a set of sample issues and recommendations, and then stores them in the "past_issues" collection
within the database named by DATABASE.

Usage:
    python create_issue_embeddings.py

Ensure the following environment variables are set:
    - VOYAGE_API_KEY: Your Voyage AI API key.
    - MONGO_URI: Your MongoDB Atlas connection string.
    - DATABASE: The database to seed.

Safe to run again: skips seeding if past_issues already has documents.
"""

import os
import time
import voyageai
import pymongo

from dotenv import load_dotenv
load_dotenv()

fleet_issues = os.environ.get("DATABASE")
app_name = os.environ.get("APP_NAME", "devrel-demo-langgraph-voyageai-fleet")
vo_client = voyageai.Client()


# Sample issues and recommendations (add more samples as desired)
sample_issues = [
    {"issue": "Engine knocking when turning", "recommendation": "Inspect spark plugs and engine oil."},
    {"issue": "Suspension noise under load", "recommendation": "Check suspension components for wear."},
    {"issue": "Brake pedal sponginess", "recommendation": "Check brake fluid level and bleed brakes if necessary."},
    {"issue": "Overheating engine", "recommendation": "Inspect coolant level, radiator, and water pump."},
    {"issue": "Strange vibration at high speeds", "recommendation": "Check wheel balance, tire condition, and alignment."},
]

def get_embedding(text, retries=3, backoff_seconds=25):
    """
    Generate an embedding for the given text using Voyage AI's embedding API.

    Voyage accounts without a payment method on file are capped at 3
    requests/minute; retry with a backoff instead of failing the whole seed
    run over a transient rate limit.
    """
    for attempt in range(1, retries + 1):
        try:
            response = vo_client.embed(text, model="voyage-3-large", input_type="document")
            return response.embeddings[0]
        except Exception as e:
            if "rate limit" in str(e).lower() and attempt < retries:
                print(f"Rate limited, waiting {backoff_seconds}s before retry {attempt + 1}/{retries}...")
                time.sleep(backoff_seconds)
                continue
            print(f"Error generating embedding for '{text}': {e}")
            return None

def main():


    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        print("Error: MONGO_URI environment variable not set.")
        return

    # Connect to MongoDB
    client = pymongo.MongoClient(mongo_uri, appname=app_name)
    db = client[fleet_issues]
    collection = db["past_issues"]

    existing = collection.count_documents({})
    if existing:
        print(f"past_issues already has {existing} document(s), skipping seed.")
        client.close()
        return

    # Process each sample record
    for record in sample_issues:
        issue_text = record["issue"]
        print(f"Processing issue: {issue_text}")
        embedding = get_embedding(issue_text)
        if embedding is not None:
            record["embedding"] = embedding
            result = collection.insert_one(record)
            print(f"Inserted document with _id: {result.inserted_id}")
        else:
            print(f"Skipping issue: {issue_text} due to an error in embedding generation.")

    client.close()
    print("Completed inserting sample issues with embeddings.")

if __name__ == "__main__":
    main()
