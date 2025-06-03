"""
Supabase client utilities for interacting with Supabase services.
"""

from typing import Dict, List, Optional, Any, Union
from flask import current_app
from supabase import create_client, Client
import os
import json
from datetime import datetime
import tempfile
import uuid


class SupabaseClient:
    """Wrapper class for Supabase client operations."""
    
    def __init__(self):
        """Initialize Supabase client."""
        self._client = None
    
    @property
    def client(self) -> Client:
        """Get or create Supabase client instance."""
        if self._client is None:
            url = current_app.config.get('SUPABASE_URL')
            key = current_app.config.get('SUPABASE_KEY')
            
            if not url or not key:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY must be configured")
            
            self._client = create_client(url, key)
        
        return self._client


# Global client instance
_supabase_client = SupabaseClient()


def get_supabase_client() -> Client:
    """Get configured Supabase client."""
    return _supabase_client.client


def upload_file(bucket: str, file_path: str, file_data: Union[bytes, str], 
                content_type: str = None, upsert: bool = False) -> Dict:
    """
    Upload a file to Supabase Storage.
    
    Args:
        bucket: Storage bucket name
        file_path: Path/name for the file in storage
        file_data: File data as bytes or string
        content_type: MIME type of the file
        upsert: Whether to overwrite existing file
    
    Returns:
        Dict with upload result and file URL
    """
    client = get_supabase_client()
    
    try:
        # Convert string to bytes if needed
        if isinstance(file_data, str):
            file_data = file_data.encode('utf-8')
        
        # Upload file
        response = client.storage.from_(bucket).upload(
            file_path,
            file_data,
            file_options={
                'content-type': content_type,
                'upsert': upsert
            }
        )
        
        # Get public URL
        public_url = client.storage.from_(bucket).get_public_url(file_path)
        
        return {
            'success': True,
            'file_path': file_path,
            'public_url': public_url,
            'size': len(file_data),
            'response': response
        }
        
    except Exception as e:
        current_app.logger.error(f"Error uploading file to Supabase: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def download_file(bucket: str, file_path: str) -> Dict:
    """
    Download a file from Supabase Storage.
    
    Args:
        bucket: Storage bucket name
        file_path: Path of the file in storage
    
    Returns:
        Dict with file data or error
    """
    client = get_supabase_client()
    
    try:
        response = client.storage.from_(bucket).download(file_path)
        
        return {
            'success': True,
            'data': response,
            'size': len(response) if response else 0
        }
        
    except Exception as e:
        current_app.logger.error(f"Error downloading file from Supabase: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def delete_file(bucket: str, file_path: str) -> Dict:
    """
    Delete a file from Supabase Storage.
    
    Args:
        bucket: Storage bucket name
        file_path: Path of the file to delete
    
    Returns:
        Dict with operation result
    """
    client = get_supabase_client()
    
    try:
        response = client.storage.from_(bucket).remove([file_path])
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        current_app.logger.error(f"Error deleting file from Supabase: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def get_file_url(bucket: str, file_path: str, expires_in: int = None) -> str:
    """
    Get public URL for a file in Supabase Storage.
    
    Args:
        bucket: Storage bucket name
        file_path: Path of the file
        expires_in: URL expiration time in seconds (for private files)
    
    Returns:
        Public URL string
    """
    client = get_supabase_client()
    
    try:
        if expires_in:
            # Create signed URL for private files
            response = client.storage.from_(bucket).create_signed_url(file_path, expires_in)
            return response.get('signedURL', '')
        else:
            # Get public URL
            return client.storage.from_(bucket).get_public_url(file_path)
    except Exception as e:
        current_app.logger.error(f"Error getting file URL from Supabase: {e}")
        return ""


def list_files(bucket: str, folder: str = None, limit: int = 100, 
               search: str = None) -> List[Dict]:
    """
    List files in a Supabase Storage bucket.
    
    Args:
        bucket: Storage bucket name
        folder: Folder path to list (optional)
        limit: Maximum number of files to return
        search: Search query for file names
    
    Returns:
        List of file objects
    """
    client = get_supabase_client()
    
    try:
        options = {'limit': limit}
        if search:
            options['search'] = search
        
        response = client.storage.from_(bucket).list(folder, options)
        
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error listing files from Supabase: {e}")
        return []


def create_bucket(bucket_name: str, public: bool = False) -> Dict:
    """
    Create a new storage bucket.
    
    Args:
        bucket_name: Name of the bucket to create
        public: Whether the bucket should be public
    
    Returns:
        Dict with operation result
    """
    client = get_supabase_client()
    
    try:
        response = client.storage.create_bucket(bucket_name, {'public': public})
        
        return {
            'success': True,
            'bucket_name': bucket_name,
            'response': response
        }
        
    except Exception as e:
        current_app.logger.error(f"Error creating bucket in Supabase: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def update_file_metadata(bucket: str, file_path: str, metadata: Dict) -> Dict:
    """
    Update file metadata in Supabase Storage.
    
    Args:
        bucket: Storage bucket name
        file_path: Path of the file
        metadata: Metadata dictionary to update
    
    Returns:
        Dict with operation result
    """
    client = get_supabase_client()
    
    try:
        response = client.storage.from_(bucket).update(file_path, metadata)
        
        return {
            'success': True,
            'response': response
        }
        
    except Exception as e:
        current_app.logger.error(f"Error updating file metadata in Supabase: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# Database Operations

def execute_query(query: str, params: Dict = None) -> List[Dict]:
    """
    Execute a raw SQL query using Supabase.
    
    Args:
        query: SQL query string
        params: Query parameters
    
    Returns:
        Query results as list of dictionaries
    """
    client = get_supabase_client()
    
    try:
        # Use Supabase RPC for raw queries
        response = client.rpc('execute_query', {
            'query': query,
            'params': json.dumps(params or {})
        }).execute()
        
        return response.data
        
    except Exception as e:
        current_app.logger.error(f"Error executing query in Supabase: {e}")
        return []


def upsert_data(table: str, data: Union[Dict, List[Dict]], 
                on_conflict: str = None) -> Dict:
    """
    Insert or update data in a Supabase table.
    
    Args:
        table: Table name
        data: Data to upsert (single dict or list of dicts)
        on_conflict: Columns to use for conflict resolution
    
    Returns:
        Dict with operation result
    """
    client = get_supabase_client()
    
    try:
        query = client.table(table)
        
        if on_conflict:
            response = query.upsert(data, on_conflict=on_conflict).execute()
        else:
            response = query.upsert(data).execute()
        
        return {
            'success': True,
            'data': response.data,
            'count': len(response.data) if response.data else 0
        }
        
    except Exception as e:
        current_app.logger.error(f"Error upserting data in Supabase: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def select_data(table: str, columns: str = "*", filters: Dict = None, 
                order_by: str = None, limit: int = None) -> List[Dict]:
    """
    Select data from a Supabase table.
    
    Args:
        table: Table name
        columns: Columns to select
        filters: Filter conditions
        order_by: Order by clause
        limit: Maximum number of records
    
    Returns:
        List of records
    """
    client = get_supabase_client()
    
    try:
        query = client.table(table).select(columns)
        
        # Apply filters
        if filters:
            for key, value in filters.items():
                if isinstance(value, dict):
                    # Handle complex filters like {'gte': 10}
                    for op, val in value.items():
                        query = getattr(query, op)(key, val)
                else:
                    query = query.eq(key, value)
        
        # Apply ordering
        if order_by:
            desc = order_by.startswith('-')
            column = order_by.lstrip('-')
            query = query.order(column, desc=desc)
        
        # Apply limit
        if limit:
            query = query.limit(limit)
        
        response = query.execute()
        return response.data
        
    except Exception as e:
        current_app.logger.error(f"Error selecting data from Supabase: {e}")
        return []


def delete_data(table: str, filters: Dict) -> Dict:
    """
    Delete data from a Supabase table.
    
    Args:
        table: Table name
        filters: Filter conditions for deletion
    
    Returns:
        Dict with operation result
    """
    client = get_supabase_client()
    
    try:
        query = client.table(table)
        
        # Apply filters
        for key, value in filters.items():
            query = query.eq(key, value)
        
        response = query.delete().execute()
        
        return {
            'success': True,
            'deleted_count': len(response.data) if response.data else 0
        }
        
    except Exception as e:
        current_app.logger.error(f"Error deleting data from Supabase: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# Realtime subscriptions

def create_realtime_subscription(table: str, callback_function,
                               event: str = '*', schema: str = 'public'):
    """
    Create a real-time subscription to table changes.
    
    Args:
        table: Table to subscribe to
        callback_function: Function to call when changes occur
        event: Type of event to listen for (* for all)
        schema: Database schema
    
    Returns:
        Subscription object
    """
    client = get_supabase_client()
    
    try:
        subscription = (
            client
            .channel(f'{table}_changes')
            .on(
                'postgres_changes',
                {
                    'event': event,
                    'schema': schema,
                    'table': table
                },
                callback_function
            )
            .subscribe()
        )
        
        return subscription
        
    except Exception as e:
        current_app.logger.error(f"Error creating realtime subscription: {e}")
        return None


# Authentication helpers (if using Supabase Auth)

def create_auth_user(email: str, password: str, user_metadata: Dict = None) -> Dict:
    """
    Create a new user with Supabase Auth.
    
    Args:
        email: User email
        password: User password
        user_metadata: Additional user metadata
    
    Returns:
        Dict with user creation result
    """
    client = get_supabase_client()
    
    try:
        response = client.auth.sign_up({
            'email': email,
            'password': password,
            'options': {
                'user_metadata': user_metadata or {}
            }
        })
        
        return {
            'success': True,
            'user': response.user,
            'session': response.session
        }
        
    except Exception as e:
        current_app.logger.error(f"Error creating auth user: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def sign_in_user(email: str, password: str) -> Dict:
    """
    Sign in a user with Supabase Auth.
    
    Args:
        email: User email
        password: User password
    
    Returns:
        Dict with sign-in result
    """
    client = get_supabase_client()
    
    try:
        response = client.auth.sign_in_with_password({
            'email': email,
            'password': password
        })
        
        return {
            'success': True,
            'user': response.user,
            'session': response.session
        }
        
    except Exception as e:
        current_app.logger.error(f"Error signing in user: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# Utility functions

def backup_table_to_storage(table: str, bucket: str, 
                           backup_name: str = None) -> Dict:
    """
    Backup a table to Supabase Storage as JSON.
    
    Args:
        table: Table name to backup
        bucket: Storage bucket name
        backup_name: Name for the backup file
    
    Returns:
        Dict with backup result
    """
    client = get_supabase_client()
    
    try:
        # Get all data from table
        data = select_data(table)
        
        # Create backup filename
        if not backup_name:
            backup_name = f"{table}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Convert to JSON
        backup_data = json.dumps(data, indent=2, default=str)
        
        # Upload to storage
        result = upload_file(bucket, f"backups/{backup_name}", backup_data, 
                           content_type='application/json')
        
        return {
            'success': result['success'],
            'backup_name': backup_name,
            'records_count': len(data),
            'file_url': result.get('public_url')
        }
        
    except Exception as e:
        current_app.logger.error(f"Error backing up table: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def restore_table_from_storage(table: str, bucket: str, 
                              backup_name: str) -> Dict:
    """
    Restore a table from a backup in Supabase Storage.
    
    Args:
        table: Table name to restore
        bucket: Storage bucket name
        backup_name: Name of the backup file
    
    Returns:
        Dict with restore result
    """
    client = get_supabase_client()
    
    try:
        # Download backup file
        backup_data = download_file(bucket, f"backups/{backup_name}")
        
        if not backup_data['success']:
            return backup_data
        
        # Parse JSON data
        data = json.loads(backup_data['data'])
        
        # Restore data to table
        result = upsert_data(table, data)
        
        return {
            'success': result['success'],
            'restored_records': result.get('count', 0),
            'error': result.get('error')
        }
        
    except Exception as e:
        current_app.logger.error(f"Error restoring table: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def get_storage_usage(bucket: str = None) -> Dict:
    """Get storage usage statistics."""
    client = get_supabase_client()
    
    try:
        if bucket:
            # Get usage for specific bucket
            files = list_files(bucket)
            total_size = sum(file.get('size', 0) for file in files)
            return {
                'bucket': bucket,
                'file_count': len(files),
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024)
            }
        else:
            # Get all buckets
            response = client.storage.list_buckets()
            bucket_stats = []
            
            for bucket_info in response:
                bucket_name = bucket_info['name']
                files = list_files(bucket_name)
                total_size = sum(file.get('size', 0) for file in files)
                
                bucket_stats.append({
                    'bucket': bucket_name,
                    'file_count': len(files),
                    'total_size_bytes': total_size,
                    'total_size_mb': total_size / (1024 * 1024)
                })
            
            return {
                'buckets': bucket_stats,
                'total_buckets': len(bucket_stats)
            }
            
    except Exception as e:
        current_app.logger.error(f"Error getting storage usage: {e}")
        return {
            'success': False,
            'error': str(e)
        }