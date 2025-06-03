# app/services/queue_service.py
import redis
import json
import uuid
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class RedisQueue:
    """
    Redis-based queue service for handling asynchronous tasks
    """
    
    def __init__(self, redis_url, default_queue='default'):
        """Initialize the queue with Redis connection and default queue name"""
        self.redis_conn = redis.from_url(redis_url)
        self.default_queue = default_queue
    
    def enqueue(self, func, *args, queue=None, **kwargs):
        """
        Add a task to the queue
        func: function to execute (or function name as string)
        args, kwargs: arguments to pass to the function
        queue: optional queue name, defaults to self.default_queue
        """
        # Determine which queue to use
        queue_name = queue or self.default_queue
        
        # Create a unique task ID
        task_id = str(uuid.uuid4())
        
        # Prepare the task data
        task_data = {
            'id': task_id,
            'function': func.__name__ if callable(func) else func,
            'args': args,
            'kwargs': kwargs
        }
        
        # Serialize task data
        serialized_task = json.dumps(task_data)
        
        # Add to queue
        self.redis_conn.lpush(f'queue:{queue_name}', serialized_task)
        logger.debug(f"Enqueued task {task_id} to queue '{queue_name}'")
        
        return task_id
    
    def process_queue(self, queue=None, limit=None):
        """
        Process tasks in the queue
        queue: optional queue name, defaults to self.default_queue
        limit: optional maximum number of tasks to process
        """
        queue_name = queue or self.default_queue
        count = 0
        
        while True:
            # Stop if we've reached the limit
            if limit is not None and count >= limit:
                break
            
            # Try to get a task from the queue
            serialized_task = self.redis_conn.rpop(f'queue:{queue_name}')
            if not serialized_task:
                break
            
            try:
                # Deserialize task data
                task_data = json.loads(serialized_task)
                
                # Get function to execute
                func_name = task_data['function']
                
                # Import and execute the function
                module_name, func_name = func_name.rsplit('.', 1) if '.' in func_name else ('app.services.message_handler', func_name)
                module = __import__(module_name, fromlist=[func_name])
                func = getattr(module, func_name)
                
                # Execute function with arguments
                result = func(*task_data['args'], **task_data['kwargs'])
                
                logger.debug(f"Processed task {task_data['id']} from queue '{queue_name}'")
                count += 1
                
            except Exception as e:
                logger.exception(f"Error processing task from queue '{queue_name}': {str(e)}")
                
                # Add task to failure queue for later inspection
                self.redis_conn.lpush(f'queue:{queue_name}:failed', serialized_task)
        
        return count