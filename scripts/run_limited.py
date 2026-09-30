"""Run a noninteractive command in a Windows memory-limited Job Object.

The cap is aggregate committed memory, not a strict RSS cap. It applies to the
gated bootstrap, command and descendants; this small supervisor is outside it.
stdout/stderr stream directly to the caller. Command stdin is disconnected.

Example:
    python run_limited.py --memory-mib 384 --report run.json -- tar -tf file.rar
"""

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BOOTSTRAP = """
import subprocess, sys
if sys.stdin.buffer.read(1) != b'G':
    raise SystemExit(125)
raise SystemExit(subprocess.call(sys.argv[1:], stdin=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NO_WINDOW))
"""


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class BASIC_LIMIT(ctypes.Structure):
    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                ("PerJobUserTimeLimit", ctypes.c_longlong),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD)]


class EXTENDED_LIMIT(ctypes.Structure):
    _fields_ = [("BasicLimitInformation", BASIC_LIMIT),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


class ACCOUNTING(ctypes.Structure):
    _fields_ = [("TotalUserTime", ctypes.c_longlong),
                ("TotalKernelTime", ctypes.c_longlong),
                ("ThisPeriodTotalUserTime", ctypes.c_longlong),
                ("ThisPeriodTotalKernelTime", ctypes.c_longlong),
                ("TotalPageFaultCount", wintypes.DWORD),
                ("TotalProcesses", wintypes.DWORD),
                ("ActiveProcesses", wintypes.DWORD),
                ("TotalTerminatedProcesses", wintypes.DWORD)]


class THREAD_ENTRY(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ThreadID", wintypes.DWORD), ("th32OwnerProcessID", wintypes.DWORD),
                ("tpBasePri", wintypes.LONG), ("tpDeltaPri", wintypes.LONG),
                ("dwFlags", wintypes.DWORD)]


def windows_api():
    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    api.CreateJobObjectW.restype = wintypes.HANDLE
    api.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                           ctypes.c_void_p, wintypes.DWORD]
    api.SetInformationJobObject.restype = wintypes.BOOL
    api.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int,
                                             ctypes.c_void_p, wintypes.DWORD,
                                             ctypes.c_void_p]
    api.QueryInformationJobObject.restype = wintypes.BOOL
    api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    api.AssignProcessToJobObject.restype = wintypes.BOOL
    api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    api.TerminateJobObject.restype = wintypes.BOOL
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    api.CloseHandle.restype = wintypes.BOOL
    api.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    api.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    api.Thread32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREAD_ENTRY)]
    api.Thread32First.restype = wintypes.BOOL
    api.Thread32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(THREAD_ENTRY)]
    api.Thread32Next.restype = wintypes.BOOL
    api.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenThread.restype = wintypes.HANDLE
    api.ResumeThread.argtypes = [wintypes.HANDLE]
    api.ResumeThread.restype = wintypes.DWORD
    return api


def require(success, operation):
    if not success:
        raise OSError(f"{operation}: {ctypes.WinError(ctypes.get_last_error())}")


def query(api, job, info_class, structure):
    value = structure()
    require(api.QueryInformationJobObject(job, info_class, ctypes.byref(value),
                                          ctypes.sizeof(value), None),
            "QueryInformationJobObject")
    return value


