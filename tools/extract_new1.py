# -*- coding: utf-8 -*-
import pdfplumber
import glob
import os

path = glob.glob(r"C:\Users\playdata2\Downloads\2024*.pdf")[0]
with pdfplumber.open(path) as pdf:
    n = len(pdf.pages)
    full = "".join((p.extract_text() or "") + "\n" for p in pdf.pages)

out_dir = r"C:\Users\PLAYDA~1\AppData\Local\Temp\claude\C--Users-playdata2-Desktop-skn35-report\3de228d4-0842-49d7-9719-300b97c01a4f\scratchpad"
with open(os.path.join(out_dir, "new2024_full.txt"), "w", encoding="utf-8") as f:
    f.write(full)
print("pages:", n, "chars:", len(full))
