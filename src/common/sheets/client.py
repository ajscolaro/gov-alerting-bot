"""Google Sheets client for watchlist synchronization."""

import os
from typing import Dict, List, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleSheetsClient:
    """Client for interacting with Google Sheets API."""

    def __init__(self, credentials_path: str, spreadsheet_id: str):
        """Initialize the Google Sheets client.
        
        Args:
            credentials_path: Path to the service account credentials JSON file
            spreadsheet_id: ID of the Google Spreadsheet to access
        """
        self.spreadsheet_id = spreadsheet_id
        self.service = self._build_service(credentials_path)

    def _build_service(self, credentials_path: str):
        """Build the Google Sheets service.
        
        Args:
            credentials_path: Path to the service account credentials JSON file
            
        Returns:
            Google Sheets API service object
        """
        try:
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
            )
            return build('sheets', 'v4', credentials=credentials)
        except Exception as e:
            raise RuntimeError(f"Failed to build Google Sheets service: {str(e)}")

    def get_sheet_data(self, sheet_name: str, range_name: str = "A1:Z1000") -> List[List[str]]:
        """Get data from a specific sheet.
        
        Args:
            sheet_name: Name of the sheet to read
            range_name: Range of cells to read (default: A1:Z1000)
            
        Returns:
            List of rows, where each row is a list of cell values
            
        Raises:
            HttpError: If the API request fails
        """
        try:
            range_spec = f"{sheet_name}!{range_name}"
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_spec
            ).execute()
            return result.get('values', [])
        except HttpError as e:
            raise RuntimeError(f"Failed to get sheet data: {str(e)}")

    def get_all_sheets(self) -> List[str]:
        """Get list of all sheets in the spreadsheet.
        
        Returns:
            List of sheet names
        """
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            return [sheet['properties']['title'] for sheet in spreadsheet['sheets']]
        except HttpError as e:
            raise RuntimeError(f"Failed to get sheet list: {str(e)}") 