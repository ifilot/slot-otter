/* Host bridge: exercise the actual transport byte by byte through the card
 * model. */
#include "../emulation/slot_model.h"
#include "WRITE.H"
static unsigned delay, pending;
unsigned wt_host_unfinished, wt_host_idle_loads, wt_host_idle_repeats;
static slot_model *card;
static U32 clocks;
static U16 tick_base;
static int tick_frozen;
unsigned wt_host_pull_high_calls, wt_host_startup_clocks;
static int startup_selected;
int wt_host_selected;
int wt_host_open(const char *path, unsigned flags) {
  if (card)
    slot_model_close(card);
  card = slot_model_open_ex(path, flags);
  clocks = 0;
  tick_base = 0; tick_frozen = 0;
  delay = pending = wt_host_unfinished = wt_host_idle_loads = wt_host_idle_repeats = 0;
  wt_host_pull_high_calls = wt_host_startup_clocks = 0;
  startup_selected = wt_host_selected = 0;
  return card ? 0 : -1;
}
void wt_host_close(void) {
  if (card)
    slot_model_close(card);
  card = 0;
}
void wt_host_config(unsigned option, unsigned value) {
  slot_model_config(card, option, value);
}
/* Optional transaction-delayed bridge: completion takes N I/O accesses. */
static unsigned pending_offset;
static U8 pending_value;
static void exchange(unsigned offset, U8 value) {
  if (offset <= 1) {
    ++clocks;
    if (!startup_selected && !wt_host_selected && value == 255) {
      ++wt_host_startup_clocks;
      if (offset == 0) ++wt_host_idle_loads;
      else ++wt_host_idle_repeats;
    }
  }
  slot_model_write(card, offset, value);
}
static void advance(void) {
  if (pending && !--pending) exchange(pending_offset, pending_value);
}
void wt_host_timing(unsigned accesses) { delay = accesses; }
void wt_reg_write(unsigned offset, U8 value) {
  advance();
  if (pending) { ++wt_host_unfinished; pending = 0; }
  if (offset == 2 || offset == 3) {
    wt_host_selected = offset == 3;
    if (wt_host_selected) startup_selected = 1;
  }
  if (offset <= 1 && delay) {
    pending_offset = offset; pending_value = value; pending = delay;
  } else exchange(offset, value);
}
U8 wt_reg_read(unsigned offset) {
  advance();
  if (offset == 3) ++wt_host_pull_high_calls;
  return slot_model_read(card, offset);
}
void wt_host_clock(unsigned base, int frozen) { tick_base = (U16)base; clocks = 0; tick_frozen = frozen; }
U16 wt_ticks(void) { return (U16)(tick_base + (tick_frozen ? 0 : clocks / 2048UL)); }
