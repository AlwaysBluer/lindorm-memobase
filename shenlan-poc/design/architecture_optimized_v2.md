# 方案二：基于Ray Task的动态资源池架构

## 1. 架构概述

本方案采用Ray Task动态调度模型，将记忆处理任务分解为细粒度的独立任务，通过Ray的任务调度器实现动态负载均衡和资源优化。相比Actor模型，Task模型更加灵活，能够更好地应对突发流量和不均匀负载。

## 2. 核心设计理念

- **无状态化**：所有处理逻辑无状态，便于水平扩展
- **任务分解**：将大任务分解为多个小任务并行执行
- **动态调度**：Ray自动调度任务到空闲节点
- **资源感知**：根据任务类型分配不同的资源需求
- **弹性伸缩**：根据队列深度自动调整并发度

## 3. 系统架构图

```
┌──────────────────────────────────────────────────────────────────┐
│                          Ray Cluster                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │                   Task Scheduler                         │    │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐│    │
│   │  │ Priority │  │ Resource │  │   Load   │  │  Task   ││    │
│   │  │  Queue   │  │ Allocator│  │ Balancer │  │ Router  ││    │
│   │  └──────────┘  └──────────┘  └──────────┘  └─────────┘│    │
│   └─────────────────────────────────────────────────────────┘    │
│                              │                                    │
│                              ▼                                    │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │                    Task Execution Layer                  │    │
│   ├─────────────────────────────────────────────────────────┤    │
│   │                                                          │    │
│   │  ┌──────────────────────────────────────────────────┐   │    │
│   │  │            Kafka Consumer Tasks                   │   │    │
│   │  │  @ray.remote(num_cpus=0.5)                       │   │    │
│   │  │  - consume_partition_batch()                     │   │    │
│   │  │  - parse_cdc_messages()                          │   │    │
│   │  └──────────────────────────────────────────────────┘   │    │
│   │                          │                              │    │
│   │                          ▼                              │    │
│   │  ┌──────────────────────────────────────────────────┐   │    │
│   │  │          Buffer Management Tasks                  │   │    │
│   │  │  @ray.remote(num_cpus=1)                         │   │    │
│   │  │  - check_buffer_status()                         │   │    │
│   │  │  - prepare_batch_data()                          │   │    │
│   │  └──────────────────────────────────────────────────┘   │    │
│   │                          │                              │    │
│   │                          ▼                              │    │
│   │  ┌──────────────────────────────────────────────────┐   │    │
│   │  │         Memory Processing Tasks                   │   │    │
│   │  │  @ray.remote(num_cpus=2, num_gpus=0.1)          │   │    │
│   │  │  - extract_user_profiles()                       │   │    │
│   │  │  - process_events()                              │   │    │
│   │  │  - call_llm_batch()                              │   │    │
│   │  └──────────────────────────────────────────────────┘   │    │
│   │                          │                              │    │
│   │                          ▼                              │    │
│   │  ┌──────────────────────────────────────────────────┐   │    │
│   │  │           Storage Tasks                           │   │    │
│   │  │  @ray.remote(num_cpus=0.5)                       │   │    │
│   │  │  - persist_profiles()                            │   │    │
│   │  │  - index_events()                                │   │    │
│   │  └──────────────────────────────────────────────────┘   │    │
│   │                                                          │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                   │
│   ┌─────────────────────────────────────────────────────────┐    │
│   │              Shared Object Store (Plasma)               │    │
│   │  - User Buffers                                        │    │
│   │  - Processed Results                                   │    │
│   │  - Cache Data                                          │    │
│   └─────────────────────────────────────────────────────────┘    │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

## 4. 核心组件设计

### 4.1 任务编排器（Task Orchestrator）

```python
class TaskOrchestrator:
    """
    任务编排器：负责整个处理流程的编排和调度
    """
    def __init__(self):
        self.task_queue = PriorityQueue()
        self.running_tasks = {}
        self.task_dependencies = {}
        
    async def submit_workflow(self, user_id: str, messages: List[dict]):
        """
        提交处理工作流
        将整个处理流程分解为多个可并行的任务
        """
        workflow_id = str(uuid.uuid4())
        
        # 创建任务DAG（有向无环图）
        tasks = self._create_task_dag(user_id, messages, workflow_id)
        
        # 提交任务到Ray
        futures = []
        for task in tasks:
            if task['type'] == 'consume':
                future = consume_messages_task.remote(**task['params'])
            elif task['type'] == 'buffer':
                future = manage_buffer_task.remote(**task['params'])
            elif task['type'] == 'process':
                future = process_memory_task.remote(**task['params'])
            elif task['type'] == 'store':
                future = store_results_task.remote(**task['params'])
                
            futures.append(future)
            self.running_tasks[task['id']] = future
            
        # 异步等待结果
        return workflow_id, futures
