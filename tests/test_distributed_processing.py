import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from feed_processor.content_enhancement.models import ContentItem, EnhancementResult
from feed_processor.distributed.worker_manager import (
    HealthMonitor,
    TaskDistributor,
    WorkerManager,
    WorkerNode,
    WorkerStatus,
)


class TestWorkerNode:
    @pytest.fixture
    def worker_node(self):
        return WorkerNode(id="worker-1", host="localhost", port=5000, capacity=10)

    def test_worker_node_creation(self, worker_node):
        """Test worker node initialization"""
        assert worker_node.id == "worker-1"
        assert worker_node.host == "localhost"
        assert worker_node.port == 5000
        assert worker_node.capacity == 10
        assert worker_node.status == WorkerStatus.IDLE
        assert worker_node.current_load == 0
        assert worker_node.last_heartbeat is not None

    def test_worker_node_load_calculation(self, worker_node):
        """Test worker load calculation"""
        worker_node.current_load = 5
        assert worker_node.load_percentage == 50  # 5/10 * 100

        worker_node.current_load = 10
        assert worker_node.load_percentage == 100

        worker_node.current_load = 0
        assert worker_node.load_percentage == 0

    def test_worker_node_health_check(self, worker_node):
        """Test worker health check logic"""
        # Recent heartbeat
        assert worker_node.is_healthy()

        # Old heartbeat
        worker_node.last_heartbeat = datetime.utcnow() - timedelta(minutes=5)
        assert not worker_node.is_healthy()

        # Update heartbeat
        worker_node.update_heartbeat()
        assert worker_node.is_healthy()


class TestHealthMonitor:
    @pytest.fixture
    def health_monitor(self):
        return HealthMonitor(heartbeat_interval=1, health_check_interval=5, unhealthy_threshold=60)

    @pytest.fixture
    def mock_worker_nodes(self):
        return [
            WorkerNode(id=f"worker-{i}", host="localhost", port=5000 + i, capacity=10)
            for i in range(3)
        ]

    @pytest.mark.asyncio
    async def test_health_check_healthy_workers(self, health_monitor, mock_worker_nodes):
        """Test health check with healthy workers"""
        for node in mock_worker_nodes:
            health_monitor.register_worker(node)

        unhealthy_workers = await health_monitor.check_workers_health()
        assert len(unhealthy_workers) == 0

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_workers(self, health_monitor, mock_worker_nodes):
        """Test health check with unhealthy workers"""
        # Make one worker unhealthy
        mock_worker_nodes[1].last_heartbeat = datetime.utcnow() - timedelta(minutes=2)

        for node in mock_worker_nodes:
            health_monitor.register_worker(node)

        unhealthy_workers = await health_monitor.check_workers_health()
        assert len(unhealthy_workers) == 1
        assert unhealthy_workers[0].id == "worker-1"

    @pytest.mark.asyncio
    async def test_worker_recovery(self, health_monitor, mock_worker_nodes):
        """Test worker recovery after being unhealthy"""
        worker = mock_worker_nodes[0]
        worker.last_heartbeat = datetime.utcnow() - timedelta(minutes=2)
        health_monitor.register_worker(worker)

        # First check - worker should be unhealthy
        unhealthy_workers = await health_monitor.check_workers_health()
        assert len(unhealthy_workers) == 1

        # Simulate worker recovery
        worker.update_heartbeat()

        # Second check - worker should be healthy
        unhealthy_workers = await health_monitor.check_workers_health()
        assert len(unhealthy_workers) == 0


