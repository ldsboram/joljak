#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HamCode Encoder (Python, Tkinter + optional Pillow)
- Spec: 20x20 grid, finder pattern fixed, inner 16x16 carries 16 chunks of Extended Hamming(16,11) (SECDED) bits.
- Input: UTF-8 text up to 21 bytes, then append NUL (0x00). Pack to 176 bits (22 bytes); pad random bits after NUL to fill.
- Data bits per chunk at indices [3,5,6,7,9,10,11,12,13,14,15]; parity indices [1,2,4,8]; overall parity index 0.
- Mapping: inner 16x16 split into 4x4 regions. Region k (0..15) holds the k-th bit (0..15) from all 16 chunks.
  Inside each region, cells ordered left->right, top->bottom map to chunk index 0..15.
- Colors: white=0, black=1.
- Output: shows grid; can save as PNG (with a 1-cell white border) if Pillow is available.
"""

import sys
import os
import random
import tkinter as tk
from tkinter import messagebox, filedialog

try:
    from PIL import Image, ImageDraw  # optional
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

SIZE = 20
DATA_START = 4  # 0-based index of inner top-left (row/col 5 in spec)
DATA_POSITIONS = [3,5,6,7,9,10,11,12,13,14,15]
PARITY_POSITIONS = [1,2,4,8]

def empty_grid():
    return [[False for _ in range(SIZE)] for __ in range(SIZE)]

def clone_grid(g):
    return [row[:] for row in g]

def apply_finder_overlay(g):
    g = clone_grid(g)
    # Clear top 4 rows and left 4 cols to white
    for r in range(4):
        for c in range(SIZE):
            g[r][c] = False
    for r in range(SIZE):
        for c in range(4):
            g[r][c] = False
    # Black lines: row 0 (all), col 0 (all), row 2 (cols 2..19), col 2 (rows 2..19)
    for c in range(SIZE):
        g[0][c] = True
    for r in range(SIZE):
        g[r][0] = True
    for c in range(2, SIZE):
        g[2][c] = True
    for r in range(2, SIZE):
        g[r][2] = True
    # Points (2,4), (4,2), (2,20), (20,2) -> 0-based (1,3), (3,1), (1,19), (19,1)
    g[1][3] = True
    g[3][1] = True
    g[1][19] = True
    g[19][1] = True
    return g

def parity(bits):
    p = 0
    for b in bits:
        p ^= (1 if b else 0)
    return p

def bytes_to_bits_msb(barr):
    out = []
    for B in barr:
        for i in range(7,-1,-1):
            out.append((B >> i) & 1)
    return out

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

def encode_chunk_11_to_16(data11):
    cw = [0]*16
    for i in range(11):
        cw[DATA_POSITIONS[i]] = 1 if data11[i] else 0
    # Hamming parity bits over positions 1..15 (even parity)
    for p in PARITY_POSITIONS:
        covered = [cw[idx] for idx in range(1,16) if (idx & p) != 0]
        cw[p] = parity(covered)
    # Overall parity bit (index 0) to make total even
    cw[0] = parity(cw[1:16])
    return cw

def build_codewords_from_text(text):
    raw = text.encode('utf-8')
    if len(raw) > 21:
        raise ValueError("입력은 UTF-8 기준 21바이트 이하여야 합니다.")
    with_nul = raw + b'\x00'
    bits = bytes_to_bits_msb(with_nul)
    TOTAL = 176
    # Pad random bits to reach 176
    while len(bits) < TOTAL:
        bits.append(random.getrandbits(1))
    bits = bits[:TOTAL]
    # Split into 16 chunks of 11 bits
    chunks11 = [bits[i*11:i*11+11] for i in range(16)]
    cws = [encode_chunk_11_to_16(ch) for ch in chunks11]
    return cws

def place_codewords_to_grid(cws, base=None):
    g = apply_finder_overlay(base if base is not None else empty_grid())
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
            g[r][c] = True if cws[ch][b] else False
    return g

# --- Tk UI ---
CELL = 22  # pixel per cell for canvas display

class EncoderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HamCode Encoder (Python)")
        self.grid = apply_finder_overlay(empty_grid())
        frm = tk.Frame(root)
        frm.pack(padx=8, pady=8)

        self.entry = tk.Entry(frm, width=50)
        self.entry.grid(row=0, column=0, columnspan=3, sticky='we', pady=(0,4))
        self.entry.bind('<KeyRelease>', self._update_len)

        self.len_label = tk.Label(frm, text="0 바이트")
        self.len_label.grid(row=0, column=3, sticky='w', padx=(6,0))

        tk.Button(frm, text="인코드", command=self.encode).grid(row=1, column=0, sticky='we')
        tk.Button(frm, text="PNG로 저장", command=self.save_png).grid(row=1, column=1, sticky='we')

        self.info = tk.Label(frm, text="", fg="#1f4f99", anchor='w', justify='left')
        self.info.grid(row=2, column=0, columnspan=4, sticky='we', pady=(4,6))

        self.canvas = tk.Canvas(frm, width=SIZE*CELL, height=SIZE*CELL, bg='white', highlightthickness=0)
        self.canvas.grid(row=3, column=0, columnspan=4)
        self.draw_grid()

    def _update_len(self, event=None):
        b = len(self.entry.get().encode('utf-8'))
        self.len_label.config(text=f"{b} 바이트")

    def draw_grid(self):
        self.canvas.delete('all')
        for r in range(SIZE):
            for c in range(SIZE):
                x0, y0 = c*CELL, r*CELL
                x1, y1 = x0+CELL, y0+CELL
                color = '#000000' if self.grid[r][c] else '#ffffff'
                self.canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline='#cccccc')
        # thin grid lines overlay (optional)
        for i in range(SIZE+1):
            self.canvas.create_line(0, i*CELL, SIZE*CELL, i*CELL, fill='#dddddd')
            self.canvas.create_line(i*CELL, 0, i*CELL, SIZE*CELL, fill='#dddddd')

    def encode(self):
        text = self.entry.get()
        try:
            cws = build_codewords_from_text(text)
            self.grid = place_codewords_to_grid(cws, self.grid)
            self.draw_grid()
            self.info.config(text="인코딩 완료: 16개 청크(각 16비트), 데이터 176비트. (백=0, 흑=1)")
        except Exception as e:
            messagebox.showerror("에러", str(e))

    def save_png(self):
        if not PIL_AVAILABLE:
            messagebox.showwarning("Pillow 없음", "Pillow가 없어 PNG 저장 불가합니다. 'pip install pillow' 후 다시 시도하세요.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Image","*.png")])
        if not path:
            return
        scale = 18
        border = 1  # cells
        total_cells = SIZE + border*2
        img = Image.new("RGB", (total_cells*scale, total_cells*scale), (255,255,255))
        draw = ImageDraw.Draw(img)
        # Draw black squares offset by border
        for r in range(SIZE):
            for c in range(SIZE):
                if self.grid[r][c]:
                    x0 = (c + border) * scale
                    y0 = (r + border) * scale
                    x1 = x0 + scale - 1
                    y1 = y0 + scale - 1
                    draw.rectangle([x0, y0, x1, y1], fill=(0,0,0))
        img.save(path)
        self.info.config(text=f"PNG로 저장(1칸 흰 여백 포함): {os.path.basename(path)}")

def main():
    root = tk.Tk()
    app = EncoderApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