```

### 4.2 Kafka消费任务

```python
@ray.remote(num_cpus=0.5)
def consume_buffer_zone_events_task(
    partition_id: int, 
    batch_size: int = 100,
    timeout: float = 5.0
) -> List[dict]:
    """
    消费buffer_zone表的CDC事件
    - 监听buffer_zone表的变更
    - 批量消费提高效率
    - 返回解析后的事件列表
    """
    consumer = create_kafka_consumer(partition_id)
    events = []
    
    try:
        raw_messages = consumer.consume(batch_size, timeout)
        
        for msg in raw_messages:
            if msg.error():
                continue
                
            # 解析buffer_zone CDC消息
            event = parse_buffer_zone_cdc(msg.value())
            if event:
                events.append(event)
                
        # 提交offset
        consumer.commit()
        
    finally:
        consumer.close()
        
    return events

@ray.remote(num_cpus=0.2)  
def parse_buffer_zone_cdc(raw_message: bytes) -> dict:
    """
    解析buffer_zone表的CDC消息
    提取用户ID和缓冲区变更信息
    """
    try:
        message = json.loads(raw_message)
        after_data = message.get('after', {})
        
        if after_data:
            return {
                'user_id': after_data.get('user_id'),
                'buffer_id': after_data.get('buffer_id'),
                'operation': message.get('op'),  # INSERT/UPDATE/DELETE
                'timestamp': after_data.get('updated_at'),
                'buffer_size': after_data.get('buffer_size', 0),
                'metadata': after_data.get('metadata', {})
            }
    except Exception as e:
        logger.error(f"Parse buffer_zone CDC error: {e}")
        return None
```

### 4.3 缓冲区管理任务

```python
@ray.remote(num_cpus=1)
def check_buffer_status_task(buffer_events: List[dict]) -> List[dict]:
    """
    检查缓冲区状态任务
    根据buffer_zone事件检查对应用户的缓冲区状态
    注意：不负责添加数据到缓冲区，只负责检查和触发
    """
    memobase = get_memobase_instance()
    processing_tasks = []
    
    # 按用户分组，避免重复检查
    user_events = {}
    for event in buffer_events:
        user_id = event['user_id']
        if user_id not in user_events:
            user_events[user_id] = []
        user_events[user_id].append(event)
    
    # 检查每个用户的缓冲区状态
    for user_id, events in user_events.items():
        try:
            # 检查缓冲区是否已满
            status = memobase.detect_buffer_full_or_not(user_id)
            
            if status['is_full']:
                # 准备处理任务
                batch_data = {
                    'user_id': user_id,
                    'blob_ids': status['buffer_full_ids'],
                    'priority': calculate_priority(user_id),
                    'created_at': time.time(),
                    'trigger_events': events  # 记录触发事件
                }
                
                # 将批次数据放入对象存储
                batch_ref = ray.put(batch_data)
                
                processing_tasks.append({
                    'user_id': user_id,
                    'batch_ref': batch_ref,
                    'batch_size': len(status['buffer_full_ids']),
                    'priority': batch_data['priority']
                })
                
                logger.info(f"Buffer full for user {user_id}, created processing task")
            else:
                logger.debug(f"Buffer not full for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error checking buffer for user {user_id}: {e}")
            
    return processing_tasks