class TestTaskDistributor:
    @pytest.fixture
    def task_distributor(self):
        return TaskDistributor(min_worker_capacity=2, max_retries=3, retry_delay=1)

    @pytest.fixture
    def mock_workers(self):
        return [
            WorkerNode(id=f"worker-{i}", host="localhost", port=5000 + i, capacity=10)
            for i in range(3)
        ]

    @pytest.fixture
    def test_content_item(self):
        return ContentItem(
            title="Test Article",
            content="Test content",
            source_url="https://example.com/test",
            published_date=datetime.utcnow(),
            metadata={},
        )

    @pytest.mark.asyncio
    async def test_task_distribution(self, task_distributor, mock_workers, test_content_item):
        """Test task distribution among workers"""
        for worker in mock_workers:
            task_distributor.register_worker(worker)

        # Distribute multiple tasks
        assignments = []
        for _ in range(5):
            worker = await task_distributor.get_available_worker()
            assignments.append(worker)
            worker.current_load += 1

        assert len(assignments) == 5
        # Verify load distribution
        worker_loads = {w.id: w.current_load for w in mock_workers}
        assert (
            max(worker_loads.values()) - min(worker_loads.values()) <= 1
        )  # Load difference should be at most 1

    @pytest.mark.asyncio
    async def test_overloaded_workers(self, task_distributor, mock_workers):
        """Test behavior when all workers are overloaded"""
        for worker in mock_workers:
            worker.current_load = worker.capacity
            task_distributor.register_worker(worker)

        with pytest.raises(Exception, match="No available workers"):
            await task_distributor.get_available_worker()

    @pytest.mark.asyncio
    async def test_worker_selection_strategy(self, task_distributor, mock_workers):
        """Test worker selection strategy based on load"""
        for worker in mock_workers:
            task_distributor.register_worker(worker)

        # Set different loads
        mock_workers[0].current_load = 2  # 20%
        mock_workers[1].current_load = 5  # 50%
        mock_workers[2].current_load = 8  # 80%

        # Should select least loaded worker
        selected_worker = await task_distributor.get_available_worker()
        assert selected_worker.id == mock_workers[0].id


