import streamlit as st
from datetime import datetime
import time

# Function to upload files to Google (your existing function)
def upload_to_google(files, metadata):
    # Simulate uploading logic
    success = []
    overwritten = []
    for file in files:
        # Simulate file upload and overwriting detection
        if file.name.endswith('.pdf'):
            overwritten.append(file.name)
        else:
            success.append(file.name)
    return success, overwritten

# To prevent excessive uploads, use a timestamp check
# For simplicity, assume we track the last upload time globally.
last_upload_time = st.session_state.get('last_upload_time', None)

# To prevent upload frequency, set a minimum interval between uploads
MIN_UPLOAD_INTERVAL = 60  # 60 seconds

# Check if the user can upload based on time elapsed since last upload
def can_upload():
    global last_upload_time
    if last_upload_time is None:
        return True
    if (datetime.now() - last_upload_time).seconds > MIN_UPLOAD_INTERVAL:
        return True
    return False

# Main Streamlit app
def app():
    st.set_page_config(page_title="File Upload", page_icon="📤")
    
    # Header of the site
    st.title("Welcome to the File Upload Portal")
    
    # Form for the user details
    with st.form(key="user_info"):
        st.subheader("Please fill in your details")
        
        name = st.text_input("Your Name", "")
        email = st.text_input("Your Email", "")
        institution = st.text_input("Your Institution", "")
        
        submit_button = st.form_submit_button(label="Submit Info")
    
    # Ensure user fills out name and email
    if submit_button:
        if not name or not email:
            st.error("Both name and email are required.")
        else:
            st.success("Information submitted successfully!")
    
    # File uploader section
    st.subheader("Upload Your Files")
    uploaded_files = st.file_uploader("Choose files", type=["txt", "pdf", "docx"], accept_multiple_files=True)
    
    # Check if files are uploaded
    if uploaded_files:
        # Check if the user can upload
        if not can_upload():
            st.error("You must wait a while before uploading again.")
        else:
            st.success("Files ready for upload.")
            
            # Upload button
            upload_button = st.button("Upload Files")
            
            if upload_button:
                # Track the upload time
                st.session_state.last_upload_time = datetime.now()
                
                # Preprocess files and metadata
                metadata = {
                    "name": name,
                    "email": email,
                    "institution": institution,
                    "upload_time": str(datetime.now())
                }
                
                # Call the function to upload files
                success_files, overwritten_files = upload_to_google(uploaded_files, metadata)
                
                if success_files:
                    st.success(f"Files uploaded successfully: {', '.join(success_files)}")
                
                if overwritten_files:
                    st.warning(f"Some files were overwritten: {', '.join(overwritten_files)}")

# Run the app
if __name__ == "__main__":
    app()
