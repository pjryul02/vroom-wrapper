"""
VROOMExecutor - VROOM 바이너리 직접 호출

Roouty Engine (Go)의 패턴을 Python으로 구현:
- vroom-express (Node.js) 제거
- subprocess stdin/stdout 파이프로 직접 통신
- 파일 I/O 없음 → 성능 최적

참고: roouty-engine/pkg/optimizing/vroouty/vroouty.go
"""

import asyncio
import json
import logging
import shutil
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class VROOMExecutor:
    """
    VROOM C++ 바이너리 직접 실행기

    Roouty Engine의 exec.Command + stdin/stdout 패턴을 asyncio로 구현.
    vroom-express 없이 VROOM과 직접 통신.
    """

    # VROOM exit codes
    CODE_OK = 0
    CODE_INTERNAL = 1
    CODE_INPUT = 2
    CODE_ROUTING = 3

    def __init__(
        self,
        vroom_path: str = "vroom",
        router: str = "osrm",
        router_host: str = "localhost",
        router_port: int = 5000,
        default_threads: int = 4,
        default_exploration: int = 5,
        timeout: int = 300,
    ):
        self.vroom_path = vroom_path
        self.router = router
        self.router_host = router_host
        self.router_port = router_port
        self.default_threads = default_threads
        self.default_exploration = default_exploration
        self.timeout = timeout

        # 바이너리 존재 확인 (PATH에서 탐색)
        resolved = shutil.which(vroom_path)
        if resolved:
            self.vroom_path = resolved
            logger.info(f"VROOM binary found: {resolved}")
        else:
            logger.warning(f"VROOM binary not found in PATH: {vroom_path}")

    def _build_args(
        self,
        threads: Optional[int] = None,
        exploration: Optional[int] = None,
        geometry: bool = False,
        plan_mode: bool = False,
    ) -> list:
        """
        VROOM CLI 인자 구성

        Roouty 패턴:
          vroom -r osrm -a car:host -p car:port -t N -x N [-g] [-c] -i -
        """
        args = [self.vroom_path]

        # 라우터 설정
        args.extend(["-r", self.router])

        # 라우터 서버 (libosrm이 아닌 경우)
        if self.router != "libosrm":
            args.extend(["-a", f"car:{self.router_host}"])
            args.extend(["-p", f"car:{self.router_port}"])

        # 스레드 수
        t = threads or self.default_threads
        args.extend(["-t", str(t)])

        # 탐색 레벨 (0-5)
        x = exploration or self.default_exploration
        args.extend(["-x", str(x)])

        # Geometry 반환
        if geometry:
            args.append("-g")

        # Plan mode (ETA 계산용)
        if plan_mode:
            args.append("-c")

        # stdin에서 입력 읽기 (VROOM 1.14: -i 없으면 stdin 자동 읽기)

        return args

    async def execute(
        self,
        vrp_input: Dict[str, Any],
        threads: Optional[int] = None,
        exploration: Optional[int] = None,
        geometry: bool = False,
        plan_mode: bool = False,
    ) -> Dict[str, Any]:
        """
        VROOM 실행 (비동기)

        stdin으로 JSON 전송, stdout에서 JSON 수신.
        Roouty의 RequestOptimizing() 패턴.

        Args:
            vrp_input: VROOM 입력 (vehicles, jobs, matrices 등)
            threads: 스레드 수 (None이면 기본값)
            exploration: 탐색 레벨 0-5 (None이면 기본값)
            geometry: 경로 형상 반환 여부
            plan_mode: plan mode (-c) 사용 여부

        Returns:
            VROOM 결과 JSON (code, summary, routes, unassigned)

        Raises:
            ValueError: VROOM 입력 에러 (exit code 2)
            RuntimeError: VROOM 내부/라우팅 에러 (exit code 1, 3)
            TimeoutError: 타임아웃 초과
        """
        args = self._build_args(threads, exploration, geometry, plan_mode)
        input_json = json.dumps(vrp_input, ensure_ascii=False)

        logger.info(
            f"VROOM execute: threads={threads or self.default_threads}, "
            f"exploration={exploration or self.default_exploration}, "
            f"jobs={len(vrp_input.get('jobs', []))}, "
            f"vehicles={len(vrp_input.get('vehicles', []))}"
        )

        try:
            # 비동기 프로세스 실행
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # stdin으로 입력 전송, stdout/stderr 수신
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=input_json.encode("utf-8")),
                timeout=self.timeout,
            )

            stdout_str = stdout.decode("utf-8").strip()
            stderr_str = stderr.decode("utf-8").strip()

            if stderr_str:
                logger.debug(f"VROOM stderr: {stderr_str}")

            # exit code 처리
            if process.returncode == self.CODE_OK:
                result = json.loads(stdout_str)
                summary = result.get("summary", {})
                logger.info(
                    f"VROOM success: cost={summary.get('cost', 0)}, "
                    f"unassigned={summary.get('unassigned', 0)}, "
                    f"routes={len(result.get('routes', []))}"
                )
                return result

            elif process.returncode == self.CODE_INPUT:
                msg = stderr_str or stdout_str or "Unknown input error"
                logger.error(f"VROOM input error: {msg}")
                raise ValueError(f"VROOM input error: {msg}")

            elif process.returncode == self.CODE_ROUTING:
                msg = stderr_str or stdout_str or "Routing error"
                logger.error(f"VROOM routing error: {msg}")
                raise RuntimeError(f"VROOM routing error: {msg}")

            else:
                msg = stderr_str or stdout_str or f"Exit code {process.returncode}"
                logger.error(f"VROOM internal error: {msg}")
                raise RuntimeError(f"VROOM execution failed: {msg}")

        except asyncio.TimeoutError:
            logger.error(f"VROOM timeout after {self.timeout}s")
            if process.returncode is None:
                process.kill()
                await process.wait()
            raise TimeoutError(f"VROOM execution timeout ({self.timeout}s)")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from VROOM: {stdout_str[:200]}")
            raise RuntimeError(f"VROOM returned invalid JSON: {e}")

    async def health_check(self) -> bool:
        """
        VROOM 바이너리 작동 확인

        최소한의 테스트 문제로 바이너리가 정상 동작하는지 확인.
        """
        test_input = {
            "vehicles": [{"id": 1, "start_index": 0, "end_index": 0}],
            "jobs": [{"id": 1, "location_index": 1}],
            "matrices": {
                "car": {
                    "durations": [[0, 100], [100, 0]],
                    "distances": [[0, 1000], [1000, 0]],
                }
            },
        }

        try:
            result = await self.execute(
                test_input, threads=1, exploration=1
            )
            return result.get("code", -1) == 0
        except Exception as e:
            logger.error(f"VROOM health check failed: {e}")
            return False
