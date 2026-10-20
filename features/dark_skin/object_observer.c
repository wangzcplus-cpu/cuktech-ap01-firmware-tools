typedef unsigned char u8;
typedef unsigned int u32;
typedef signed int i32;

#define ATTR_ENTRY __attribute__((section(".text.entry"), noinline, used))
#define ATTR_NOINLINE __attribute__((noinline))

#define TIMER_BYTES 0x58u
#define FIRST_DELAY_MS 1000u
#define ACTIVE_DELAY_MS 120u
#define IDLE_DELAY_MS 1000u
#define LOOP_GLOBAL 0x62FCA9A8u
#define MAX_OBJECTS 64u
#define MAX_DEPTH 6u
#define HTTP_CONTEXT_BYTES 116u
#define HTTP_RESPONSE_BYTES 64u
#define HTTP_URL_BYTES 352u
#define HTTP_URL_OFFSET 8u
#define HTTP_TIMEOUT_OFFSET 36u
#define HTTP_BUFFER_OFFSET 48u
#define HTTP_BUFFER_SIZE_OFFSET 52u
#define HTTP_STATUS_OFFSET 96u
#define HTTP_WORK_STATE_OFFSET 108u
#define HTTP_READY_OFFSET 112u

#ifndef AP01_OBSERVER_URL_PREFIX
#error AP01_OBSERVER_URL_PREFIX must be supplied by the offline build
#endif

typedef void (*one_arg_fn)(void *);
typedef int (*dispatch_fn)(void *);
typedef void *(*child_fn)(void *, int);
typedef u32 (*child_count_fn)(void *);
typedef int (*webclient_fn)(void *);
typedef void (*timer_init_fn)(void *, void *);
typedef int (*timer_schedule_fn)(void *, void *, u32, u32, u32, u32);
typedef void *(*malloc_fn)(u32);
typedef void (*free_fn)(void *);

extern void stock_ui_timer(void *);
extern int stock_get_dispatch_index(void *);
extern void *stock_get_child(void *, int);
extern void *lv_obj_get_child(void *, int);
extern u32 lv_obj_get_child_count(void *);
extern int webclient_perform(void *);
extern void stock_timer_init(void *, void *);
extern int stock_timer_schedule(void *, void *, u32, u32, u32, u32);
extern void *malloc(u32);
extern void free(void *);

void ap01_dark_skin_observer_timer(void *handle);

struct record {
  u32 object;
  u32 class_pointer;
  u32 flags;
  u32 styles;
  u32 user_data;
  i32 x1;
  i32 y1;
  i32 x2;
  i32 y2;
  u32 child_count;
  u8 depth;
  u8 path[MAX_DEPTH];
  u8 reserved;
};

struct observer_state {
  u32 sequence;
  u32 fingerprint;
  i32 page;
  i32 last_page;
  u32 last_fingerprint;
  u32 count;
  u32 next;
  u32 active;
  u32 truncated;
  struct record records[MAX_OBJECTS];
};

static const char http_method[] = "GET";
static const char url_prefix[] = AP01_OBSERVER_URL_PREFIX;

static void zero_bytes(void *target, u32 length)
{
  u8 *selected = (u8 *)target;
  while (length-- != 0u) *selected++ = 0u;
}

static char *append_text(char *out, char *end, const char *text)
{
  while (*text != '\0' && out < end) *out++ = *text++;
  return out;
}

static char *append_u32(char *out, char *end, u32 value)
{
  char digits[10];
  u32 count = 0u;
  do { digits[count++] = (char)('0' + value % 10u); value /= 10u; } while (value != 0u);
  while (count != 0u && out < end) *out++ = digits[--count];
  return out;
}

static char *append_i32(char *out, char *end, i32 value)
{
  u32 magnitude;
  if (value < 0) {
    if (out < end) *out++ = '-';
    magnitude = (u32)(-(value + 1)) + 1u;
  } else magnitude = (u32)value;
  return append_u32(out, end, magnitude);
}

static char *append_hex(char *out, char *end, u32 value)
{
  static const char digits[] = "0123456789abcdef";
  i32 shift;
  out = append_text(out, end, "0x");
  for (shift = 28; shift >= 0 && out < end; shift -= 4)
    *out++ = digits[(value >> (u32)shift) & 15u];
  return out;
}

static char *append_key_u32(char *out, char *end, const char *key, u32 value)
{
  out = append_text(out, end, key);
  return append_u32(out, end, value);
}

