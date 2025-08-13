# 基于Ray的长期记忆系统架构优化方案

## 方案一：基于Ray Actor的多级Pipeline架构（优化版）

### 1. 架构概述

本方案采用多级Actor Pipeline架构，充分利用Ray的Actor模型实现高并发处理。系统设计简洁高效，采用异步IO和动态负载均衡策略。

### 2. 核心设计理念

- **解耦合**：将Kafka消费、缓冲区管理、LLM调用、数据持久化等环节解耦
- **并行化**：不同用户的数据处理完全并行，互不干扰
- **资源池化**：LLM调用Actor池化管理，数据库连接池化
- **容错性**：每个Actor独立管理生命周期，局部故障不影响整体
- **异步优先**：所有IO操作采用异步处理，避免阻塞
- **简化设计**：去除复杂缓存层，直接与数据库交互

### 3. 系统架构图

```
┌─────────────────────────────────────────────────────────────┐
│                     Ray Cluster                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Kafka      │───▶│   Load       │───▶│   Buffer     │  │
│  │   Consumer   │    │   Balancer   │    │   Manager    │  │
│  │   Actors     │    │   Actor      │    │   Actors     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│       (N个)              (1个)               (M个)          │
│         │                   │                    │          │
│         │                   │                    ▼          │
│         │                   │           ┌──────────────┐   │
│         │                   │           │   Memory     │   │
│         │                   │           │   Processor  │   │
│         │                   │           │   Actor Pool │   │
│         │                   │           └──────────────┘   │
│         │                   │                 (K个)        │
│         │                   │                    │         │
│         │                   │                    ▼         │
│         │                   │           ┌──────────────┐   │
│         │                   │           │   Storage    │   │
│         │                   │           │   Writer     │   │
│         │                   │           │   Actors     │   │
│         │                   │           └──────────────┘   │
│         │                   │                 (P个)        │
│         │                   │                    │         │
│         ▼                   ▼                    ▼         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Monitoring & Metrics Actor              │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4. 核心组件设计

#### 4.1 Kafka Consumer Actors（消息消费层）

```python
@ray.remote
class KafkaConsumerActor:
    """
    负责从特定Kafka分区消费buffer_zone表的CDC消息
    - 每个Actor负责一个或多个分区
    - 监听buffer_zone表的变更事件
    - 实现至少一次(at-least-once)语义
    """
    def __init__(self, partition_ids: List[int], load_balancer_actor):
        self.partitions = partition_ids
        self.load_balancer = load_balancer_actor
        self.consumer = self._init_consumer()
        
    async def consume_messages(self):
        """持续消费buffer_zone表的CDC消息并转发给负载均衡器"""
        while True:
            messages = self.consumer.poll(timeout=1.0)
            # 批量发送以提高效率
            batch = []
            for msg in messages:
                buffer_event = self._parse_buffer_zone_cdc(msg)
                if buffer_event:
                    batch.append(buffer_event)
                    
            if batch:
                # 批量发送给负载均衡器
                await self.load_balancer.route_batch_events.remote(batch)
                
    def _parse_buffer_zone_cdc(self, msg):
        """
        解析buffer_zone表的CDC消息
        提取用户ID和缓冲区变更信息
        """
        try:
            message = json.loads(msg.value())
            after_data = message.get('after', {})
            
            if after_data:
                return {
                    'user_id': after_data.get('user_id'),
                    'buffer_id': after_data.get('buffer_id'),
                    'operation': message.get('op'),
                    'timestamp': after_data.get('updated_at'),
                    'buffer_size': after_data.get('buffer_size', 0),
                    'metadata': after_data.get('metadata', {})
                }
        except Exception as e:
            logger.error(f"Failed to parse buffer_zone CDC: {e}")
            return None