@ray.remote(num_cpus=0.5)
def batch_aggregator_task(user_batches: List[dict], max_batch_size: int = 10):
    """
    批次聚合任务
    将多个用户的小批次聚合成大批次，提高LLM调用效率
    """
    aggregated_batches = []
    current_batch = []
    current_size = 0
    
    # 按优先级排序
    sorted_batches = sorted(user_batches, key=lambda x: x['priority'], reverse=True)
    
    for batch in sorted_batches:
        batch_size = batch['batch_size']
        
        if current_size + batch_size <= max_batch_size:
            current_batch.append(batch)
            current_size += batch_size
        else:
            if current_batch:
                aggregated_batches.append(current_batch)
            current_batch = [batch]
            current_size = batch_size
            
    if current_batch:
        aggregated_batches.append(current_batch)
        
    return aggregated_batches
```

### 4.4 记忆处理任务

```python
@ray.remote(num_cpus=2, num_gpus=0.1)
def process_memory_task(batch_ref: ray.ObjectRef) -> dict:
    """
    记忆处理任务
    执行实际的LLM调用和记忆抽取
    """
    batch_data = ray.get(batch_ref)
    user_id = batch_data['user_id']
    blob_ids = batch_data['blob_ids']
    
    # 获取memobase实例
    memobase = get_memobase_instance()
    
    try:
        # 处理缓冲区（包含LLM调用）
        result = memobase.process_buffer(
            user_id=user_id,
            blob_type=BlobType.chat,
            blob_ids=blob_ids
        )
        
        # 将结果放入对象存储
        result_ref = ray.put(result)
        
        return {
            'success': True,
            'user_id': user_id,
            'result_ref': result_ref,
            'processed_count': len(blob_ids)
        }
        
    except Exception as e:
        return {
            'success': False,
            'user_id': user_id,
            'error': str(e),
            'retry_needed': should_retry(e)
        }

@ray.remote(num_cpus=3, num_gpus=0.2)
def parallel_llm_task(user_batches: List[dict]) -> List[dict]:
    """
    并行LLM处理任务
    对多个用户的数据进行批量LLM调用
    """
    # 准备批量输入
    llm_inputs = []
    for batch in user_batches:
        user_data = ray.get(batch['batch_ref'])
        llm_inputs.append(prepare_llm_input(user_data))
        
    # 批量调用LLM
    llm_results = batch_call_llm(llm_inputs)
    
    # 解析结果
    processed_results = []
    for i, result in enumerate(llm_results):
        processed_results.append({
            'user_id': user_batches[i]['user_id'],
            'profiles': extract_profiles(result),
            'events': extract_events(result)
        })
        
    return processed_results
```

### 4.5 存储任务

```python
@ray.remote(num_cpus=0.5)
def store_results_task(result_ref: ray.ObjectRef) -> bool:
    """
    存储结果任务
    将处理结果持久化到数据库
    """
    result = ray.get(result_ref)
    
    try:
        # 存储用户画像
        if 'profiles' in result:
            store_profiles(result['user_id'], result['profiles'])
            
        # 存储事件
        if 'events' in result:
            store_events(result['user_id'], result['events'])
            
        # 更新索引
        update_search_index(result['user_id'], result)
        
        return True
        
    except Exception as e:
        logger.error(f"Storage error: {e}")
        return False

@ray.remote(num_cpus=1)
def batch_storage_task(results: List[dict]) -> dict:
    """
    批量存储任务
    批量写入数据库提高效率
    """
    profiles_batch = []
    events_batch = []
    
    for result in results:
        if 'profiles' in result:
            profiles_batch.extend(result['profiles'])
        if 'events' in result:
            events_batch.extend(result['events'])
            
    # 批量写入
    success_count = 0
    if profiles_batch:
        success_count += batch_insert_profiles(profiles_batch)
    if events_batch:
        success_count += batch_insert_events(events_batch)
        
    return {
        'total_processed': len(results),
        'success_count': success_count
    }
