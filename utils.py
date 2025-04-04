import logging
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
import re, io, os, tempfile, time
import pymupdf

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class GoogleDriveFolder:
    def __init__(self, credentials, folder_id=None):
        """
        Initializes the GoogleDriveFolder instance and authenticates.
        :param credentials: Path to the service account JSON file OR a dictionary containing credentials.
        :param folder_id: Folder ID to work with (None if working with root).
        """
        self.credentials = credentials
        self.folder_id = folder_id
        self.drive = self.authenticate_google_drive()

    def authenticate_google_drive(self):
        """
        Authenticates using the Service Account and returns the GoogleDrive instance.
        Supports both JSON file path and dictionary credentials.
        """
        scopes = ["https://www.googleapis.com/auth/drive"]
        gauth = GoogleAuth()

        try:
            if isinstance(self.credentials, str):  # If it's a file path
                creds = ServiceAccountCredentials.from_json_keyfile_name(self.credentials, scopes)
            elif isinstance(self.credentials, dict):  # If it's a dictionary
                creds = ServiceAccountCredentials.from_json_keyfile_dict(self.credentials, scopes)
            else:
                raise ValueError("Invalid credentials format. Provide a file path (str) or a dictionary (dict).")

            gauth.credentials = creds
            drive = GoogleDrive(gauth)
            logging.info("Authenticated successfully with Google Drive!")
            return drive

        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            raise

    def get_folder_files(self):
        """
        Lists the files in the specified folder or root.
        :return: A list of files.
        """
        try:
            query = f"'{self.folder_id}' in parents and trashed=false" if self.folder_id else "trashed=false"
            file_list = self.drive.ListFile({'q': query}).GetList()

            logging.info(f"Found {len(file_list)} files in folder '{self.folder_id or 'root'}'.")
            return file_list

        except Exception as e:
            logging.error(f"Error fetching folder files: {e}")
            return []

    def create_folder(self, folder_name):
        """
        Creates a new folder inside the specified folder or root.
        :param folder_name: The name of the folder to create.
        :return: The ID of the created folder.
        """
        try:
            folder_metadata = {
                'title': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [{'id': self.folder_id}] if self.folder_id else []
            }

            folder = self.drive.CreateFile(folder_metadata)
            folder.Upload()
            logging.info(f"Folder '{folder_name}' created successfully!")

            return folder['id']

        except Exception as e:
            logging.error(f"Error creating folder '{folder_name}': {e}")
            return None

    def upload_file(self, file_path:str, file_name:str, folder_id:str):
        """
        Uploads a file to Google Drive, enforcing overwrite if the file already exists.

        :param file_path: The local file path.
        :param file_name: The destination file name in Drive (e.g., "file.pdf").
        :param folder_id: The ID of the destination folder in Google Drive (default is "root").
        :return: The uploaded file's ID.
        """
        try:
            # Check if file exists locally
            if not os.path.exists(file_path):
                logging.error(f"Error: File '{file_path}' does not exist.")
                return None

            # Check if the file already exists in the folder
            query = f"title = '{file_name}' and mimeType != 'application/vnd.google-apps.folder' and '{folder_id}' in parents"
            existing_files = self.drive.ListFile({'q': query}).GetList()

            # Delete existing files with the same name (overwrite enforcement)
            for f in existing_files:
                logging.info(f"Deleting existing file: {f['title']}")
                f.Delete()

            # Upload the new file
            file_metadata = {'title': file_name, 'parents': [{'id': folder_id}]}
            file = self.drive.CreateFile(file_metadata)
            file.SetContentFile(file_path)
            file.Upload()

            logging.info(f"File '{file_name}' uploaded successfully to folder ID '{folder_id}', replacing any previous versions.")
            return file['id']

        except Exception as e:
            logging.error(f"Error uploading file '{file_name}': {e}")
            return None
        
    def upload_file_2(self, file_content=None, file_path=None, file_name:str=None, folder_id:str="root"):
        """
        Uploads a file to Google Drive, either from memory (variable) or from a file path.

        :param file_content: The content of the file as a string or bytes (if given, will be used instead of file_path).
        :param file_path: The local file path (optional, if file_content is not used).
        :param file_name: The destination file name in Drive.
        :param folder_id: The ID of the destination folder in Google Drive.
        :return: The uploaded file's ID.
        """
        try:
            if file_content is None and file_path is None:
                logging.error("Error: No file content or file path provided.")
                return None

            if file_content is not None:
                # Convert string content to a file-like object
                if isinstance(file_content, str):
                    file_obj = io.StringIO(file_content)  # Text-based file
                elif isinstance(file_content, bytes):
                    file_obj = io.BytesIO(file_content)  # Binary file
                else:
                    logging.error("Error: file_content must be a string or bytes.")
                    return None
            else:
                if not os.path.exists(file_path):
                    logging.error(f"Error: File '{file_path}' does not exist.")
                    return None

            # Check if the file already exists in the folder
            query = f"title = '{file_name}' and mimeType != 'application/vnd.google-apps.folder' and '{folder_id}' in parents"
            existing_files = self.drive.ListFile({'q': query}).GetList()

            # Delete existing files with the same name (overwrite enforcement)
            for f in existing_files:
                logging.info(f"Deleting existing file: {f['title']}")
                f.Delete()

            # Upload the file
            file_metadata = {'title': file_name, 'parents': [{'id': folder_id}]}
            file = self.drive.CreateFile(file_metadata)

            if file_content is not None:
                file.SetContentString(file_obj.getvalue())  # Set content directly from variable
            else:
                file.SetContentFile(file_path)  # Upload from file

            file.Upload()

            logging.info(f"File '{file_name}' uploaded successfully to folder ID '{folder_id}', replacing any previous versions.")
            return file['id']

        except Exception as e:
            logging.error(f"Error uploading file '{file_name}': {e}")
            return None


    def get_or_create_folder(self, user_name):
        """
        Checks if a folder with the user's name exists, and creates it if it doesn't.
        :param user_name: The name of the user whose folder we need.
        :return: The ID of the user's folder.
        """
        try:
            query = f"'{self.folder_id}' in parents and title = '{user_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed=false"
            folder_list = self.drive.ListFile({'q': query}).GetList()

            if folder_list:
                return folder_list[0]['id']
            else:
                logging.info(f"Creating '{user_name}' folder.")
                return self.create_folder(user_name)

        except Exception as e:
            logging.error(f"Error getting/creating user folder '{user_name}': {e}")
            return None
    
    def create_nested_folders(self, folder_path):
        """
        Recursively creates nested folders in Google Drive.

        :param folder_path: The full folder path (e.g., "DocsToProcess/DocsOrig").
        :return: The final folder ID where the file should be uploaded.
        """
        parent_id = None  # Start at root
        folders = folder_path.split("/")

        for folder in folders:
            # Check if folder exists under the parent
            query = f"title = '{folder}' and mimeType = 'application/vnd.google-apps.folder' and trashed=false"
            if parent_id:
                query += f" and '{parent_id}' in parents"

            existing_folders = self.drive.ListFile({'q': query}).GetList()

            if existing_folders:
                folder_id = existing_folders[0]['id']  # Use existing folder
                logging.info(f"Found existing folder: '{folder}' with ID: {folder_id}")
            else:
                # Create new folder
                folder_metadata = {
                    'title': folder,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [{'id': parent_id}] if parent_id else []
                }
                folder_obj = self.drive.CreateFile(folder_metadata)
                folder_obj.Upload()
                folder_id = folder_obj['id']
                logging.info(f"Created new folder: '{folder}' with ID: {folder_id}")

            parent_id = folder_id  # Move to next level

        return parent_id
    
    def read_csv_from_drive(self, file_name, folder_id):
        """
        Reads a CSV file from a specific Google Drive folder (including Shared Drives) and loads it into a pandas DataFrame.
        :param file_name: The name of the CSV file to read.
        :param folder_id: The ID of the folder containing the file.
        :return: A pandas DataFrame containing the file data, or None if an error occurs.
        """
        try:
            # First, list all files in the folder
            file_list = self.list_files_in_shared_drive(folder_id)
            
            if not file_list:
                logging.error(f"No files found in folder {folder_id}.")
                return None

            logging.info(f"Listing files with details: {file_list}")

            # Filter the files to find the one that matches the name and mimeType (CSV)
            csv_file = None
            for file in file_list:
                logging.info(f"Inspecting file: {file['title']} (MimeType: {file['mimeType']})")
                if file['title'] == file_name and file['mimeType'] in ['text/csv', 'application/vnd.ms-excel']:
                    csv_file = file
                    break
            
            if not csv_file:
                logging.error(f"Error: File '{file_name}' not found in folder ID '{folder_id}'.")
                return None

            logging.info(f"Found file: {csv_file['title']} (ID: {csv_file['id']})")

            # Read the file content and load into pandas
            csv_content = csv_file.GetContentString()
            df = pd.read_csv(io.StringIO(csv_content))

            logging.info(f"File '{file_name}' successfully read into a DataFrame.")
            return df

        except Exception as e:
            logging.error(f"Error reading CSV file '{file_name}': {e}")
            return None
    
    def list_files_in_shared_drive(self, folder_id):
        try:
            query = f"'{folder_id}' in parents"
            file_list = self.drive.ListFile({
                'q': query,
                'supportsAllDrives': True,
                'includeItemsFromAllDrives': True
            }).GetList()

            logging.info(f"Files in folder {folder_id}: {[file['title'] for file in file_list]}")
            return file_list

        except Exception as e:
            logging.error(f"Error listing files in folder '{folder_id}': {e}")
            return None
    
    def upload_csv_from_df(self, df: pd.DataFrame, file_name: str, folder_id: str):
        """
        Uploads a CSV file generated from a pandas DataFrame to Google Drive,
        enforcing overwrite if a file with the same name already exists.

        :param df: The pandas DataFrame to be saved as CSV.
        :param file_name: The destination file name in Drive (e.g., "data.csv").
        :param folder_id: The ID of the destination folder in Google Drive.
        :return: The uploaded file's ID.
        """
        try:
            # Create a temporary CSV file to store the DataFrame
            with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp_file:
                temp_file_path = tmp_file.name

            # Write the DataFrame to the temporary CSV file
            df.to_csv(temp_file_path, index=False)

            # Check if the file already exists in the destination folder
            query = f"title = '{file_name}' and mimeType != 'application/vnd.google-apps.folder' and '{folder_id}' in parents"
            existing_files = self.drive.ListFile({'q': query}).GetList()

            # Delete any existing files with the same name (overwrite enforcement)
            for f in existing_files:
                logging.info(f"Deleting existing file: {f['title']}")
                f.Delete()

            # Prepare file metadata and upload the new CSV file
            file_metadata = {'title': file_name, 'parents': [{'id': folder_id}]}
            file = self.drive.CreateFile(file_metadata)
            file.SetContentFile(temp_file_path)
            file.Upload()

            logging.info(f"CSV file '{file_name}' uploaded successfully to folder ID '{folder_id}', replacing any previous versions.")

            # Clean up the temporary file
            #os.remove(temp_file_path)

            return file['id']

        except Exception as e:
            logging.error(f"Error uploading CSV file '{file_name}': {e}")
            raise
    
    def update_csv_from_df(self, df: pd.DataFrame, file_name: str, folder_id: str):
        """
        Uploads a CSV file generated from a pandas DataFrame to Google Drive,
        updating the file if it already exists (preserving metadata) or creating a new one.
        
        :param df: The pandas DataFrame to be saved as CSV.
        :param file_name: The destination file name in Drive (e.g., "data.csv").
        :param folder_id: The ID of the destination folder in Google Drive.
        :return: The uploaded file's ID.
        """
        try:
            # Create a temporary CSV file using mkstemp to avoid Windows file-locking issues.
            fd, temp_file_path = tempfile.mkstemp(suffix='.csv')
            os.close(fd)  # Close the file descriptor immediately.
            
            # Write the DataFrame to the temporary CSV file.
            df.to_csv(temp_file_path, index=False)
            
            # Build the query to check if the file already exists in the destination folder.
            query = (
                f"title = '{file_name}' and mimeType != 'application/vnd.google-apps.folder' "
                f"and '{folder_id}' in parents"
            )
            existing_files = self.drive.ListFile({'q': query}).GetList()
            
            if existing_files:
                # If the file exists, update its content.
                file = existing_files[0]
                logging.info(f"Updating existing file: {file['title']}")
                file.SetContentFile(temp_file_path)
                file.Upload()
                
                # Optionally, if multiple files exist with the same name, remove extras.
                if len(existing_files) > 1:
                    for duplicate in existing_files[1:]:
                        logging.info(f"Deleting duplicate file: {duplicate['title']}")
                        duplicate.Delete()
            else:
                # If the file does not exist, create a new file.
                file_metadata = {'title': file_name, 'parents': [{'id': folder_id}]}
                file = self.drive.CreateFile(file_metadata)
                file.SetContentFile(temp_file_path)
                file.Upload()
            
            logging.info(
                f"CSV file '{file_name}' uploaded successfully to folder ID '{folder_id}'."
            )
            
            # Clean up the temporary file.
            #os.remove(temp_file_path)
            
            return file['id']

        except Exception as e:
            logging.error(f"Error uploading CSV file '{file_name}': {e}")
            raise
        
    def update_csv_from_df_retry(self, df: pd.DataFrame, file_name: str, folder_id: str):
        """
        Uploads a CSV file generated from a pandas DataFrame to Google Drive,
        updating the file if it already exists (preserving metadata) or creating a new one.
        Implements a retry mechanism to handle potential update conflicts.

        :param df: The pandas DataFrame to be saved as CSV.
        :param file_name: The destination file name in Drive (e.g., "data.csv").
        :param folder_id: The ID of the destination folder in Google Drive.
        :return: The uploaded file's ID.
        """
        try:
            # Create a temporary CSV file using mkstemp to avoid Windows file-locking issues.
            fd, temp_file_path = tempfile.mkstemp(suffix='.csv')
            os.close(fd)  # Close the file descriptor immediately.

            # Write the DataFrame to the temporary CSV file.
            df.to_csv(temp_file_path, index=False)

            # Build the query to check if the file already exists in the destination folder.
            query = (
                f"title = '{file_name}' and mimeType != 'application/vnd.google-apps.folder' "
                f"and '{folder_id}' in parents"
            )
            existing_files = self.drive.ListFile({'q': query}).GetList()

            max_retries = 3
            if existing_files:
                # If the file exists, update its content.
                file = existing_files[0]
                logging.info(f"Updating existing file: {file['title']}")

                retry_count = 0
                while retry_count < max_retries:
                    try:
                        file.SetContentFile(temp_file_path)
                        file.Upload()
                        break  # Upload succeeded, exit the retry loop.
                    except Exception as e:
                        # Check for conflict or transient error.
                        if "conflict" in str(e).lower():
                            retry_count += 1
                            wait_time = 2 ** retry_count
                            logging.warning(f"Conflict detected. Retrying in {wait_time} seconds... (attempt {retry_count})")
                            time.sleep(wait_time)
                            file.FetchMetadata()  # Refresh metadata before retrying.
                            continue
                        else:
                            raise
                else:
                    raise Exception("Max retries reached. File update failed due to concurrent modifications.")

                # Optionally, if multiple files exist with the same name, remove extras.
                if len(existing_files) > 1:
                    for duplicate in existing_files[1:]:
                        logging.info(f"Deleting duplicate file: {duplicate['title']}")
                        duplicate.Delete()
            else:
                # If the file does not exist, create a new file.
                file_metadata = {'title': file_name, 'parents': [{'id': folder_id}]}
                file = self.drive.CreateFile(file_metadata)
                file.SetContentFile(temp_file_path)
                file.Upload()

            logging.info(f"CSV file '{file_name}' uploaded successfully to folder ID '{folder_id}'.")
            #os.remove(temp_file_path)
            return file['id']

        except Exception as e:
            logging.error(f"Error uploading CSV file '{file_name}': {e}")
            raise
    
    def get_folder_id(self, folder_path):
        """
        Recursively finds or creates the folder structure in Google Drive.

        :param folder_path: The folder path (e.g., "DocsToProcess/Reports").
        :return: The Google Drive folder ID.
        """
        parent_id = "root"  # Start from root folder
        for folder in folder_path.split('/'):
            query = f"title = '{folder}' and mimeType = 'application/vnd.google-apps.folder' and '{parent_id}' in parents"
            folder_list = self.drive.ListFile({'q': query}).GetList()

            if folder_list:
                parent_id = folder_list[0]['id']  # Folder exists, get its ID
            else:
                # Folder does not exist, create it
                folder_metadata = {
                    'title': folder,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [{'id': parent_id}]
                }
                folder = self.drive.CreateFile(folder_metadata)
                folder.Upload()
                parent_id = folder['id']  # Get the newly created folder ID

        return parent_id
    
    def upload_text_file(self, text_content, file_name, folder_id=None):
        """
        Uploads text content as a file to Google Drive, enforcing overwrite if a file with the same name exists.
        
        :param text_content: The text content to upload.
        :param file_name: The destination file name in Drive (e.g., "file.txt").
        :param folder_id: The ID of the destination folder in Google Drive (if None, uses default).
        :return: The uploaded file's ID.
        """
        folder_id = folder_id or self.default_folder_id

        try:
            # Build query to check for existing file
            query = f"title = '{file_name}' and mimeType != 'application/vnd.google-apps.folder'"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            existing_files = self.drive.ListFile({'q': query}).GetList()

            # Delete existing files with the same name
            for f in existing_files:
                logging.info(f"Deleting existing file: {f['title']}")
                f.Delete()

            # Prepare file metadata including folder info if available
            file_metadata = {'title': file_name}
            if folder_id:
                file_metadata['parents'] = [{'id': folder_id}]

            # Create and upload the file
            file = self.drive.CreateFile(file_metadata)
            file.SetContentString(text_content)
            file.Upload()

            logging.info(f"File '{file_name}' uploaded successfully to folder ID '{folder_id}', replacing any previous versions.")
            return file['id']

        except Exception as e:
            logging.error(f"Error uploading file '{file_name}': {e}")
            return None

    def extract_text_and_upload(self, pdf_path, file_name, folder_id=None, y_tolerance=5):
        """
        Extracts text from a PDF file and uploads it to Google Drive without saving locally.
        Enforces overwrite if a file with the same name exists.

        :param pdf_path: Path to the input PDF file.
        :param file_name: Name of the output file in Google Drive (e.g., "output.txt").
        :param folder_id: The destination folder ID (if None, uses default).
        :param y_tolerance: Y-axis tolerance for grouping text lines.
        :return: The uploaded file's ID (or None if failed).
        """
        folder_id = folder_id or self.default_folder_id

        try:
            doc = pymupdf.open(pdf_path)
            extracted_text = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text_blocks = page.get_text("blocks")

                if not text_blocks:
                    continue  # Skip empty pages

                # Convert to structured array: (x0, y0, x1, y1, text)
                block_data = [(b[0], b[1], b[2], b[3], b[4]) for b in text_blocks]
                block_data = sorted(block_data, key=lambda b: b[1])  # Sort by Y initially

                # Extract x-coordinates for clustering
                x_positions = np.array([b[0] for b in block_data]).reshape(-1, 1)

                # Perform hierarchical clustering to identify columns
                Z = linkage(x_positions, method='ward')
                column_labels = fcluster(Z, t=50, criterion='distance')  # Adjust distance threshold as needed

                # Group blocks by detected column
                column_dict = {}
                for label, block in zip(column_labels, block_data):
                    if label not in column_dict:
                        column_dict[label] = []
                    column_dict[label].append(block)

                # Sort blocks within each column (top to bottom)
                for col in column_dict:
                    column_dict[col] = sorted(column_dict[col], key=lambda b: b[1])

                # Order columns from left to right (based on mean x-coordinates)
                sorted_columns = sorted(column_dict.keys(), key=lambda c: np.mean([b[0] for b in column_dict[c]]))

                # Flatten text output in proper order
                ordered_text = []
                for col in sorted_columns:
                    ordered_text.extend([b[4] for b in column_dict[col]])

                extracted_text.append(f"--- Page {page_num + 1} ---\n" + "\n".join(ordered_text))

            # Merge all pages' text into a single string
            text_data = "\n\n".join(extracted_text)

            # Manually create file metadata and upload extracted text
            file_metadata = {'title': file_name}
            if folder_id:
                file_metadata['parents'] = [{'id': folder_id}]

            # Check if file already exists
            query = f"title = '{file_name}' and mimeType != 'application/vnd.google-apps.folder'"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            existing_files = self.drive.ListFile({'q': query}).GetList()

            # Delete existing files with the same name
            for f in existing_files:
                logging.info(f"Deleting existing file: {f['title']}")
                f.Delete()

            # Create and upload the file
            file = self.drive.CreateFile(file_metadata)
            file.SetContentString(text_data)
            file.Upload()

            logging.info(f"File '{file_name}' uploaded successfully to folder ID '{folder_id}', replacing any previous versions.")
            return file['id']

        except Exception as e:
            logging.error(f"Error extracting text from '{pdf_path}': {e}")
            raise


