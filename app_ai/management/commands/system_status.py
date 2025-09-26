"""
系统状态检查命令
用于检查数据库、Celery、Redis等服务的状态
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import redis
from celery import current_app
# DatabaseClient 已删除，不再需要数据库操作


class Command(BaseCommand):
    help = '检查系统各组件的运行状态'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细信息',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.SUCCESS('=== 代码审查系统状态检查 ===\n')
        )
        
        # 检查数据库
        self._check_database(verbose)
        
        # 检查Redis
        self._check_redis(verbose)
        
        # 检查Celery
        self._check_celery(verbose)
        
        self.stdout.write(
            self.style.SUCCESS('\n=== 状态检查完成 ===')
        )

    def _check_database(self, verbose):
        """检查数据库连接和数据"""
        self.stdout.write('📊 数据库状态:')
        
        try:
            db_client = DatabaseClient()
            stats = db_client.get_database_stats()
            
            self.stdout.write(
                self.style.SUCCESS(f'  ✅ 数据库连接正常')
            )
            
            if verbose:
                self.stdout.write(f'     - 提交分析存储功能已禁用')
                self.stdout.write(f'     - 使用新的仓库配置管理模式')
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ 数据库连接失败: {str(e)}')
            )

    def _check_redis(self, verbose):
        """检查Redis连接"""
        self.stdout.write('\n🔴 Redis状态:')
        
        try:
            # 从Celery配置获取Redis URL
            broker_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
            
            # 解析Redis连接信息
            if broker_url.startswith('redis://'):
                import urllib.parse
                parsed = urllib.parse.urlparse(broker_url)
                host = parsed.hostname or 'localhost'
                port = parsed.port or 6379
                db = parsed.path.lstrip('/') or '0'
                
                r = redis.Redis(host=host, port=port, db=int(db))
                r.ping()
                
                self.stdout.write(
                    self.style.SUCCESS(f'  ✅ Redis连接正常')
                )
                
                if verbose:
                    info = r.info()
                    self.stdout.write(f'     - 版本: {info.get("redis_version", "未知")}')
                    self.stdout.write(f'     - 内存使用: {info.get("used_memory_human", "未知")}')
                    self.stdout.write(f'     - 连接数: {info.get("connected_clients", "未知")}')
                    
            else:
                self.stdout.write(
                    self.style.WARNING(f'  ⚠️  非Redis broker: {broker_url}')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Redis连接失败: {str(e)}')
            )

    def _check_celery(self, verbose):
        """检查Celery状态"""
        self.stdout.write('\n🔄 Celery状态:')
        
        try:
            # 检查Celery连接
            inspect = current_app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                active_workers = len(stats)
                self.stdout.write(
                    self.style.SUCCESS(f'  ✅ Celery运行正常 ({active_workers} 个worker)')
                )
                
                if verbose:
                    for worker_name, worker_stats in stats.items():
                        self.stdout.write(f'     - Worker: {worker_name}')
                        self.stdout.write(f'       进程ID: {worker_stats.get("pid", "未知")}')
                        self.stdout.write(f'       任务总数: {worker_stats.get("total", "未知")}')
                        
                # 检查活跃任务
                active_tasks = inspect.active()
                if active_tasks:
                    total_active = sum(len(tasks) for tasks in active_tasks.values())
                    self.stdout.write(f'     - 活跃任务数: {total_active}')
                else:
                    self.stdout.write(f'     - 活跃任务数: 0')
                    
            else:
                self.stdout.write(
                    self.style.ERROR(f'  ❌ 没有活跃的Celery worker')
                )
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ❌ Celery检查失败: {str(e)}')
            )
