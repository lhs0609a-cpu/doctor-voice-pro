#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
시스템 모니터링, 백업, 로그 로테이션 통합 모듈
"""

import os
import sys
import time
import shutil
import glob
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import psutil
import threading
import schedule


class PerformanceMonitor:
    """시스템 성능 모니터링"""

    def __init__(self, cpu_threshold=80, memory_threshold=80):
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.history = []
        self.max_history = 1000

    def get_cpu_usage(self) -> float:
        """CPU 사용률 (%)"""
        return psutil.cpu_percent(interval=1)

    def get_memory_usage(self) -> Dict:
        """메모리 사용 정보"""
        mem = psutil.virtual_memory()
        return {
            'total_gb': mem.total / (1024 ** 3),
            'available_gb': mem.available / (1024 ** 3),
            'used_gb': mem.used / (1024 ** 3),
            'percent': mem.percent
        }

    def get_disk_usage(self, path='/') -> Dict:
        """디스크 사용 정보"""
        disk = psutil.disk_usage(path)
        return {
            'total_gb': disk.total / (1024 ** 3),
            'used_gb': disk.used / (1024 ** 3),
            'free_gb': disk.free / (1024 ** 3),
            'percent': disk.percent
        }

    def get_network_stats(self) -> Dict:
        """네트워크 통계"""
        net = psutil.net_io_counters()
        return {
            'bytes_sent_mb': net.bytes_sent / (1024 ** 2),
            'bytes_recv_mb': net.bytes_recv / (1024 ** 2),
            'packets_sent': net.packets_sent,
            'packets_recv': net.packets_recv
        }

    def get_process_info(self) -> List[Dict]:
        """현재 프로세스 정보"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = proc.info
                if info['cpu_percent'] > 5 or info['memory_percent'] > 5:
                    processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return sorted(processes, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:10]

    def check_thresholds(self) -> Dict:
        """임계값 체크"""
        cpu = self.get_cpu_usage()
        memory = self.get_memory_usage()

        warnings = []

        if cpu > self.cpu_threshold:
            warnings.append({
                'type': 'cpu',
                'severity': 'warning',
                'message': f'CPU 사용률이 높습니다: {cpu:.1f}%',
                'value': cpu,
                'threshold': self.cpu_threshold
            })

        if memory['percent'] > self.memory_threshold:
            warnings.append({
                'type': 'memory',
                'severity': 'warning',
                'message': f'메모리 사용률이 높습니다: {memory["percent"]:.1f}%',
                'value': memory['percent'],
                'threshold': self.memory_threshold
            })

        return {
            'cpu': cpu,
            'memory': memory,
            'warnings': warnings
        }

    def get_full_report(self) -> Dict:
        """전체 시스템 리포트"""
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu': self.get_cpu_usage(),
            'memory': self.get_memory_usage(),
            'disk': self.get_disk_usage(),
            'network': self.get_network_stats(),
            'top_processes': self.get_process_info(),
            'warnings': self.check_thresholds()['warnings']
        }

    def log_metrics(self):
        """메트릭 기록"""
        metrics = {
            'timestamp': datetime.now(),
            'cpu': self.get_cpu_usage(),
            'memory': self.get_memory_usage()['percent']
        }

        self.history.append(metrics)

        # 최대 개수 유지
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]

    def print_report(self):
        """리포트 출력"""
        report = self.get_full_report()

        print("\n" + "=" * 60)
        print(f"📊 시스템 성능 리포트 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        print(f"\n💻 CPU:")
        print(f"   사용률: {report['cpu']:.1f}%")

        print(f"\n🧠 메모리:")
        mem = report['memory']
        print(f"   사용: {mem['used_gb']:.2f}GB / {mem['total_gb']:.2f}GB")
        print(f"   사용률: {mem['percent']:.1f}%")

        print(f"\n💾 디스크:")
        disk = report['disk']
        print(f"   사용: {disk['used_gb']:.2f}GB / {disk['total_gb']:.2f}GB")
        print(f"   여유: {disk['free_gb']:.2f}GB ({100-disk['percent']:.1f}%)")

        if report['warnings']:
            print(f"\n⚠️  경고:")
            for warning in report['warnings']:
                print(f"   - {warning['message']}")

        print("\n" + "=" * 60)


class BackupSystem:
    """자동 백업 시스템"""

    def __init__(self, project_root, backup_dir='backups', retention_days=7):
        self.project_root = Path(project_root)
        self.backup_dir = self.project_root / backup_dir
        self.backup_dir.mkdir(exist_ok=True)
        self.retention_days = retention_days

    def create_backup(self) -> Optional[Path]:
        """데이터베이스 및 중요 파일 백업"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"
        backup_path = self.backup_dir / backup_name
        backup_path.mkdir(exist_ok=True)

        print(f"📦 백업 생성 중: {backup_name}")

        try:
            # 데이터베이스 백업
            db_files = list(self.project_root.glob("**/*.db")) + \
                      list(self.project_root.glob("**/*.sqlite")) + \
                      list(self.project_root.glob("**/*.sqlite3"))

            for db_file in db_files:
                if 'backup' not in str(db_file):  # 백업 폴더는 제외
                    dest = backup_path / db_file.name
                    shutil.copy2(db_file, dest)
                    print(f"   ✅ {db_file.name}")

            # .env 파일 백업
            env_file = self.project_root / "backend" / ".env"
            if env_file.exists():
                shutil.copy2(env_file, backup_path / ".env")
                print(f"   ✅ .env")

            # uploads 폴더 백업 (있으면)
            uploads_dir = self.project_root / "uploads"
            if uploads_dir.exists() and uploads_dir.is_dir():
                shutil.copytree(uploads_dir, backup_path / "uploads")
                print(f"   ✅ uploads/")

            # 백업을 압축
            archive_path = self.backup_dir / f"{backup_name}.tar.gz"
            shutil.make_archive(
                str(self.backup_dir / backup_name),
                'gztar',
                backup_path
            )

            # 임시 폴더 삭제
            shutil.rmtree(backup_path)

            # 압축 파일 크기 확인
            size_mb = archive_path.stat().st_size / (1024 ** 2)

            print(f"✅ 백업 완료: {archive_path.name} ({size_mb:.2f}MB)")

            # 오래된 백업 정리
            self.cleanup_old_backups()

            return archive_path

        except Exception as e:
            print(f"❌ 백업 실패: {e}")
            return None

    def cleanup_old_backups(self):
        """보관 기간이 지난 백업 삭제"""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        backup_files = list(self.backup_dir.glob("backup_*.tar.gz"))

        deleted_count = 0
        for backup_file in backup_files:
            # 파일 수정 시간 확인
            mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)

            if mtime < cutoff_date:
                backup_file.unlink()
                deleted_count += 1
                print(f"   🗑️  삭제: {backup_file.name}")

        if deleted_count > 0:
            print(f"✅ {deleted_count}개의 오래된 백업 삭제")

    def list_backups(self) -> List[Dict]:
        """백업 목록 조회"""
        backup_files = list(self.backup_dir.glob("backup_*.tar.gz"))
        backups = []

        for backup_file in sorted(backup_files, key=lambda x: x.stat().st_mtime, reverse=True):
            stat = backup_file.stat()
            backups.append({
                'name': backup_file.name,
                'path': backup_file,
                'size_mb': stat.st_size / (1024 ** 2),
                'created': datetime.fromtimestamp(stat.st_mtime)
            })

        return backups

    def restore_backup(self, backup_name: str) -> bool:
        """백업 복원"""
        backup_file = self.backup_dir / backup_name

        if not backup_file.exists():
            print(f"❌ 백업 파일을 찾을 수 없습니다: {backup_name}")
            return False

        print(f"📥 백업 복원 중: {backup_name}")

        try:
            # 압축 해제
            shutil.unpack_archive(backup_file, self.backup_dir / "temp_restore")

            # 파일 복원 (여기서는 수동 확인 필요)
            print("⚠️  주의: 복원하기 전에 현재 데이터를 백업하세요!")
            print(f"복원할 파일 위치: {self.backup_dir / 'temp_restore'}")
            print("수동으로 필요한 파일을 복사하세요.")

            return True

        except Exception as e:
            print(f"❌ 복원 실패: {e}")
            return False


class LogRotation:
    """로그 로테이션 시스템"""

    def __init__(self, log_dir='logs', max_size_mb=10, backup_count=5):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.backup_count = backup_count

    def rotate_log(self, log_file: Path):
        """로그 파일 로테이션"""
        if not log_file.exists():
            return

        # 파일 크기 확인
        size = log_file.stat().st_size

        if size < self.max_size_bytes:
            return

        print(f"🔄 로그 로테이션: {log_file.name}")

        # 기존 백업 파일들 이동
        for i in range(self.backup_count - 1, 0, -1):
            old_backup = log_file.with_suffix(f".log.{i}.gz")
            new_backup = log_file.with_suffix(f".log.{i+1}.gz")

            if old_backup.exists():
                if new_backup.exists():
                    new_backup.unlink()
                old_backup.rename(new_backup)

        # 현재 로그 파일을 .1.gz로 압축 저장
        backup_file = log_file.with_suffix(".log.1.gz")

        with open(log_file, 'rb') as f_in:
            with gzip.open(backup_file, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)

        # 원본 로그 파일 비우기
        with open(log_file, 'w') as f:
            f.write(f"# Log rotated at {datetime.now().isoformat()}\n")

        print(f"✅ {log_file.name} 로테이션 완료")

    def rotate_all_logs(self):
        """모든 로그 파일 로테이션"""
        log_files = list(self.log_dir.glob("*.log"))

        for log_file in log_files:
            self.rotate_log(log_file)

    def cleanup_old_logs(self):
        """오래된 로그 백업 삭제"""
        pattern = "*.log.*.gz"
        log_backups = list(self.log_dir.glob(pattern))

        # 각 로그 파일별로 backup_count 이상인 것 삭제
        log_groups = {}
        for backup in log_backups:
            base_name = backup.name.split('.log.')[0]
            if base_name not in log_groups:
                log_groups[base_name] = []
            log_groups[base_name].append(backup)

        for base_name, backups in log_groups.items():
            # 수정 시간 기준 정렬
            backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # backup_count 이상인 것 삭제
            for backup in backups[self.backup_count:]:
                backup.unlink()
                print(f"   🗑️  삭제: {backup.name}")


class SystemMonitor:
    """통합 시스템 모니터"""

    def __init__(self, project_root=None):
        self.project_root = Path(project_root or os.getcwd())
        self.performance = PerformanceMonitor()
        self.backup = BackupSystem(self.project_root)
        self.log_rotation = LogRotation(self.project_root / "logs")
        self.running = False
        self.thread = None

    def start_monitoring(self, interval_minutes=60):
        """백그라운드 모니터링 시작"""
        self.running = True

        def monitor_loop():
            # 스케줄 설정
            schedule.every(interval_minutes).minutes.do(self.performance.log_metrics)
            schedule.every(24).hours.do(self.backup.create_backup)
            schedule.every(1).hours.do(self.log_rotation.rotate_all_logs)

            while self.running:
                schedule.run_pending()
                time.sleep(60)

        self.thread = threading.Thread(target=monitor_loop, daemon=True)
        self.thread.start()

        print("✅ 시스템 모니터링 시작")

    def stop_monitoring(self):
        """모니터링 중지"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("✅ 시스템 모니터링 중지")

    def run_manual_tasks(self):
        """수동 작업 실행"""
        print("\n" + "=" * 60)
        print("  수동 시스템 관리")
        print("=" * 60)

        # 1. 성능 리포트
        self.performance.print_report()

        # 2. 백업 생성
        print("\n백업을 생성하시겠습니까? (y/n): ", end="")
        if input().strip().lower() == 'y':
            self.backup.create_backup()

        # 3. 로그 로테이션
        print("\n로그 로테이션을 실행하시겠습니까? (y/n): ", end="")
        if input().strip().lower() == 'y':
            self.log_rotation.rotate_all_logs()

        print("\n✅ 작업 완료")


def main():
    """메인 함수"""
    import argparse

    parser = argparse.ArgumentParser(description='시스템 모니터링 및 유지보수 도구')
    parser.add_argument('--monitor', action='store_true', help='성능 모니터링 리포트')
    parser.add_argument('--backup', action='store_true', help='백업 생성')
    parser.add_argument('--rotate-logs', action='store_true', help='로그 로테이션')
    parser.add_argument('--list-backups', action='store_true', help='백업 목록 조회')
    parser.add_argument('--auto', action='store_true', help='자동 모니터링 시작 (백그라운드)')

    args = parser.parse_args()

    monitor = SystemMonitor()

    if args.monitor:
        monitor.performance.print_report()

    elif args.backup:
        monitor.backup.create_backup()

    elif args.rotate_logs:
        monitor.log_rotation.rotate_all_logs()

    elif args.list_backups:
        backups = monitor.backup.list_backups()
        print(f"\n📦 백업 목록 ({len(backups)}개):")
        for backup in backups:
            print(f"   - {backup['name']}")
            print(f"     크기: {backup['size_mb']:.2f}MB")
            print(f"     생성: {backup['created'].strftime('%Y-%m-%d %H:%M:%S')}")
            print()

    elif args.auto:
        print("자동 모니터링을 시작합니다...")
        print("종료하려면 Ctrl+C를 누르세요.")
        try:
            monitor.start_monitoring()
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            monitor.stop_monitoring()

    else:
        # 인터랙티브 모드
        monitor.run_manual_tasks()


if __name__ == '__main__':
    main()
