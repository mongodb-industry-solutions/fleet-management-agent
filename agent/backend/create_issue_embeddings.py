#!/usr/bin/env python3
"""
Script to generate vector embeddings for sample vehicle issues and store them in MongoDB.

This script uses OpenAI's text-embedding-ada-002 to generate embeddings
for a set of sample issues and recommendations, and then stores them in the "past_issues" collection
within the "fleet_issues" database.

Usage:
    python create_issue_embeddings.py

Ensure the following environment variables are set:
    - OPENAI_API_KEY: Your OpenAI API key.
    - MONGO_URI: Your MongoDB Atlas connection string.
"""

import os
from openai import OpenAI
import voyageai
import pymongo

from dotenv import load_dotenv
load_dotenv()

# Check that necessary environment variables are set.
openai_api_key = os.environ.get("OPENAI_API_KEY")
voyage_api_key = os.environ.get("VOYAGE_API_KEY")
fleet_issues = os.environ.get("DATABASE")
client = OpenAI( api_key=os.environ.get("OPENAI_API_KEY"))
vo_client = voyageai.Client()


# Sample issues and recommendations (add more samples as desired)
sample_issues = [
    {"issue": "Engine knocking when turning", "recommendation": "Inspect spark plugs and engine oil."},
    {"issue": "Suspension noise under load", "recommendation": "Check suspension components for wear."},
    {"issue": "Brake pedal sponginess", "recommendation": "Check brake fluid level and bleed brakes if necessary."},
    {"issue": "Overheating engine", "recommendation": "Inspect coolant level, radiator, and water pump."},
    {"issue": "Strange vibration at high speeds", "recommendation": "Check wheel balance, tire condition, and alignment."},
]

def get_embedding(text):
    """
    Generate an embedding for the given text using OpenAI's embedding API.
    """
    try:
        #response = client.embeddings.create(model="text-embedding-ada-002", input=text)
        #embedding = response.data[0].embedding
        response = vo_client.embed(text,model="voyage-3-large",input_type="document")
        embedding = response.embeddings[0]
        return embedding
    except Exception as e:
        print(f"Error generating embedding for '{text}': {e}")
        return None

def main():


    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        print("Error: MONGO_URI environment variable not set.")
        return

    # Connect to MongoDB
    client = pymongo.MongoClient(mongo_uri)
    db = client[fleet_issues]
    collection = db["past_issues"]

    # Optionally, clear existing documents (uncomment the next line to start fresh)
    # collection.delete_many({})

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