class TestWorkerManager:
    @pytest.fixture
    def worker_manager(self):
        return WorkerManager(
            min_workers=2,
            max_workers=5,
            scaling_threshold=80,
            worker_startup_timeout=10,
            metrics_collector=Mock(),
        )

    @pytest.fixture
    def mock_container_client(self):
        client = Mock()
        client.create_container = AsyncMock()
        client.stop_container = AsyncMock()
        client.list_containers = AsyncMock(return_value=[])
        return client

    @pytest.mark.asyncio
    async def test_scale_up_creates_new_workers(self, worker_manager, mock_container_client):
        """Test scaling up creates new worker containers"""
        worker_manager.container_client = mock_container_client

        # Add initial workers at high load
        initial_workers = [
            WorkerNode(id=f"worker-{i}", host="localhost", port=5000 + i, capacity=10)
            for i in range(2)
        ]
        for worker in initial_workers:
            worker.current_load = 9  # 90% load
            await worker_manager.register_worker(worker)

        # Trigger scale up
        await worker_manager._scale_up()

        # Verify new container was created
        mock_container_client.create_container.assert_called()
        assert mock_container_client.create_container.call_count == 1

        # Verify metrics were collected
        worker_manager.metrics_collector.increment.assert_called_with("workers_scaled_up")

    @pytest.mark.asyncio
    async def test_scale_up_respects_max_workers(self, worker_manager, mock_container_client):
        """Test scaling up respects maximum worker limit"""
        worker_manager.container_client = mock_container_client

        # Add maximum number of workers
        for i in range(worker_manager.max_workers):
            worker = WorkerNode(id=f"worker-{i}", host="localhost", port=5000 + i, capacity=10)
            await worker_manager.register_worker(worker)

        # Attempt to scale up
        await worker_manager._scale_up()

        # Verify no new containers were created
        mock_container_client.create_container.assert_not_called()
        worker_manager.metrics_collector.increment.assert_called_with("scale_up_rejected")

    @pytest.mark.asyncio
    async def test_scale_down_removes_workers(self, worker_manager, mock_container_client):
        """Test scaling down removes workers gracefully"""
        worker_manager.container_client = mock_container_client

        # Add workers with low load
        workers = [
            WorkerNode(id=f"worker-{i}", host="localhost", port=5000 + i, capacity=10)
            for i in range(4)  # More than min_workers
        ]
        for worker in workers:
            worker.current_load = 1  # 10% load
            await worker_manager.register_worker(worker)

        # Trigger scale down
        await worker_manager._scale_down()

        # Verify container was stopped
        mock_container_client.stop_container.assert_called()
        assert len(worker_manager.get_active_workers()) >= worker_manager.min_workers

    @pytest.mark.asyncio
    async def test_scale_down_respects_min_workers(self, worker_manager, mock_container_client):
        """Test scaling down respects minimum worker limit"""
        worker_manager.container_client = mock_container_client

        # Add minimum number of workers
        for i in range(worker_manager.min_workers):
            worker = WorkerNode(id=f"worker-{i}", host="localhost", port=5000 + i, capacity=10)
            await worker_manager.register_worker(worker)

        # Attempt to scale down
        await worker_manager._scale_down()

        # Verify no containers were stopped
        mock_container_client.stop_container.assert_not_called()
        worker_manager.metrics_collector.increment.assert_called_with("scale_down_rejected")

    @pytest.mark.asyncio
    async def test_worker_startup_timeout(self, worker_manager, mock_container_client):
        """Test handling of worker startup timeout"""
        worker_manager.container_client = mock_container_client
        mock_container_client.create_container.return_value = "new-worker-id"

        # Simulate timeout by not sending heartbeat
        with pytest.raises(TimeoutError, match="Worker startup timeout"):
            await worker_manager._scale_up()

        worker_manager.metrics_collector.increment.assert_called_with("worker_startup_timeout")

    @pytest.mark.asyncio
    async def test_graceful_worker_shutdown(self, worker_manager, mock_container_client):
        """Test graceful shutdown of workers during scale down"""
        worker_manager.container_client = mock_container_client

        # Add workers
        workers = [
            WorkerNode(id=f"worker-{i}", host="localhost", port=5000 + i, capacity=10)
            for i in range(4)
        ]
        for worker in workers:
            worker.current_load = 1
            await worker_manager.register_worker(worker)

        # Select worker for shutdown
        worker_to_shutdown = workers[-1]

        # Trigger graceful shutdown
        await worker_manager._graceful_shutdown(worker_to_shutdown)

        # Verify worker was marked for shutdown
        assert worker_to_shutdown.status == WorkerStatus.SHUTTING_DOWN

        # Verify tasks were rebalanced
        remaining_workers = worker_manager.get_active_workers()
        assert worker_to_shutdown not in remaining_workers

        # Verify container was stopped
        mock_container_client.stop_container.assert_called_with(worker_to_shutdown.id)

    @pytest.mark.asyncio
    async def test_worker_registration(self, worker_manager):
        """Test worker registration process"""
        worker = WorkerNode(id="worker-1", host="localhost", port=5000, capacity=10)
        await worker_manager.register_worker(worker)

        assert len(worker_manager.get_active_workers()) == 1
        assert worker_manager.get_worker_by_id("worker-1") == worker

    @pytest.mark.asyncio
    async def test_auto_scaling(self, worker_manager):
        """Test automatic scaling based on load"""
        # Add workers with high load
        for i in range(3):
            worker = WorkerNode(id=f"worker-{i}", host="localhost", port=5000 + i, capacity=10)
            worker.current_load = 9  # 90% load
            await worker_manager.register_worker(worker)

        # Should trigger scaling up
        await worker_manager.check_scaling_needs()
        scale_up_calls = len(
            [
                call
                for call in worker_manager.metrics_collector.mock_calls
                if "scale_up" in str(call)
            ]
        )
        assert scale_up_calls > 0

    @pytest.mark.asyncio
    async def test_worker_failure_handling(self, worker_manager):
        """Test handling of worker failures"""
        worker = WorkerNode(id="worker-1", host="localhost", port=5000, capacity=10)
        await worker_manager.register_worker(worker)

        # Simulate worker failure
        worker.last_heartbeat = datetime.utcnow() - timedelta(minutes=5)
        await worker_manager.handle_worker_failure(worker)

        assert worker not in worker_manager.get_active_workers()
        assert worker.status == WorkerStatus.FAILED

    @pytest.mark.asyncio
    async def test_task_rebalancing(self, worker_manager):
        """Test task rebalancing when workers are added or removed"""
        # Add initial workers
        workers = [
            WorkerNode(id=f"worker-{i}", host="localhost", port=5000 + i, capacity=10)
            for i in range(3)
        ]
        for worker in workers:
            await worker_manager.register_worker(worker)
            worker.current_load = 5

        # Add new worker
        new_worker = WorkerNode(id="worker-new", host="localhost", port=5004, capacity=10)
        await worker_manager.register_worker(new_worker)

        # Check if tasks were rebalanced
        await worker_manager.rebalance_tasks()
        loads = [w.current_load for w in worker_manager.get_active_workers()]
        assert max(loads) - min(loads) <= 1  # Load should be evenly distributed
