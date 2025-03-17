import pandas as pd
from scipy.stats import pearsonr
import matplotlib.pyplot as plt
from src.utils.spreadsheet import SpreadsheetUtils
from src.utils.environment import EnvironmentUtils as env
from src.utils.logging_config import get_logger
import os

# ロガーの設定
logger = get_logger(__name__)

def load_data():
    """
    スプレッドシートからデータをロードする関数
    """
    # 環境設定の読み込み
    env.load_env()
    
    # スプレッドシート設定を取得
    spreadsheet_id = env.get_config_value("SPREADSHEET", "spreadsheet_id")
    sheet_name = env.get_config_value("SPREADSHEET", "sheet_name")
    range_name = f"{sheet_name}!A1:M10000"  # 読み込む範囲を指定
    
    # スプレッドシートからデータを取得
    df = SpreadsheetUtils.read_as_dataframe(spreadsheet_id, range_name)
    
    return df

def convert_percentage_to_float(series):
    """
    パーセンテージ形式の文字列を小数に変換する関数
    """
    return series.apply(lambda x: float(x.rstrip('%')) / 100 if isinstance(x, str) and '%' in x else float(x))

def analyze_correlation(df):
    """
    相関を分析し、結果を表示し、スプレッドシートに出力する関数
    """
    # 日本語フォントの設定
    plt.rcParams['font.family'] = 'Meiryo'  # Windowsの場合
    # plt.rcParams['font.family'] = 'IPAPGothic'  # Linuxの場合
    # plt.rcParams['font.family'] = 'Hiragino Maru Gothic Pro'  # macOSの場合

    # カラム名を確認
    logger.info("DataFrameのカラム名: %s", df.columns)

    # パーセンテージ文字列を数値に変換
    df['検索トップシェア'] = convert_percentage_to_float(df['検索トップシェア'])
    df['CVR'] = convert_percentage_to_float(df['CVR'])

    # 全体の相関係数を計算
    overall_correlation, overall_p_value = pearsonr(df['検索トップシェア'], df['CVR'])
    logger.info("全体の相関係数: %f", overall_correlation)
    logger.info("全体のp値: %f", overall_p_value)

    # 各キャンペーンごとの相関係数を計算
    campaign_correlations = []
    for campaign_id, group in df.groupby('キャンペーンID'):
        if len(group) > 1:  # データが2行以上ある場合のみ計算
            correlation, p_value = pearsonr(group['検索トップシェア'], group['CVR'])
            campaign_correlations.append((campaign_id, correlation, p_value))
            logger.info("キャンペーンID %s の相関係数: %f, p値: %f", campaign_id, correlation, p_value)

    # 結果をスプレッドシートに出力
    output_spreadsheet_id = env.get_config_value("SPREADSHEET", "spreadsheet_id")
    output_sheet_name = "output"
    output_range = f"{output_sheet_name}!A1"
    output_data = pd.DataFrame({
        "キャンペーンID": [c[0] for c in campaign_correlations],
        "相関係数": [c[1] for c in campaign_correlations],
        "p値": [c[2] for c in campaign_correlations]
    })
    SpreadsheetUtils.write_dataframe_to_sheet(output_spreadsheet_id, output_range, output_data)

    # 可視化
    plt.figure(figsize=(8, 6))
    plt.scatter(df['検索トップシェア'], df['CVR'], color='blue', alpha=0.7)
    plt.xlabel('検索トップシェア')
    plt.ylabel('CVR')
    plt.title('検索トップシェアとCVRの相関')
    plt.grid(True)
    
    # 結果を保存
    output_dir = 'data'
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, 'correlation_plot.png'))
    plt.show()

def main():
    # データをロード
    df = load_data()
    
    # データの確認
    logger.info("データの先頭: \n%s", df.head())
    
    # 相関を分析
    analyze_correlation(df)

if __name__ == "__main__":
    main() 