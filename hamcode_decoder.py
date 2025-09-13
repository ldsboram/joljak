#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HamCode Simple Decoder (Python, Tkinter)
- Finder area fixed; user toggles other cells (inner 16x16) by clicking.
- On Decode: extract 16 codewords from inner 16x16 using same mapping as encoder.
- Apply Extended Hamming(16,11) (SECDED): correct <=1 bit per chunk; if any chunk indicates double-bit error (syndrome!=0 and overall parity==0), reject.
- Decode to bytes (176 bits -> 22 bytes), stop at first NUL (0x00), and show resulting UTF-8 string.
"""

import tkinter as tk
from tkinter import messagebox
from typing import List

SIZE = 20
DATA_START = 4
DATA_POSITIONS = [3,5,6,7,9,10,11,12,13,14,15]
PARITY_POSITIONS = [1,2,4,8]

def empty_grid():
    return [[False for _ in range(SIZE)] for __ in range(SIZE)]

def clone_grid(g):
    return [row[:] for row in g]

def apply_finder_overlay(g):
    g = clone_grid(g)
    # Reset top 4 rows & left 4 cols to white
    for r in range(4):
        for c in range(SIZE):
            g[r][c] = False
    for r in range(SIZE):
        for c in range(4):
            g[r][c] = False
    # Black lines
    for c in range(SIZE):
        g[0][c] = True
    for r in range(SIZE):
        g[r][0] = True
    for c in range(2, SIZE):
        g[2][c] = True
    for r in range(2, SIZE):
        g[r][2] = True
    # Points
    g[1][3] = True
    g[3][1] = True
    g[1][19] = True
    g[19][1] = True
    return g

def is_in_finder(r, c):
    return r < 4 or c < 4

def parity(bits: List[int]) -> int:
    p = 0
    for b in bits:
        p ^= (1 if b else 0)
    return p

def bits_to_bytes_msb(bits):
    n = (len(bits) + 7) // 8
    out = bytearray(n)
    for i in range(n):
        v = 0
        for b in range(8):
            idx = i*8 + b
            v = (v << 1) | (1 if (idx < len(bits) and bits[idx]) else 0)
        out[i] = v
    return bytes(out)

def extract_codewords_from_grid(g):
    cws = [[0]*16 for _ in range(16)]  # 16 chunks x 16 bits
    for b in range(16):
        region_row = b // 4
        region_col = b % 4
        start_r = DATA_START + region_row*4
        start_c = DATA_START + region_col*4
        for ch in range(16):
            rr = ch // 4
            cc = ch % 4
            r = start_r + rr
            c = start_c + cc
            cws[ch][b] = 1 if g[r][c] else 0
    return cws

def decode_chunk_16(cw_in):
    cw = cw_in[:]
    # Syndrome over positions 1..15 (even parity expected)
    syndrome = 0
    for p in PARITY_POSITIONS:
        covered = [cw[idx] for idx in range(1,16) if (idx & p) != 0]
        sbit = parity(covered)
        if sbit:
            syndrome |= p
    overall = parity(cw)  # parity over all 16 bits
    corrected = False
    double_error = False
    if overall == 1 and syndrome == 0:
        # Error at overall parity bit (index 0)
        cw[0] ^= 1
        corrected = True
    elif overall == 1 and syndrome != 0:
        # Single-bit error at 'syndrome' (1..15)
        cw[syndrome] ^= 1
        corrected = True
    elif overall == 0 and syndrome != 0:
        # Two-bit error detected
        double_error = True
    # Extract 11 data bits
    data = [cw[pos] & 1 for pos in DATA_POSITIONS]
    return {'ok': not double_error, 'doubleError': double_error, 'corrected': corrected, 'dataBits': data}

# --- Tk UI ---
CELL = 22

class DecoderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HamCode Simple Decoder (Python)")
        self.grid = apply_finder_overlay(empty_grid())

        frm = tk.Frame(root)
        frm.pack(padx=8, pady=8)

        tk.Button(frm, text="디코드", command=self.decode).grid(row=0, column=0, sticky='we')
        tk.Button(frm, text="입력 초기화", command=self.reset).grid(row=0, column=1, sticky='we')

        self.info = tk.Label(frm, text="파인더 영역(상단4/좌측4)은 고정입니다. 나머지를 클릭해 흑/백을 토글하세요.", fg="#1f4f99", anchor='w', justify='left')
        self.info.grid(row=1, column=0, columnspan=2, sticky='we', pady=(4,6))

        self.canvas = tk.Canvas(frm, width=SIZE*CELL, height=SIZE*CELL, bg='white', highlightthickness=0)
        self.canvas.grid(row=2, column=0, columnspan=2)
        self.canvas.bind("<Button-1>", self.on_click)

        self.result_label = tk.Label(frm, text="디코딩 결과:", anchor='w')
        self.result_label.grid(row=3, column=0, sticky='w', pady=(6,0))
        self.result_box = tk.Text(frm, width=60, height=4)
        self.result_box.grid(row=4, column=0, columnspan=2, sticky='we')

        self.draw_grid()

    def draw_grid(self):
        self.canvas.delete('all')
        for r in range(SIZE):
            for c in range(SIZE):
                x0, y0 = c*CELL, r*CELL
                x1, y1 = x0+CELL, y0+CELL
                color = '#000000' if self.grid[r][c] else '#ffffff'
                outline = '#bbbbbb'
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline=outline)
        for i in range(SIZE+1):
            self.canvas.create_line(0, i*CELL, SIZE*CELL, i*CELL, fill='#dddddd')
            self.canvas.create_line(i*CELL, 0, i*CELL, SIZE*CELL, fill='#dddddd')

    def on_click(self, event):
        c = event.x // CELL
        r = event.y // CELL
        if r < 0 or r >= SIZE or c < 0 or c >= SIZE:
            return
        if r < 4 or c < 4:
            # Finder area locked
            return
        self.grid[r][c] = not self.grid[r][c]
        # Re-apply overlay to ensure black lines/points remain
        self.grid = apply_finder_overlay(self.grid)
        self.draw_grid()

    def reset(self):
        self.grid = apply_finder_overlay(empty_grid())
        self.draw_grid()
        self.result_box.delete("1.0", tk.END)
        self.info.config(text="입력을 초기화했습니다.")

    def decode(self):
        cws = extract_codewords_from_grid(self.grid)
        data_bits = []
        corrected_count = 0
        for i in range(16):
            res = decode_chunk_16(cws[i])
            if not res['ok']:
                messagebox.showwarning("디코딩 거부", "2비트 오류가 감지되어 디코딩을 거부했습니다. (특정 청크에서 2비트 오류)")
                return
            if res['corrected']:
                corrected_count += 1
            data_bits.extend(res['dataBits'])
        # Convert to bytes and stop at NUL
        data_bytes = bits_to_bytes_msb(data_bits)
        nul_idx = data_bytes.find(b'\x00')
        if nul_idx == -1:
            payload = data_bytes
        else:
            payload = data_bytes[:nul_idx]
        try:
            text = payload.decode('utf-8')
        except Exception:
            text = "(바이트 해석 오류) HEX: " + ' '.join(f"{b:02x}" for b in payload)
        self.result_box.delete("1.0", tk.END)
        self.result_box.insert(tk.END, text + f"\n(정정된 청크 수: {corrected_count})")

def main():
    root = tk.Tk()
    app = DecoderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
