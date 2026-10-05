/* SPDX-License-Identifier: GPL-3.0-or-later */
/* Turbo C's startup initializes environ to null before calling this hook.
 * Arguments use the original DOS environment independently. This program does
 * not use environ, so avoid copying it and linking an unused heap allocator.
 * Keep the normal startup and keep() vector restoration. */
void _setenvp(void) { }

#include <process.h>
/* No atexit registrations or stdio buffers exist in this program. The low-level
 * CRT exit still restores vectors and returns the requested DOS exit status. */
void exit(int status) { _exit(status); }