```

#### 4.2 Load Balancer Actor（负载均衡层）

```python
@ray.remote
class LoadBalancerActor:
    """
    负载均衡器，动态分发事件到Buffer Managers
    - 动态负载均衡分发
    - 实时监控各Buffer Manager负载
    - 支持批量路由优化
    """
    def __init__(self, num_buffer_managers: int, processor_pool):
        self.buffer_managers = []
        self.manager_loads = {}  # 各管理器的当前负载
        self.processor_pool = processor_pool
        
        self._init_managers(num_buffer_managers)
        
    def _init_managers(self, count: int):
        """初始化Buffer Manager池"""
        for i in range(count):
            manager = BufferManagerActor.remote(
                manager_id=i, 
                processor_pool=self.processor_pool
            )
            self.buffer_managers.append(manager)
            self.manager_loads[i] = 0
            
    async def route_batch_events(self, events: List[dict]):
        """批量路由事件到Buffer Managers"""
        # 按负载分组事件
        grouped_events = self._group_events_by_load(events)
        
        # 并发发送到各个Manager
        tasks = []
        for manager_id, manager_events in grouped_events.items():
            manager = self.buffer_managers[manager_id]
            task = manager.batch_check_buffers.remote(manager_events)
            tasks.append(task)
            # 更新负载计数
            self.manager_loads[manager_id] += len(manager_events)
            
        # 异步等待所有任务完成
        await asyncio.gather(*tasks, return_exceptions=True)
        
    def _group_events_by_load(self, events: List[dict]) -> dict:
        """根据负载均衡策略分组事件"""
        grouped = {}
        
        for event in events:
            # 选择负载最低的管理器
            manager_id = self._select_least_loaded_manager()
            if manager_id not in grouped:
                grouped[manager_id] = []
            grouped[manager_id].append(event)
            
        return grouped
        
    def _select_least_loaded_manager(self) -> int:
        """选择负载最低的管理器"""
        # 简单的最小负载策略
        return min(self.manager_loads, key=self.manager_loads.get)
        
    async def update_manager_load(self, manager_id: int, completed_count: int):
        """更新管理器负载信息"""
        self.manager_loads[manager_id] = max(0, self.manager_loads[manager_id] - completed_count)
```

#### 4.3 Buffer Manager Actors（缓冲区管理层 - 简化版）

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

@ray.remote
class BufferManagerActor:
    """
    管理用户缓冲区状态检查和处理触发（简化版）
    - 直接与数据库交互，无缓存
    - 异步数据库查询提高吞吐量
    - 批量处理优化
    """
    def __init__(self, manager_id: int, processor_pool):
        self.manager_id = manager_id
        self.processor_pool = processor_pool
        
        # 异步处理组件
        self.db_thread_pool = ThreadPoolExecutor(max_workers=10)
        self.memobase = LindormMemobase()
        
        # 性能统计
        self.stats = {
            'total_checks': 0,
            'buffer_full_count': 0
        }
        
    async def batch_check_buffers(self, events: List[dict]):
        """批量检查多个用户的缓冲区状态"""
        # 去重：同一用户的多个事件只检查一次
        unique_users = {}
        for event in events:
            user_id = event['user_id']
            if user_id not in unique_users:
                unique_users[user_id] = event
                
        # 并发检查所有用户
        tasks = []
        for user_id, event in unique_users.items():
            task = self._async_check_buffer(user_id, event)
            tasks.append(task)
                
        # 等待所有检查完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 更新统计并通知负载均衡器
        completed_count = len([r for r in results if not isinstance(r, Exception)])
        await self.load_balancer.update_manager_load.remote(self.manager_id, completed_count)
        
        return results
        
    async def _async_check_buffer(self, user_id: str, event: dict):
        """异步检查单个用户的缓冲区状态"""
        self.stats['total_checks'] += 1
        
        # 在线程池中执行数据库查询
        loop = asyncio.get_event_loop()
        
        try:
            # 将同步的数据库查询放到线程池执行
            status = await loop.run_in_executor(
                self.db_thread_pool,
                self.memobase.detect_buffer_full_or_not,
                user_id
            )
            
            if status['is_full']:
                self.stats['buffer_full_count'] += 1
                logging.info(f"Buffer full for user {user_id}, triggering processing")
                # 异步提交处理任务
                await self._submit_processing_task(user_id, status['buffer_full_ids'])
            else:
                logging.debug(f"Buffer not full for user {user_id}")
                
            return {'user_id': user_id, 'status': status}
            
        except Exception as e:
            logging.error(f"Error checking buffer for user {user_id}: {e}")
            raise
            
    async def _submit_processing_task(self, user_id: str, blob_ids: List[str]):
        """提交处理任务到处理器池"""
        # 获取可用的处理器
        processor = await self.processor_pool.get_available_processor.remote()
        
        # 异步处理，不阻塞当前Actor
        task_ref = processor.process_user_buffer_async.remote(user_id, blob_ids)
        
        # 记录任务提交
        logging.info(f"Submitted processing task for user {user_id} with {len(blob_ids)} blobs")
        
        return task_ref
        
    def get_stats(self):
        """获取性能统计信息"""
        return self.stats
```

