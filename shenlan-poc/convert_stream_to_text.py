#!/usr/bin/env python3
"""
将CSV文件中的流式响应转换为完整文本内容
"""
import csv
import json
import re
from typing import Optional


def parse_streaming_response(response_text: str) -> str:
    """
    解析流式响应，提取完整的文本内容
    
    Args:
        response_text: 原始流式响应文本
        
    Returns:
        合并后的完整文本内容
    """
    # 处理非流式响应（如错误响应）
    if not response_text.strip().startswith('data:'):
        try:
            # 尝试解析为JSON错误响应
            error_data = json.loads(response_text)
            if 'detail' in error_data:
                return f"ERROR: {error_data['detail']}"
            return response_text
        except json.JSONDecodeError:
            return response_text
    
    # 解析流式响应
    content_parts = []
    lines = response_text.strip().split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or not line.startswith('data: '):
            continue
            
        # 移除 'data: ' 前缀
        json_str = line[6:]  # len('data: ') = 6
        
        if not json_str or json_str == '[DONE]':
            continue
            
        try:
            chunk_data = json.loads(json_str)
            
            # 提取content内容
            if 'choices' in chunk_data and chunk_data['choices']:
                choice = chunk_data['choices'][0]
                if 'delta' in choice and 'content' in choice['delta']:
                    content = choice['delta']['content']
                    if content:
                        content_parts.append(content)
                        
        except json.JSONDecodeError as e:
            # 忽略JSON解析错误，继续处理下一行
            continue
    
    return ''.join(content_parts)


def convert_csv_streaming_to_text(input_file: str, output_file: str):
    """
    转换CSV文件，将流式响应转换为完整文本
    
    Args:
        input_file: 输入CSV文件路径
        output_file: 输出CSV文件路径
    """
    processed_count = 0
    error_count = 0
    
    with open(input_file, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:
        
        reader = csv.reader(infile)
        writer = csv.writer(outfile)
        
        # 处理表头
        header = next(reader)
        writer.writerow(header)
        
        # 处理数据行
        for row_num, row in enumerate(reader, start=2):
            try:
                if len(row) >= 6:  # 确保有足够的列
                    # response在第6列（索引5）
                    original_response = row[5]
                    
                    # 转换流式响应为完整文本
                    converted_response = parse_streaming_response(original_response)
                    
                    # 创建新行
                    new_row = row.copy()
                    new_row[5] = converted_response
                    
                    writer.writerow(new_row)
                    processed_count += 1
                    
                    # 每处理1000行输出进度
                    if processed_count % 1000 == 0:
                        print(f"已处理 {processed_count} 行...")
                        
                else:
                    # 行格式不正确，直接写入
                    writer.writerow(row)
                    error_count += 1
                    
            except Exception as e:
                print(f"处理第 {row_num} 行时出错: {e}")
                writer.writerow(row)  # 出错时保留原始数据
                error_count += 1
    
    print(f"转换完成！")
    print(f"成功处理: {processed_count} 行")
    print(f"错误/跳过: {error_count} 行")
    print(f"输出文件: {output_file}")


def main():
    """主函数"""
    input_file = "./data/shenlandata.csv"
    output_file = "./data/shenlandata_converted.csv"
    
    print("开始转换CSV文件...")
    print(f"输入文件: {input_file}")
    print(f"输出文件: {output_file}")
    
    convert_csv_streaming_to_text(input_file, output_file)


if __name__ == "__main__":
    main()