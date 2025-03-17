"""
Google スプレッドシート操作用ユーティリティ

このモジュールは、Google スプレッドシートへの接続、読み取り、書き込みなどの
操作を簡単に行うためのユーティリティ関数を提供します。
"""

import os
from typing import List, Dict, Any, Optional, Union
import pandas as pd
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

from src.utils.environment import EnvironmentUtils as env


class SpreadsheetUtils:
    """
    Google スプレッドシートを操作するためのユーティリティクラス
    
    このクラスは、スプレッドシートへの接続、データの読み取り、書き込みなどの
    基本的な操作を提供します。
    """
    
    # OAuth 2.0 スコープ
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    
    # サービスのキャッシュ
    _service_cache = None
    
    # 認証情報のキャッシュ
    _credentials_cache = None
    
    @classmethod
    def get_service(cls):
        """
        Google Sheets APIサービスを取得する
        
        Returns:
            Resource: Google Sheets APIサービス
        """
        # キャッシュがあればそれを返す
        if cls._service_cache is not None:
            return cls._service_cache
            
        # 認証情報を取得
        credentials = cls.get_credentials()
        
        # サービスを構築
        service = build('sheets', 'v4', credentials=credentials)
        
        # キャッシュに保存
        cls._service_cache = service
        
        return service
    
    @classmethod
    def get_credentials(cls) -> Credentials:
        """
        Google APIの認証情報を取得する
        
        環境設定に基づいて、適切な認証情報を取得します。
        サービスアカウントまたはOAuth2.0認証をサポートします。
        
        Returns:
            Credentials: Google API認証情報
        
        Raises:
            FileNotFoundError: 認証ファイルが見つからない場合
        """
        # キャッシュがあればそれを返す
        if cls._credentials_cache is not None:
            return cls._credentials_cache
            
        # 環境変数をロード
        env.load_env()
        
        # 認証方法の決定（デフォルトはサービスアカウント）
        auth_method = env.get_env_var("GOOGLE_AUTH_METHOD", "service_account")
        
        if auth_method == "service_account":
            # サービスアカウント認証
            try:
                # SERVICE_ACCOUNT_FILE環境変数からサービスアカウントファイルのパスを取得
                service_account_file = env.get_env_var("SERVICE_ACCOUNT_FILE")
                
                if not service_account_file:
                    raise ValueError("SERVICE_ACCOUNT_FILE 環境変数が設定されていません")
                
                # 相対パスの場合はプロジェクトルートからの絶対パスに変換
                if not os.path.isabs(service_account_file):
                    service_account_file = os.path.join(
                        env.get_project_root(), service_account_file
                    )
                
                if not os.path.exists(service_account_file):
                    raise FileNotFoundError(f"サービスアカウントファイルが見つかりません: {service_account_file}")
                
                print(f"サービスアカウント認証を使用します: {service_account_file}")
                credentials = Credentials.from_service_account_file(
                    service_account_file, scopes=cls.SCOPES
                )
                
                # キャッシュに保存
                cls._credentials_cache = credentials
                
                return credentials
            except Exception as e:
                print(f"サービスアカウント認証に失敗しました: {str(e)}")
                raise
        else:
            # OAuth認証
            credentials_path = os.path.join(env.get_project_root(), "config", "credentials.json")
            token_path = os.path.join(env.get_project_root(), "config", "token.pickle")
            
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(f"OAuth認証ファイルが見つかりません: {credentials_path}")
            
            credentials = None
            
            # トークンが既に存在する場合はそれを使用
            if os.path.exists(token_path):
                with open(token_path, 'rb') as token:
                    credentials = pickle.load(token)
            
            # 有効な認証情報がない場合、またはリフレッシュが必要な場合
            if not credentials or not credentials.valid:
                if credentials and credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        credentials_path, cls.SCOPES
                    )
                    credentials = flow.run_local_server(port=0)
                
                # トークンを保存
                with open(token_path, 'wb') as token:
                    pickle.dump(credentials, token)
            
            # キャッシュに保存
            cls._credentials_cache = credentials
            
            return credentials
    
    @classmethod
    def read_range(cls, spreadsheet_id: str, range_name: str) -> List[List[Any]]:
        """
        スプレッドシートの指定範囲を読み取る
        
        Args:
            spreadsheet_id (str): スプレッドシートID
            range_name (str): 読み取る範囲（例: 'Sheet1!A1:D10'）
            
        Returns:
            List[List[Any]]: 読み取ったデータの2次元配列
            
        Raises:
            Exception: API呼び出しに失敗した場合
        """
        try:
            service = cls.get_service()
            sheet = service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            return values
        except Exception as e:
            print(f"スプレッドシートの読み取りに失敗しました: {str(e)}")
            raise
    
    @classmethod
    def write_range(cls, spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> Dict[str, Any]:
        """
        スプレッドシートの指定範囲にデータを書き込む
        
        Args:
            spreadsheet_id (str): スプレッドシートID
            range_name (str): 書き込む範囲（例: 'Sheet1!A1'）
            values (List[List[Any]]): 書き込むデータの2次元配列
            
        Returns:
            Dict[str, Any]: API応答
            
        Raises:
            Exception: API呼び出しに失敗した場合
        """
        try:
            service = cls.get_service()
            body = {
                'values': values
            }
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            print(f"{result.get('updatedCells')} セルを更新しました。")
            return result
        except Exception as e:
            print(f"スプレッドシートの書き込みに失敗しました: {str(e)}")
            raise
    
    @classmethod
    def append_values(cls, spreadsheet_id: str, range_name: str, values: List[List[Any]]) -> Dict[str, Any]:
        """
        スプレッドシートの指定範囲にデータを追加する
        
        Args:
            spreadsheet_id (str): スプレッドシートID
            range_name (str): 追加する範囲（例: 'Sheet1!A1'）
            values (List[List[Any]]): 追加するデータの2次元配列
            
        Returns:
            Dict[str, Any]: API応答
            
        Raises:
            Exception: API呼び出しに失敗した場合
        """
        try:
            service = cls.get_service()
            body = {
                'values': values
            }
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            
            print(f"{result.get('updates').get('updatedRows')} 行を追加しました。")
            return result
        except Exception as e:
            print(f"スプレッドシートへのデータ追加に失敗しました: {str(e)}")
            raise
    
    @classmethod
    def read_as_dataframe(cls, spreadsheet_id: str, range_name: str, header: bool = True) -> pd.DataFrame:
        """
        スプレッドシートの指定範囲をPandas DataFrameとして読み取る
        
        Args:
            spreadsheet_id (str): スプレッドシートID
            range_name (str): 読み取る範囲（例: 'Sheet1!A1:D10'）
            header (bool, optional): 1行目をヘッダーとして扱うかどうか。デフォルトはTrue
            
        Returns:
            pd.DataFrame: 読み取ったデータのDataFrame
            
        Raises:
            Exception: API呼び出しに失敗した場合
        """
        values = cls.read_range(spreadsheet_id, range_name)
        
        if not values:
            return pd.DataFrame()
        
        if header:
            # 1行目をヘッダーとして使用
            headers = values[0]
            data = values[1:] if len(values) > 1 else []
            return pd.DataFrame(data, columns=headers)
        else:
            # ヘッダーなし
            return pd.DataFrame(values)
    
    @classmethod
    def write_dataframe(cls, df: pd.DataFrame, spreadsheet_id: str, range_name: str, include_header: bool = True) -> Dict[str, Any]:
        """
        DataFrameをスプレッドシートに書き込む
        
        Args:
            df (pd.DataFrame): 書き込むDataFrame
            spreadsheet_id (str): スプレッドシートID
            range_name (str): 書き込む範囲（例: 'Sheet1!A1'）
            include_header (bool, optional): ヘッダーを含めるかどうか。デフォルトはTrue
            
        Returns:
            Dict[str, Any]: API応答
            
        Raises:
            Exception: API呼び出しに失敗した場合
        """
        # DataFrameを2次元配列に変換
        values = []
        
        if include_header:
            values.append(df.columns.tolist())
        
        for _, row in df.iterrows():
            values.append(row.tolist())
        
        return cls.write_range(spreadsheet_id, range_name, values)
    
    @classmethod
    def append_dataframe(cls, df: pd.DataFrame, spreadsheet_id: str, range_name: str, include_header: bool = False) -> Dict[str, Any]:
        """
        DataFrameをスプレッドシートに追加する
        
        Args:
            df (pd.DataFrame): 追加するDataFrame
            spreadsheet_id (str): スプレッドシートID
            range_name (str): 追加する範囲（例: 'Sheet1!A1'）
            include_header (bool, optional): ヘッダーを含めるかどうか。デフォルトはFalse
            
        Returns:
            Dict[str, Any]: API応答
            
        Raises:
            Exception: API呼び出しに失敗した場合
        """
        # DataFrameを2次元配列に変換
        values = []
        
        if include_header:
            values.append(df.columns.tolist())
        
        for _, row in df.iterrows():
            values.append(row.tolist())
        
        return cls.append_values(spreadsheet_id, range_name, values)
    
    @classmethod
    def create_sheet(cls, spreadsheet_id: str, sheet_name: str) -> Dict[str, Any]:
        """
        新しいシートを作成する
        
        Args:
            spreadsheet_id (str): スプレッドシートID
            sheet_name (str): 新しいシート名
            
        Returns:
            Dict[str, Any]: API応答
            
        Raises:
            Exception: API呼び出しに失敗した場合
        """
        try:
            service = cls.get_service()
            
            request = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]
            }
            
            result = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=request
            ).execute()
            
            print(f"新しいシート '{sheet_name}' を作成しました。")
            return result
        except Exception as e:
            print(f"シートの作成に失敗しました: {str(e)}")
            raise
    
    @classmethod
    def get_sheet_id(cls, spreadsheet_id: str, sheet_name: str) -> Optional[int]:
        """
        シート名からシートIDを取得する
        
        Args:
            spreadsheet_id (str): スプレッドシートID
            sheet_name (str): シート名
            
        Returns:
            Optional[int]: シートID（見つからない場合はNone）
            
        Raises:
            Exception: API呼び出しに失敗した場合
        """
        try:
            service = cls.get_service()
            spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
            
            for sheet in spreadsheet.get('sheets', []):
                if sheet.get('properties', {}).get('title') == sheet_name:
                    return sheet.get('properties', {}).get('sheetId')
            
            return None
        except Exception as e:
            print(f"シートIDの取得に失敗しました: {str(e)}")
            raise
    
    @staticmethod
    def write_dataframe_to_sheet(spreadsheet_id: str, range_name: str, dataframe: pd.DataFrame):
        """
        Pandas DataFrameをスプレッドシートに書き込む
        """
        # Google Sheets APIの認証情報を設定
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_file('config/boxwood-dynamo-384411-6dec80faabfc.json', scopes=SCOPES)
        
        # Google Sheets APIサービスを構築
        service = build('sheets', 'v4', credentials=creds)
        
        # DataFrameをリストに変換
        values = [dataframe.columns.tolist()] + dataframe.values.tolist()
        
        # スプレッドシートにデータを書き込む
        body = {
            'values': values
        }
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption='RAW', body=body).execute()
        
        print(f"{result.get('updatedCells')} cells updated.") 