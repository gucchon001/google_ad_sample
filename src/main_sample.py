from google.ads.googleads.client import GoogleAdsClient
from pathlib import Path
import yaml
import sys
import datetime
from src.utils.environment import EnvironmentUtils as env

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
        "developer_token": env.get_env_var("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": env.get_env_var("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": env.get_env_var("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": env.get_env_var("GOOGLE_ADS_REFRESH_TOKEN"),
        "login_customer_id": env.get_env_var("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
        "use_proto_plus": True
    }
    
    # ディレクトリが存在しない場合は作成
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    
    # YAMLファイルに書き込み
    with open(yaml_path, 'w') as f:
        yaml.dump(config, f)
    
    print(f"新しいYAMLファイルを作成しました: {yaml_path}")
    return yaml_path

def get_campaign_metrics_simple(client_customer_id):
    """
    シンプルなキャンペーンメトリクス取得関数
    
    Args:
        client_customer_id (str): クライアントアカウントID
        
    Returns:
        list: キャンペーンメトリクスのリスト
    """
    print(f"アカウントID: {client_customer_id} のキャンペーンメトリクスを取得します")
    
    # google-ads.yamlファイルを作成
    yaml_path = create_google_ads_yaml()
    
    # GoogleAdsClientの初期化
    client = GoogleAdsClient.load_from_storage(str(yaml_path))
    
    # GoogleAdsServiceの取得
    ga_service = client.get_service("GoogleAdsService")
    
    # 日付範囲の設定（過去30日間）
    today = datetime.date.today()
    thirty_days_ago = today - datetime.timedelta(days=30)
    
    print(f"期間: {thirty_days_ago} から {today} までのデータを取得します")
    
    # クエリの作成 - アクティブなキャンペーンかつインプレッションが1以上に絞り込み
    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign.campaign_group,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM campaign
        WHERE 
            segments.date BETWEEN '{thirty_days_ago}' AND '{today}'
            AND campaign.status = 'ENABLED'
            AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
        LIMIT 10
    """
    
    print("実行するクエリ:")
    print(query)
    
    try:
        # クエリの実行
        response = ga_service.search(customer_id=client_customer_id, query=query)
        
        # 結果の処理
        campaign_metrics = []
        for row in response:
            # キャンペーングループの処理
            campaign_group = "なし"
            if hasattr(row.campaign, 'campaign_group') and row.campaign.campaign_group:
                if hasattr(row.campaign.campaign_group, 'name'):
                    campaign_group = row.campaign.campaign_group.name
                elif hasattr(row.campaign.campaign_group, 'resource_name'):
                    resource_name = row.campaign.campaign_group.resource_name
                    campaign_group_id = resource_name.split('/')[-1] if '/' in resource_name else resource_name
                    campaign_group = f"ID: {campaign_group_id}"
                else:
                    campaign_group = str(row.campaign.campaign_group)
            
            # メトリクスの取得
            campaign = {
                "キャンペーンID": row.campaign.id,
                "キャンペーン名": row.campaign.name,
                "キャンペーンタイプ": row.campaign.advertising_channel_type.name,
                "キャンペーングループ": campaign_group,
                "ステータス": row.campaign.status.name,
                "インプレッション数": row.metrics.impressions,
                "クリック数": row.metrics.clicks,
                "コスト": row.metrics.cost_micros / 1000000,  # マイクロ単位から円に変換
                "コンバージョン数": row.metrics.conversions,
                "CTR": row.metrics.ctr,
                "平均CPC": row.metrics.average_cpc / 1000000,  # マイクロ単位から円に変換
            }
            campaign_metrics.append(campaign)
            
            # ログに出力
            print(f"\nキャンペーン: {campaign['キャンペーン名']}")
            print(f"  ID: {campaign['キャンペーンID']}")
            print(f"  タイプ: {campaign['キャンペーンタイプ']}")
            print(f"  グループ: {campaign['キャンペーングループ']}")
            print(f"  インプレッション数: {campaign['インプレッション数']}")
            print(f"  クリック数: {campaign['クリック数']}")
            print(f"  コスト: {campaign['コスト']:.2f}円")
            print(f"  コンバージョン数: {campaign['コンバージョン数']:.2f}")
            print(f"  CTR: {campaign['CTR']:.2%}")
            print(f"  平均CPC: {campaign['平均CPC']:.2f}円")
        
        print(f"\n合計 {len(campaign_metrics)} 件のキャンペーンデータを取得しました")
        return campaign_metrics
        
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return []

def main():
    """メイン関数"""
    # クライアントアカウントID
    CLIENT_CUSTOMER_ID = "2197645811"
    
    try:
        # キャンペーンメトリクスの取得
        campaign_metrics = get_campaign_metrics_simple(CLIENT_CUSTOMER_ID)
        
        # 結果の表示
        if campaign_metrics:
            print("\n=== キャンペーンメトリクスのサマリー ===")
            total_impressions = sum(c["インプレッション数"] for c in campaign_metrics)
            total_clicks = sum(c["クリック数"] for c in campaign_metrics)
            total_cost = sum(c["コスト"] for c in campaign_metrics)
            total_conversions = sum(c["コンバージョン数"] for c in campaign_metrics)
            
            print(f"総インプレッション数: {total_impressions}")
            print(f"総クリック数: {total_clicks}")
            print(f"総コスト: {total_cost:.2f}円")
            print(f"総コンバージョン数: {total_conversions:.2f}")
            
            if total_clicks > 0:
                overall_ctr = total_clicks / total_impressions
                print(f"全体のCTR: {overall_ctr:.2%}")
            
            if total_conversions > 0:
                overall_cpa = total_cost / total_conversions
                print(f"全体のCPA: {overall_cpa:.2f}円")
        
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {str(e)}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main() 