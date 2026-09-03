`timescale 1ns / 1ps
`default_nettype none
// TOP MODULE
module exmmm_cms (
    input  wire [7:0] ui_in,       // Dedicated inputs
    output wire [7:0] uo_out,     // Dedicated outputs
    input  wire [7:0] uio_in,     // Bidirectional input path
    output wire [7:0] uio_out,    // Bidirectional output path
    output wire [7:0] uio_oe,     // Bidirectional output enable
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
    // Internal CPU Interface
    reg        cpu_req_valid;
    reg        cpu_we;
    reg [7:0]  cpu_addr;
    reg [7:0]  cpu_wdata;

    wire       cpu_req_ready;
    wire [7:0] cpu_rdata;
    wire       cpu_rdata_valid;
    // Internal Memory Interface
    wire        mem_req_valid;
    wire        mem_we;
    wire [7:0]  mem_addr;
    wire [7:0]  mem_wdata;

    reg         mem_ready;
    reg [31:0]  mem_rdata;
    // CPU INPUT FSM
    // ui_in protocol:
    // Cycle 0 : Address
    // Cycle 1 : Write data
    // Cycle 2 : Control
    // ui_in[0] = Write enable
    // ui_in[1] = Request valid
    reg [1:0] cpu_in_state;
    localparam CPU_ADDR  = 2'b00;
    localparam CPU_DATA  = 2'b01;
    localparam CPU_CTRL  = 2'b10;
    localparam CPU_WAIT  = 2'b11;
    always @(posedge clk) begin
        if (!rst_n) begin
            cpu_in_state  <= CPU_ADDR;
            cpu_addr      <= 8'd0;
            cpu_wdata     <= 8'd0;
            cpu_we        <= 1'b0;
            cpu_req_valid <= 1'b0;
        end
        else begin
            case (cpu_in_state)
                // Get address
                CPU_ADDR: begin
                    cpu_addr <= ui_in;
                    cpu_in_state <= CPU_DATA;
                end
                // Get write data
                CPU_DATA: begin
                    cpu_wdata <= ui_in;
                    cpu_in_state <= CPU_CTRL;
                end
                // Get control and generate request
                CPU_CTRL: begin
                    cpu_we        <= ui_in[0];
                    cpu_req_valid <= ui_in[1];
                    if (ui_in[1]) begin
                        cpu_in_state <= CPU_WAIT;
                    end
                    else begin
                        cpu_in_state <= CPU_ADDR;
                    end
                end
                // Wait until cache accepts request
                CPU_WAIT: begin
                    if (cpu_req_ready) begin
                        cpu_req_valid <= 1'b0;
                        cpu_in_state <= CPU_ADDR;
                    end
                end
                default: begin
                    cpu_in_state <= CPU_ADDR;
                end
            endcase
        end
    end
        // INTERNAL MAIN MEMORY
    // 32 blocks
    // Each block = 32 bits = 4 bytes
        // Total = 32 × 4 = 128 bytes
    // Address:
    // [6:2] = memory block
    // [1:0] = byte offset
    // NOTE:
    // Address bit [7] is ignored by this 128-byte memory.
    reg [31:0] internal_main_memory [0:31];
    integer i;
    always @(posedge clk) begin
        if (!rst_n) begin
            mem_ready <= 1'b0;
            mem_rdata <= 32'd0;
            for (i = 0; i < 32; i = i + 1) begin
                internal_main_memory[i] <= 32'd0;
            end
        end
        else begin
            // Default: memory transaction not complete
            mem_ready <= 1'b0;
            // Memory request
            if (mem_req_valid) begin
                // WRITE
                if (mem_we) begin
                    case (mem_addr[1:0])
                        2'b00:
                            internal_main_memory[mem_addr[6:2]][7:0]
                                <= mem_wdata;
                        2'b01:
                            internal_main_memory[mem_addr[6:2]][15:8]
                                <= mem_wdata;
                        2'b10:
                            internal_main_memory[mem_addr[6:2]][23:16]
                                <= mem_wdata;
                        2'b11:
                            internal_main_memory[mem_addr[6:2]][31:24]
                                <= mem_wdata;
                        default:
                            internal_main_memory[mem_addr[6:2]]
                                <= internal_main_memory[mem_addr[6:2]];
                    endcase
                    mem_ready <= 1'b1;
                end
                // READ
                else begin
                    mem_rdata <=
                        internal_main_memory[mem_addr[6:2]];
                    mem_ready <= 1'b1;
                end
            end
        end
    end


    // ============================================================
    // OUTPUTS
    // ============================================================

    // Full 8-bit cache read data
    assign uo_out = cpu_rdata;


    // UIO pins 0 and 1 are status outputs
    //
    // UIO[0] = cache ready
    // UIO[1] = read data valid
    //
    // UIO[7:2] unused
    // ============================================================

    assign uio_oe = 8'b00000011;

    assign uio_out[0] = cpu_req_ready;
    assign uio_out[1] = cpu_rdata_valid;

    assign uio_out[7:2] = 6'b000000;


    // ============================================================
    // CACHE MODULE INSTANTIATION
    //
    // IMPORTANT:
    // This MUST be inside exmmm_cms.
    // ============================================================

    direct_mapped_cache cache_inst (

        .clk             (clk),
        .rst_n           (rst_n),

        // CPU interface
        .cpu_req_valid   (cpu_req_valid),
        .cpu_we          (cpu_we),
        .cpu_addr        (cpu_addr),
        .cpu_wdata       (cpu_wdata),

        .cpu_req_ready   (cpu_req_ready),
        .cpu_rdata       (cpu_rdata),
        .cpu_rdata_valid (cpu_rdata_valid),

        // Memory interface
        .mem_req_valid   (mem_req_valid),
        .mem_we          (mem_we),
        .mem_addr        (mem_addr),
        .mem_wdata       (mem_wdata),

        .mem_ready       (mem_ready),
        .mem_rdata       (mem_rdata)

    );

endmodule


// ============================================================
// DIRECT-MAPPED CACHE
// ============================================================

module direct_mapped_cache (

    input  wire       clk,
    input  wire       rst_n,

    // ----------------------------------------------------------
    // CPU INTERFACE
    // ----------------------------------------------------------

    input  wire       cpu_req_valid,
    input  wire       cpu_we,
    input  wire [7:0] cpu_addr,
    input  wire [7:0] cpu_wdata,

    output reg        cpu_req_ready,
    output reg [7:0]  cpu_rdata,
    output reg        cpu_rdata_valid,

    // ----------------------------------------------------------
    // MEMORY INTERFACE
    // ----------------------------------------------------------

    output reg        mem_req_valid,
    output reg        mem_we,
    output reg [7:0]  mem_addr,
    output reg [7:0]  mem_wdata,

    input  wire       mem_ready,
    input  wire [31:0] mem_rdata

);


    // ==========================================================
    // CACHE PARAMETERS
    //
    // 16 cache lines
    // 4 bytes per line
    // Total cache = 64 bytes
    //
    // Address format:
    //
    // [7:6] = TAG      2 bits
    // [5:2] = INDEX    4 bits
    // [1:0] = OFFSET   2 bits
     // FSM STATES
    localparam IDLE          = 2'b00;
    localparam COMPARE       = 2'b01;
    localparam ALLOCATE      = 2'b10;
    localparam WRITE_THROUGH = 2'b11;
    reg [1:0] state;
    // CPU REQUEST REGISTERS
    reg       req_we;
    reg [7:0] req_addr;
    reg [7:0] req_wdata;
    // ADDRESS DECODER
    wire [1:0] offset;
    wire [3:0] index;
    wire [1:0] tag;
    assign offset = req_addr[1:0];
    assign index  = req_addr[5:2];
    assign tag    = req_addr[7:6];
    // CACHE STORAGE
    // 16 lines × 2-bit tag
    reg [1:0] tag_ram [0:15];
    // 16 lines × 32-bit data
    reg [31:0] data_ram [0:15];
    // 16 valid bits
    reg valid_array [0:15];
    // HIT DETECTION
    wire hit;
    assign hit =
        valid_array[index] &&
        (tag_ram[index] == tag);
    // BYTE SELECTION
    reg [7:0] cache_rdata_byte;
    always @(*) begin
        case (offset)
            2'b00:
                cache_rdata_byte = data_ram[index][7:0];
            2'b01:
                cache_rdata_byte = data_ram[index][15:8];
            2'b10:
                cache_rdata_byte = data_ram[index][23:16];
            2'b11:
                cache_rdata_byte = data_ram[index][31:24];
            default:
                cache_rdata_byte = 8'd0;
        endcase
    end
    // MAIN CACHE FSM
    integer j;
    always @(posedge clk) begin
        if (!rst_n) begin
            state <= IDLE;
            cpu_req_ready   <= 1'b1;
            cpu_rdata_valid <= 1'b0;
            cpu_rdata       <= 8'd0;
            mem_req_valid <= 1'b0;
            mem_we        <= 1'b0;
            mem_addr      <= 8'd0;
            mem_wdata     <= 8'd0;
            req_we    <= 1'b0;
            req_addr  <= 8'd0;
            req_wdata <= 8'd0;
            for (j = 0; j < 16; j = j + 1) begin
                valid_array[j] <= 1'b0;
                tag_ram[j]     <= 2'b00;
                data_ram[j]    <= 32'd0;
            end
        end
        else begin
            // Default
            cpu_rdata_valid <= 1'b0;
            case (state)
                // IDLE
                IDLE: begin
                    cpu_req_ready <= 1'b1;
                    if (cpu_req_valid && cpu_req_ready) begin
                        // Latch CPU request
                        req_we    <= cpu_we;
                        req_addr  <= cpu_addr;
                        req_wdata <= cpu_wdata;
                        cpu_req_ready <= 1'b0;
                        state <= COMPARE;
                    end
                end
                // COMPARE
                COMPARE: begin
                    // READ
                    if (!req_we) begin
                        // READ HIT
                        if (hit) begin
                            cpu_rdata <= cache_rdata_byte;
                            cpu_rdata_valid <= 1'b1;
                            cpu_req_ready   <= 1'b1;
                            state <= IDLE;
                        end
                        // READ MISS
                        else begin
                            // Request complete cache line
                            mem_req_valid <= 1'b1;
                            mem_we <= 1'b0;
                            // Block aligned address
                            mem_addr <= {
                                tag,
                                index,
                                2'b00
                            };
                            state <= ALLOCATE;
                        end
                    end
                    // WRITE
                    else begin
                        // Write-through
                        mem_req_valid <= 1'b1;
                        mem_we <= 1'b1;
                        mem_addr  <= req_addr;
                        mem_wdata <= req_wdata;
                        // No-write-allocate
                        // If cache already contains the block,
                        // update cache copy as well.
                        if (hit) begin
                            case (offset)
                                2'b00:
                                    data_ram[index][7:0]
                                        <= req_wdata;
                                2'b01:
                                    data_ram[index][15:8]
                                        <= req_wdata;
                                2'b10:
                                    data_ram[index][23:16]
                                        <= req_wdata;
                                2'b11:
                                    data_ram[index][31:24]
                                        <= req_wdata;
                            endcase
                        end
                        state <= WRITE_THROUGH;
                    end
                end
                // ALLOCATE
                ALLOCATE: begin
                    if (mem_ready) begin
                        mem_req_valid <= 1'b0;
                        // Store fetched block
                        data_ram[index] <= mem_rdata;
                        // Store tag
                        tag_ram[index] <= tag;
                        // Mark valid
                        valid_array[index] <= 1'b1;
                        // Go back and perform read
                        state <= COMPARE;
                    end
                end
                // WRITE THROUGH
                WRITE_THROUGH: begin
                    if (mem_ready) begin
                        mem_req_valid <= 1'b0;
                        cpu_req_ready <= 1'b1;
                        state <= IDLE;
                    end
                end
                default: begin
                    state <= IDLE;
                    cpu_req_ready <= 1'b1;
                end
            endcase
        end
    end
endmodule
`default_nettype wire
