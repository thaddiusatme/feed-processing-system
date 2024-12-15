import pytest
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from feed_processor.database import Database, ConnectionPool, DatabaseError

class TestDatabaseOptimization:
    @pytest.fixture
    def db(self, tmp_path):
        db_path = tmp_path / "test.db"
        return Database(
            database=str(db_path),
            min_connections=2,
            max_connections=10
        )
    
    def test_connection_pool_reuse(self, db):
        """Test that connections are properly reused from the pool."""
        with db.pool.get_connection() as conn1:
            conn1_id = id(conn1)
        
        with db.pool.get_connection() as conn2:
            conn2_id = id(conn2)
        
        # Should reuse the same connection
        assert conn1_id == conn2_id
    
    def test_concurrent_transactions(self, db):
        """Test concurrent transactions with proper isolation."""
        def worker(feed_id: int):
            feed_data = {
                "id": f"feed_{feed_id}",
                "url": f"http://example.com/feed_{feed_id}",
                "status": "pending"
            }
            with db.transaction() as tx:
                tx.add_feed(feed_data)
                time.sleep(0.1)  # Simulate some work
        
        # Run concurrent transactions
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, i) for i in range(10)]
            for future in futures:
                future.result()
        
        # Verify all feeds were added
        with db.pool.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM feeds")
            count = cursor.fetchone()[0]
            assert count == 10
    
    def test_connection_pool_overflow(self, db):
        """Test handling of connection pool overflow."""
        connections = []
        try:
            # Try to get more connections than max_connections
            for _ in range(db.pool.max_connections + 1):
                connections.append(db.pool.get_connection())
            pytest.fail("Should have raised DatabaseError")
        except DatabaseError as e:
            assert "Connection pool exhausted" in str(e)
        finally:
            for conn in connections:
                conn.close()
    
    def test_transaction_isolation(self, db):
        """Test transaction isolation levels."""
        feed_data = {"id": "test_feed", "url": "http://example.com", "status": "pending"}
        
        def transaction1():
            with db.transaction() as tx:
                tx.add_feed(feed_data)
                time.sleep(0.2)  # Hold transaction
                raise Exception("Rollback transaction")
        
        def transaction2():
            time.sleep(0.1)  # Start after transaction1
            with db.pool.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM feeds")
                return cursor.fetchone()[0]
        
        # Run transactions in separate threads
        with ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(transaction1)
            future2 = executor.submit(transaction2)
            
            # Transaction2 should see 0 records due to isolation
            assert future2.result() == 0
            
            # Transaction1 should rollback
            with pytest.raises(Exception):
                future1.result()
    
    def test_connection_timeout(self, db):
        """Test connection acquisition timeout."""
        connections = []
        start_time = time.time()
        
        try:
            # Hold all connections
            for _ in range(db.pool.max_connections):
                connections.append(db.pool.get_connection())
            
            # Try to get one more connection
            with pytest.raises(DatabaseError) as exc_info:
                db.pool.get_connection()
            
            duration = time.time() - start_time
            assert duration >= db.pool.timeout
            assert "Connection pool exhausted" in str(exc_info.value)
            
        finally:
            for conn in connections:
                conn.close()
    
    @pytest.mark.parametrize("isolation_level", ["DEFERRED", "IMMEDIATE", "EXCLUSIVE"])
    def test_transaction_isolation_levels(self, db, isolation_level):
        """Test different transaction isolation levels."""
        with db.transaction(isolation_level=isolation_level) as tx:
            feed_data = {
                "id": f"feed_{isolation_level}",
                "url": "http://example.com",
                "status": "pending"
            }
            tx.add_feed(feed_data)
