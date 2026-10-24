typedef unsigned char u8;
typedef unsigned int u32;

#define ATTR_ENTRY __attribute__((section(".text.entry"), noinline, used))
#define ATTR_NOINLINE __attribute__((noinline))

#define TIMER_BYTES 0x58u
#define FIRST_DELAY_MS 2000u
#define REPEAT_DELAY_MS 2000u
#define TIMER_PROBE_LIMIT 64u
#define LOOP_GLOBAL 0x62FCA9A8u
#define HTTP_CONTEXT_BYTES 116u
#define HTTP_RESPONSE_BYTES 4096u
#define HTTP_URL_OFFSET 8u
#define HTTP_TIMEOUT_OFFSET 36u
#define HTTP_BUFFER_OFFSET 48u
#define HTTP_BUFFER_SIZE_OFFSET 52u
#define HTTP_SINK_OFFSET 60u
#define HTTP_SINK_ARG_OFFSET 64u
#define HTTP_WORK_STATE_OFFSET 108u
#define HTTP_READY_OFFSET 112u

#define ERR_INVAL (-22)

#ifndef AP01_OBSERVER_URL_PREFIX
#error AP01_OBSERVER_URL_PREFIX must be supplied by the offline build
#endif

typedef void (*one_arg_fn)(void *);
typedef int (*webclient_fn)(void *);
typedef void (*timer_init_fn)(void *, void *);
typedef int (*timer_schedule_fn)(void *, void *, u32, u32, u32, u32);
typedef void *(*malloc_fn)(u32);
typedef void (*free_fn)(void *);

extern void stock_ui_timer(void *);
extern int webclient_perform(void *);
extern void stock_timer_init(void *, void *);
extern int stock_timer_schedule(void *, void *, u32, u32, u32, u32);
extern void *malloc(u32);
extern void free(void *);

void ap01_dark_skin_observer_timer(void *handle);

static const char http_method[] = "GET";
static const char probe_url[] =
  AP01_OBSERVER_URL_PREFIX
  "seq=0&page=-1&index=0&count=0&depth=0&path=root"
  "&object=0x00000000&class=0x00000000&flags=0x00000000"
  "&styles=0x00000000&user_data=0x00000000&x=0&y=0&w=0&h=0"
  "&children=0&truncated=0";

static void zero_bytes(void *target, u32 length)
{
  u8 *selected = (u8 *)target;
  while (length-- != 0u) *selected++ = 0u;
}

static ATTR_NOINLINE void *timer_loop(void)
{
  volatile u8 *global = (volatile u8 *)LOOP_GLOBAL;
  if (global[8] != 0x0du) return (void *)0;
  return *(void * volatile *)(global + 4u);
}

static ATTR_NOINLINE void ensure_probe_timer(void)
{
  void *loop = timer_loop();
  void *node;
  void *timer;
  u32 hops;
  if (loop == (void *)0) return;
  node = *(void **)((u8 *)loop + 0x0cu);
  for (hops = 0u;
       hops < TIMER_PROBE_LIMIT && node != (void *)((u8 *)loop + 8u);
       ++hops) {
    u8 *handle = (u8 *)node - 0x10u;
    if (handle[8] == 0x0du &&
        *(void **)(handle + 0x30u) == (void *)ap01_dark_skin_observer_timer)
      return;
    node = *(void **)((u8 *)node + 4u);
  }
  timer = ((malloc_fn)malloc)(TIMER_BYTES);
  if (timer == (void *)0) return;
  ((timer_init_fn)stock_timer_init)(loop, timer);
  (void)((timer_schedule_fn)stock_timer_schedule)(
      timer, (void *)ap01_dark_skin_observer_timer,
      FIRST_DELAY_MS, 0u, 0u, 0u);
}

static ATTR_NOINLINE int discard_response_sink(char **buffer, int offset,
                                                int data_end,
                                                int *buffer_length,
                                                void *argument)
{
  if (argument == (void *)0 || buffer == (void *)0 ||
      *buffer == (void *)0 || buffer_length == (void *)0 ||
      offset < 0 || data_end < offset || *buffer_length < 0 ||
      data_end > *buffer_length)
    return ERR_INVAL;
  return 0;
}

static ATTR_NOINLINE int send_startup_probe(void)
{
  u8 *context = (u8 *)((malloc_fn)malloc)(HTTP_CONTEXT_BYTES);
  void *response;
  int result;
  if (context == (void *)0) return -1;
  response = ((malloc_fn)malloc)(HTTP_RESPONSE_BYTES);
  if (response == (void *)0) {
    ((free_fn)free)(context);
    return -1;
  }
  zero_bytes(context, HTTP_CONTEXT_BYTES);
  zero_bytes(response, HTTP_RESPONSE_BYTES);
  *(const char **)(context + 4u) = http_method;
  *(const char **)(context + HTTP_URL_OFFSET) = probe_url;
  *(u32 *)(context + HTTP_TIMEOUT_OFFSET) = 2u;
  *(void **)(context + HTTP_BUFFER_OFFSET) = response;
  *(u32 *)(context + HTTP_BUFFER_SIZE_OFFSET) = HTTP_RESPONSE_BYTES;
  *(void **)(context + HTTP_SINK_OFFSET) = (void *)discard_response_sink;
  *(void **)(context + HTTP_SINK_ARG_OFFSET) = (void *)context;
  context[HTTP_READY_OFFSET] = 1u;
  result = ((webclient_fn)webclient_perform)(context);
  *(void **)(context + HTTP_SINK_ARG_OFFSET) = (void *)0;
  *(void **)(context + HTTP_WORK_STATE_OFFSET) = (void *)0;
  ((free_fn)free)(response);
  ((free_fn)free)(context);
  return result;
}

ATTR_NOINLINE __attribute__((used)) void ap01_dark_skin_observer_timer(void *handle)
{
  if (handle == (void *)0) return;
  (void)send_startup_probe();
  (void)((timer_schedule_fn)stock_timer_schedule)(
      handle, (void *)ap01_dark_skin_observer_timer,
      REPEAT_DELAY_MS, 0u, 0u, 0u);
}

ATTR_ENTRY void ap01_dark_skin_ui_timer_wrapper(void *timer)
{
  ensure_probe_timer();
  ((one_arg_fn)stock_ui_timer)(timer);
}