#### 4.4 Memory Processor Actor Pool（记忆处理层 - 简化限流版）

```python
import asyncio
import time

class RateLimitError(Exception):
    """限流错误"""
    pass

@ray.remote(num_cpus=2, num_gpus=0.1)
class MemoryProcessorActor:
    """
    执行实际的记忆抽取处理
    - 简化的自适应并发控制：正常不限制，限流时限制10个并发
    - 1分钟无错误自动恢复
    """
    def __init__(self, processor_id: int):
        self.processor_id = processor_id
        self.memobase = LindormMemobase()
        
        # 简化的并发控制
        self.is_rate_limited = False
        self.last_rate_limit_time = 0
        self.current_concurrent = 0
        
        # 动态信号量
        self.llm_semaphore = None  # 正常状态不使用信号量
        
        # 性能统计
        self.stats = {
            'total_processed': 0,
            'success_count': 0,
            'error_count': 0,
            'rate_limit_count': 0,
            'avg_processing_time': 0,
            'current_concurrency': 0,
            'max_concurrency_reached': 0
        }
        
    async def process_user_buffer_async(self, user_id: str, blob_ids: List[str]):
        """异步处理用户缓冲区数据（简化的自适应并发）"""
        start_time = time.time()
        self.current_concurrent += 1
        
        # 更新最大并发记录
        if self.current_concurrent > self.stats['max_concurrency_reached']:
            self.stats['max_concurrency_reached'] = self.current_concurrent
        
        # 检查是否应该恢复（1分钟无限流错误）
        if self.is_rate_limited and time.time() - self.last_rate_limit_time > 60:
            self.is_rate_limited = False
            self.llm_semaphore = None
            logging.info("No rate limit errors for 1 minute, removing concurrency limit")
        
        try:
            # 根据是否被限流决定是否使用信号量
            if self.llm_semaphore:
                async with self.llm_semaphore:
                    result = await self._call_process_buffer(user_id, blob_ids)
            else:
                # 正常状态，不限制并发
                result = await self._call_process_buffer(user_id, blob_ids)
                
            self.stats['success_count'] += 1
            self.stats['total_processed'] += 1
            
            # 更新平均处理时间
            processing_time = time.time() - start_time
            self._update_avg_time(processing_time)
            
            logging.info(f"Successfully processed user {user_id} in {processing_time:.2f}s, "
                        f"concurrent: {self.current_concurrent}")
            
            return {'success': True, 'user_id': user_id, 'result': result}
                
        except RateLimitError as e:
            # 检测到限流错误，启用并发限制
            if not self.is_rate_limited:
                self.is_rate_limited = True
                self.llm_semaphore = asyncio.Semaphore(10)
                logging.warning(f"Rate limit detected, limiting to 10 concurrent requests")
            
            self.last_rate_limit_time = time.time()
            self.stats['rate_limit_count'] += 1
            
            # 简单等待2秒后重试
            await asyncio.sleep(2)
            return await self.process_user_buffer_async(user_id, blob_ids)
            
        except Exception as e:
            self.stats['error_count'] += 1
            logging.error(f"Failed to process user {user_id}: {e}")
            
            if self._should_retry(e):
                return await self._retry_processing(user_id, blob_ids, e)
                
            return {'success': False, 'user_id': user_id, 'error': str(e)}
            
        finally:
            self.current_concurrent -= 1
            self.stats['current_concurrency'] = self.current_concurrent
            
    async def _call_process_buffer(self, user_id: str, blob_ids: List[str]):
        """调用process_buffer并处理限流"""
        try:
            result = await self.memobase.process_buffer(
                user_id=user_id,
                blob_type=BlobType.chat,
                blob_ids=blob_ids
            )
            return result
        except Exception as e:
            # 检查是否是限流错误
            if self._is_rate_limit_error(e):
                raise RateLimitError(str(e))
            raise
            
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """判断是否是限流错误"""
        error_msg = str(error).lower()
        rate_limit_keywords = [
            'rate limit', 'too many requests', '429',
            'quota exceeded', 'throttled', 'retry after'
        ]
        return any(keyword in error_msg for keyword in rate_limit_keywords)
            
    async def process_batch_users(self, user_batches: List[dict]):
        """批量处理多个用户（并发执行）"""
        tasks = []
        
        # 创建所有处理任务
        for batch in user_batches:
            task = self.process_user_buffer_async(
                batch['user_id'],
                batch['blob_ids']
            )
            tasks.append(task)
            
        # 并发执行所有任务
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get('success'))
        error_count = len(results) - success_count
        
        logging.info(f"Batch processing completed: {success_count} success, {error_count} errors")
        
        return results
        
    def _should_retry(self, error: Exception) -> bool:
        """判断是否应该重试"""
        # 根据错误类型决定是否重试
        retryable_errors = (ConnectionError, TimeoutError)
        return isinstance(error, retryable_errors)
        
    async def _retry_processing(self, user_id: str, blob_ids: List[str], original_error):
        """重试处理逻辑"""
        max_retries = 3
        for attempt in range(max_retries):
            await asyncio.sleep(2 ** attempt)  # 指数退避
            try:
                return await self.process_user_buffer_async(user_id, blob_ids)
            except Exception as e:
                if attempt == max_retries - 1:
                    return {'success': False, 'user_id': user_id, 'error': str(e)}
                    
    def _update_avg_time(self, new_time: float):
        """更新平均处理时间"""
        total = self.stats['total_processed']
        if total == 0:
            self.stats['avg_processing_time'] = new_time
        else:
            # 移动平均
            self.stats['avg_processing_time'] = (
                self.stats['avg_processing_time'] * (total - 1) + new_time
            ) / total
            
    def is_available(self) -> bool:
        """检查处理器是否可用"""
        return self.processing_count < self.max_concurrent
        
    def get_stats(self):
        """获取性能统计"""
        return self.stats
```

