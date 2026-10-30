"""Read-only console check; Windows NUL isatty is not a human console."""
import ctypes,os,sys
def interactive_input():
    if not sys.stdin.isatty():return False
    if os.name!="nt":return True
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.GetStdHandle.argtypes=[ctypes.c_ulong];kernel.GetStdHandle.restype=ctypes.c_void_p
    kernel.GetConsoleMode.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)];kernel.GetConsoleMode.restype=ctypes.c_int
    handle=kernel.GetStdHandle(ctypes.c_ulong(-10).value);mode=ctypes.c_ulong()
    return bool(handle and kernel.GetConsoleMode(handle,ctypes.byref(mode)))