def resume_primary_thread(api, process_id):
    """Popen closes the primary thread handle; reopen its suspended thread."""
    snapshot = api.CreateToolhelp32Snapshot(0x00000004, 0)  # TH32CS_SNAPTHREAD
    require(snapshot and snapshot != ctypes.c_void_p(-1).value, "CreateToolhelp32Snapshot")
    try:
        entry = THREAD_ENTRY()
        entry.dwSize = ctypes.sizeof(entry)
        found = api.Thread32First(snapshot, ctypes.byref(entry))
        while found:
            if entry.th32OwnerProcessID == process_id:
                thread = api.OpenThread(0x0002, False, entry.th32ThreadID)
                require(thread, "OpenThread")
                try:
                    previous = api.ResumeThread(thread)
                    require(previous != 0xFFFFFFFF, "ResumeThread")
                    if previous != 1:
                        raise OSError(f"unexpected primary thread suspension count {previous}")
                    return
                finally:
                    api.CloseHandle(thread)
            found = api.Thread32Next(snapshot, ctypes.byref(entry))
        raise OSError("newly created suspended process has no identifiable primary thread")
    finally:
        api.CloseHandle(snapshot)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--memory-mib", type=int, default=384)
    parser.add_argument("--timeout-seconds", type=float, default=0,
                        help="zero means no time limit")
    parser.add_argument("--report", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if os.name != "nt":
        parser.error("this helper requires Windows")
    if not command or args.memory_mib <= 0 or args.timeout_seconds < 0:
        parser.error("supply a command, positive memory cap and nonnegative timeout")

    started = time.monotonic()
    report = {"command": command, "job_memory_limit_bytes": args.memory_mib * 1024**2,
              "memory_measure": "aggregate committed memory; not RSS",
              "priority": "IDLE", "stdout_stderr": "inherited, not captured",
              "stdin": "disconnected", "command_started_after_job_assignment": False,
              "status": "setup_failed", "exit_code": 2}
    api = windows_api()
    job = None
    child = None
    assigned = False
    try:
        job = api.CreateJobObjectW(None, None)
        require(job, "CreateJobObjectW")
        limits = EXTENDED_LIMIT()
        # JOB_MEMORY | KILL_ON_JOB_CLOSE | PRIORITY_CLASS; no breakaway permission.
        limits.BasicLimitInformation.LimitFlags = 0x00000200 | 0x00002000 | 0x00000020
        limits.BasicLimitInformation.PriorityClass = 0x00000040  # IDLE_PRIORITY_CLASS
        limits.JobMemoryLimit = report["job_memory_limit_bytes"]
        require(api.SetInformationJobObject(job, 9, ctypes.byref(limits),
                                            ctypes.sizeof(limits)),
                "SetInformationJobObject")
        child = subprocess.Popen(
            [sys.executable, "-I", "-c", BOOTSTRAP, *command],
            stdin=subprocess.PIPE,
            creationflags=subprocess.IDLE_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
            | 0x00000004)  # CREATE_SUSPENDED: no launch-before-assignment race.
        require(api.AssignProcessToJobObject(job, int(child._handle)),
                "AssignProcessToJobObject; command was not released")
        assigned = True
        resume_primary_thread(api, child.pid)
        child.stdin.write(b"G")
        child.stdin.flush()
        child.stdin.close()
        report["command_started_after_job_assignment"] = True
        report["status"] = "running"
        while True:
            accounting = query(api, job, 1, ACCOUNTING)
            if accounting.ActiveProcesses == 0:
                break
            if args.timeout_seconds and time.monotonic() - started >= args.timeout_seconds:
                require(api.TerminateJobObject(job, 124), "TerminateJobObject")
                report["status"] = "timeout"
                report["exit_code"] = 124
                break
            time.sleep(0.1)
        child_code = child.wait(timeout=10)
        report["child_exit_code"] = child_code
        if report["status"] != "timeout":
            report["status"] = "completed" if child_code == 0 else "command_failed"
            report["exit_code"] = child_code
        final_limits = query(api, job, 9, EXTENDED_LIMIT)
        final_accounting = query(api, job, 1, ACCOUNTING)
        report["peak_job_committed_bytes"] = final_limits.PeakJobMemoryUsed
        report["peak_process_committed_bytes"] = final_limits.PeakProcessMemoryUsed
        report["total_job_processes"] = final_accounting.TotalProcesses
        report["active_job_processes_at_finish"] = final_accounting.ActiveProcesses
        if child_code != 0:
            report["failure_note"] = (
                "See command stderr. Allocation above the job cap is denied; "
                "a nonzero exit alone does not prove memory exhaustion.")
    except KeyboardInterrupt:
        report["status"], report["exit_code"] = "interrupted", 130
    except Exception as error:
        report["error"] = str(error)
        report["status"], report["exit_code"] = "supervisor_failed", 2
    finally:
        if child is not None:
            if child.stdin is not None and not child.stdin.closed:
                child.stdin.close()
            if child.poll() is None:
                if assigned:
                    api.TerminateJobObject(job, report["exit_code"] or 2)
                else:
                    child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
        # KILL_ON_JOB_CLOSE also ends any descendants left by a failed command.
        if job:
            api.CloseHandle(job)
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
        encoded = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(encoded, encoding="utf-8")
        print("LIMITED_RUN " + json.dumps(report, ensure_ascii=True), file=sys.stderr)
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
