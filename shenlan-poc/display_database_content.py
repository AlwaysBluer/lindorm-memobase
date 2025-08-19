#!/usr/bin/env python3
"""
Display structured content from Lindorm database tables
Shows blob_content and user_profiles tables in readable format
"""
import mysql.connector
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
import sys


class LindormDatabaseViewer:
    """Database viewer for Lindorm tables"""
    
    def __init__(self):
        """Initialize database connection"""
        self.connection = None
        self.cursor = None
        
        # Database connection config
        self.config = {
            'host': 'ld-2ze896px34592aho7-proxy-lindorm-pub.lindorm.aliyuncs.com',
            'port': 33060,
            'user': 'root',
            'password': 'NQinCrGdVtev',
            'database': 'default',
            'charset': 'utf8mb4',
            'autocommit': False
        }
    
    def connect(self) -> bool:
        """Connect to the database"""
        try:
            print("Connecting to Lindorm database...")
            self.connection = mysql.connector.connect(**self.config)
            self.cursor = self.connection.cursor(dictionary=True)
            print("✅ Connected successfully!")
            return True
        except Exception as e:
            print(f" Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        print("🔚 Database connection closed")
    
    def format_timestamp(self, ts) -> str:
        """Format timestamp for display"""
        if ts is None:
            return "None"
        if isinstance(ts, datetime):
            return ts.strftime("%Y-%m-%d %H:%M:%S")
        return str(ts)
    
    def format_json(self, json_data) -> str:
        """Format JSON data for display"""
        if json_data is None:
            return "None"
        try:
            if isinstance(json_data, str):
                parsed = json.loads(json_data)
            else:
                parsed = json_data
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except:
            return str(json_data)
    
    def get_table_stats(self, table_name: str) -> Dict[str, Any]:
        """Get basic statistics for a table"""
        try:
            # Get total count
            self.cursor.execute(f"SELECT COUNT(*) as total_count FROM {table_name}")
            result = self.cursor.fetchone()
            total_count = result['total_count'] if result else 0
            
            # Get unique user count
            self.cursor.execute(f"SELECT COUNT(DISTINCT user_id) as unique_users FROM {table_name}")
            result = self.cursor.fetchone()
            unique_users = result['unique_users'] if result else 0
            
            return {
                'total_count': total_count,
                'unique_users': unique_users
            }
        except Exception as e:
            print(f"❌ Error getting stats for {table_name}: {e}")
            return {'total_count': 0, 'unique_users': 0}
    
    def display_blob_content(self, limit: int = 5):
        """Display blob_content table data"""
        print("\n" + "=" * 100)
        print("🗂️  BLOB_CONTENT Table")
        print("=" * 100)
        
        # Get statistics
        stats = self.get_table_stats('blob_content')
        print(f"📊 Statistics: {stats['total_count']} total records, {stats['unique_users']} unique users")
        print()
        
        try:
            # Get data
            query = """
            SELECT user_id, blob_id, blob_data, created_at, updated_at 
            FROM blob_content 
            ORDER BY created_at DESC 
            LIMIT %s
            """
            self.cursor.execute(query, (limit,))
            results = self.cursor.fetchall()
            
            if not results:
                print("📭 No data found in blob_content table")
                return
            
            for i, row in enumerate(results, 1):
                print(f"[Record {i}/{len(results)}]")
                print("-" * 80)
                print(f"👤 User ID: {row['user_id']}")
                print(f"🆔 Blob ID: {row['blob_id']}")
                print(f"📅 Created: {self.format_timestamp(row['created_at'])}")
                print(f"📅 Updated: {self.format_timestamp(row['updated_at'])}")
                print(f"💾 Blob Data:")
                
                # Try to parse and format blob_data as JSON
                try:
                    if row['blob_data']:
                        blob_data = json.loads(row['blob_data'])
                        print("   📋 Type:", blob_data.get('type', 'Unknown'))
                        
                        if 'messages' in blob_data:
                            messages = blob_data['messages']
                            print(f"   💬 Messages ({len(messages)}):")
                            for j, msg in enumerate(messages[:3], 1):  # Show first 3 messages
                                role = msg.get('role', 'unknown')
                                content = msg.get('content', '')[:100]  # First 100 chars
                                created_at = msg.get('created_at', 'No timestamp')
                                print(f"      {j}. [{role}] {content}{'...' if len(msg.get('content', '')) > 100 else ''}")
                                print(f"         📅 {created_at}")
                            
                            if len(messages) > 3:
                                print(f"      ... and {len(messages) - 3} more messages")
                        
                        # Show other blob data fields
                        for key, value in blob_data.items():
                            if key not in ['type', 'messages']:
                                print(f"   🏷️  {key}: {value}")
                    else:
                        print("   📭 No blob data")
                except json.JSONDecodeError:
                    print(f"   📄 Raw data: {str(row['blob_data'])[:200]}...")
                except Exception as e:
                    print(f"   ❌ Error parsing blob data: {e}")
                
                print()
        
        except Exception as e:
            print(f"❌ Error querying blob_content: {e}")
    
    def display_user_profiles(self, limit: int = 10):
        """Display user_profiles table data"""
        print("\n" + "=" * 100)
        print("👤 USER_PROFILES Table")
        print("=" * 100)
        
        # Get statistics
        stats = self.get_table_stats('user_profiles')
        print(f"📊 Statistics: {stats['total_count']} total profiles, {stats['unique_users']} unique users")
        print()
        
        try:
            # Get data grouped by user
            query = """
            SELECT user_id, profile_id, content, attributes, created_at, updated_at 
            FROM user_profiles 
            ORDER BY user_id, created_at DESC 
            LIMIT %s
            """
            self.cursor.execute(query, (limit,))
            results = self.cursor.fetchall()
            
            if not results:
                print("📭 No data found in user_profiles table")
                return
            
            # Group by user_id
            users_data = {}
            for row in results:
                user_id = row['user_id']
                if user_id not in users_data:
                    users_data[user_id] = []
                users_data[user_id].append(row)
            
            for user_idx, (user_id, profiles) in enumerate(users_data.items(), 1):
                print(f"[User {user_idx}/{len(users_data)}]")
                print("-" * 80)
                print(f"👤 User ID: {user_id}")
                print(f"📋 Profiles ({len(profiles)}):")
                print()
                
                for profile_idx, profile in enumerate(profiles, 1):
                    print(f"   📝 Profile {profile_idx}:")
                    print(f"      🆔 Profile ID: {profile['profile_id']}")
                    print(f"      📅 Created: {self.format_timestamp(profile['created_at'])}")
                    print(f"      📅 Updated: {self.format_timestamp(profile['updated_at'])}")
                    
                    # Display content
                    content = profile['content'] or ''
                    if len(content) > 200:
                        print(f"      📄 Content: {content[:200]}...")
                    else:
                        print(f"      📄 Content: {content}")
                    
                    # Display attributes
                    if profile['attributes']:
                        try:
                            attrs = profile['attributes']
                            if isinstance(attrs, str):
                                attrs = json.loads(attrs)
                            print("      🏷️  Attributes:")
                            for key, value in attrs.items():
                                print(f"         • {key}: {value}")
                        except Exception as e:
                            print(f"      ❌ Error parsing attributes: {e}")
                    else:
                        print("      🏷️  Attributes: None")
                    print()
                
                print("-" * 40)
                print()
        
        except Exception as e:
            print(f"❌ Error querying user_profiles: {e}")
    
    def display_user_summary(self):
        """Display user summary across both tables"""
        print("\n" + "=" * 100)
        print("📈 USER SUMMARY")
        print("=" * 100)
        
        try:
            # Get profile statistics (Lindorm doesn't support JOINs, so we'll do separate queries)
            print("👥 User Profile Statistics:")
            query = """
            SELECT 
                user_id,
                COUNT(profile_id) as profile_count,
                MAX(updated_at) as last_profile_update
            FROM user_profiles
            GROUP BY user_id
            ORDER BY profile_count DESC
            LIMIT 10
            """
            
            self.cursor.execute(query)
            profile_results = self.cursor.fetchall()
            
            if profile_results:
                print(f"{'Rank':<4} {'User ID':<20} {'Profiles':<8} {'Last Update':<19}")
                print("-" * 60)
                
                for i, row in enumerate(profile_results, 1):
                    user_id = row['user_id'][:18] + '...' if len(row['user_id']) > 20 else row['user_id']
                    profile_count = row['profile_count'] or 0
                    last_update = self.format_timestamp(row['last_profile_update'])
                    
                    print(f"{i:<4} {user_id:<20} {profile_count:<8} {last_update:<19}")
            
            print()
            print("🗂️  User Blob Statistics:")
            
            # Get blob statistics
            query = """
            SELECT 
                user_id,
                COUNT(blob_id) as blob_count,
                MAX(updated_at) as last_blob_update
            FROM blob_content
            GROUP BY user_id
            ORDER BY blob_count DESC
            LIMIT 10
            """
            
            self.cursor.execute(query)
            blob_results = self.cursor.fetchall()
            
            if blob_results:
                print(f"{'Rank':<4} {'User ID':<20} {'Blobs':<6} {'Last Update':<19}")
                print("-" * 55)
                
                for i, row in enumerate(blob_results, 1):
                    user_id = row['user_id'][:18] + '...' if len(row['user_id']) > 20 else row['user_id']
                    blob_count = row['blob_count'] or 0
                    last_update = self.format_timestamp(row['last_blob_update'])
                    
                    print(f"{i:<4} {user_id:<20} {blob_count:<6} {last_update:<19}")
            
            # Show overall statistics
            print()
            print("📊 Overall Statistics:")
            
            # Get total profile count
            self.cursor.execute("SELECT COUNT(*) as total FROM user_profiles")
            total_profiles = self.cursor.fetchone()['total']
            
            # Get total blob count
            self.cursor.execute("SELECT COUNT(*) as total FROM blob_content")
            total_blobs = self.cursor.fetchone()['total']
            
            # Get unique users in profiles
            self.cursor.execute("SELECT COUNT(DISTINCT user_id) as unique_users FROM user_profiles")
            unique_profile_users = self.cursor.fetchone()['unique_users']
            
            # Get unique users in blobs
            self.cursor.execute("SELECT COUNT(DISTINCT user_id) as unique_users FROM blob_content")
            unique_blob_users = self.cursor.fetchone()['unique_users']
            
            print(f"   📋 Total Profiles: {total_profiles}")
            print(f"   🗂️  Total Blobs: {total_blobs}")
            print(f"   👤 Users with Profiles: {unique_profile_users}")
            print(f"   👤 Users with Blobs: {unique_blob_users}")
            
        except Exception as e:
            print(f"❌ Error generating user summary: {e}")
    
    def run(self):
        """Main execution function"""
        print("=" * 100)
        print("🗄️  Lindorm Database Content Viewer")
        print("=" * 100)
        
        if not self.connect():
            return
        
        try:
            # Display blob content
            self.display_blob_content(limit=5)
            
            # Display user profiles
            self.display_user_profiles(limit=15)
            
            # Display user summary
            self.display_user_summary()
            
        except KeyboardInterrupt:
            print("\n⏹️  Display interrupted by user")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.disconnect()


def main():
    """Main function"""
    try:
        viewer = LindormDatabaseViewer()
        viewer.run()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()