# import streamlit as st
# import requests
# import json

# # Configure the page
# st.set_page_config(
#     page_title="Chatbot Interface",
#     page_icon="💬",
#     layout="centered"
# )

# # Initialize session state for chat history
# if "messages" not in st.session_state:
#     st.session_state.messages = []

# # Backend URL
# BACKEND_URL = "http://localhost:8000"

# def stream_response(query: str):
#     """
#     Stream the response from the backend using Server-Sent Events
#     """
#     messages_container = st.empty()
#     current_response = ""
    
#     try:
#         # Connect to the streaming endpoint
#         url = f"{BACKEND_URL}/api/v1/chat/stream"
#         headers = {
#             "Content-Type": "application/json",
#             "Accept": "text/event-stream"
#         }
#         data = {
#             "query": query,
#             "user_id": "streamlit_user"  # You can implement proper user management later
#         }
        
#         # Make the streaming request
#         with requests.post(url, headers=headers, json=data, stream=True) as response:
#             for line in response.iter_lines():
#                 if line:
#                     try:
#                         # Remove "data: " prefix and parse JSON
#                         line = line.decode('utf-8')
#                         if line.startswith('data: '):
#                             data = json.loads(line[6:])
                            
#                             # Handle different types of messages
#                             if data.get("type") == "category":
#                                 st.session_state.current_category = data.get("category")
#                             elif data.get("type") == "content":
#                                 current_response += data.get("token", "")
#                                 # Update the message in place
#                                 messages_container.markdown(current_response + "▌")
#                             elif data.get("type") == "error":
#                                 st.error(data.get("error"))
#                                 break
#                             elif data.get("type") == "done":
#                                 messages_container.markdown(current_response)
#                                 break
#                     except json.JSONDecodeError:
#                         st.error("Error parsing server response")
#                         break
                    
#     except Exception as e:
#         st.error(f"Error connecting to backend: {str(e)}")
#         return None
    
#     return current_response

# # Page header
# st.title("💬 Chatbot Interface")
# st.markdown("Chat with the AI assistant using the text input below.")

# # Display chat history
# for message in st.session_state.messages:
#     with st.chat_message(message["role"]):
#         st.markdown(message["content"])

# # Chat input
# if prompt := st.chat_input("What would you like to know?"):
#     # Add user message to chat history
#     st.session_state.messages.append({"role": "user", "content": prompt})
#     with st.chat_message("user"):
#         st.markdown(prompt)
    
#     # Add assistant response
#     with st.chat_message("assistant"):
#         response = stream_response(prompt)
#         if response:
#             st.session_state.messages.append({"role": "assistant", "content": response})

# # Add a status indicator for backend connection
# try:
#     status = requests.get(f"{BACKEND_URL}/api/v1/status")
#     if status.ok:
#         st.sidebar.success("✅ Backend is connected")
#         status_data = status.json()
#         st.sidebar.write("Vectorstore status:", 
#                         "Ready" if status_data.get("vectorstore_ready") else "Loading")
# except:
#     st.sidebar.error("❌ Backend is not connected")