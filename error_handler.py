#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
고급 에러 핸들링 및 리포트 생성 시스템
모든 에러를 캡처하여 상세한 리포트를 생성하고 해결 방법을 제시합니다.
"""

import os
import sys
import traceback
import platform
import inspect
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import json


class ErrorHandler:
    """에러 핸들링 및 리포트 생성 클래스"""

    def __init__(self, project_root=None):
        self.project_root = Path(project_root or os.getcwd())
        self.error_reports_dir = self.project_root / "error_reports"
        self.error_reports_dir.mkdir(exist_ok=True)

    def capture_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        severity: str = "ERROR"
    ) -> str:
        """
        에러를 캡처하고 상세 리포트 생성

        Args:
            error: 발생한 예외
            context: 추가 컨텍스트 정보
            severity: 심각도 (INFO, WARNING, ERROR, CRITICAL)

        Returns:
            생성된 리포트 파일 경로
        """
        # 에러 정보 수집
        error_info = self._collect_error_info(error, context)

        # 리포트 생성
        report_text = self._generate_report(error_info, severity)

        # 파일 저장
        report_path = self._save_report(report_text, error_info)

        # 콘솔 출력
        self._print_report(report_text, report_path)

        return str(report_path)

    def _collect_error_info(
        self,
        error: Exception,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """에러 관련 모든 정보 수집"""
        tb = traceback.extract_tb(error.__traceback__)

        # 에러 발생 위치 (스택 트레이스에서 마지막)
        if tb:
            last_frame = tb[-1]
            error_file = last_frame.filename
            error_line = last_frame.lineno
            error_func = last_frame.name
        else:
            error_file = "Unknown"
            error_line = 0
            error_func = "Unknown"

        # 코드 스니펫 추출
        code_snippet = self._extract_code_snippet(error_file, error_line)

        # 변수 상태 추출
        variables = self._extract_variables(error)

        # 시스템 정보
        system_info = {
            'os': platform.system(),
            'os_version': platform.release(),
            'python_version': sys.version.split()[0],
            'working_directory': os.getcwd(),
        }

        return {
            'timestamp': datetime.now(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'error_file': error_file,
            'error_line': error_line,
            'error_func': error_func,
            'code_snippet': code_snippet,
            'stack_trace': traceback.format_exc(),
            'variables': variables,
            'context': context or {},
            'system_info': system_info,
        }

    def _extract_code_snippet(
        self,
        file_path: str,
        line_number: int,
        context_lines: int = 5
    ) -> Dict[str, Any]:
        """에러 발생 위치 코드 스니펫 추출"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            start = max(0, line_number - context_lines - 1)
            end = min(len(lines), line_number + context_lines)

            snippet_lines = []
            for i in range(start, end):
                line_num = i + 1
                line_text = lines[i].rstrip()
                is_error_line = (line_num == line_number)

                snippet_lines.append({
                    'line_number': line_num,
                    'text': line_text,
                    'is_error': is_error_line
                })

            return {
                'file': file_path,
                'error_line': line_number,
                'lines': snippet_lines
            }

        except Exception:
            return {
                'file': file_path,
                'error_line': line_number,
                'lines': [],
                'note': '코드를 읽을 수 없습니다.'
            }

    def _extract_variables(self, error: Exception) -> Dict[str, str]:
        """에러 발생 시점의 주요 변수 상태 추출"""
        variables = {}

        try:
            frame = sys._getframe(2)  # 에러가 발생한 프레임
            local_vars = frame.f_locals

            # 주요 변수만 선택 (너무 많으면 읽기 어려움)
            for key, value in list(local_vars.items())[:10]:
                try:
                    variables[key] = repr(value)[:200]  # 최대 200자
                except:
                    variables[key] = "<표현 불가>"

        except:
            pass

        return variables

    def _analyze_error(self, error_info: Dict) -> Dict[str, Any]:
        """에러 분석 및 해결 방법 제시"""
        error_type = error_info['error_type']
        error_message = error_info['error_message']

        # 일반적인 에러 패턴 분석
        solutions = []
        causes = []

        # ConnectionError 관련
        if 'ConnectionError' in error_type or 'connection' in error_message.lower():
            causes.append("데이터베이스 또는 외부 서비스 연결 실패")
            solutions.append({
                'title': '.env 파일 확인',
                'description': '.env 파일에 데이터베이스 경로가 올바르게 설정되어 있는지 확인하세요.',
                'code': 'DATABASE_URL=sqlite:///./app.db'
            })
            solutions.append({
                'title': '서비스 실행 확인',
                'description': '연결하려는 서비스(데이터베이스, API 등)가 실행 중인지 확인하세요.'
            })

        # ModuleNotFoundError
        elif 'ModuleNotFoundError' in error_type or 'No module named' in error_message:
            module_name = error_message.split("'")[1] if "'" in error_message else "unknown"
            causes.append(f"'{module_name}' 모듈이 설치되어 있지 않습니다.")
            solutions.append({
                'title': '패키지 설치',
                'description': f'누락된 패키지를 설치하세요.',
                'code': f'pip install {module_name}'
            })
            solutions.append({
                'title': '전체 재설치',
                'description': 'requirements.txt의 모든 패키지를 재설치하세요.',
                'code': 'pip install -r backend/requirements.txt'
            })

        # FileNotFoundError
        elif 'FileNotFoundError' in error_type or 'No such file' in error_message:
            causes.append("필요한 파일이나 폴더가 존재하지 않습니다.")
            solutions.append({
                'title': '경로 확인',
                'description': '파일 경로가 올바른지, 파일이 실제로 존재하는지 확인하세요.'
            })
            solutions.append({
                'title': '상대 경로 사용',
                'description': '절대 경로 대신 상대 경로를 사용하고 있는지 확인하세요.'
            })

        # PermissionError
        elif 'PermissionError' in error_type:
            causes.append("파일이나 폴더에 대한 접근 권한이 없습니다.")
            solutions.append({
                'title': '권한 확인',
                'description': '관리자 권한으로 실행하거나 파일 권한을 확인하세요.'
            })
            solutions.append({
                'title': '파일 사용 중 확인',
                'description': '다른 프로그램에서 해당 파일을 사용하고 있지 않은지 확인하세요.'
            })

        # AttributeError, TypeError
        elif error_type in ['AttributeError', 'TypeError', 'ValueError']:
            causes.append("잘못된 데이터 타입이나 속성 사용")
            solutions.append({
                'title': '타입 확인',
                'description': '변수의 타입과 값을 확인하세요.',
                'code': 'print(type(variable), variable)'
            })
            solutions.append({
                'title': 'None 체크',
                'description': '변수가 None이 아닌지 확인하세요.',
                'code': 'if variable is not None:'
            })

        # 일반적인 해결 방법
        if not solutions:
            solutions.append({
                'title': '스택 트레이스 확인',
                'description': '아래 스택 트레이스를 참고하여 에러 발생 위치와 원인을 파악하세요.'
            })
            solutions.append({
                'title': 'Claude에게 문의',
                'description': '아래 "Claude에게 붙여넣기용" 섹션의 내용을 복사하여 Claude에게 질문하세요.'
            })

        return {
            'causes': causes,
            'solutions': solutions
        }

    def _generate_report(self, error_info: Dict, severity: str) -> str:
        """상세 에러 리포트 생성"""
        analysis = self._analyze_error(error_info)

        # 타임스탬프 포맷
        timestamp = error_info['timestamp'].strftime("%Y-%m-%d %H:%M:%S")

        # 코드 스니펫 포맷팅
        code_lines = []
        for line_info in error_info['code_snippet'].get('lines', []):
            line_num = line_info['line_number']
            text = line_info['text']
            marker = " ← 여기서 에러" if line_info['is_error'] else ""
            code_lines.append(f"{line_num:4d} | {text}{marker}")

        code_snippet_text = "\n".join(code_lines) if code_lines else "코드를 사용할 수 없습니다."

        # 변수 상태 포맷팅
        variables_text = "\n".join(
            f"   - {key}: {value}"
            for key, value in error_info['variables'].items()
        ) if error_info['variables'] else "   (변수 정보 없음)"

        # 해결 방법 포맷팅
        solutions_text = ""
        for i, solution in enumerate(analysis['solutions'], 1):
            solutions_text += f"\n[방법 {i}] {solution['title']}\n"
            solutions_text += f"   {solution['description']}\n"
            if 'code' in solution:
                solutions_text += f"   코드:\n"
                for line in solution['code'].split('\n'):
                    solutions_text += f"   {line}\n"

        # 원인 분석 텍스트
        causes_text = "\n".join(f"   {i+1}. {cause}" for i, cause in enumerate(analysis['causes']))
        if not causes_text:
            causes_text = "   (자동 분석 불가)"

        # Claude용 텍스트 생성
        claude_text = self._generate_claude_text(error_info, code_snippet_text)

        # 전체 리포트 조합
        report = f"""=====================================
🚨 에러 리포트
=====================================
📅 발생 시각: {timestamp}
🖥️  시스템: {error_info['system_info']['os']} {error_info['system_info']['os_version']}, Python {error_info['system_info']['python_version']}
📁 작업 디렉토리: {error_info['system_info']['working_directory']}
⚠️  심각도: {severity}

=====================================
❌ 에러 정보
=====================================
타입: {error_info['error_type']}
메시지: {error_info['error_message']}

발생 위치:
   파일: {error_info['error_file']}
   라인: {error_info['error_line']}
   함수: {error_info['error_func']}()

코드:
{code_snippet_text}

=====================================
🔍 상세 분석
=====================================
문제 원인:
{causes_text}

당시 변수 상태:
{variables_text}

컨텍스트 정보:
{self._format_context(error_info['context'])}

=====================================
💡 해결 방법
=====================================
{solutions_text}

=====================================
📋 Claude에게 붙여넣기용
=====================================
'''
{claude_text}
'''

=====================================
📊 스택 트레이스
=====================================
{error_info['stack_trace']}

=====================================
"""

        return report

    def _format_context(self, context: Dict) -> str:
        """컨텍스트 정보 포맷팅"""
        if not context:
            return "   (없음)"

        lines = []
        for key, value in context.items():
            lines.append(f"   - {key}: {value}")

        return "\n".join(lines)

    def _generate_claude_text(self, error_info: Dict, code_snippet: str) -> str:
        """Claude에게 복사할 수 있는 형식의 텍스트 생성"""
        text = f"""{error_info['error_type']} 에러가 발생했습니다.

에러 정보:
- 파일: {error_info['error_file']}
- 라인: {error_info['error_line']}
- 함수: {error_info['error_func']}()
- 메시지: {error_info['error_message']}

현재 코드:
```python
{code_snippet}
```

시스템 정보:
- OS: {error_info['system_info']['os']} {error_info['system_info']['os_version']}
- Python: {error_info['system_info']['python_version']}

이 문제를 해결하는 코드를 작성해주세요.
"""
        return text

    def _save_report(self, report_text: str, error_info: Dict) -> Path:
        """리포트를 파일로 저장"""
        # 파일명 생성 (타임스탬프 + 에러 타입)
        timestamp = error_info['timestamp'].strftime("%Y%m%d_%H%M%S")
        error_type = error_info['error_type']
        filename = f"{timestamp}_{error_type}.txt"

        report_path = self.error_reports_dir / filename

        # 파일 저장
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)

        # JSON 형식으로도 저장 (기계 판독용)
        json_path = self.error_reports_dir / f"{timestamp}_{error_type}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            # datetime 객체를 문자열로 변환
            json_data = {**error_info, 'timestamp': str(error_info['timestamp'])}
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        return report_path

    def _print_report(self, report_text: str, report_path: Path):
        """리포트를 콘솔에 출력"""
        print("\n" + "=" * 60)
        print("🚨 에러가 발생했습니다!")
        print("=" * 60)
        print(report_text)
        print("=" * 60)
        print(f"📁 리포트 저장 위치: {report_path}")
        print("=" * 60)


