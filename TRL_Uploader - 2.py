import streamlit as st
from utils import GoogleDriveFolder, is_valid_email, is_valid_password, update_observation
import time, re
import tempfile

#This application allows researchers to upload multiple files, which are then 
#stored in a dedicated folder assigned to each researcher.

#Features:
#- Accepts multiple file uploads.
#- Automatically organizes files into researcher-specific folders.
#- Ensures secure and structured storage for research data

# ========================================
# 🔒 SECRETS 🔒
# ========================================
FOLDER_ID = st.secrets["google"]
#CREDENTIALS = "trl-doc-uploader-ca4496d60409.json"
CREDENTIALS = dict(st.secrets["gcp_service_account"])

PASSWORD = str(st.secrets["app"]["password"])

# ========================================
# 🛠️ FUNCTIONS 🛠️
# ========================================
# Retry Authentication
def authenticate_with_retries(max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            st.session_state.gdrive = GoogleDriveFolder(credentials=CREDENTIALS, folder_id=FOLDER_ID)
            return True
        except Exception as e:
            st.warning(f"Authentication failed (Attempt {attempt}/{max_retries}): {e}")
            time.sleep(2)
    st.error("Failed to authenticate with Google Drive after multiple attempts.")
    return False

# Validation Functions
def validate_inputs(email, password, files):
    errors = []
    if not is_valid_email(email):
        errors.append("⚠️ Ingrese un correo electrónico válido.")
    if not is_valid_password(password, PASSWORD):
        errors.append("⚠️ Verifique que su contraseña sea correcta.")
    if not files:
        errors.append("⚠️ Adjunte al menos un archivo PDF.")
    
    return errors  # Returns a list of errors

# ========================================
# 📂 STATES 📂
# ========================================
# 🛠 Initialize Session State for Stored Files
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []  # Store uploaded file names

# Ensure authentication on app start
if "gdrive" not in st.session_state:
    if not authenticate_with_retries():
        st.stop()

# ========================================
# 📌 GUI Components📌
# ========================================
# Streamlit UI
st.title("📝 TRL Reporter")
st.write("""Este sistema permite cargar un documento PDF, a partir del cuál se generará un reporte TRL. Cada usuario podrá generar <u>solo un reporte TRL.</u>

🔹 **Instrucciones:**\n
1️⃣ Ingrese su correo electrónico y contraseña correctamente.\n
2️⃣ Cargue su documento en formato PDF.\n

📢 **Notificación**: Una vez que su documento sea procesado, recibirá una copia en el correo electrónico registrado.""", unsafe_allow_html=True)

email = st.text_input("📧 Email")
password = st.text_input("🔒 Contraseña", type="password")
files = st.file_uploader("📄 Subir archivos PDF", type=["pdf"], accept_multiple_files=True)

# ========================================
# 🚀 Submit Button 🚀
# ========================================
# Submit button
if st.button("⬆️ Upload"):
    
    errors = validate_inputs(email, password, files)
    
    if errors:
        for error in errors:
            st.warning(error)
    
    else:
        name = re.sub(r'[^a-zA-Z0-9]', '', email.split('@')[0])  # Remove non-alphanumeric characters
        
        try:
            # ☁️ Read workListFile
            workListFile = st.session_state.gdrive.read_csv_from_drive(
                file_name="workListFile.csv", folder_id=FOLDER_ID["DocsToProcess_id"]
                )
            
            # Determine if cleanup is needed
            existing_record = workListFile[workListFile["email"] == email]
            cleanup_required = not existing_record.empty and existing_record["status"].iloc[0] != "Ready"
            
            if cleanup_required:
                # 🧹 Clean previous uploads (only if not marked as 'Ready')
                st.session_state.gdrive.delete_user_folder_if_exists(FOLDER_ID["DocsOrig_id"], name)
                st.session_state.gdrive.delete_user_folder_if_exists(FOLDER_ID["DocsToProcess_id"], name)
            
            # Check if user's folder already exists, otherwise create it
            user_folder_id = st.session_state.gdrive.create_folder_if_not_exists(
                folder_name=name, parent_folder_id=FOLDER_ID["DocsOrig_id"]
            )
            user_folder_txts = st.session_state.gdrive.create_folder_if_not_exists(
                folder_name=name, parent_folder_id=FOLDER_ID["DocsToProcess_id"]
            )
                
            
            # Track if at least one successful upload occurs
            successful_uploads = False
            
            for file in files:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(file.getbuffer())
                    temp_file_path = temp_file.name
                
                final_filename = f"{name}_{file.name}"
                txt_filename = f"{final_filename}.txt"
                
                status, workListFile = update_observation(workListFile, txt_filename, email)

                if status == "Negado: Servicio ya provisto.":
                    st.error(f"❌ Ya se brindó el servicio a la cuenta: {email}")
                else:
                    file_id = st.session_state.gdrive.upload_file(
                        temp_file_path, file_name=final_filename, folder_id=user_folder_id
                        )
                    txt_id = st.session_state.gdrive.extract_text_and_upload(
                        temp_file_path, file_name=final_filename, folder_id=user_folder_txts
                        )
                    # Store uploaded files in session state
                    st.session_state.uploaded_files.append(file.name)
                    st.success(f"✅ {file.name} cargado correctamente.")
                    successful_uploads = True
            
            if successful_uploads:
                csv_id = st.session_state.gdrive.update_csv_from_df_retry(
                    workListFile, file_name="workListFile.csv", folder_id=FOLDER_ID["DocsToProcess_id"]
                    )
                st.info("📄 Base de datos actualizado correctamente.")

                
        except Exception as e:
            st.error(f"❌ Error al cargar: {e}")

# ========================================
# 📜 Show Previously Uploaded Files
# ========================================
if st.session_state.uploaded_files:
    st.subheader("📜 Archivos Subidos")
    st.write(", ".join(st.session_state.uploaded_files))