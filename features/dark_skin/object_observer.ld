OUTPUT_ARCH(riscv)
ENTRY(ap01_dark_skin_ui_timer_wrapper)

MEMORY
{
    PAYLOAD (rx) : ORIGIN = 0xA02465D0, LENGTH = 60934
}

PROVIDE(stock_ui_timer = 0xA00BB5DA);
PROVIDE(stock_get_dispatch_index = 0xA00BE388);
PROVIDE(stock_get_child = 0xA00BE3CA);
PROVIDE(lv_obj_get_child = 0xA00C5D84);
PROVIDE(lv_obj_get_child_count = 0xA00C5FE4);
PROVIDE(webclient_perform = 0xA00D86BA);
PROVIDE(stock_timer_init = 0xA009B376);
PROVIDE(stock_timer_schedule = 0xA009B3B6);
PROVIDE(malloc = 0xA007E1C4);
PROVIDE(free = 0xA007C256);

SECTIONS
{
    .payload :
    {
        KEEP(*(.text.entry))
        *(.text .text.*)
        *(.rodata .rodata.*)
    } > PAYLOAD

    /DISCARD/ :
    {
        *(.comment)
        *(.note*)
        *(.riscv.attributes)
        *(.eh_frame*)
    }
}
