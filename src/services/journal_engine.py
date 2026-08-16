import json
import io
import os
import re
import uuid
import datetime
import pandas as pd
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request as GoogleAuthRequest
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from ..config import get_user_keys, update_user_keys

# Drive scope for application-specific data
SCOPES = ['https://www.googleapis.com/auth/drive.appdata']

class JournalEngine:
    @staticmethod
    def get_flow():
        # Only relax oauthlib's HTTPS enforcement when the configured redirect
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI", "")
        if redirect_uri.startswith("http://"):
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
        else:
            os.environ.pop('OAUTHLIB_INSECURE_TRANSPORT', None)
        return Flow.from_client_config(
            client_config={
                "web": {
                    "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
                    "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=SCOPES,
            redirect_uri=os.environ.get("GOOGLE_REDIRECT_URI")
        )

    @staticmethod
    def get_creds(uid):
        # Load and parse user credentials from database
        user_data = get_user_keys(uid)
        token_json = user_data.get("google_token_json")
        if not token_json: return None
        try:
            creds = Credentials.from_authorized_user_info(json.loads(token_json))
        except Exception as e:
            print(f"⚠️ Token Load Error: {e}")
            return None

        # The stored token snapshot is only ever written once
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(GoogleAuthRequest())
                update_user_keys(uid, {"google_token_json": creds.to_json()})
            except Exception as e:
                print(f"⚠️ Token Refresh Error: {e}")
                return None

        return creds

    @staticmethod
    def get_drive_service(creds):
        # Initialize Google Drive API client
        return build('drive', 'v3', credentials=creds)

    @staticmethod
    def load_journal(service, file_id):
        # Download journal.json from Drive and parse to list
        try:
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            content = fh.getvalue().decode('utf-8')
            return json.loads(content) if content else []
        except HttpError as e:
            if e.resp.status == 404:
                # Cached file_id points at a file that no longer exists
                raise
            print(f"⚠️ Journal Load Error: {e}")
            return []
        except Exception as e:
            print(f"⚠️ Journal Load Error: {e}")
            return []

    @staticmethod
    def save_to_drive(service, file_id, journal_data):
        # Upload current journal state to Drive
        media = MediaIoBaseUpload(
            io.BytesIO(json.dumps(journal_data).encode('utf-8')), 
            mimetype='application/json',
            resumable=True
        )
        service.files().update(fileId=file_id, media_body=media).execute()

    @staticmethod
    def initialize_journal(service, uid=None):
        # Find existing journal or create a new one in hidden app data folder.
        if uid:
            cached_id = get_user_keys(uid).get("journal_drive_file_id")
            if cached_id:
                return cached_id

        try:
            response = service.files().list(
                q="name='journal.json' and 'appDataFolder' in parents",
                spaces='appDataFolder',
                fields='files(id, name)',
                pageSize=1
            ).execute()
            
            files = response.get('files', [])
            if files:
                file_id = files[0]['id']
            else:
                file_metadata = {'name': 'journal.json', 'parents': ['appDataFolder']}
                media = MediaIoBaseUpload(
                    io.BytesIO(json.dumps([]).encode('utf-8')), 
                    mimetype='application/json',
                    resumable=True
                )
                file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                file_id = file.get('id')

            if uid and file_id:
                update_user_keys(uid, {"journal_drive_file_id": file_id})
            return file_id
        except Exception as e:
            print(f"⚠️ Journal Init Error: {e}")
            raise e

    @classmethod
    def save_trade(cls, service, file_id, trade_data):
        # Add new trade with ID/date tags or update existing record
        journal = cls.load_journal(service, file_id)
        
        if 'trade_date' in trade_data:
            try:
                dt = datetime.datetime.strptime(trade_data['trade_date'], "%Y-%m-%d")
                trade_data['week'] = dt.strftime("%Y-W%W")
                trade_data['month'] = dt.strftime("%Y-%m")
            except ValueError:
                pass

        trade_id = trade_data.get('id')
        updated = False
        
        if not trade_id:
            trade_data['id'] = str(uuid.uuid4())
            journal.append(trade_data)
        else:
            for i, existing in enumerate(journal):
                if existing.get('id') == trade_id:
                    journal[i] = trade_data
                    updated = True
                    break
            if not updated:
                journal.append(trade_data)
                
        cls.save_to_drive(service, file_id, journal)
        return True

    @classmethod
    def delete_trade(cls, service, file_id, trade_id):
        # Remove trade by ID and sync with Drive
        journal = cls.load_journal(service, file_id)
        
        initial_len = len(journal)
        new_journal = [t for t in journal if str(t.get('id')) != str(trade_id)]
        
        if len(new_journal) < initial_len:
            cls.save_to_drive(service, file_id, new_journal)
            return True
        return False

    @staticmethod
    def parse_pnl(pnl_str):
        # Clean PnL string and convert to float
        try:
            clean = re.sub(r'[^\d\.-]', '', str(pnl_str))
            return float(clean) if clean else 0.0
        except: return 0.0

    @classmethod
    def calculate_stats(cls, journal_data):
        # Compute winrate, best trade, and dominant bias
        if not journal_data: return {"winrate": "0%", "best_trade": "--", "bias": "Neutral"}
        
        wins = [t for t in journal_data if cls.parse_pnl(t.get('pnl', 0)) > 0]
        total = len(journal_data)
        winrate = (len(wins) / total) * 100 if total > 0 else 0
        
        best_trade = max(journal_data, key=lambda x: cls.parse_pnl(x.get('pnl', 0)), default={})
        
        biases = []
        for t in journal_data:
            if t.get('bias'): 
                biases.append(t.get('bias'))
            elif 'rules_followed' in t:
                biases.append("Disciplined" if str(t['rules_followed']) == "true" else "Mistake")
                
        main_bias = max(set(biases), key=biases.count) if biases else "Neutral"

        return {
            "winrate": f"{winrate:.0f}%",
            "best_trade": best_trade.get('ticker', '--'),
            "bias": main_bias
        }