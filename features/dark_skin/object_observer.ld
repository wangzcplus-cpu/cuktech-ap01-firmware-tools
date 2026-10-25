OUTPUT_ARCH(riscv)
ENTRY(ap01_dark_skin_ui_timer_wrapper)

MEMORY
{
    PAYLOAD (rx) : ORIGIN = 0xA02465D0, LENGTH = 60934
}

PROVIDE(stock_ui_timer = 0xA00BB5DA);
PROVIDE(webclient_perform = 0xA00D86BA);
PROVIDE(open = 0xA003F448);
PROVIDE(close = 0xA0026788);
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
