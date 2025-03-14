import streamlit as st
from utils import GoogleDriveFolder, is_valid_email, is_valid_password, update_observation
from datetime import datetime
import time, re
from datetime import datetime

# Access secrets
FOLDER_ID = st.secrets["google"]
#CREDENTIALS = "trl-doc-uploader-ca4496d60409.json"
CREDENTIALS = dict(st.secrets["gcp_service_account"])

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

# Ensure authentication on app start
if "gdrive" not in st.session_state:
    if not authenticate_with_retries():
        st.stop()

# Streamlit UI
st.title("📝 TRL Reporter")
st.write("""Este sistema permite cargar un documento PDF, a partir del cuál se generará un reporte TRL. Cada usuario podrá generar <u>solo un reporte TRL.</u>

🔹 **Instrucciones:**\n
1️⃣ Ingrese su correo electrónico y contraseña correctamente.\n
2️⃣ Cargue su documento en formato PDF.\n

📢 **Notificación**: Una vez que su documento sea procesado, recibirá una copia en el correo electrónico registrado.""", unsafe_allow_html=True)

# User input fields
email = st.text_input("Email")
password = st.text_input("Contraseña", type="password")
file = st.file_uploader("Elija un archivo PDF", type=["pdf"])

valid_email = is_valid_email(email)
valid_password = is_valid_password(password)

# Submit button
if st.button("⬆️ Upload"):
    if valid_email and valid_password and file:
        # Save uploaded file temporarily
        temp_file_path = f"{file.name}"
        with open(temp_file_path, "wb") as f:
            f.write(file.getbuffer())

        # Read workListFile.csv
        #workListFile = st.session_state.gdrive.read_csv_from_gdrive("DocsToProcess/workListFile.csv")
        #print(workListFile)
        name = email.split('@')[0]
        name = re.sub(r'[^a-zA-Z0-9]', '', name) # Eliminar caracteres no alfanuméricos
        #date = datetime.today().strftime("%d_%m_%Y")
        # Upload file
        try:
            #file_id = st.session_state.gdrive.upload_file(temp_file_path, file_name=f'{name}.pdf', folder_id=FOLDER_ID["DocsOrig_id"])
            #st.session_state.gdrive.list_files_in_shared_drive(FOLDER_ID["DocsToProcess_id"])
            workListFile = st.session_state.gdrive.read_csv_from_drive(file_name="workListFile.csv", folder_id=FOLDER_ID["DocsToProcess_id"])
            print("🐢")
            print(workListFile)
            status, workListFile = update_observation(workListFile, f"{name}.txt", email)
            print("🐢")
            print(status)
            print(workListFile)
            
            if status == "Negado: Servicio ya provisto.":
                 st.error(f"❌ Ya se brindó el servicio a la cuenta: {email}")
            else:
                file_id = st.session_state.gdrive.upload_file(temp_file_path, file_name=f'{name}.pdf', folder_id=FOLDER_ID["DocsOrig_id"])
                txt_id = st.session_state.gdrive.extract_text_and_upload(temp_file_path, file_name=f'{name}.txt', folder_id=FOLDER_ID["DocsToProcess_id"])
                csv_id = st.session_state.gdrive.update_csv_from_df_retry(workListFile, file_name="workListFile.csv", folder_id=FOLDER_ID["DocsToProcess_id"])
            
            if status == "Aceptado: Sobre-Escritura.":
                st.success(f"✅ Se identificó archivo previamente subido. Sobre-escritura exitosa! Al culminar el proceso, se mandará el resultado a {email} .ID de Archivo: {file_id}, ID CSV:{csv_id}")
            
            if status == "Aceptado: Nuevo Registro.":
                st.success(f"✅ Carga exitosa! Al culminar el proceso, se mandará el resultado a {email} .ID de Archivo: {file_id}, ID CSV:{csv_id}")
            
        except Exception as e:
            st.error(f"❌ Error al cargar: {e}")
    else:
        if not valid_email:
            st.warning("⚠️ Ingrese un correo electrónico válido.")
        elif not valid_password:
            st.warning("⚠️ Por favor, verifique que su contraseña sea la correcta.")
        elif not file:
            st.warning("⚠️ Adjunte un archivo, por favor.")