def is_valid_email(email: str) -> bool:
    """
    Validates if the provided string is a valid email address.
    :param email: The email address to validate.
    :return: True if valid, False otherwise.
    """
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return bool(re.match(email_regex, email))

def is_valid_password(password: str, real: str) -> bool:
    """
    Validates possword.
    """
    return password == real

def update_observation(df: pd.DataFrame, file_name: str, email: str) -> tuple[str, pd.DataFrame]:
    # Check if email exists in the dataframe
    existing_record = df[df['email'] == email]

    if not existing_record.empty and existing_record['status'].iloc[0] == "Ready":
        # If the email exists and status is 'Listo', deny any changes
        return "Negado: Servicio ya provisto.", df
    
    if not existing_record.empty:
        # If the email exists and status is not 'Listo', overwrite with 'Process'
        df.loc[df['email'] == email, ['file_name', 'status']] = file_name, "Process"
        return "Aceptado: Sobre-Escritura.", df

    # If email doesn't exist, create a new observation with 'Process'
    new_data = pd.DataFrame([[file_name, email, "Process"]], columns=['file_name', 'email', 'status'])
    df = pd.concat([df, new_data], ignore_index=True)
    return "Aceptado: Nuevo Registro.", df

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

def send_email(sender_email, sender_password, recipient_email, subject, body, attachment_path=None):
    """
    Sends an email with an optional attachment via Gmail SMTP.

    Parameters:
    sender_email (str): Sender's Gmail address.
    sender_password (str): App Password for the sender's Gmail account.
    recipient_email (str): Recipient's email address.
    subject (str): Email subject.
    body (str): Email body content.
    attachment_path (str, optional): Path to the file to attach. Defaults to None.

    Returns:
    bool: True if email sent successfully, False otherwise.
    """

    try:
        # 📨 Create Email Object
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Subject"] = subject

        # 📌 Attach Email Body
        msg.attach(MIMEText(body, "plain"))

        # 📎 Attach File if Provided
        if attachment_path and os.path.exists(attachment_path):
            filename = os.path.basename(attachment_path)
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={filename}")
                msg.attach(part)
        elif attachment_path:
            print(f"⚠️ File not found: {attachment_path}")
            return False

        # 📤 Send Email
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()  # Secure connection
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()

        print("✅ Email sent successfully.")
        return True

    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False
