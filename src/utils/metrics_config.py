"""
メトリクス設定管理ユーティリティ

このモジュールは、スプレッドシートからメトリクス設定を読み込み、
Google Ads APIクエリのためのパラメータを管理します。
"""

from typing import Dict, List, Any, Tuple
import pandas as pd
from src.utils.environment import EnvironmentUtils as env
from src.utils.spreadsheet import SpreadsheetUtils


class MetricsConfigUtils:
    """
    メトリクス設定を管理するユーティリティクラス
    
    スプレッドシートからメトリクス設定を読み込み、Google Ads APIクエリに
    必要なパラメータを提供します。
    """
    
    # クラス変数としてキャッシュを保持
    _metrics_df_cache = None
    
    @classmethod
    def get_metrics_config(cls) -> pd.DataFrame:
        """
        スプレッドシートからメトリクス設定を読み込む
        
        Returns:
            pd.DataFrame: メトリクス設定のDataFrame
            
        Raises:
            Exception: スプレッドシートの読み取りに失敗した場合
        """
        # キャッシュがあればそれを返す
        if cls._metrics_df_cache is not None:
            return cls._metrics_df_cache
            
        try:
            # 設定を読み込む
            spreadsheet_id = env.get_config_value("SPREADSHEET", "spreadsheet_id")
            metrics_sheet_name = env.get_config_value("SPREADSHEET", "metrics_sheet_name")
            
            # スプレッドシートからメトリクス設定を読み込む
            metrics_df = SpreadsheetUtils.read_as_dataframe(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{metrics_sheet_name}!A1:E100"  # 十分な範囲を指定（E列まで）
            )
            
            print(f"メトリクス設定を読み込みました: {len(metrics_df)} 行")
            print(f"カラム: {metrics_df.columns.tolist()}")
            print(f"最初の行: {metrics_df.iloc[0].to_dict()}")
            
            # キャッシュに保存
            cls._metrics_df_cache = metrics_df
            
            return metrics_df
            
        except Exception as e:
            print(f"メトリクス設定の読み込みに失敗しました: {str(e)}")
            raise
    
    @classmethod
    def get_active_metrics(cls) -> List[str]:
        """
        アクティブなメトリクス項目のリストを取得
        
        Returns:
            List[str]: アクティブなメトリクス項目のリスト
        """
        metrics_df = cls.get_metrics_config()
        
        # activeがTRUEで、metricsカラムが空でない行をフィルタリング
        active_metrics = metrics_df[
            (metrics_df['active'] == True) | 
            (metrics_df['active'] == 'TRUE') |
            (metrics_df['active'] == 'True')
        ]
        
        # メトリクス名のみを抽出（impressions, clicks, cost_micros など）
        metrics_list = active_metrics[
            ~active_metrics['metrics'].isin(['campaign_status', 'period_days', 'limit'])
        ]['metrics'].tolist()
        
        return metrics_list
    
    @classmethod
    def get_query_parameters(cls) -> Dict[str, Any]:
        """
        クエリパラメータを取得
        
        Returns:
            Dict[str, Any]: クエリパラメータの辞書
        """
        metrics_df = cls.get_metrics_config()
        
        # activeがTRUEの行をフィルタリング
        active_params = metrics_df[
            (metrics_df['active'] == True) | 
            (metrics_df['active'] == 'TRUE') |
            (metrics_df['active'] == 'True')
        ]
        
        # パラメータを辞書に変換
        params = {}
        
        # campaign_status, period_days, limitのパラメータを取得
        for param in ['campaign_status', 'period_days', 'limit']:
            param_row = active_params[active_params['metrics'] == param]
            if not param_row.empty and not pd.isna(param_row['parameter'].values[0]):
                # 数値に変換可能なパラメータは数値に変換
                if param in ['period_days', 'limit']:
                    params[param] = int(param_row['parameter'].values[0])
                else:
                    params[param] = param_row['parameter'].values[0]
        
        # デフォルト値の設定
        if 'campaign_status' not in params:
            params['campaign_status'] = 'ENABLED'
        if 'period_days' not in params:
            params['period_days'] = 30
        if 'limit' not in params:
            params['limit'] = 100
            
        return params
    
    @classmethod
    def build_query(cls) -> Tuple[str, Dict[str, Any]]:
        """
        Google Ads APIクエリを構築
        
        Returns:
            Tuple[str, Dict[str, Any]]: クエリ文字列とパラメータの辞書
        """
        # アクティブなメトリクスとパラメータを取得
        metrics_list = cls.get_active_metrics()
        params = cls.get_query_parameters()
        
        # 基本的なディメンション（固定）
        dimensions = [
            "campaign.id",
            "campaign.name",
            "campaign.status",
            "campaign.advertising_channel_type"
        ]
        
        # メトリクスリストを文字列に変換
        metrics_str = ", ".join([f"metrics.{metric}" for metric in metrics_list])
        dimensions_str = ", ".join(dimensions)
        
        # クエリの構築
        query = f"""
            SELECT
                {dimensions_str},
                {metrics_str}
            FROM campaign
            WHERE 
                segments.date BETWEEN '{{start_date}}' AND '{{end_date}}'
                AND campaign.status = '{params['campaign_status']}'
                AND metrics.impressions > 0
            ORDER BY metrics.impressions DESC
            LIMIT {params['limit']}
        """
        
        return query, params
    
    @classmethod
    def get_active_metrics_list(cls) -> List[str]:
        """
        アクティブなメトリクスのリストを取得する
        APIクエリに使用するフィールドのみを返す（計算フィールドは除外）
        
        Returns:
            List[str]: アクティブなメトリクスのリスト（APIクエリ用）
        """
        # メトリクス設定を取得
        metrics_df = cls.get_metrics_config()
        
        # カラム名を確認
        print(f"メトリクス設定のカラム: {metrics_df.columns.tolist()}")
        
        # アクティブカラムの名前を確認（大文字小文字を区別せず）
        active_column = None
        for col in metrics_df.columns:
            if col.lower() == 'active':
                active_column = col
                break
        
        if not active_column:
            print("警告: 'active'カラムが見つかりません。すべてのメトリクスをアクティブとして扱います。")
            active_metrics = metrics_df
        else:
            # アクティブなメトリクスをフィルタリング
            active_metrics = metrics_df[
                (metrics_df[active_column] == True) | 
                (metrics_df[active_column] == 'TRUE') |
                (metrics_df[active_column] == 'True')
            ]
        
        # 特定のフィールドと計算フィールドを除外
        excluded_fields = ['campaign_status', 'period_days', 'limit']
        
        # calcカラムの名前を確認
        calc_column = None
        for col in metrics_df.columns:
            if col.lower() == 'calc':
                calc_column = col
                break
        
        # APIから取得するメトリクスのみをフィルタリング
        if calc_column:
            api_metrics = active_metrics[
                (~active_metrics['metrics'].isin(excluded_fields)) & 
                (active_metrics[calc_column].isna() | (active_metrics[calc_column] == ''))
            ]['metrics'].tolist()
        else:
            # calcカラムがない場合は、除外フィールド以外のすべてのメトリクスを使用
            api_metrics = active_metrics[
                ~active_metrics['metrics'].isin(excluded_fields)
            ]['metrics'].tolist()
        
        print(f"APIから取得するメトリクス: {api_metrics}")
        return api_metrics
    
    @classmethod
    def get_calculated_metrics(cls) -> Dict[str, Dict[str, Any]]:
        """
        計算フィールドの情報を取得する
        
        Returns:
            Dict[str, Dict[str, Any]]: 計算フィールドの情報
                {
                    'metric_name': {
                        'name': '日本語名',
                        'calc': '計算式'
                    }
                }
        """
        # メトリクス設定を取得
        metrics_df = cls.get_metrics_config()
        
        # カラム名を確認
        active_column = None
        calc_column = None
        
        for col in metrics_df.columns:
            if col.lower() == 'active':
                active_column = col
            elif col.lower() == 'calc':
                calc_column = col
        
        # calcカラムがない場合は空の辞書を返す
        if not calc_column:
            print("警告: 'calc'カラムが見つかりません。計算フィールドはありません。")
            return {}
        
        # アクティブな計算フィールドをフィルタリング
        if active_column:
            calc_metrics = metrics_df[
                ((metrics_df[active_column] == True) | 
                 (metrics_df[active_column] == 'TRUE') |
                 (metrics_df[active_column] == 'True')) &
                (metrics_df[calc_column].notna()) & 
                (metrics_df[calc_column] != '')
            ]
        else:
            # activeカラムがない場合は、すべての計算フィールドを使用
            calc_metrics = metrics_df[
                (metrics_df[calc_column].notna()) & 
                (metrics_df[calc_column] != '')
            ]
        
        # 計算フィールドの情報を辞書に変換
        calc_metrics_dict = {}
        for _, row in calc_metrics.iterrows():
            calc_metrics_dict[row['metrics']] = {
                'name': row['name'],
                'calc': row[calc_column]
            }
        
        print(f"計算フィールド: {list(calc_metrics_dict.keys())}")
        return calc_metrics_dict
    
    @classmethod
    def get_period_days(cls) -> int:
        """
        取得期間の日数を取得する
        
        Returns:
            int: 取得期間の日数
        """
        # メトリクス設定を取得
        metrics_df = cls.get_metrics_config()
        
        # 'period_days' の行をフィルタリング
        period_days_row = metrics_df[metrics_df['metrics'] == 'period_days']
        
        if not period_days_row.empty:
            # 'parameter' カラムから日数を取得
            period_days = period_days_row['parameter'].values[0]
            try:
                return int(period_days)
            except ValueError:
                print(f"警告: 'period_days' の値が整数に変換できません: {period_days}")
                return 30  # デフォルト値
        else:
            print("警告: 'period_days' の設定が見つかりません。デフォルト値を使用します。")
            return 30  # デフォルト値
    
    @classmethod
    def get_limit(cls) -> int:
        """
        取得件数の上限を取得する
        
        Returns:
            int: 取得件数の上限
        """
        # メトリクス設定を取得
        metrics_df = cls.get_metrics_config()
        
        # 'limit' の行をフィルタリング
        limit_row = metrics_df[metrics_df['metrics'] == 'limit']
        
        if not limit_row.empty:
            # 'parameter' カラムから件数を取得
            limit = limit_row['parameter'].values[0]
            try:
                return int(limit)
            except ValueError:
                print(f"警告: 'limit' の値が整数に変換できません: {limit}")
                return 100  # デフォルト値
        else:
            print("警告: 'limit' の設定が見つかりません。デフォルト値を使用します。")
            return 100  # デフォルト値 

def calculate_average_cpc(cost_micros, clicks):
    try:
        if clicks > 0:
            return cost_micros / clicks
        else:
            return 0  # クリック数がゼロの場合は0を返す
    except ZeroDivisionError:
        return 0  # 例外が発生した場合も0を返す 