# 전역 에러 핸들러 인스턴스
_global_handler: Optional[ErrorHandler] = None


def setup_global_handler(project_root=None):
    """전역 에러 핸들러 설정"""
    global _global_handler
    _global_handler = ErrorHandler(project_root)

    # sys.excepthook 설정
    def exception_hook(exc_type, exc_value, exc_traceback):
        """처리되지 않은 예외를 캡처"""
        if _global_handler:
            _global_handler.capture_error(exc_value, severity="CRITICAL")

    sys.excepthook = exception_hook


def handle_error(error: Exception, context: Optional[Dict] = None, severity: str = "ERROR"):
    """에러 처리 헬퍼 함수"""
    if _global_handler:
        return _global_handler.capture_error(error, context, severity)
    else:
        # 폴백: 표준 에러 출력
        traceback.print_exc()
        return None


# 데코레이터로 함수 자동 에러 처리
def catch_errors(severity: str = "ERROR"):
    """
    함수에 에러 처리를 자동으로 추가하는 데코레이터

    사용 예시:
        @catch_errors(severity="ERROR")
        def my_function():
            # 이 함수에서 발생하는 모든 에러가 자동으로 리포트됩니다
            pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                context = {
                    'function': func.__name__,
                    'args': str(args)[:200],
                    'kwargs': str(kwargs)[:200],
                }
                handle_error(e, context, severity)
                raise  # 에러를 다시 발생시킴

        return wrapper

    return decorator


def main():
    """테스트 코드"""
    setup_global_handler()

    # 테스트 에러 발생
    try:
        def test_function():
            x = None
            return x.some_attribute  # AttributeError 발생

        test_function()

    except Exception as e:
        handle_error(e, {'test': True}, "ERROR")


if __name__ == '__main__':
    main()
