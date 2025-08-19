#!/usr/bin/env python3
"""
Display clean conversation data from CSV file
Shows only data with 'vin' field in request
"""
import csv
import json
from typing import Dict, Optional
from datetime import datetime


def parse_csv_row(row, row_num: int) -> Optional[Dict]:
    """
    Parse CSV row data - only process rows with 'vin' field
    
    Args:
        row: CSV row data
        row_num: Row number
        
    Returns:
        Parsed conversation data with user_id from vin field
    """
    if len(row) < 8:
        return None
    
    try:
        source = row[0]
        timestamp = int(row[1]) if row[1] else None
        topic = row[2]
        request = row[3]
        request_ts = int(row[4]) if row[4] else None
        response = row[5]
        response_ts = int(row[6]) if row[6] else None
        stream_id = row[7]
        
        # Parse request JSON
        try:
            request_data = json.loads(request)
        except json.JSONDecodeError:
            return None
        
        # Check if this is valid data (must have 'vin' field)
        if 'vin' not in request_data:
            return None  # Skip dirty data
            
        # Extract vin as user_id
        user_id = str(request_data['vin'])
        if not user_id or user_id == 'null':
            return None
        
        # Extract messages for conversation history
        messages = request_data.get('messages', [])
        if not messages:
            return None
        
        # Check if valid conversation (response is not error message)
        if not response or response.startswith('ERROR:') or 'Method Not Allowed' in response:
            return None
        
        return {
            "user_id": user_id,
            "source": source,
            "timestamp": timestamp,
            "topic": topic,
            "messages": messages,  # Full conversation history
            "current_response": response,  # AI's response to the last user message
            "request_ts": request_ts,
            "response_ts": response_ts,
            "stream_id": stream_id,
            "row_num": row_num
        }
        
    except Exception as e:
        return None


def timestamp_to_datetime(timestamp: Optional[int]) -> str:
    """Convert timestamp to readable datetime string"""
    if not timestamp:
        return "Unknown time"
    
    try:
        # Handle millisecond timestamp
        if timestamp > 1e12:  # milliseconds
            timestamp = timestamp / 1000
        
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return "Invalid time"


def display_conversation(conv_data: Dict, show_full_history: bool = True):
    """Display a single conversation in readable format"""
    print("=" * 80)
    print(f"User ID (VIN): {conv_data['user_id']}")
    print("-" * 80)
    
    # Display conversation messages
    if show_full_history and len(conv_data['messages']) > 1:
        print("💬 Complete Conversation History:")
        for i, msg in enumerate(conv_data['messages'], 1):
            if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                role_emoji = "👤" if msg['role'] == 'user' else "🤖"
                role_name = "User" if msg['role'] == 'user' else "Assistant"
                print(f"\n{role_emoji} {role_name} (Message {i}):")
                print(f"   {msg['content']}")
    else:
        # Show only the last user message
        last_user_msg = None
        for msg in reversed(conv_data['messages']):
            if isinstance(msg, dict) and msg.get('role') == 'user':
                last_user_msg = msg
                break
        
        if last_user_msg:
            print("👤 User:")
            print(f"   {last_user_msg['content']}")
    
    # Display AI response
    print(f"\n🤖 AI Response:")
    print(f"   {conv_data['current_response']}")
    print()


def main():
    """Main function to display clean conversations"""
    print("=" * 100)
    print("🔍 Clean Conversation Data Display (VIN-based)")
    print("=" * 100)
    
    csv_file_path = "./data/shenlandata_converted.csv"
    
    # Check if file exists
    try:
        with open(csv_file_path, 'r') as f:
            pass
        print(f"✅ Found CSV file: {csv_file_path}\n")
    except FileNotFoundError:
        print(f"❌ Cannot find CSV file: {csv_file_path}")
        print("Please run convert_stream_to_text.py first to convert raw data")
        return
    
    # Statistics
    stats = {
        "total_rows": 0,
        "valid_conversations": 0,
        "unique_users": set(),
        "error_rows": 0
    }
    
    conversations = []
    
    # Parse CSV file
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        header = next(reader)  # Skip header
        
        print(f"📋 CSV Header: {header}")
        print()
        
        for row_num, row in enumerate(reader, start=2):
            try:
                stats["total_rows"] += 1
                
                # Parse CSV row data
                conversation_data = parse_csv_row(row, row_num)
                if not conversation_data:
                    stats["error_rows"] += 1
                    continue
                
                stats["valid_conversations"] += 1
                stats["unique_users"].add(conversation_data["user_id"])
                conversations.append(conversation_data)
                
            except Exception as e:
                stats["error_rows"] += 1
                continue
    
    # Display statistics
    print(" Data Statistics:")
    print(f"   Total rows processed: {stats['total_rows']}")
    print(f"   Valid conversations: {stats['valid_conversations']}")
    print(f"   Unique users (VINs): {len(stats['unique_users'])}")
    print(f"   Error/Dirty rows: {stats['error_rows']}")
    print(f"   Success rate: {(stats['valid_conversations'] / max(stats['total_rows'], 1) * 100):.1f}%")
    print()
    
    if not conversations:
        print("❌ No valid conversations found!")
        return
    
    # Set display parameters (can be modified as needed)
    max_display = min(10, len(conversations))  # Show 3 conversations by default
    show_full_history = True  # Show full conversation history
    
    print()
    print(f"📝 Displaying {max_display} conversations:")
    print()
    
    # Display conversations
    for i, conv in enumerate(conversations[:max_display], 1):
        print(f"[Conversation {i}/{max_display}]")
        display_conversation(conv, show_full_history)
    
    # Show user distribution
    print("\n" + "=" * 80)
    print("👥 User Distribution (Top 10 VINs):")
    user_counts = {}
    for conv in conversations:
        user_id = conv["user_id"]
        user_counts[user_id] = user_counts.get(user_id, 0) + 1
    
    # Sort by conversation count
    sorted_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)
    
    for i, (user_id, count) in enumerate(sorted_users[:10], 1):
        print(f"   {i:2d}. {user_id}: {count} conversations")
    
    if len(sorted_users) > 10:
        print(f"   ... and {len(sorted_users) - 10} more users")
    
    print("\n✅ Display completed!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⏹️  Program interrupted by user")
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()