#### 4.5 Enhanced Processor Pool Manager（增强的处理器池管理）

```python
@ray.remote
class ProcessorPoolManager:
    """
    增强的Memory Processor池管理器
    - 动态扩缩容
    - 智能负载均衡
    - 健康检查
    - 性能监控
    """
    def __init__(self, initial_size: int = 10, max_size: int = 100):
        self.min_size = initial_size
        self.max_size = max_size
        self.processors = []
        self.processor_stats = {}
        self.available_queue = []
        
        self._init_pool(initial_size)
        
        # 启动监控任务
        self._start_monitoring()
        
    def _init_pool(self, size: int):
        """初始化处理器池"""
        for i in range(size):
            processor = MemoryProcessorActor.remote(processor_id=i)
            self.processors.append(processor)
            self.available_queue.append(processor)
            self.processor_stats[i] = {'status': 'idle', 'tasks_completed': 0}
            
    async def get_available_processor(self):
        """获取可用的处理器（智能选择）"""
        # 先尝试从可用队列获取
        if self.available_queue:
            processor = self.available_queue.pop(0)
            return processor
            
        # 检查是否有空闲的处理器
        for processor in self.processors:
            is_available = await processor.is_available.remote()
            if is_available:
                return processor
                
        # 需要扩容
        if len(self.processors) < self.max_size:
            return await self._expand_pool_and_get()
        else:
            # 达到最大容量，等待可用处理器
            return await self._wait_for_available()
            
    async def _expand_pool_and_get(self):
        """扩容并返回新处理器"""
        new_id = len(self.processors)
        new_processor = MemoryProcessorActor.remote(processor_id=new_id)
        self.processors.append(new_processor)
        self.processor_stats[new_id] = {'status': 'idle', 'tasks_completed': 0}
        
        logging.info(f"Expanded processor pool to {len(self.processors)} processors")
        
        return new_processor
        
    async def _wait_for_available(self):
        """等待可用的处理器"""
        while True:
            for processor in self.processors:
                is_available = await processor.is_available.remote()
                if is_available:
                    return processor
            await asyncio.sleep(0.1)
            
    async def _start_monitoring(self):
        """启动监控任务"""
        async def monitor():
            while True:
                await self._check_pool_health()
                await self._auto_scale()
                await asyncio.sleep(30)  # 每30秒检查一次
                
        # 启动后台监控
        asyncio.create_task(monitor())
        
    async def _check_pool_health(self):
        """检查池健康状态"""
        for i, processor in enumerate(self.processors):
            try:
                stats = await processor.get_stats.remote()
                self.processor_stats[i].update(stats)
            except Exception as e:
                logging.error(f"Processor {i} health check failed: {e}")
                # 可能需要重启该处理器
                
    async def _auto_scale(self):
        """自动扩缩容"""
        # 计算平均负载
        active_count = sum(
            1 for stats in self.processor_stats.values()
            if stats.get('status') != 'idle'
        )
        
        utilization = active_count / len(self.processors)
        
        # 扩容条件：利用率超过80%
        if utilization > 0.8 and len(self.processors) < self.max_size:
            expand_count = min(5, self.max_size - len(self.processors))
            for _ in range(expand_count):
                await self._expand_pool_and_get()
                
        # 缩容条件：利用率低于20%且超过最小规模
        elif utilization < 0.2 and len(self.processors) > self.min_size:
            # 标记多余的处理器准备回收
            excess_count = len(self.processors) - self.min_size
            shrink_count = min(excess_count // 2, 5)  # 每次最多缩容一半或5个
            
            # 实际的缩容逻辑需要确保没有正在处理的任务
            logging.info(f"Pool utilization low ({utilization:.1%}), consider shrinking by {shrink_count}")
```