static char *append_key_i32(char *out, char *end, const char *key, i32 value)
{
  out = append_text(out, end, key);
  return append_i32(out, end, value);
}

static char *append_key_hex(char *out, char *end, const char *key, u32 value)
{
  out = append_text(out, end, key);
  return append_hex(out, end, value);
}

static ATTR_NOINLINE void *timer_loop(void)
{
  volatile u8 *global = (volatile u8 *)LOOP_GLOBAL;
  if (global[8] != 0x0du) return (void *)0;
  return *(void * volatile *)(global + 4u);
}

static ATTR_NOINLINE struct observer_state *find_state(void)
{
  void *loop = timer_loop();
  void *node;
  u32 hops;
  if (loop == (void *)0) return (void *)0;
  node = *(void **)((u8 *)loop + 0x0cu);
  for (hops = 0u; hops < 64u && node != (void *)((u8 *)loop + 8u); ++hops) {
    u8 *handle = (u8 *)node - 0x10u;
    if (handle[8] == 0x0du && *(void **)(handle + 0x30u) == (void *)ap01_dark_skin_observer_timer)
      return (struct observer_state *)(handle + TIMER_BYTES);
    node = *(void **)((u8 *)node + 4u);
  }
  return (void *)0;
}

static ATTR_NOINLINE struct observer_state *ensure_state(void)
{
  struct observer_state *state = find_state();
  void *loop;
  u8 *handle;
  if (state != (void *)0) return state;
  loop = timer_loop();
  if (loop == (void *)0) return (void *)0;
  handle = (u8 *)malloc(TIMER_BYTES + (u32)sizeof(*state));
  if (handle == (void *)0) return (void *)0;
  zero_bytes(handle, TIMER_BYTES + (u32)sizeof(*state));
  state = (struct observer_state *)(handle + TIMER_BYTES);
  state->last_page = -1;
  ((timer_init_fn)stock_timer_init)(loop, handle);
  (void)((timer_schedule_fn)stock_timer_schedule)(handle, (void *)ap01_dark_skin_observer_timer, FIRST_DELAY_MS, 0u, 0u, 0u);
  return state;
}

static void collect_object(struct observer_state *state, void *object, u8 depth, u8 *path)
{
  struct record *record;
  u32 children;
  u32 index;
  u8 *bytes;
  if (object == (void *)0 || depth > MAX_DEPTH || state->count >= MAX_OBJECTS) {
    state->truncated = 1u;
    return;
  }
  bytes = (u8 *)object;
  children = ((child_count_fn)lv_obj_get_child_count)(object);
  record = &state->records[state->count++];
  record->object = (u32)object;
  record->class_pointer = *(u32 *)(bytes + 0u);
  record->flags = *(u32 *)(bytes + 8u);
  record->styles = *(u32 *)(bytes + 12u);
  record->user_data = *(u32 *)(bytes + 16u);
  record->x1 = *(i32 *)(bytes + 20u);
  record->y1 = *(i32 *)(bytes + 24u);
  record->x2 = *(i32 *)(bytes + 28u);
  record->y2 = *(i32 *)(bytes + 32u);
  record->child_count = children;
  record->depth = depth;
  for (index = 0u; index < MAX_DEPTH; ++index) record->path[index] = path[index];
  if (depth == MAX_DEPTH) {
    if (children != 0u) state->truncated = 1u;
    return;
  }
  for (index = 0u; index < children; ++index) {
    if (index > 255u || state->count >= MAX_OBJECTS) {
      state->truncated = 1u;
      return;
    }
    path[depth] = (u8)index;
    collect_object(state, ((child_fn)lv_obj_get_child)(object, (int)index), (u8)(depth + 1u), path);
  }
}

