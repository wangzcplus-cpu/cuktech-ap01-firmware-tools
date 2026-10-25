typedef unsigned char u8;
typedef unsigned int u32;

#define ATTR_ENTRY __attribute__((section(".text.entry"), noinline, used))
#define ATTR_NOINLINE __attribute__((noinline))

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
#define AP01_O_RDONLY 1
#define AP01_O_RDWR_CREAT_TRUNC 39
#define AP01_MODE_0666 438

#ifndef AP01_OBSERVER_URL_PREFIX
#error AP01_OBSERVER_URL_PREFIX must be supplied by the offline build
#endif

typedef void (*one_arg_fn)(void *);
typedef int (*webclient_fn)(void *);
typedef int (*open_fn)(const char *, int, int);
typedef int (*close_fn)(int);
typedef void *(*malloc_fn)(u32);
typedef void (*free_fn)(void *);

extern void stock_ui_timer(void *);
extern int webclient_perform(void *);
extern int open(const char *, int, int);
extern int close(int);
extern void *malloc(u32);
extern void free(void *);

static const char http_method[] = "GET";
static const char probe_marker_path[] =
  "/tmp/.ap01-dark-skin-wrapper-probe-v5";
static const char probe_url[] =
  AP01_OBSERVER_URL_PREFIX
  "seq=0&page=-2&index=0&count=0&depth=0&path=wrapper"
  "&object=0x00000000&class=0x00000000&flags=0x00000000"
  "&styles=0x00000000&user_data=0x00000000&x=0&y=0&w=0&h=0"
  "&children=0&truncated=0";

static void zero_bytes(void *target, u32 length)
{
  u8 *selected = (u8 *)target;
  while (length-- != 0u) *selected++ = 0u;
}

static ATTR_NOINLINE int claim_wrapper_probe(void)
{
  int descriptor = ((open_fn)open)(probe_marker_path, AP01_O_RDONLY, 0);
  if (descriptor >= 0) {
    (void)((close_fn)close)(descriptor);
    return 0;
  }
  descriptor = ((open_fn)open)(
      probe_marker_path, AP01_O_RDWR_CREAT_TRUNC, AP01_MODE_0666);
  if (descriptor < 0) return 0;
  (void)((close_fn)close)(descriptor);
  return 1;
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

ATTR_ENTRY void ap01_dark_skin_ui_timer_wrapper(void *timer)
{
  ((one_arg_fn)stock_ui_timer)(timer);
  if (claim_wrapper_probe()) (void)send_startup_probe();
}
