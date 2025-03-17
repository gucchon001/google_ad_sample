"""
Google広告分析レポート作成システム

このスクリプトは、Google Ads APIからデータを取得し、
スプレッドシートに出力した後、データ分析を行うメインスクリプトです。
"""

import sys
import pandas as pd
import datetime
import argparse
from src.utils.environment import EnvironmentUtils as env
from src.utils.spreadsheet import SpreadsheetUtils
from src.modules.google_ads import GoogleAdsAPI


def main():
    """メイン関数"""
    try:
        # コマンドライン引数の解析
        parser = argparse.ArgumentParser(description='Google広告分析レポート作成システム')
        parser.add_argument('--test', action='store_true', help='テストモードで実行')
        args = parser.parse_args()
        
        print("Google広告分析レポート作成システムを開始します")
        
        # 環境設定の読み込み
        env.load_env()
        
        # スプレッドシート設定を取得
        spreadsheet_id = env.get_config_value("SPREADSHEET", "spreadsheet_id")
        data_sheet_name = env.get_config_value("SPREADSHEET", "sheet_name")
        
        print(f"スプレッドシートID: {spreadsheet_id}")
        print(f"データシート名: {data_sheet_name}")
        
        # ステップ1: Google Ads APIからデータ取得
        print("\nステップ1: Google Ads APIからデータ取得")
        
        if args.test:
            # テストモードの場合はダミーデータを使用
            print("テストモードで実行します - ダミーデータを使用")
            campaign_metrics = GoogleAdsAPI.get_dummy_campaign_metrics()
        else:
            # 本番モードの場合は実際のAPIからデータを取得
            client_customer_id = env.get_env_var("GOOGLE_ADS_CLIENT_CUSTOMER_ID")
            if not client_customer_id:
                print("警告: GOOGLE_ADS_CLIENT_CUSTOMER_ID が設定されていません。デフォルト値を使用します。")
                client_customer_id = "2197645811"  # デフォルト値
            
            print(f"クライアントカスタマーID: {client_customer_id}")
            campaign_metrics = GoogleAdsAPI.get_campaign_metrics(client_customer_id)
        
        if not campaign_metrics:
            print("データが取得できませんでした。処理を終了します。")
            return
        
        # ステップ2: データをDataFrameに変換
        print("\nステップ2: データをDataFrameに変換")
        df = pd.DataFrame(campaign_metrics)
        
        # 取得日時を追加
        now = datetime.datetime.now()
        df['取得日時'] = now.strftime('%Y-%m-%d %H:%M:%S')
        
        print(f"変換されたDataFrame: {len(df)}行 x {len(df.columns)}列")
        
        # ステップ3: スプレッドシートにデータを出力
        print("\nステップ3: スプレッドシートにデータを出力")
        
        # 既存データを取得して新しいデータを追加
        try:
            existing_df = SpreadsheetUtils.read_as_dataframe(
                spreadsheet_id=spreadsheet_id,
                range_name=f"{data_sheet_name}!A:Z"
            )
            
            if not existing_df.empty:
                print(f"既存データ: {len(existing_df)}行")
                
                # 既存データと新しいデータを結合
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                print(f"結合後のデータ: {len(combined_df)}行")
                
                # スプレッドシートをクリアして新しいデータを書き込み
                result = SpreadsheetUtils.write_dataframe(
                    df=combined_df,
                    spreadsheet_id=spreadsheet_id,
                    range_name=f"{data_sheet_name}!A1"
                )
                print(f"{result.get('updatedCells', 0)} セルを更新しました。")
            else:
                # 既存データがない場合は新しいデータのみを書き込み
                result = SpreadsheetUtils.write_dataframe(
                    df=df,
                    spreadsheet_id=spreadsheet_id,
                    range_name=f"{data_sheet_name}!A1"
                )
                print(f"{result.get('updatedCells', 0)} セルを更新しました。")
        except Exception as e:
            print(f"既存データの読み込みに失敗しました。新しいデータのみを書き込みます: {str(e)}")
            result = SpreadsheetUtils.write_dataframe(
                df=df,
                spreadsheet_id=spreadsheet_id,
                range_name=f"{data_sheet_name}!A1"
            )
            print(f"{result.get('updatedCells', 0)} セルを更新しました。")
        
        print("データのスプレッドシートへの出力が完了しました")
        
        # ステップ4: 基本的な分析結果を表示
        print("\nステップ4: 基本的な分析結果")
        
        # 数値列のみを抽出
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        if numeric_cols:
            print("\n=== キャンペーンメトリクスのサマリー ===")
            for col in numeric_cols:
                if col != 'キャンペーンID':  # IDは集計から除外
                    total = df[col].sum()
                    avg = df[col].mean()
                    print(f"{col}:")
                    print(f"  合計: {total:.2f}")
                    print(f"  平均: {avg:.2f}")
        
        print("\nGoogle広告分析レポート作成システムが正常に完了しました")
        
    except Exception as e:
        print(f"エラーが発生しました: {str(e)}")
        import traceback
        print(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()
