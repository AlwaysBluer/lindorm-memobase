#!/usr/bin/env python3
"""
分析并打印CSV文件的结构
"""
import csv
import json
from typing import Dict, Any
from datetime import datetime


def analyze_csv_structure(csv_file_path: str):
    """分析CSV文件结构并打印详细信息"""
    
    print("=" * 80)
    print(f"CSV文件结构分析: {csv_file_path}")
    print("=" * 80)
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.reader(file)
            
            # 读取表头
            header = next(reader)
            print(f"\n📋 表头信息:")
            print(f"列数: {len(header)}")
            for i, col in enumerate(header):
                print(f"  [{i}] {col}")
            
            # 分析前几行数据
            print(f"\n🔍 数据样本分析 (前5行):")
            print("-" * 80)
            
            sample_rows = []
            for row_num, row in enumerate(reader, start=2):
                if row_num > 20:
                    break
                sample_rows.append(row)
            
            for i, row in enumerate(sample_rows):
                print(f"\n第 {i+2} 行数据:")
                print(f"列数: {len(row)}")
                
                for j, (col_name, value) in enumerate(zip(header, row)):
                    print(f"  [{j}] {col_name}: {repr(value)}")
                
                print("-" * 40)
            
            # 统计总体信息
            file.seek(0)
            reader = csv.reader(file)
            next(reader)  # 跳过表头
            
            total_rows = 0
            valid_rows = 0
            error_rows = 0
            
            for row in reader:
                total_rows += 1
                if len(row) >= 6:
                    response = row[5]
                    if response and not response.startswith('ERROR:') and 'Method Not Allowed' not in response:
                        valid_rows += 1
                    else:
                        error_rows += 1
                
                # 只统计前1000行，避免太慢
                if total_rows >= 1000:
                    print("  (仅统计前1000行)")
                    break
            
            print(f"  总行数: {total_rows}")
            print(f"  有效行数: {valid_rows}")
            print(f"  错误行数: {error_rows}")
            print(f"  有效率: {valid_rows/total_rows*100:.1f}%")
            
            # 字段类型分析
            print(f"\n🏷️  字段详细说明:")
            field_descriptions = [
                ("__source__", "来源IP地址"),
                ("__time__", "时间戳"),
                ("__topic__", "主题标识"),
                ("request", "请求内容 (JSON格式)"),
                ("request_ts", "请求时间戳 (毫秒)"),
                ("response", "响应内容 (文本)"),
                ("response_ts", "响应时间戳 (毫秒)"),
                ("stream_id", "流ID")
            ]
            
            for i, (field, desc) in enumerate(field_descriptions):
                if i < len(header):
                    print(f"  [{i}] {field}: {desc}")
    
    except FileNotFoundError:
        print(f"❌ 文件不存在: {csv_file_path}")
    except Exception as e:
        print(f"❌ 分析过程中出错: {e}")
        import traceback
        traceback.print_exc()


def main():
    """主函数"""
    csv_file_path = "./data/shenlandata_converted.csv"
    analyze_csv_structure(csv_file_path)


if __name__ == "__main__":
    main()