import sys
import os

# Add the 'Prompt' folder to the system path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'Prompt'))

import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from tavily import TavilyClient
from langchain_google_genai import GoogleGenerativeAI
from prompts import sentiment_prompt, financial_prompt, default_prompt
# MongoDB connection
client = MongoClient("mongodb+srv://admin:test1234!@cluster0.70cv6.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client.todo_db
collection = db["todo_collection"]

def initialize_environment():
    dotenv_file_path = os.path.join('config', '.env')
    load_dotenv(dotenv_file_path)
    log_directory = 'logs'
    os.makedirs(log_directory, exist_ok=True)
    log_file_path = os.path.join(log_directory, 'app.log')
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s",
        filename=log_file_path, filemode='a')
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    google_api_key = os.getenv("GOOGLE_KEY")

    if not tavily_api_key or not google_api_key:
        logging.error("API keys are missing. Please check your environment variables.")
        raise ValueError("**Program Killed**")
    return tavily_api_key, google_api_key

def perform_tavily_search(tavily_client, search_query, search_type):
    if search_type not in ["general", "news"]:
        logging.error("Invalid search type. Please enter either 'general' or 'news'.")
        raise ValueError("**Invalid search type**")
    try:
        search_results = tavily_client.search(
            query=search_query, search_depth="advanced", topic=search_type,
            max_results=20, include_answer=True)
        return search_results
    except Exception as e:
        logging.error(f"Error during search: {e}")
        raise ValueError("A problem occurred during the search process.")

def process_search_results(search_results):
    extracted_data = {
        'search_query': search_results.get('query'),
        'answer': search_results.get('answer'),
        'content': [
            result.get('content') for result in search_results.get('results', [])
            if 'content' in result]
    }
    return "\n".join([extracted_data['search_query'], extracted_data['answer'], *extracted_data['content']])

def generate_response_with_gemini(formatted_prompt, google_api_key):
    try:
        google_ai_client = GoogleGenerativeAI(
            model="gemini-pro", google_api_key=google_api_key)
        ai_response = google_ai_client.generate(prompts=[formatted_prompt])
        return ai_response.generations[0][0].text
    except Exception as e:
        logging.error(f"Error during AI generation: {e}")
        raise ValueError("Error during AI generation. Please check your input or API connection.")

# Function to save to MongoDB
def save_to_mongo(search_type, search_query, user_query, generated_answer):
    document = {
        "search_type": search_type,
        "search_query": search_query,
        "user_query": user_query,
        "generated_answer": generated_answer
    }
    collection.insert_one(document)

def get_mongo_history():
    # Fetching all documents from the collection
    documents = collection.find()
    return documents

# Function to get all documents from MongoDB (fetch history)


# Streamlit app
import streamlit as st

def run_streamlit_app():
    st.title("Tavily & Gemini Integration")

    # Get the query and type of search from the user
    search_query = st.text_input("Enter the topic you want to search:")
    search_type = st.selectbox("Select search type", ["general", "news"])

    if search_query:
        try:
            tavily_api_key, google_api_key = initialize_environment()
            tavily_client = TavilyClient(tavily_api_key)
            search_results = perform_tavily_search(tavily_client, search_query, search_type)
            formatted_content = process_search_results(search_results)

            st.write(f"Search Results: {formatted_content}")

            analysis_type = st.selectbox("Choose analysis type", ["sentiment", "financial", "general"])
            user_specific_query = st.text_input("Ask a specific question:")

            if user_specific_query:
                selected_prompt = {
                    "sentiment": sentiment_prompt,
                    "financial": financial_prompt,
                }.get(analysis_type, default_prompt)

                formatted_prompt = selected_prompt.format(custom_context=formatted_content, user_query=user_specific_query)
                generated_answer = generate_response_with_gemini(formatted_prompt, google_api_key)

                st.write("Generated Answer:")
                st.write(generated_answer)

                # Save to MongoDB
                save_to_mongo(search_type, search_query, user_specific_query, generated_answer)

                st.success("Saved to MongoDB successfully!")

        except Exception as e:
            st.error(f"An error occurred: {e}")
    
    # Fetch and display MongoDB history (saved queries)
    st.subheader("History of Saved Queries:")
    history = get_mongo_history()

    # Filter out empty records (e.g., N/A)
    filtered_history = [record for record in history if record.get('search_type') not in ['N/A', None]]

    # Loop through the filtered history and display each saved document
    for record in filtered_history:
        # Safely retrieve keys from the record
        search_type = record.get('search_type', 'N/A')
        search_query = record.get('search_query', 'N/A')
        user_query = record.get('user_query', 'N/A')
        generated_answer = record.get('generated_answer', 'N/A')

        # Display the information in the app
        st.write(f"**Search Type**: {search_type}")
        st.write(f"**Search Query**: {search_query}")
        st.write(f"**User Query**: {user_query}")
        st.write(f"**Generated Answer**: {generated_answer}")
        st.write("---")

if __name__ == "__main__":
    run_streamlit_app()