```

## 5. 动态资源管理

### 5.1 资源池管理器

```python
class DynamicResourcePool:
    """
    动态资源池管理器
    根据负载自动调整资源分配
    """
    def __init__(self):
        self.resource_limits = {
            'consume_tasks': {'min': 5, 'max': 20, 'current': 10},
            'buffer_tasks': {'min': 3, 'max': 10, 'current': 5},
            'process_tasks': {'min': 10, 'max': 100, 'current': 20},
            'storage_tasks': {'min': 5, 'max': 30, 'current': 10}
        }
        self.metrics = MetricsCollector()
        
    async def auto_scale(self):
        """
        自动扩缩容逻辑
        """
        while True:
            # 收集指标
            queue_depth = self.metrics.get_queue_depth()
            processing_time = self.metrics.get_avg_processing_time()
            error_rate = self.metrics.get_error_rate()
            
            # 计算所需资源
            for task_type, limits in self.resource_limits.items():
                current = limits['current']
                
                # 扩容条件
                if queue_depth > 1000 and current < limits['max']:
                    new_count = min(current * 1.5, limits['max'])
                    self.scale_up(task_type, new_count)
                    
                # 缩容条件
                elif queue_depth < 100 and current > limits['min']:
                    new_count = max(current * 0.7, limits['min'])
                    self.scale_down(task_type, new_count)
                    
            await asyncio.sleep(30)  # 每30秒评估一次
            
    def scale_up(self, task_type: str, new_count: int):
        """扩容任务"""
        current = self.resource_limits[task_type]['current']
        additional = int(new_count - current)
        
        logger.info(f"Scaling up {task_type}: adding {additional} tasks")
        
        # 预热新任务
        for _ in range(additional):
            if task_type == 'process_tasks':
                # 为处理任务分配更多资源
                ray.remote(num_cpus=2, num_gpus=0.1)(process_memory_task)
                
        self.resource_limits[task_type]['current'] = new_count
```

### 5.2 任务优先级调度

```python
class PriorityScheduler:
    """
    优先级调度器
    根据用户等级、数据新鲜度等因素调度任务
    """
    def __init__(self):
        self.priority_queue = []
        self.user_priorities = {}
        
    def calculate_priority(self, user_id: str, task_type: str, metadata: dict) -> float:
        """
        计算任务优先级
        """
        base_priority = 1.0
        
        # 用户等级权重
        user_level = self.get_user_level(user_id)
        base_priority *= (1 + user_level * 0.1)
        
        # 数据新鲜度权重
        age_minutes = (time.time() - metadata.get('timestamp', 0)) / 60
        if age_minutes < 5:
            base_priority *= 1.5  # 新数据优先
        elif age_minutes > 60:
            base_priority *= 0.5  # 旧数据降级
            
        # 任务类型权重
        task_weights = {
            'consume': 1.0,
            'buffer': 1.2,
            'process': 1.5,  # 处理任务最重要
            'storage': 0.8
        }
        base_priority *= task_weights.get(task_type, 1.0)
        
        # 错误重试降级
        retry_count = metadata.get('retry_count', 0)
        base_priority *= (0.9 ** retry_count)
        
        return base_priority
        
    def submit_task(self, task: dict):
        """
        提交任务到优先级队列
        """
        priority = self.calculate_priority(
            task['user_id'],
            task['type'],
            task.get('metadata', {})
        )
        
        heapq.heappush(self.priority_queue, (-priority, task))
        
    def get_next_task(self) -> dict:
        """
        获取下一个要执行的任务
        """
        if self.priority_queue:
            _, task = heapq.heappop(self.priority_queue)
            return task
        return None
```

## 6. 优化策略

### 6.1 智能批处理

```python
class SmartBatcher:
    """
    智能批处理器
    根据数据特征和系统负载动态调整批次大小
    """
    def __init__(self):
        self.batch_sizes = {
            'small': 5,
            'medium': 10,
            'large': 20
        }
        self.current_mode = 'medium'
        
    def adjust_batch_size(self, metrics: dict):
        """
        动态调整批次大小
        """
        latency = metrics.get('avg_latency_ms', 0)
        throughput = metrics.get('throughput_per_sec', 0)
        
        if latency > 5000:  # 延迟过高
            self.current_mode = 'small'
        elif throughput < 100:  # 吞吐量过低
            self.current_mode = 'large'
        else:
            self.current_mode = 'medium'
            
        return self.batch_sizes[self.current_mode]
        
    def create_optimal_batches(self, items: List[dict]) -> List[List[dict]]:
        """
        创建优化的批次
        考虑数据相似性和处理复杂度
        """
        # 按用户分组
        user_groups = {}
        for item in items:
            user_id = item['user_id']
            if user_id not in user_groups:
                user_groups[user_id] = []
            user_groups[user_id].append(item)
            
        # 创建批次
        batches = []
        current_batch = []
        current_size = 0
        max_size = self.batch_sizes[self.current_mode]
        
        for user_id, user_items in user_groups.items():
            # 估算处理复杂度
            complexity = estimate_complexity(user_items)
            
            if current_size + complexity <= max_size:
                current_batch.extend(user_items)
                current_size += complexity
            else:
                if current_batch:
                    batches.append(current_batch)
                current_batch = user_items
                current_size = complexity
                
        if current_batch:
            batches.append(current_batch)
            
        return batches
