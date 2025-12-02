"""
Redis Job Queue - Resilient domain processing with checkpoints and retries
Enables overnight runs with resume capability
"""

import os
import json
import time
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


class RedisJobQueue:
    """Redis-based job queue for resilient crawling"""
    
    KEYS = {
        'pending': 'crawler:queue:pending',
        'processing': 'crawler:queue:processing',
        'completed': 'crawler:queue:completed',
        'failed': 'crawler:queue:failed',
        'retry': 'crawler:queue:retry',
        'stats': 'crawler:stats',
        'checkpoint': 'crawler:checkpoint',
    }
    
    def __init__(self, redis_url: str = None):
        import redis
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        self.redis = redis.from_url(self.redis_url, decode_responses=True)
        self.max_retries = 3
        self.retry_delays = [60, 300, 900]  # 1min, 5min, 15min
        
    def add_domains(self, domains: List[str], clear_existing: bool = False):
        """Add domains to the pending queue"""
        if clear_existing:
            self.clear_all()
        
        pipe = self.redis.pipeline()
        for domain in domains:
            job = {
                'domain': domain,
                'status': JobStatus.PENDING.value,
                'attempts': 0,
                'created_at': datetime.now().isoformat(),
                'strategy': 'direct',
            }
            pipe.rpush(self.KEYS['pending'], json.dumps(job))
        
        pipe.execute()
        logger.info(f"Added {len(domains)} domains to queue")
        
        # Update stats
        self.redis.hset(self.KEYS['stats'], 'total_domains', len(domains))
        self.redis.hset(self.KEYS['stats'], 'started_at', datetime.now().isoformat())
    
    def get_next_job(self) -> Optional[Dict]:
        """Get next job from pending queue (atomic operation)"""
        # First check retry queue for jobs ready to retry
        retry_job = self._get_retry_job()
        if retry_job:
            return retry_job
        
        # Get from pending queue
        job_data = self.redis.lpop(self.KEYS['pending'])
        if not job_data:
            return None
        
        job = json.loads(job_data)
        job['status'] = JobStatus.PROCESSING.value
        job['started_at'] = datetime.now().isoformat()
        
        # Add to processing set
        self.redis.sadd(self.KEYS['processing'], json.dumps(job))
        
        return job
    
    def _get_retry_job(self) -> Optional[Dict]:
        """Get a job that's ready for retry"""
        now = time.time()
        
        # Check all retry jobs
        retry_jobs = self.redis.lrange(self.KEYS['retry'], 0, -1)
        for job_data in retry_jobs:
            job = json.loads(job_data)
            retry_after = job.get('retry_after', 0)
            
            if now >= retry_after:
                # Remove from retry queue
                self.redis.lrem(self.KEYS['retry'], 1, job_data)
                
                # Update job
                job['status'] = JobStatus.PROCESSING.value
                job['started_at'] = datetime.now().isoformat()
                
                # Add to processing
                self.redis.sadd(self.KEYS['processing'], json.dumps(job))
                
                return job
        
        return None
    
    def complete_job(self, job: Dict, result: Dict = None):
        """Mark job as completed"""
        job['status'] = JobStatus.COMPLETED.value
        job['completed_at'] = datetime.now().isoformat()
        job['result'] = result or {}
        
        # Remove from processing
        self._remove_from_processing(job['domain'])
        
        # Add to completed
        self.redis.rpush(self.KEYS['completed'], json.dumps(job))
        
        # Update stats
        self.redis.hincrby(self.KEYS['stats'], 'completed', 1)
        
        # Save checkpoint
        self._save_checkpoint()
    
    def fail_job(self, job: Dict, error: str, retry: bool = True):
        """Mark job as failed, optionally schedule retry"""
        job['error'] = error
        job['failed_at'] = datetime.now().isoformat()
        job['attempts'] = job.get('attempts', 0) + 1
        
        # Remove from processing
        self._remove_from_processing(job['domain'])
        
        if retry and job['attempts'] < self.max_retries:
            # Schedule retry with next strategy
            strategies = ['direct', 'proxy', 'stealth', 'wayback']
            current_idx = strategies.index(job.get('strategy', 'direct'))
            next_idx = min(current_idx + 1, len(strategies) - 1)
            
            job['strategy'] = strategies[next_idx]
            job['status'] = JobStatus.RETRY.value
            job['retry_after'] = time.time() + self.retry_delays[min(job['attempts'], len(self.retry_delays)) - 1]
            
            self.redis.rpush(self.KEYS['retry'], json.dumps(job))
            self.redis.hincrby(self.KEYS['stats'], 'retries', 1)
            logger.info(f"Scheduled retry for {job['domain']} with strategy {job['strategy']}")
        else:
            # Permanent failure
            job['status'] = JobStatus.FAILED.value
            self.redis.rpush(self.KEYS['failed'], json.dumps(job))
            self.redis.hincrby(self.KEYS['stats'], 'failed', 1)
            logger.warning(f"Permanent failure for {job['domain']}: {error}")
        
        self._save_checkpoint()
    
    def _remove_from_processing(self, domain: str):
        """Remove a job from processing set"""
        processing = self.redis.smembers(self.KEYS['processing'])
        for job_data in processing:
            job = json.loads(job_data)
            if job.get('domain') == domain:
                self.redis.srem(self.KEYS['processing'], job_data)
                break
    
    def _save_checkpoint(self):
        """Save progress checkpoint"""
        stats = self.get_stats()
        checkpoint = {
            'timestamp': datetime.now().isoformat(),
            'stats': stats,
        }
        self.redis.set(self.KEYS['checkpoint'], json.dumps(checkpoint))
    
    def get_stats(self) -> Dict:
        """Get queue statistics"""
        return {
            'pending': self.redis.llen(self.KEYS['pending']),
            'processing': self.redis.scard(self.KEYS['processing']),
            'completed': self.redis.llen(self.KEYS['completed']),
            'failed': self.redis.llen(self.KEYS['failed']),
            'retry': self.redis.llen(self.KEYS['retry']),
            'total': int(self.redis.hget(self.KEYS['stats'], 'total_domains') or 0),
            'retries': int(self.redis.hget(self.KEYS['stats'], 'retries') or 0),
        }
    
    def get_progress(self) -> float:
        """Get completion percentage"""
        stats = self.get_stats()
        total = stats['total']
        if total == 0:
            return 0.0
        completed = stats['completed'] + stats['failed']
        return (completed / total) * 100
    
    def is_complete(self) -> bool:
        """Check if all jobs are processed"""
        stats = self.get_stats()
        return stats['pending'] == 0 and stats['processing'] == 0 and stats['retry'] == 0
    
    def resume(self) -> bool:
        """Resume from checkpoint (move stale processing back to pending)"""
        # Move any stale processing jobs back to pending
        processing = self.redis.smembers(self.KEYS['processing'])
        for job_data in processing:
            job = json.loads(job_data)
            job['status'] = JobStatus.PENDING.value
            self.redis.rpush(self.KEYS['pending'], json.dumps(job))
        
        self.redis.delete(self.KEYS['processing'])
        
        logger.info(f"Resumed: moved {len(processing)} stale jobs back to pending")
        return len(processing) > 0
    
    def clear_all(self):
        """Clear all queues"""
        for key in self.KEYS.values():
            self.redis.delete(key)
        logger.info("Cleared all queues")
    
    def get_completed_domains(self) -> List[str]:
        """Get list of completed domains"""
        completed = self.redis.lrange(self.KEYS['completed'], 0, -1)
        return [json.loads(j)['domain'] for j in completed]
    
    def get_failed_domains(self) -> List[Dict]:
        """Get list of failed domains with errors"""
        failed = self.redis.lrange(self.KEYS['failed'], 0, -1)
        return [json.loads(j) for j in failed]


# Singleton instance
_job_queue = None

def get_job_queue() -> RedisJobQueue:
    global _job_queue
    if _job_queue is None:
        _job_queue = RedisJobQueue()
    return _job_queue