### 5. 海量租户优化策略

#### 5.1 内存管理优化

- **LRU缓存**：每个Buffer Manager最多缓存10,000个用户记录
- **TTL机制**：5分钟未访问的记录自动清理
- **分片策略**：将用户按ID范围分片到不同的Manager

#### 5.2 性能优化要点

1. **批量处理**
   - Kafka消息批量消费和路由
   - 多用户缓冲区状态批量检查
   - LLM调用批量优化

2. **异步IO**
   - 数据库查询使用线程池
   - LLM调用并发控制
   - 结果存储异步化

3. **资源池化**
   - 数据库连接池（每个Actor维护）
   - LLM客户端复用
   - 线程池复用

4. **动态扩缩容**
   - 基于负载的Actor数量调整
   - 处理器池自动扩容
   - 优雅的缩容机制

### 6. 性能指标

在海量租户场景下的预期性能：

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 支持租户数 | 100万+ | 通过LRU缓存和分片 |
| 消息吞吐量 | 10,000 msg/s | 批量处理优化 |
| 缓冲区检查延迟 | < 50ms | 异步数据库查询 |
| LLM处理延迟 | < 5s | 并发处理和批量优化 |
| 内存使用 | < 10GB/Actor | LRU缓存限制 |
| CPU利用率 | 70-80% | 动态扩缩容维持 |

### 7. 部署配置

```yaml
# ray_config.yaml
cluster:
  head_node:
    num_cpus: 16
    num_gpus: 2
    object_store_memory: 16GB
    
  worker_nodes:
    - num_cpus: 32
      num_gpus: 4
      count: 5
      
actors:
  kafka_consumers:
    num_actors: 20
    resources_per_actor:
      num_cpus: 0.5
      
  load_balancer:
    num_actors: 1
    resources_per_actor:
      num_cpus: 2
      
  buffer_managers:
    num_actors: 10
    resources_per_actor:
      num_cpus: 2
      memory: 4GB
      
  memory_processors:
    min_actors: 20
    max_actors: 100
    resources_per_actor:
      num_cpus: 2
      num_gpus: 0.1
      memory: 2GB
      
optimization:
  lru_cache_size: 10000
  ttl_seconds: 300
  batch_size: 100
  db_thread_pool_size: 10
  llm_concurrent_limit: 3
  
monitoring:
  enable_metrics: true
  metrics_interval: 10
  auto_scale_interval: 30
```

### 8. 监控指标

关键监控指标：

- **系统级指标**
  - Actor CPU/内存使用率
  - 消息队列深度
  - 处理延迟分布

- **业务级指标**
  - 每秒处理用户数
  - 缓冲区命中率
  - LLM调用成功率

- **缓存指标**
  - 缓存命中率
  - 缓存驱逐频率
  - 活跃用户数

### 9. 故障恢复

- **Actor自动重启**：失败的Actor自动重新创建
- **消息重试**：失败的消息进入重试队列
- **断路器模式**：连续失败触发断路保护
- **优雅降级**：过载时自动降级非关键功能

### 10. 实施建议

1. **分阶段部署**
   - Phase 1: 基础异步化改造
   - Phase 2: LRU缓存和批处理
   - Phase 3: 动态扩缩容和监控

2. **性能测试**
   - 模拟百万用户负载测试
   - 突发流量压力测试
   - 长时间稳定性测试

3. **调优建议**
   - 根据实际负载调整缓存大小
   - 优化批处理大小
   - 调整并发限制参数