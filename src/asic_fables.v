
`timescale 1ns/1ps
`default_nettype none

module tt_um_tpmdle (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire ena,
    input  wire clk,
    input  wire rst_n
);

    // One-cycle CPU input protocol:
    // ui_in[3:0]  = address [3:0]
    // ui_in[7:4]  = write data [7:4]
    // uio_in[3:0] = write data [3:0]
    // uio_in[4]   = write enable
    // uio_in[5]   = request valid
    // uio_in[6]   = 0 (input)
    // uio_in[7]   = 0 (input)
    //
    // Outputs:
    // uo_out[7:0] = read data
    // uio_out[6]  = cache ready
    // uio_out[7]  = read-data valid
    assign uio_oe = 8'b1100_0000;

    wire [7:0] cpu_wdata = {ui_in[7:4], uio_in[3:0]};
    wire [7:0] cpu_addr  = {4'b0000, ui_in[3:0]};
    wire       cpu_we   = uio_in[4];
    wire       cpu_req  = uio_in[5];

    wire       cpu_ready;
    wire [7:0] cpu_rdata;
    wire       cpu_rvalid;

    assign uo_out = cpu_rdata;
    assign uio_out = {cpu_rvalid, cpu_ready, 6'b000000};

    wire       mem_req_valid;
    wire       mem_we;
    wire [3:0] mem_addr;
    wire [7:0] mem_wdata;
    wire       mem_ready;
    wire [7:0] mem_rdata;

    direct_mapped_cache cache_inst (
        .clk             (clk),
        .rst_n           (rst_n),
        .ena             (ena),
        .cpu_req_valid   (cpu_req),
        .cpu_we          (cpu_we),
        .cpu_addr        (cpu_addr),
        .cpu_wdata       (cpu_wdata),
        .cpu_req_ready   (cpu_ready),
        .cpu_rdata       (cpu_rdata),
        .cpu_rdata_valid (cpu_rvalid),
        .mem_req_valid   (mem_req_valid),
        .mem_we          (mem_we),
        .mem_addr        (mem_addr),
        .mem_wdata       (mem_wdata),
        .mem_ready       (mem_ready),
        .mem_rdata       (mem_rdata)
    );

    main_memory_16B memory_inst (
        .clk        (clk),
        .rst_n      (rst_n),
        .ena        (ena),
        .mem_req_valid(mem_req_valid),
        .mem_we     (mem_we),
        .mem_addr   (mem_addr),
        .mem_wdata  (mem_wdata),
        .mem_ready  (mem_ready),
        .mem_rdata  (mem_rdata)
    );

endmodule


module direct_mapped_cache (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       ena,

    input  wire       cpu_req_valid,
    input  wire       cpu_we,
    input  wire [7:0] cpu_addr,
    input  wire [7:0] cpu_wdata,

    output reg        cpu_req_ready,
    output reg [7:0]  cpu_rdata,
    output reg        cpu_rdata_valid,

    output reg        mem_req_valid,
    output reg        mem_we,
    output reg [3:0]  mem_addr,
    output reg [7:0]  mem_wdata,
    input  wire       mem_ready,
    input  wire [7:0] mem_rdata
);

    // Latched CPU request.
    reg [3:0] req_addr;
    reg [7:0] req_wdata;
    reg       req_we;

    // Address: [3]=tag, [2:1]=index, [0]=byte offset.
    wire       req_tag    = req_addr[3];
    wire [1:0] req_index  = req_addr[2:1];
    wire       req_offset = req_addr[0];

    reg       valid_array [0:3];
    reg       tag_ram     [0:3];
    reg [15:0] data_ram   [0:3];

    localparam S_IDLE      = 3'd0;
    localparam S_COMPARE   = 3'd1;
    localparam S_MISS0     = 3'd2;
    localparam S_MISS1     = 3'd3;
    localparam S_WRITE     = 3'd4;
    reg [2:0] state;

    wire hit = valid_array[req_index] && (tag_ram[req_index] == req_tag);

    integer i;

    always @(posedge clk) begin
        if (!rst_n) begin
            state           <= S_IDLE;
            cpu_req_ready   <= 1'b0;
            cpu_rdata       <= 8'd0;
            cpu_rdata_valid <= 1'b0;
            mem_req_valid   <= 1'b0;
            mem_we          <= 1'b0;
            mem_addr        <= 4'd0;
            mem_wdata       <= 8'd0;
            req_addr        <= 4'd0;
            req_wdata       <= 8'd0;
            req_we          <= 1'b0;

            for (i = 0; i < 4; i = i + 1) begin
                valid_array[i] <= 1'b0;
                tag_ram[i]     <= 1'b0;
                data_ram[i]    <= 16'd0;
            end
        end else if (!ena) begin
            state           <= S_IDLE;
            cpu_req_ready   <= 1'b0;
            cpu_rdata_valid <= 1'b0;
            mem_req_valid   <= 1'b0;
        end else begin
            cpu_rdata_valid <= 1'b0;

            case (state)
                S_IDLE: begin
                    cpu_req_ready <= 1'b1;
                    mem_req_valid <= 1'b0;

                    if (cpu_req_valid) begin
                        req_addr  <= cpu_addr[3:0];
                        req_wdata <= cpu_wdata;
                        req_we    <= cpu_we;
                        cpu_req_ready <= 1'b0;
                        state <= S_COMPARE;
                    end
                end

                S_COMPARE: begin
                    cpu_req_ready <= 1'b0;

                    if (req_we) begin
                        // Write-through, no-write-allocate.
                        mem_req_valid <= 1'b1;
                        mem_we        <= 1'b1;
                        mem_addr      <= req_addr[3:0];
                        mem_wdata     <= req_wdata;
                        state         <= S_WRITE;

                        // If the block is already cached, keep cache coherent.
                        if (hit) begin
                            if (req_offset)
                                data_ram[req_index][15:8] <= req_wdata;
                            else
                                data_ram[req_index][7:0]  <= req_wdata;
                        end
                    end else if (hit) begin
                        // Read hit.
                        if (req_offset)
                            cpu_rdata <= data_ram[req_index][15:8];
                        else
                            cpu_rdata <= data_ram[req_index][7:0];

                        cpu_rdata_valid <= 1'b1;
                        cpu_req_ready   <= 1'b1;
                        state           <= S_IDLE;
                    end else begin
                        // Read miss: fetch two bytes of the cache line.
                        mem_req_valid <= 1'b1;
                        mem_we        <= 1'b0;
                        mem_addr      <= {req_addr[3:1], 1'b0};
                        state         <= S_MISS0;
                    end
                end

                S_MISS0: begin
                    if (mem_ready) begin
                        data_ram[req_index][7:0] <= mem_rdata;

                        mem_req_valid <= 1'b1;
                        mem_we        <= 1'b0;
                        mem_addr      <= {req_addr[3:1], 1'b1};
                        state         <= S_MISS1;
                    end
                end

                S_MISS1: begin
                    if (mem_ready) begin
                        data_ram[req_index][15:8] <= mem_rdata;
                        tag_ram[req_index]        <= req_tag;
                        valid_array[req_index]    <= 1'b1;
                        mem_req_valid             <= 1'b0;
                        state                     <= S_COMPARE;
                    end
                end

                S_WRITE: begin
                    if (mem_ready) begin
                        mem_req_valid <= 1'b0;
                        cpu_req_ready <= 1'b1;
                        state         <= S_IDLE;
                    end
                end

                default: begin
                    state         <= S_IDLE;
                    cpu_req_ready <= 1'b1;
                    mem_req_valid <= 1'b0;
                end
            endcase
        end
    end

endmodule


module main_memory_16B (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       ena,

    input  wire       mem_req_valid,
    input  wire       mem_we,
    input  wire [3:0] mem_addr,
    input  wire [7:0] mem_wdata,

    output wire       mem_ready,
    output wire [7:0] mem_rdata
);

    // 16 addresses x 8 bits = 16-byte main memory.
    reg [7:0] memory [0:15];
    integer k;

    // Reads are combinational; writes occur on the clock edge.
    // This makes a requested byte available during the cycle in
    // which mem_req_valid is asserted.
    assign mem_ready = ena && mem_req_valid;
    assign mem_rdata = memory[mem_addr];

    always @(posedge clk) begin
        if (!rst_n) begin
            for (k = 0; k < 16; k = k + 1)
                memory[k] <= 8'd0;
        end else if (ena && mem_req_valid && mem_we) begin
            memory[mem_addr] <= mem_wdata;
        end
    end

endmodule
