import streamlit as st
from pymongo import MongoClient
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os

# Load dotenv 
load_dotenv() 

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI") 
client = MongoClient(MONGO_URI)
db = client["wiki"]
collection = db["embeddings"]

# Fetch all titles for dropdown
def get_titles():
    return [doc["title"] for doc in collection.find({}, {"title": 1, "_id": 0})]

# Fetch embedding for a selected title
def get_embedding(title):
    doc = collection.find_one({"title": title}, {"_id": 0, "embedding": 1})
    return doc["embedding"] if doc else None

# Perform vector search
def find_similar_articles(title, num_recommendations):
    query_vector = get_embedding(title)
    if not query_vector:
        return []
    
    pipeline = [
        {
            "$vectorSearch": {
                "exact": False,
                "index": "wiki_vectorindex",
                "limit": num_recommendations + 1,  # Fetch extra to skip the first
                "numCandidates": 50,
                "path": "embedding",
                "queryVector": query_vector,
            }
        },
        {"$project": {"title": 1, "_id": 0}},
    ]
    
    results = [doc["title"] for doc in collection.aggregate(pipeline)]
    return results[1:]  # Skip the first result (same as input)

# Fetch Wikipedia Page Content
def get_wikipedia_content(title):
    url_title = title.replace(" ", "_")  # Convert spaces to underscores
    url = f"https://en.wikipedia.org/wiki/{url_title}"
    
    response = requests.get(url)
    if response.status_code != 200:
        return "⚠️ Wikipedia page not found.", url

    soup = BeautifulSoup(response.text, "html.parser")
    
    # Extract first paragraph
    paragraphs = soup.select("p")
    content = ""
    for p in paragraphs:
        text = p.get_text().strip()
        if text:
            content = text
            break  # Take only the first non-empty paragraph
    
    return content, url

# Streamlit UI
st.set_page_config(page_title="Wikipedia Vector Search", layout="wide")
st.title("🔍 Wikipedia Article Recommendation Engine")

# Sidebar for selection
st.sidebar.header("Select Search Options")
all_titles = get_titles()
selected_title = st.sidebar.selectbox("Choose a Wikipedia Article", all_titles)
num_recommendations = st.sidebar.slider("Number of Similar Articles", min_value=1, max_value=10, value=5)

# Button to trigger search
if st.sidebar.button("Find Similar Articles"):
    with st.spinner("Fetching Wikipedia content and recommendations..."):
        # Fetch Wikipedia content
        wiki_content, wiki_url = get_wikipedia_content(selected_title)
        
        # Fetch recommendations
        recommendations = find_similar_articles(selected_title, num_recommendations)

        # Layout: Two columns (left = Wikipedia content, right = recommendations)
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader(f"📖 {selected_title}")
            st.markdown(f"[Read full article]({wiki_url})", unsafe_allow_html=True)
            st.write(wiki_content)

        with col2:
            st.subheader("🔗 Top Similar Articles")
            for idx, title in enumerate(recommendations, 1):
                article_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
                st.markdown(f"**{idx}.** [{title}]({article_url})", unsafe_allow_html=True)