```

### 6.2 结果缓存

```python
@ray.remote
class ResultCache:
    """
    结果缓存服务
    使用Ray的对象存储实现分布式缓存
    """
    def __init__(self, max_size: int = 10000):
        self.cache = {}
        self.max_size = max_size
        self.access_times = {}
        
    def get(self, key: str) -> Optional[ray.ObjectRef]:
        """获取缓存结果"""
        if key in self.cache:
            self.access_times[key] = time.time()
            return self.cache[key]
        return None
        
    def put(self, key: str, value: Any) -> ray.ObjectRef:
        """缓存结果"""
        # 检查容量
        if len(self.cache) >= self.max_size:
            self._evict_lru()
            
        # 将数据放入对象存储
        ref = ray.put(value)
        self.cache[key] = ref
        self.access_times[key] = time.time()
        
        return ref
        
    def _evict_lru(self):
        """LRU淘汰策略"""
        oldest_key = min(self.access_times, key=self.access_times.get)
        del self.cache[oldest_key]
        del self.access_times[oldest_key]
```

## 7. 容错和恢复

### 7.1 任务重试机制

```python
class TaskRetryManager:
    """
    任务重试管理器
    实现指数退避和断路器模式
    """
    def __init__(self):
        self.retry_configs = {
            'consume': {'max_retries': 3, 'base_delay': 1},
            'buffer': {'max_retries': 3, 'base_delay': 2},
            'process': {'max_retries': 5, 'base_delay': 5},
            'storage': {'max_retries': 3, 'base_delay': 1}
        }
        self.circuit_breakers = {}
        
    async def execute_with_retry(self, task_func, task_type: str, **kwargs):
        """
        执行任务with重试
        """
        config = self.retry_configs[task_type]
        max_retries = config['max_retries']
        base_delay = config['base_delay']
        
        for attempt in range(max_retries):
            try:
                # 检查断路器状态
                if self.is_circuit_open(task_type):
                    raise CircuitOpenError(f"Circuit breaker open for {task_type}")
                    
                # 执行任务
                result = await task_func(**kwargs)
                
                # 重置断路器
                self.reset_circuit(task_type)
                
                return result
                
            except Exception as e:
                # 记录错误
                self.record_error(task_type, e)
                
                if attempt == max_retries - 1:
                    # 最后一次尝试失败
                    raise
                    
                # 计算重试延迟（指数退避）
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
                
    def is_circuit_open(self, task_type: str) -> bool:
        """检查断路器是否打开"""
        breaker = self.circuit_breakers.get(task_type)
        if not breaker:
            return False
            
        error_rate = breaker['errors'] / max(breaker['total'], 1)
        return error_rate > 0.5 and breaker['total'] > 10
```

### 7.2 检查点和恢复

```python
class CheckpointManager:
    """
    检查点管理器
    定期保存处理进度，支持故障恢复
    """
    def __init__(self):
        self.checkpoint_interval = 60  # 秒
        self.checkpoints = {}
        
    async def save_checkpoint(self, workflow_id: str, state: dict):
        """保存检查点"""
        checkpoint = {
            'workflow_id': workflow_id,
            'state': state,
            'timestamp': time.time(),
            'completed_tasks': state.get('completed_tasks', []),
            'pending_tasks': state.get('pending_tasks', []),
            'user_buffers': state.get('user_buffers', {})
        }
        
        # 持久化到存储
        await self.persist_checkpoint(checkpoint)
        
        self.checkpoints[workflow_id] = checkpoint
        
    async def restore_from_checkpoint(self, workflow_id: str) -> dict:
        """从检查点恢复"""
        checkpoint = self.checkpoints.get(workflow_id)
        
        if not checkpoint:
            # 从持久化存储加载
            checkpoint = await self.load_checkpoint(workflow_id)
            
        if checkpoint:
            # 恢复状态
            state = checkpoint['state']
            
            # 重新提交未完成的任务
            for task in state['pending_tasks']:
                await self.resubmit_task(task)
                
            return state
            
        return None
