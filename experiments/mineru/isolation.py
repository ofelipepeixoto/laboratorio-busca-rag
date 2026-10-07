"""Limites do experimento Linux. Não é sandbox de filesystem para PDFs hostis."""
import ctypes
import errno
import resource
import socket
import sys

MAX_INPUT = 10 * 1024 * 1024
MAX_OUTPUT = 2 * 1024 * 1024
MAX_PAGES = 50
MAX_PAGE_TEXT = 16 * 1024
CPU_SECONDS = 20
WALL_SECONDS = 30
MEMORY_BYTES = 2 * 1024**3


def restrict_worker():
    """Aplicado antes de imports de terceiros. Falha fechada sem libseccomp."""
    if sys.platform != "linux":
        raise RuntimeError("linux_required")
    for kind, limits in [
        (resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES)),
        (resource.RLIMIT_CPU, (CPU_SECONDS, CPU_SECONDS + 1)),
        (resource.RLIMIT_FSIZE, (MAX_OUTPUT, MAX_OUTPUT)),
        (resource.RLIMIT_NOFILE, (64, 64)),
        (resource.RLIMIT_CORE, (0, 0)),
    ]:
        resource.setrlimit(kind, limits)
    # Valores da ABI pública de libseccomp (seccomp.h).
    class Comparison(ctypes.Structure):
        _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int),
                    ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]

    lib = ctypes.CDLL("libseccomp.so.2")
    lib.seccomp_init.argtypes = [ctypes.c_uint32]
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    lib.seccomp_syscall_resolve_name.restype = ctypes.c_int
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32,
                                        ctypes.c_int, ctypes.c_uint, ctypes.POINTER(Comparison)]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_release.argtypes = [ctypes.c_void_p]
    context = lib.seccomp_init(0x7FFF0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("seccomp_init_failed")
    try:
        # Pares Unix anônimos para asyncio; connect também é bloqueado para Unix.
        # O renderizador inicia subprocessos Python; eles herdam seccomp e rlimits.
        for name in ["socket", "socketpair", "connect",
                     "io_uring_setup", "io_uring_enter", "io_uring_register"]:
            syscall = lib.seccomp_syscall_resolve_name(name.encode())
            if syscall < 0:
                raise RuntimeError("unsupported_syscall")
            comparison = Comparison(0, 1, socket.AF_UNIX, 0)  # SCMP_CMP_NE
            filtered = name in {"socket", "socketpair"}
            if lib.seccomp_rule_add_array(context, 0x00050000 | errno.EPERM,
                                         syscall, int(filtered),
                                         ctypes.byref(comparison) if filtered else None) != 0:
                raise RuntimeError("seccomp_rule_failed")
        if lib.seccomp_load(context) != 0:
            raise RuntimeError("seccomp_load_failed")
    finally:
        lib.seccomp_release(context)
