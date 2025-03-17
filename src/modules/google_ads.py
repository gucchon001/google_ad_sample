"""
Google Ads API連携モジュール

このモジュールは、Google Ads APIを使用して広告データを取得し、
必要な形式に変換する機能を提供します。
"""

import datetime
import yaml
from pathlib import Path
from google.ads.googleads.client import GoogleAdsClient
from typing import List, Dict, Any

from src.utils.environment import EnvironmentUtils as env
from src.utils.metrics_config import MetricsConfigUtils


class GoogleAdsAPI:
    """
    Google Ads APIとの連携を行うクラス
    
    Google Ads APIを使用して広告データを取得し、必要な形式に変換します。
    """
    
    @staticmethod
    def create_google_ads_yaml():
        """
        Google Ads API用のYAMLファイルを作成する
        
        Returns:
            Path: 作成したYAMLファイルのパス
        """
        # プロジェクトルートからの正しいパスを指定
        yaml_path = env.get_project_root() / "config" / "google-ads.yaml"
        
        # すでに存在する場合は、そのパスを返す
        if yaml_path.exists():
            print(f"既存のYAMLファイルを使用します: {yaml_path}")
            return yaml_path
        
        # 環境変数をロード
        env.load_env()
        
        # 設定情報を環境変数から取得
        config = {
            "developer_token": env.get_env_var("developer_token"),
            "client_id": env.get_env_var("client_id"),
            "client_secret": env.get_env_var("client_secret"),
            "refresh_token": env.get_env_var("refresh_token"),
            "use_proto_plus": True
        }
        
        # login_customer_id が設定されている場合は追加
        login_customer_id = env.get_env_var("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
        if login_customer_id:
            config["login_customer_id"] = login_customer_id
        
        # ディレクトリが存在しない場合は作成
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        
        # YAMLファイルに書き込み
        with open(yaml_path, 'w') as f:
            yaml.dump(config, f)
        
        print(f"新しいYAMLファイルを作成しました: {yaml_path}")
        return yaml_path
    
    @staticmethod
    def get_field_mapping(metric: str) -> str:
        """
        メトリクス名をAPIクエリ用のフィールド名に変換する
        
        Args:
            metric (str): メトリクス名
            
        Returns:
            str: APIクエリ用のフィールド名
        """
        # メトリクス名とAPIフィールド名のマッピング
        field_mapping = {
            'impressions': 'metrics.impressions',
            'clicks': 'metrics.clicks',
            'cost_micros': 'metrics.cost_micros',
            'conversions': 'metrics.conversions',
            'ctr': 'metrics.ctr',
            'average_cpc': 'metrics.average_cpc',
            'search_top_impression_share': 'metrics.search_top_impression_share',
            # 必要に応じて他のメトリクスを追加
        }
        
        return field_mapping.get(metric, metric)
    
    @staticmethod
    def get_campaign_metrics(client_customer_id: str = None) -> List[Dict[str, Any]]:
        """
        Google Ads APIからキャンペーンメトリクスを取得する
        
        Args:
            client_customer_id (str, optional): クライアントカスタマーID
            
        Returns:
            List[Dict[str, Any]]: キャンペーンメトリクスのリスト
        """
        print(f"アカウントID: {client_customer_id} のキャンペーンメトリクスを取得します")
        
        # クライアントカスタマーIDが指定されていない場合は環境変数から取得
        if not client_customer_id:
            client_customer_id = env.get_env_var("GOOGLE_ADS_CLIENT_CUSTOMER_ID")
            print(f"環境変数からクライアントカスタマーIDを取得しました: {client_customer_id}")
        
        # Google Ads API用のYAMLファイルを作成
        yaml_path = GoogleAdsAPI.create_google_ads_yaml()
        
        # メトリクス設定を取得
        metrics_df = MetricsConfigUtils.get_metrics_config()
        active_metrics_list = MetricsConfigUtils.get_active_metrics_list()
        calculated_metrics = MetricsConfigUtils.get_calculated_metrics()
        
        # 日付範囲の設定
        today = datetime.date.today()
        days_ago = int(MetricsConfigUtils.get_period_days())
        start_date = today - datetime.timedelta(days=days_ago)
        
        # 日付フォーマットをYYYY-MM-DDに変換
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = today.strftime('%Y-%m-%d')
        
        # 取得件数上限の設定
        limit = int(MetricsConfigUtils.get_limit())
        
        try:
            # Google Ads APIクライアントを初期化
            client = GoogleAdsClient.load_from_storage(yaml_path)
            
            # クエリサービスを取得
            ga_service = client.get_service("GoogleAdsService")
            
            # メトリクスリストをAPIクエリ用に変換
            metrics_query_fields = []
            for metric in active_metrics_list:
                # フィールド名のマッピング
                field_name = GoogleAdsAPI.get_field_mapping(metric)
                metrics_query_fields.append(field_name)
            
            # クエリの構築
            query = f"""
            SELECT 
                campaign.id, 
                campaign.name, 
                campaign.status, 
                campaign.advertising_channel_type, 
                {', '.join(metrics_query_fields)}
            FROM campaign 
            WHERE 
                campaign.status = 'ENABLED' 
                AND segments.date >= '{start_date_str}' 
                AND segments.date <= '{end_date_str}'
            LIMIT {limit}
            """
            
            print(f"実行するクエリ: {query}")
            
            # クエリの実行
            search_request = client.get_type("SearchGoogleAdsRequest")
            search_request.customer_id = client_customer_id
            search_request.query = query
            
            # 結果の取得
            response = ga_service.search(request=search_request)
            
            # 結果をリストに変換
            campaign_metrics = []
            
            for row in response:
                campaign = row.campaign
                metrics = row.metrics
                
                # キャンペーン情報を辞書に変換
                campaign_data = {
                    "キャンペーンID": campaign.id,
                    "キャンペーン名": campaign.name,
                    "ステータス": campaign.status.name,
                    "キャンペーンタイプ": campaign.advertising_channel_type.name,
                }
                
                # APIから取得したメトリクス情報を追加
                variables = {}  # 計算フィールド用に値を保存
                
                for metric in active_metrics_list:
                    # メトリクス設定から日本語名を取得
                    metric_row = metrics_df[metrics_df['metrics'] == metric]
                    if not metric_row.empty:
                        metric_name = metric_row['name'].values[0]
                    else:
                        metric_name = metric
                    
                    # メトリクス値を取得
                    if hasattr(metrics, metric):
                        value = getattr(metrics, metric)
                        
                        # マイクロ単位の値を変換
                        if metric == 'cost_micros':
                            value = value / 1000000  # マイクロ単位から通常単位に変換
                        
                        campaign_data[metric_name] = value
                        variables[metric] = value
                
                # 計算フィールドを追加
                for metric, info in calculated_metrics.items():
                    metric_name = info['name']
                    calc_expr = info['calc']
                    
                    # 計算式を評価
                    try:
                        # 計算式で使用される変数を取得
                        if metric == 'conversion_rate' and 'conversions' in variables and 'clicks' in variables:
                            # CVRの場合は特別処理
                            if variables['clicks'] > 0:
                                result = variables['conversions'] / variables['clicks']
                            else:
                                result = 0
                        else:
                            # その他の計算式は文字列として評価
                            # 注意: 実際の実装では、eval()の使用は避け、より安全な方法を検討すべき
                            result = eval(calc_expr, {"__builtins__": {}}, variables)
                        
                        campaign_data[metric_name] = result
                    except Exception as calc_error:
                        print(f"計算フィールド '{metric}' の計算中にエラーが発生しました: {str(calc_error)}")
                        campaign_data[metric_name] = None
                
                campaign_metrics.append(campaign_data)
            
            print(f"\n合計 {len(campaign_metrics)} 件のキャンペーンデータを取得しました")
            return campaign_metrics
            
        except Exception as e:
            print(f"エラーが発生しました: {str(e)}")
            import traceback
            print(traceback.format_exc())
            return None

    @staticmethod
    def get_dummy_campaign_metrics() -> List[Dict[str, Any]]:
        """
        テスト用のダミーキャンペーンメトリクスを生成する
        
        Returns:
            List[Dict[str, Any]]: ダミーキャンペーンメトリクスのリスト
        """
        print("テスト用のダミーキャンペーンメトリクスを生成します")
        
        # メトリクス設定を取得
        metrics_df = MetricsConfigUtils.get_metrics_config()
        active_metrics_list = MetricsConfigUtils.get_active_metrics_list()
        calculated_metrics = MetricsConfigUtils.get_calculated_metrics()
        
        # ダミーデータの件数
        num_campaigns = 10
        
        # ダミーキャンペーンメトリクスのリスト
        campaign_metrics = []
        
        for i in range(1, num_campaigns + 1):
            # キャンペーン基本情報
            campaign = {
                "キャンペーンID": f"10000{i}",
                "キャンペーン名": f"テストキャンペーン {i}",
                "ステータス": "ENABLED",
                "キャンペーンタイプ": "SEARCH",
            }
            
            # APIから取得するメトリクス情報を追加
            variables = {}  # 計算フィールド用に値を保存
            
            for metric in active_metrics_list:
                # メトリクス設定から日本語名を取得
                metric_row = metrics_df[metrics_df['metrics'] == metric]
                if not metric_row.empty:
                    metric_name = metric_row['name'].values[0]
                else:
                    metric_name = metric
                
                # ダミー値を生成
                if metric == 'impressions':
                    value = i * 1000 + (i * 100)
                elif metric == 'clicks':
                    value = i * 50 + (i * 10)
                elif metric == 'cost_micros':
                    value = (i * 5000 + (i * 500)) / 1000000  # 既に通常単位に変換
                elif metric == 'conversions':
                    value = i * 2 + (i * 0.5)
                elif metric == 'ctr':
                    value = 0.05 + (i * 0.005)
                elif metric == 'average_cpc':
                    value = 100 + (i * 10)
                elif metric == 'search_top_impression_share':
                    value = 0.3 + (i * 0.05)
                else:
                    value = i * 10
                
                campaign[metric_name] = value
                variables[metric] = value
            
            # 計算フィールドを追加
            for metric, info in calculated_metrics.items():
                metric_name = info['name']
                calc_expr = info['calc']
                
                # 計算式を評価
                try:
                    # 計算式で使用される変数を取得
                    if metric == 'conversion_rate' and 'conversions' in variables and 'clicks' in variables:
                        # CVRの場合は特別処理
                        if variables['clicks'] > 0:
                            result = variables['conversions'] / variables['clicks']
                        else:
                            result = 0
                    else:
                        # その他の計算式は文字列として評価
                        # 注意: 実際の実装では、eval()の使用は避け、より安全な方法を検討すべき
                        result = eval(calc_expr, {"__builtins__": {}}, variables)
                    
                    campaign[metric_name] = result
                except Exception as calc_error:
                    print(f"計算フィールド '{metric}' の計算中にエラーが発生しました: {str(calc_error)}")
                    campaign[metric_name] = None
            
            campaign_metrics.append(campaign)
        
        # 結果のサマリーを出力
        for campaign in campaign_metrics:
            print(f"\nキャンペーン: {campaign['キャンペーン名']}")
            print(f"  ID: {campaign['キャンペーンID']}")
            print(f"  タイプ: {campaign['キャンペーンタイプ']}")
            
            # 動的なメトリクスのログ出力
            for key, value in campaign.items():
                if key not in ["キャンペーンID", "キャンペーン名", "キャンペーンタイプ", "ステータス"]:
                    # 数値の場合はフォーマットを整える
                    if isinstance(value, (int, float)):
                        if key in ["クリック率", "CVR"]:
                            print(f"  {key}: {value:.2%}")
                        elif key in ["費用", "平均クリック単価"]:
                            print(f"  {key}: {value:.2f}円")
                        else:
                            print(f"  {key}: {value}")
                    else:
                        print(f"  {key}: {value}")
        
        print(f"\n合計 {len(campaign_metrics)} 件のダミーデータを生成しました")
        return campaign_metrics 