static ATTR_NOINLINE int send_record(struct observer_state *state, struct record *record, u32 index)
{
  u8 *context = (u8 *)malloc(HTTP_CONTEXT_BYTES);
  void *response;
  char url[HTTP_URL_BYTES];
  char *out = url;
  char *end = url + HTTP_URL_BYTES - 1u;
  u32 path_index;
  int result;
  if (context == (void *)0) return -1;
  response = malloc(HTTP_RESPONSE_BYTES);
  if (response == (void *)0) { free(context); return -1; }
  zero_bytes(context, HTTP_CONTEXT_BYTES);
  zero_bytes(response, HTTP_RESPONSE_BYTES);
  out = append_text(out, end, url_prefix);
  out = append_key_u32(out, end, "seq=", state->sequence);
  out = append_key_i32(out, end, "&page=", state->page);
  out = append_key_u32(out, end, "&index=", index);
  out = append_key_u32(out, end, "&count=", state->count);
  out = append_key_u32(out, end, "&depth=", record->depth);
  out = append_text(out, end, "&path=");
  if (record->depth == 0u) out = append_text(out, end, "root");
  for (path_index = 0u; path_index < record->depth; ++path_index) {
    if (path_index != 0u && out < end) *out++ = '.';
    out = append_u32(out, end, record->path[path_index]);
  }
  out = append_key_hex(out, end, "&object=", record->object);
  out = append_key_hex(out, end, "&class=", record->class_pointer);
  out = append_key_hex(out, end, "&flags=", record->flags);
  out = append_key_hex(out, end, "&styles=", record->styles);
  out = append_key_hex(out, end, "&user_data=", record->user_data);
  out = append_key_i32(out, end, "&x=", record->x1);
  out = append_key_i32(out, end, "&y=", record->y1);
  out = append_key_i32(out, end, "&w=", record->x2 - record->x1 + 1);
  out = append_key_i32(out, end, "&h=", record->y2 - record->y1 + 1);
  out = append_key_u32(out, end, "&children=", record->child_count);
  out = append_key_u32(out, end, "&truncated=", state->truncated);
  *out = '\0';
  *(const char **)(context + 4u) = http_method;
  *(const char **)(context + HTTP_URL_OFFSET) = url;
  *(u32 *)(context + HTTP_TIMEOUT_OFFSET) = 2u;
  *(void **)(context + HTTP_BUFFER_OFFSET) = response;
  *(u32 *)(context + HTTP_BUFFER_SIZE_OFFSET) = HTTP_RESPONSE_BYTES;
  context[HTTP_READY_OFFSET] = 1u;
  result = ((webclient_fn)webclient_perform)(context);
  if (result >= 0 && *(u32 *)(context + HTTP_STATUS_OFFSET) != 200u) result = -1;
  *(void **)(context + HTTP_WORK_STATE_OFFSET) = (void *)0;
  free(response);
  free(context);
  return result;
}

ATTR_NOINLINE __attribute__((used)) void ap01_dark_skin_observer_timer(void *handle)
{
  struct observer_state *state;
  u32 delay = IDLE_DELAY_MS;
  if (handle == (void *)0) return;
  state = (struct observer_state *)((u8 *)handle + TIMER_BYTES);
  if (state->active != 0u && state->next < state->count) {
    if (send_record(state, &state->records[state->next], state->next) < 0) {
      state->active = 0u;
      state->count = 0u;
    } else {
      ++state->next;
      if (state->next < state->count) delay = ACTIVE_DELAY_MS;
      else { state->active = 0u; state->count = 0u; }
    }
  }
  (void)((timer_schedule_fn)stock_timer_schedule)(handle, (void *)ap01_dark_skin_observer_timer, delay, 0u, 0u, 0u);
}

ATTR_ENTRY void ap01_dark_skin_ui_timer_wrapper(void *timer)
{
  struct observer_state *state;
  void *theme;
  void *root;
  i32 page;
  u32 fingerprint;
  u8 path[MAX_DEPTH];
  ((one_arg_fn)stock_ui_timer)(timer);
  if (timer == (void *)0) return;
  state = ensure_state();
  if (state == (void *)0 || state->active != 0u) return;
  theme = *(void **)((u8 *)timer + 12u);
  if (theme == (void *)0) return;
  page = ((dispatch_fn)stock_get_dispatch_index)(theme);
  if (page < 0 || page > 8) return;
  root = ((child_fn)stock_get_child)(theme, page);
  if (root == (void *)0) return;
  fingerprint = (u32)root ^ *(u32 *)root ^ ((child_count_fn)lv_obj_get_child_count)(root);
  if (state->last_page == page && state->last_fingerprint == fingerprint) return;
  zero_bytes(path, MAX_DEPTH);
  state->page = page;
  state->count = 0u;
  state->next = 0u;
  state->truncated = 0u;
  collect_object(state, root, 0u, path);
  if (state->count == 0u) return;
  ++state->sequence;
  state->fingerprint = fingerprint;
  state->last_page = page;
  state->last_fingerprint = fingerprint;
  state->active = 1u;
}