```

## 8. 监控和可观测性

### 8.1 指标收集

```python
@ray.remote
class MetricsCollector:
    """
    指标收集器
    收集系统各项性能指标
    """
    def __init__(self):
        self.metrics = {
            'throughput': deque(maxlen=1000),
            'latency': deque(maxlen=1000),
            'error_count': 0,
            'success_count': 0
        }
        
    def record_task_completion(self, task_type: str, duration: float, success: bool):
        """记录任务完成"""
        self.metrics['throughput'].append({
            'timestamp': time.time(),
            'task_type': task_type
        })
        
        self.metrics['latency'].append(duration)
        
        if success:
            self.metrics['success_count'] += 1
        else:
            self.metrics['error_count'] += 1
            
    def get_metrics_summary(self) -> dict:
        """获取指标摘要"""
        return {
            'throughput_per_min': len(self.metrics['throughput']),
            'avg_latency_ms': np.mean(self.metrics['latency']) * 1000,
            'p99_latency_ms': np.percentile(self.metrics['latency'], 99) * 1000,
            'error_rate': self.metrics['error_count'] / max(
                self.metrics['success_count'] + self.metrics['error_count'], 1
            )
        }
```

## 9. 部署配置

```yaml
# ray_task_config.yaml
ray:
  cluster:
    head_node:
      resources:
        cpu: 16
        memory: 32GB
        object_store_memory: 8GB
        
    worker_nodes:
      - resources:
          cpu: 32
          memory: 64GB
          gpu: 2
        count: 3
        
task_configs:
  consume_tasks:
    num_cpus: 0.5
    max_concurrent: 20
    batch_size: 100
    
  buffer_tasks:
    num_cpus: 1
    max_concurrent: 10
    
  process_tasks:
    num_cpus: 2
    num_gpus: 0.1
    max_concurrent: 50
    timeout_seconds: 30
    
  storage_tasks:
    num_cpus: 0.5
    max_concurrent: 30
    batch_size: 500
    
optimization:
  enable_batching: true
  batch_window_seconds: 5
  max_batch_size: 20
  
  enable_caching: true
  cache_size_mb: 1024
  cache_ttl_seconds: 3600
  
monitoring:
  metrics_interval_seconds: 10
  enable_tracing: true
  trace_sample_rate: 0.1
```

## 10. 性能对比

| 指标 | Actor方案 | Task方案 |
|------|----------|----------|
| 并发能力 | 受Actor数量限制 | 动态扩展，理论无上限 |
| 资源利用率 | 较低（Actor空闲时占用资源） | 高（按需分配） |
| 延迟 | 低（Actor预热） | 中等（任务调度开销） |
| 吞吐量 | 中等 | 高 |
| 故障恢复 | Actor级别 | 任务级别，更细粒度 |
| 适用场景 | 稳定负载 | 突发流量、不均匀负载 |

## 11. 实施建议

1. **混合使用策略**
   - 对于稳定的Kafka消费，使用少量Actor
   - 对于LLM调用等计算密集型任务，使用Task模式
   - 缓存和存储操作使用Task批处理

2. **渐进式迁移**
   - 先实现核心的Task处理逻辑
   - 逐步将Actor组件替换为Task
   - 保留关键的状态管理Actor

3. **性能调优**
   - 根据实际负载调整任务粒度
   - 优化批处理大小和时间窗口
   - 合理设置资源限制和并发度

4. **监控和告警**
   - 实时监控任务队列深度
   - 设置性能指标告警阈值
   - 定期分析任务执行日志优化配置